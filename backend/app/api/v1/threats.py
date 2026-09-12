"""Alerts, incidents and dashboard stats (Module 3)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, require_min_role
from app.core.exceptions import NotFoundError
from app.models.alert import Alert, AlertNote, Incident
from app.models.enums import AlertStatus, IncidentStatus, UserRole
from app.models.quantum import QuantumExposureScore
from app.models.user import User
from app.models.verification_event import Finding, VerificationEvent
from app.schemas.common import Page
from app.schemas.threats import (
    AlertDetail,
    AlertOut,
    AlertPatch,
    IncidentDetail,
    IncidentOut,
    IncidentPatch,
    ThreatStats,
)

router = APIRouter(prefix="/threats", tags=["threats"])

Analyst = Annotated[User, Depends(require_min_role(UserRole.ANALYST))]

_QUANTUM_VULNERABLE = {"rsa", "ec", "dsa"}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@router.get("/alerts", response_model=Page[AlertOut])
async def list_alerts(
    session: SessionDep,
    _: CurrentUser,
    status: AlertStatus | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[AlertOut]:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    count_stmt = select(func.count()).select_from(Alert)
    if status:
        stmt = stmt.where(Alert.status == status)
        count_stmt = count_stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
        count_stmt = count_stmt.where(Alert.severity == severity)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(
        items=[AlertOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
async def get_alert(alert_id: str, session: SessionDep, _: CurrentUser) -> AlertDetail:
    row = (
        await session.execute(
            select(Alert)
            .options(selectinload(Alert.event).selectinload(VerificationEvent.findings))
            .where(Alert.id == alert_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Alert not found")
    return AlertDetail.model_validate(row)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
async def patch_alert(
    alert_id: str, payload: AlertPatch, session: SessionDep, actor: Analyst
) -> AlertOut:
    row = (await session.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Alert not found")

    if payload.status is not None and payload.status != row.status:
        row.status = payload.status
        if payload.status != AlertStatus.OPEN:
            row.triaged_by = actor.id
            row.triaged_at = _utcnow()
    if payload.assigned_to is not None:
        row.assigned_to = payload.assigned_to or None
    if payload.note:
        session.add(AlertNote(alert_id=row.id, author_id=actor.id, body=payload.note))
        row.notes = (row.notes + "\n" if row.notes else "") + payload.note

    await session.commit()
    await session.refresh(row)
    return AlertOut.model_validate(row)


@router.get("/incidents", response_model=Page[IncidentOut])
async def list_incidents(
    session: SessionDep,
    _: CurrentUser,
    status: IncidentStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[IncidentOut]:
    stmt = select(Incident).order_by(Incident.last_seen_at.desc())
    count_stmt = select(func.count()).select_from(Incident)
    if status:
        stmt = stmt.where(Incident.status == status)
        count_stmt = count_stmt.where(Incident.status == status)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(
        items=[IncidentOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: str, session: SessionDep, _: CurrentUser) -> IncidentDetail:
    row = (
        await session.execute(
            select(Incident)
            .options(selectinload(Incident.alerts))
            .where(Incident.id == incident_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Incident not found")
    return IncidentDetail.model_validate(row)


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
async def patch_incident(
    incident_id: str, payload: IncidentPatch, session: SessionDep, _: Analyst
) -> IncidentOut:
    row = (
        await session.execute(select(Incident).where(Incident.id == incident_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Incident not found")
    row.status = payload.status
    await session.commit()
    await session.refresh(row)
    return IncidentOut.model_validate(row)


@router.get("/stats", response_model=ThreatStats)
async def stats(session: SessionDep, _: CurrentUser) -> ThreatStats:
    now = _utcnow()
    day_ago = now - dt.timedelta(hours=24)

    events_total = (
        await session.execute(select(func.count()).select_from(VerificationEvent))
    ).scalar_one()
    events_24h = (
        await session.execute(
            select(func.count())
            .select_from(VerificationEvent)
            .where(VerificationEvent.created_at >= day_ago)
        )
    ).scalar_one()
    invalid_24h = (
        await session.execute(
            select(func.count())
            .select_from(VerificationEvent)
            .where(
                VerificationEvent.created_at >= day_ago,
                VerificationEvent.verdict == "invalid",
            )
        )
    ).scalar_one()
    open_alerts = (
        await session.execute(
            select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.OPEN)
        )
    ).scalar_one()

    sev_rows = (
        await session.execute(
            select(Alert.severity, func.count())
            .where(Alert.status != AlertStatus.CLOSED)
            .group_by(Alert.severity)
        )
    ).all()
    alerts_by_severity = {s: int(c) for s, c in sev_rows}

    open_incidents = (
        await session.execute(
            select(func.count())
            .select_from(Incident)
            .where(Incident.status != IncidentStatus.CLOSED)
        )
    ).scalar_one()

    qv = (
        await session.execute(
            select(func.count())
            .select_from(VerificationEvent)
            .where(VerificationEvent.key_type.in_(_QUANTUM_VULNERABLE))
        )
    ).scalar_one()

    triaged = (
        await session.execute(
            select(Alert.created_at, Alert.triaged_at).where(Alert.triaged_at.is_not(None))
        )
    ).all()
    mttt = None
    if triaged:
        deltas = [(t - c).total_seconds() for c, t in triaged if t and c]
        if deltas:
            mttt = round(sum(deltas) / len(deltas), 1)

    timeline_rows = (
        await session.execute(
            select(VerificationEvent.created_at, VerificationEvent.verdict).where(
                VerificationEvent.created_at >= now - dt.timedelta(days=7)
            )
        )
    ).all()
    buckets: dict[str, dict[str, int]] = {}
    for created, verdict in timeline_rows:
        day = created.date().isoformat()
        b = buckets.setdefault(day, {"valid": 0, "invalid": 0, "indeterminate": 0})
        b[verdict] = b.get(verdict, 0) + 1
    timeline = [{"date": d, **counts} for d, counts in sorted(buckets.items())]

    # top firing rules (24h)
    top_rule_rows = (
        await session.execute(
            select(Finding.rule_code, func.count())
            .join(VerificationEvent, VerificationEvent.id == Finding.event_id)
            .where(VerificationEvent.created_at >= day_ago)
            .group_by(Finding.rule_code)
            .order_by(func.count().desc())
            .limit(6)
        )
    ).all()
    top_rules = [{"code": c, "count": int(n)} for c, n in top_rule_rows]

    recent_rows = (
        (await session.execute(select(Alert).order_by(Alert.created_at.desc()).limit(5)))
        .scalars()
        .all()
    )
    recent_alerts = [
        {
            "id": a.id,
            "title": a.title,
            "severity": a.severity,
            "status": a.status,
            "risk_score": a.risk_score,
            "created_at": a.created_at.isoformat(),
        }
        for a in recent_rows
    ]

    pqc_rows = (
        await session.execute(
            select(QuantumExposureScore.band, func.count()).group_by(QuantumExposureScore.band)
        )
    ).all()
    pqc_by_band = {b: int(n) for b, n in pqc_rows}

    return ThreatStats(
        events_24h=int(events_24h),
        events_total=int(events_total),
        invalid_24h=int(invalid_24h),
        open_alerts=int(open_alerts),
        alerts_by_severity=alerts_by_severity,
        open_incidents=int(open_incidents),
        quantum_vulnerable_events=int(qv),
        mean_time_to_triage_seconds=mttt,
        timeline=timeline,
        top_rules=top_rules,
        recent_alerts=recent_alerts,
        pqc_by_band=pqc_by_band,
    )
