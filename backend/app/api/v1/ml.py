"""ML anomaly-detection routes (Module 5). Off by default; advisory only."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, require_min_role, require_role
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import UserRole
from app.models.ml_model import MlModel
from app.models.user import User
from app.models.verification_event import VerificationEvent
from app.schemas.common import Message
from app.schemas.ml import (
    MlModelOut,
    MlStatus,
    ScoreRequest,
    ScoreResponse,
    TrainRequest,
)
from app.services.ml import registry, service
from app.services.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION

router = APIRouter(prefix="/ml", tags=["ml"])

Analyst = Annotated[User, Depends(require_min_role(UserRole.ANALYST))]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/status", response_model=MlStatus)
async def ml_status(session: SessionDep, _: CurrentUser) -> MlStatus:
    active = (
        await session.execute(select(MlModel.id).where(MlModel.is_active.is_(True)))
    ).scalar_one_or_none()
    return MlStatus(
        enabled=settings.ml_enabled,
        active_model_id=active,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_count=len(FEATURE_NAMES),
        anomaly_weight=settings.ml_anomaly_weight,
    )


@router.get("/models", response_model=list[MlModelOut])
async def list_models(session: SessionDep, _: CurrentUser) -> list[MlModelOut]:
    return [MlModelOut.model_validate(m) for m in await registry.list_models(session)]


@router.post("/train", response_model=MlModelOut)
async def train_model(payload: TrainRequest, session: SessionDep, user: Analyst) -> MlModelOut:
    row = await service.train(
        session,
        algo=payload.algo,
        source=payload.source,
        lookback_days=payload.lookback_days,
        contamination=payload.contamination,
        trained_by=user.id,
        activate=payload.activate,
    )
    return MlModelOut.model_validate(row)


@router.post("/models/{model_id}/activate", response_model=MlModelOut)
async def activate_model(model_id: str, session: SessionDep, _: Admin) -> MlModelOut:
    row = await registry.activate(session, model_id)
    return MlModelOut.model_validate(row)


@router.post("/models/deactivate", response_model=Message)
async def deactivate(session: SessionDep, _: Admin) -> Message:
    await registry.deactivate_all(session)
    return Message(detail="No model is active")


@router.delete("/models/{model_id}", response_model=Message)
async def delete_model(model_id: str, session: SessionDep, _: Admin) -> Message:
    await registry.delete_model(session, model_id)
    return Message(detail="Model deleted")


@router.post("/score", response_model=ScoreResponse)
async def score_event(payload: ScoreRequest, session: SessionDep, _: Analyst) -> ScoreResponse:
    if not settings.ml_enabled:
        raise ValidationAppError("ML is disabled (set ML_ENABLED=true)")
    ev = (
        await session.execute(
            select(VerificationEvent)
            .options(selectinload(VerificationEvent.findings))
            .where(VerificationEvent.id == payload.event_id)
        )
    ).scalar_one_or_none()
    if ev is None:
        raise NotFoundError("Verification event not found")

    model = await registry.get_active_model(session)
    if model is None:
        raise ValidationAppError("No active model")

    from app.services.ml.features import event_to_vector

    vec = event_to_vector(
        key_type=ev.key_type,
        key_bits=ev.key_bits,
        curve=ev.curve,
        hash_alg=ev.hash_alg,
        envelope_type=ev.envelope_type,
        verdict=ev.verdict,
        chain_status=ev.chain_status,
        signing_time=ev.signing_time,
        tsa_present=ev.tsa_present,
        created_at=ev.created_at or dt.datetime.now(dt.UTC),
        finding_categories=[f.category for f in ev.findings],
    )
    score = round(float(model.score(vec)[0]), 4)
    active_id = (
        await session.execute(select(MlModel.id).where(MlModel.is_active.is_(True)))
    ).scalar_one_or_none()
    return ScoreResponse(
        event_id=ev.id,
        anomaly_score=score,
        flagged=score >= 0.7,
        threshold=0.7,
        model_id=active_id,
    )
