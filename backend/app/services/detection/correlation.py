"""Greedy alert correlation into incidents (Module 4 adds a quantum-inspired variant)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert, Incident
from app.models.enums import IncidentStatus, Severity
from app.models.verification_event import VerificationEvent

_WINDOW = dt.timedelta(hours=6)
_LINK_THRESHOLD = 0.34


def _severity_rank(value: str) -> int:
    order = ["info", "low", "medium", "high", "critical"]
    return order.index(value) if value in order else 0


def similarity(
    a: VerificationEvent, b: VerificationEvent, a_codes: set[str], b_codes: set[str]
) -> float:
    """Weighted feature overlap in [0, 1]."""
    score = 0.0
    if a.signer_spki_sha256 and a.signer_spki_sha256 == b.signer_spki_sha256:
        score += 0.4
    if a.submitter_ip_hash and a.submitter_ip_hash == b.submitter_ip_hash:
        score += 0.3
    if a.payload_sha256 and a.payload_sha256 == b.payload_sha256:
        score += 0.2
    shared = a_codes & b_codes
    if shared:
        score += 0.2 * len(shared) / max(len(a_codes | b_codes), 1)
    dt_gap = abs((a.created_at - b.created_at).total_seconds())
    if dt_gap < 900:
        score += 0.1
    return min(1.0, score)


async def correlate(session: AsyncSession, alert: Alert, event: VerificationEvent) -> Incident:
    now = dt.datetime.now(dt.UTC)
    since = now - _WINDOW
    new_codes = set(alert.rule_codes)

    recent = (
        (
            await session.execute(
                select(Alert)
                .options(selectinload(Alert.incident))
                .join(VerificationEvent, VerificationEvent.id == Alert.event_id)
                .where(Alert.id != alert.id, VerificationEvent.created_at >= since)
                .order_by(Alert.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    best: tuple[float, Incident] | None = None
    for other in recent:
        other_event = (
            await session.execute(
                select(VerificationEvent).where(VerificationEvent.id == other.event_id)
            )
        ).scalar_one()
        sim = similarity(event, other_event, new_codes, set(other.rule_codes))
        linkable = sim >= _LINK_THRESHOLD and other.incident is not None
        if linkable and (best is None or sim > best[0]):
            best = (sim, other.incident)  # type: ignore[assignment]

    if best is not None:
        incident = best[1]
        incident.alert_count += 1
        incident.last_seen_at = now
        incident.cohesion_score = round((incident.cohesion_score + best[0]) / 2, 3)
        if _severity_rank(alert.severity) > _severity_rank(incident.severity):
            incident.severity = alert.severity
        alert.incident_id = incident.id
        await session.commit()
        return incident

    incident = Incident(
        title=_incident_title(alert, event),
        status=IncidentStatus.OPEN,
        severity=alert.severity,
        cohesion_score=1.0,
        method="greedy",
        alert_count=1,
        first_seen_at=now,
        last_seen_at=now,
        signals={
            "signer_spki": event.signer_spki_sha256,
            "ip_hash": event.submitter_ip_hash,
            "rule_codes": alert.rule_codes,
        },
    )
    session.add(incident)
    await session.flush()
    alert.incident_id = incident.id
    await session.commit()
    return incident


def _incident_title(alert: Alert, event: VerificationEvent) -> str:
    top = alert.rule_codes[0] if alert.rule_codes else "detection"
    who = (event.signer_subject or event.submitter_ip_hash or "unknown source")[:60]
    sev = (
        Severity(alert.severity).value
        if alert.severity in Severity._value2member_map_
        else alert.severity
    )
    return f"[{sev}] {top} activity involving {who}"
