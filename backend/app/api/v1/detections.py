"""Detection-rule configuration + verification-event browsing (Module 3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_min_role
from app.core.exceptions import NotFoundError
from app.models.detection_rule import DetectionRule
from app.models.enums import UserRole
from app.models.user import User
from app.models.verification_event import VerificationEvent
from app.schemas.common import Message, Page
from app.schemas.threats import (
    DetectionRuleOut,
    DetectionRulePatch,
    EventDetail,
    EventListItem,
)

router = APIRouter(prefix="/detections", tags=["detections"])

Analyst = Annotated[User, Depends(require_min_role(UserRole.ANALYST))]


@router.get("/rules", response_model=list[DetectionRuleOut])
async def list_rules(session: SessionDep, _: CurrentUser) -> list[DetectionRuleOut]:
    rows = (
        (await session.execute(select(DetectionRule).order_by(DetectionRule.code))).scalars().all()
    )
    return [DetectionRuleOut.model_validate(r) for r in rows]


@router.patch("/rules/{code}", response_model=DetectionRuleOut)
async def patch_rule(
    code: str, payload: DetectionRulePatch, session: SessionDep, _: Analyst
) -> DetectionRuleOut:
    rule = (
        await session.execute(select(DetectionRule).where(DetectionRule.code == code))
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError(f"No detection rule {code!r}")
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.weight is not None:
        rule.weight = payload.weight
    if payload.config is not None:
        rule.config = payload.config
    await session.commit()
    await session.refresh(rule)
    return DetectionRuleOut.model_validate(rule)


@router.get("/events", response_model=Page[EventListItem])
async def list_events(
    session: SessionDep,
    _: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    verdict: str | None = Query(None),
    min_risk: float | None = Query(None, ge=0, le=100),
) -> Page[EventListItem]:
    stmt = select(VerificationEvent).order_by(VerificationEvent.created_at.desc())
    count_stmt = select(func.count()).select_from(VerificationEvent)
    if verdict:
        stmt = stmt.where(VerificationEvent.verdict == verdict)
        count_stmt = count_stmt.where(VerificationEvent.verdict == verdict)
    if min_risk is not None:
        stmt = stmt.where(VerificationEvent.risk_score >= min_risk)
        count_stmt = count_stmt.where(VerificationEvent.risk_score >= min_risk)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(
        items=[EventListItem.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(event_id: str, session: SessionDep, _: CurrentUser) -> EventDetail:
    row = (
        await session.execute(select(VerificationEvent).where(VerificationEvent.id == event_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Verification event not found")
    return EventDetail.model_validate(row)


@router.post("/rules/resync", response_model=Message)
async def resync_rules(session: SessionDep, _: Analyst) -> Message:
    from app.services.detection.engine import sync_rules

    added = await sync_rules(session)
    return Message(detail=f"{added} rule(s) added")
