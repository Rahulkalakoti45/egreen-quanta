"""Quantum-inspired optimisation routes (Module 4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_min_role, require_role
from app.core.exceptions import NotFoundError
from app.models.enums import UserRole
from app.models.quantum import QuantumRun
from app.models.user import User
from app.schemas.common import Page
from app.schemas.quantum import (
    CorrelationRunRequest,
    CorrelationRunResponse,
    MigrationPlanRequest,
    MigrationPlanResponse,
    PortfolioRequest,
    PortfolioResponse,
    QESRequest,
    QESResponse,
    QuantumRunDetail,
    QuantumRunOut,
    TuningApplyRequest,
    TuningRequest,
    TuningResponse,
)
from app.services.quantum import pq_risk, service

router = APIRouter(prefix="/quantum", tags=["quantum"])

Analyst = Annotated[User, Depends(require_min_role(UserRole.ANALYST))]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.post("/pq-risk/score", response_model=QESResponse)
async def pq_risk_score(payload: QESRequest, _: CurrentUser) -> QESResponse:
    res = pq_risk.score_qes(
        pq_risk.QESInput(
            algo=payload.algo,
            key_bits=payload.key_bits,
            curve=payload.curve,
            data_lifetime_years=payload.data_lifetime_years,
            exposure=payload.exposure,
            label=payload.label,
        ),
        assumptions={"qc_year": payload.qc_year} if payload.qc_year else None,
    )
    return QESResponse(**res.as_dict())


@router.post("/pq-risk/portfolio", response_model=PortfolioResponse)
async def pq_risk_portfolio(
    payload: PortfolioRequest, session: SessionDep, user: Analyst
) -> PortfolioResponse:
    data = await service.score_portfolio(
        session,
        lookback_days=payload.lookback_days,
        data_lifetime_years=payload.data_lifetime_years,
        exposure=payload.exposure,
        qc_year=payload.qc_year,
        created_by=user.id,
    )
    return PortfolioResponse(**data)


@router.post("/pq-risk/plan", response_model=MigrationPlanResponse)
async def pq_risk_plan(
    payload: MigrationPlanRequest, session: SessionDep, user: Analyst
) -> MigrationPlanResponse:
    return MigrationPlanResponse(
        **await service.run_migration_plan(session, payload, created_by=user.id)
    )


@router.post("/tuning/run", response_model=TuningResponse)
async def tuning_run(payload: TuningRequest, session: SessionDep, user: Analyst) -> TuningResponse:
    return TuningResponse(**await service.run_tuning(session, payload, created_by=user.id))


@router.post("/tuning/apply")
async def tuning_apply(payload: TuningApplyRequest, session: SessionDep, _: Admin) -> dict:
    return await service.apply_tuning(session, payload.run_id)


@router.post("/correlation/run", response_model=CorrelationRunResponse)
async def correlation_run(
    payload: CorrelationRunRequest, session: SessionDep, user: Analyst
) -> CorrelationRunResponse:
    return CorrelationRunResponse(
        **await service.run_correlation(session, payload, created_by=user.id)
    )


@router.get("/runs", response_model=Page[QuantumRunOut])
async def list_runs(
    session: SessionDep,
    _: CurrentUser,
    run_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[QuantumRunOut]:
    stmt = select(QuantumRun).order_by(QuantumRun.created_at.desc())
    count_stmt = select(func.count()).select_from(QuantumRun)
    if run_type:
        stmt = stmt.where(QuantumRun.run_type == run_type)
        count_stmt = count_stmt.where(QuantumRun.run_type == run_type)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(
        items=[QuantumRunOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=QuantumRunDetail)
async def get_run(run_id: str, session: SessionDep, _: CurrentUser) -> QuantumRunDetail:
    row = (
        await session.execute(select(QuantumRun).where(QuantumRun.id == run_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Quantum run not found")
    return QuantumRunDetail.model_validate(row)
