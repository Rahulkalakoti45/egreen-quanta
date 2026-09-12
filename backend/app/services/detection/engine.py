"""Detection orchestration: persist an event, run rules, score, alert, correlate."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.detection_rule import DetectionRule
from app.models.enums import AlertStatus, EnvelopeType, EventSource, Severity
from app.models.enums import Verdict as VerdictEnum
from app.models.verification_event import Finding, VerificationEvent
from app.services.crypto.types import CryptoFinding, VerificationResult
from app.services.detection.catalog import CATALOG_BY_CODE, DEFAULT_ALERT_THRESHOLD, RULE_CATALOG
from app.services.detection.correlation import correlate
from app.services.detection.history_rules import HistoryContext, evaluate_history_rules
from app.services.detection.scoring import alert_severity, risk_score

log = get_logger("egreen.detection")


@dataclass(slots=True)
class DetectionOutcome:
    event: VerificationEvent
    findings: list[Finding]
    alert: Alert | None
    incident_id: str | None


async def sync_rules(session: AsyncSession) -> int:
    """Insert any catalog rules missing from ``detection_rules`` (never clobbers edits)."""
    existing = set((await session.execute(select(DetectionRule.code))).scalars().all())
    added = 0
    for spec in RULE_CATALOG:
        if spec.code in existing:
            continue
        session.add(
            DetectionRule(
                code=spec.code,
                name=spec.name,
                description=spec.description,
                category=spec.category,
                default_severity=spec.default_severity.value,
                enabled=True,
                weight=spec.default_weight,
                config={},
            )
        )
        added += 1
    if added:
        await session.commit()
        log.info("detection_rules_synced", added=added)
    return added


async def _rule_config(session: AsyncSession) -> tuple[dict[str, float], set[str], dict[str, dict]]:
    rows = (await session.execute(select(DetectionRule))).scalars().all()
    weights = {r.code: r.weight for r in rows}
    disabled = {r.code for r in rows if not r.enabled}
    configs = {r.code: (r.config or {}) for r in rows}
    return weights, disabled, configs


def _sig_fields(result: VerificationResult) -> dict:
    s = result.signature
    return {
        "algo": s.algorithm if s else None,
        "hash_alg": s.hash_alg if s else None,
        "key_type": (s.key.key_type if s and s.key else None),
        "key_bits": (s.key.key_bits if s and s.key else None),
        "curve": (s.key.curve if s and s.key else None),
    }


async def run_detection(
    session: AsyncSession,
    result: VerificationResult,
    *,
    source: EventSource = EventSource.API,
    source_ref: str | None = None,
    submitter_id: str | None = None,
    ip_hash: str | None = None,
    signature_sha256: str | None = None,
) -> DetectionOutcome:
    now = dt.datetime.now(dt.UTC)
    weights, disabled, configs = await _rule_config(session)

    verdict = VerdictEnum(result.verdict.value)
    history_ctx = HistoryContext(
        envelope=result.envelope,
        verdict=verdict,
        payload_sha256=result.payload_sha256,
        signature_sha256=signature_sha256,
        signer_spki_sha256=result.signer.spki_sha256 if result.signer else None,
        submitter_ip_hash=ip_hash,
        now=now,
    )
    history_findings = await evaluate_history_rules(
        session,
        history_ctx,
        config={**configs.get("T15", {}), **configs.get("T14", {})},
    )

    # optional local ML anomaly score (advisory; never overrides a crypto verdict)
    anomaly_score: float | None = None
    if settings.ml_enabled:
        from app.services.ml.scorer import score_verification

        anomaly_score, ml_finding = await score_verification(session, result, created_at=now)
        if ml_finding is not None:
            history_findings = [*history_findings, ml_finding]

    all_findings: list[CryptoFinding] = [
        f for f in [*result.findings, *history_findings] if f.code not in disabled
    ]

    score = risk_score(
        all_findings,
        rule_weights=weights,
        disabled_codes=disabled,
        anomaly_score=anomaly_score,
        anomaly_weight=settings.ml_anomaly_weight if anomaly_score is not None else 0.0,
    )

    envelope = (
        EnvelopeType(result.envelope)
        if result.envelope in EnvelopeType._value2member_map_
        else EnvelopeType.RAW
    )
    sig = _sig_fields(result)

    event = VerificationEvent(
        source=source,
        source_ref=source_ref,
        envelope_type=envelope,
        verdict=verdict,
        algo=sig["algo"],
        hash_alg=sig["hash_alg"],
        key_type=sig["key_type"],
        key_bits=sig["key_bits"],
        curve=sig["curve"],
        signer_subject=result.signer.subject if result.signer else None,
        signer_spki_sha256=result.signer.spki_sha256 if result.signer else None,
        signing_time=result.signing_time,
        tsa_present=result.tsa_present,
        chain_status=result.chain.status if result.chain else None,
        revocation_status=result.revocation.status if result.revocation else None,
        risk_score=score,
        anomaly_score=anomaly_score,
        submitter_id=submitter_id,
        submitter_ip_hash=ip_hash,
        payload_sha256=result.payload_sha256,
        signature_sha256=signature_sha256,
        summary=result.summary,
        result_json=result.as_dict(),
    )
    session.add(event)
    await session.flush()

    finding_rows: list[Finding] = []
    for f in all_findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        cat = f.category.value if hasattr(f.category, "value") else str(f.category)
        row = Finding(
            event_id=event.id,
            rule_code=f.code,
            title=f.title,
            severity=sev,
            category=cat,
            detail=f.detail,
        )
        session.add(row)
        finding_rows.append(row)
    await session.commit()

    alert: Alert | None = None
    incident_id: str | None = None
    has_critical = any(
        (f.severity.value if hasattr(f.severity, "value") else f.severity)
        == Severity.CRITICAL.value
        for f in all_findings
    )
    if all_findings and (score >= DEFAULT_ALERT_THRESHOLD or has_critical):
        codes = sorted({f.code for f in all_findings}, key=lambda c: -_code_priority(c))
        alert = Alert(
            event_id=event.id,
            title=_alert_title(codes, result),
            severity=alert_severity(all_findings),
            status=AlertStatus.OPEN,
            risk_score=score,
            rule_codes=codes,
        )
        session.add(alert)
        await session.commit()
        incident = await correlate(session, alert, event)
        incident_id = incident.id
        await _broadcast(alert, incident_id)

    return DetectionOutcome(
        event=event, findings=finding_rows, alert=alert, incident_id=incident_id
    )


async def _broadcast(alert: Alert, incident_id: str | None) -> None:
    try:
        from app.services.realtime import broker

        await broker.publish(
            {
                "type": "alert",
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity,
                "risk_score": alert.risk_score,
                "rule_codes": alert.rule_codes,
                "incident_id": incident_id,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }
        )
    except Exception as exc:  # pragma: no cover - realtime is best-effort
        log.warning("alert_broadcast_failed", error=str(exc))

    try:
        from app.services.notifications import notify_alert

        await notify_alert(
            title=alert.title,
            severity=alert.severity,
            risk_score=alert.risk_score,
            rule_codes=alert.rule_codes,
        )
    except Exception as exc:  # pragma: no cover - notifications are best-effort
        log.warning("alert_notify_failed", error=str(exc))


def _code_priority(code: str) -> int:
    spec = CATALOG_BY_CODE.get(code)
    if spec is None:
        return 0
    return int(spec.default_severity.weight * spec.default_weight)


def _alert_title(codes: list[str], result: VerificationResult) -> str:
    lead = CATALOG_BY_CODE[codes[0]].name if codes and codes[0] in CATALOG_BY_CODE else "Detection"
    who = ""
    if result.signer and result.signer.subject:
        who = f" · {result.signer.subject[:50]}"
    return f"{lead}{who}"


def signature_digest(signature_bytes: bytes | None) -> str | None:
    return hashlib.sha256(signature_bytes).hexdigest() if signature_bytes else None


async def attach_detection(
    session: AsyncSession,
    result: VerificationResult,
    *,
    source: EventSource = EventSource.API,
    source_ref: str | None = None,
    submitter_id: str | None = None,
    ip_hash: str | None = None,
    signature_bytes: bytes | None = None,
) -> dict:
    """Run detection for a verification and return ``result.as_dict()`` + detection fields."""
    outcome = await run_detection(
        session,
        result,
        source=source,
        source_ref=source_ref,
        submitter_id=submitter_id,
        ip_hash=ip_hash,
        signature_sha256=signature_digest(signature_bytes),
    )
    payload = result.as_dict()
    payload["risk_score"] = outcome.event.risk_score
    payload["event_id"] = outcome.event.id
    payload["alert_id"] = outcome.alert.id if outcome.alert else None
    payload["incident_id"] = outcome.incident_id
    return payload
