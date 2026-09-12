"""run_detection: persistence, alerting, correlation."""

from __future__ import annotations

import pytest
from app.models.alert import Incident
from app.models.verification_event import Finding, VerificationEvent
from app.services.crypto.types import (
    CryptoFinding,
    FindingCategory,
    Severity,
    Verdict,
    VerificationResult,
)
from app.services.detection.engine import run_detection, sync_rules
from sqlalchemy import func, select

pytestmark = pytest.mark.asyncio


def _result(verdict: Verdict, findings: list[CryptoFinding], **kw) -> VerificationResult:
    return VerificationResult(
        verdict=verdict,
        envelope="raw",
        signature=None,
        signer=None,
        chain=None,
        revocation=None,
        signing_time=None,
        tsa_present=False,
        tsa_trusted=False,
        findings=findings,
        payload_sha256=kw.get("payload_sha256", "payload-1"),
        summary="test",
    )


async def test_clean_verification_no_alert(db_session) -> None:
    await sync_rules(db_session)
    outcome = await run_detection(db_session, _result(Verdict.VALID, []))
    assert outcome.alert is None
    assert (
        await db_session.execute(select(func.count()).select_from(VerificationEvent))
    ).scalar_one() == 1


async def test_forgery_opens_alert_and_incident(db_session) -> None:
    await sync_rules(db_session)
    findings = [
        CryptoFinding(
            "T01", "Signature does not verify", Severity.CRITICAL, FindingCategory.FORGERY
        )
    ]
    outcome = await run_detection(
        db_session, _result(Verdict.INVALID, findings), signature_sha256="sig-x"
    )
    assert outcome.alert is not None
    assert outcome.alert.severity == "critical"
    assert "T01" in outcome.alert.rule_codes
    assert outcome.incident_id is not None

    persisted_findings = (
        await db_session.execute(select(func.count()).select_from(Finding))
    ).scalar_one()
    assert persisted_findings >= 1


async def test_similar_alerts_correlate_into_one_incident(db_session) -> None:
    await sync_rules(db_session)
    findings = [CryptoFinding("T01", "forged", Severity.CRITICAL, FindingCategory.FORGERY)]

    a = await run_detection(
        db_session,
        _result(Verdict.INVALID, findings, payload_sha256="same-doc"),
        ip_hash="attacker-ip",
        signature_sha256="s1",
    )
    b = await run_detection(
        db_session,
        _result(Verdict.INVALID, findings, payload_sha256="same-doc"),
        ip_hash="attacker-ip",
        signature_sha256="s2",
    )
    assert a.incident_id == b.incident_id
    incident_count = (
        await db_session.execute(select(func.count()).select_from(Incident))
    ).scalar_one()
    assert incident_count == 1
    incident = (
        await db_session.execute(select(Incident).where(Incident.id == a.incident_id))
    ).scalar_one()
    assert incident.alert_count == 2


async def test_disabled_rule_suppresses_finding(db_session) -> None:
    await sync_rules(db_session)
    from app.models.detection_rule import DetectionRule

    rule = (
        await db_session.execute(select(DetectionRule).where(DetectionRule.code == "T05"))
    ).scalar_one()
    rule.enabled = False
    await db_session.commit()

    findings = [CryptoFinding("T05", "malleable", Severity.LOW, FindingCategory.FORGERY)]
    outcome = await run_detection(db_session, _result(Verdict.VALID, findings))
    assert not any(f.rule_code == "T05" for f in outcome.findings)
