"""History-aware rules: T14 replay, T15 verification-failure burst."""

from __future__ import annotations

import datetime as dt

import pytest
from app.models.enums import EnvelopeType, EventSource, Verdict
from app.models.verification_event import VerificationEvent
from app.services.detection.history_rules import HistoryContext, evaluate_history_rules

pytestmark = pytest.mark.asyncio


def _event(session, **kw) -> VerificationEvent:
    defaults = {
        "source": EventSource.API,
        "envelope_type": EnvelopeType.RAW,
        "verdict": Verdict.VALID,
        "risk_score": 0.0,
        "summary": "",
        "result_json": {},
    }
    defaults.update(kw)
    ev = VerificationEvent(**defaults)
    session.add(ev)
    return ev


async def _ctx(**kw) -> HistoryContext:
    base = {
        "envelope": "raw",
        "verdict": Verdict.VALID,
        "payload_sha256": "pay-a",
        "signature_sha256": "sig-a",
        "signer_spki_sha256": "spki-a",
        "submitter_ip_hash": "ip-a",
        "now": dt.datetime.now(dt.UTC),
    }
    base.update(kw)
    return HistoryContext(**base)


async def test_replay_same_payload(db_session) -> None:
    _event(db_session, payload_sha256="pay-a", signature_sha256="sig-a")
    await db_session.commit()

    findings = await evaluate_history_rules(db_session, await _ctx())
    assert any(f.code == "T14" and "replay" in f.title.lower() for f in findings)


async def test_signature_reused_on_new_payload_is_critical(db_session) -> None:
    _event(db_session, payload_sha256="pay-OLD", signature_sha256="sig-a")
    await db_session.commit()

    findings = await evaluate_history_rules(db_session, await _ctx(payload_sha256="pay-NEW"))
    t14 = [f for f in findings if f.code == "T14"]
    assert t14 and t14[0].severity.value == "critical"


async def test_no_replay_for_novel_signature(db_session) -> None:
    findings = await evaluate_history_rules(db_session, await _ctx(signature_sha256="brand-new"))
    assert not any(f.code == "T14" for f in findings)


async def test_failure_burst(db_session) -> None:
    now = dt.datetime.now(dt.UTC)
    for _ in range(4):
        _event(
            db_session,
            verdict=Verdict.INVALID,
            submitter_ip_hash="ip-burst",
            created_at=now - dt.timedelta(minutes=1),
        )
    await db_session.commit()

    ctx = await _ctx(
        verdict=Verdict.INVALID, submitter_ip_hash="ip-burst", signature_sha256="s", now=now
    )
    findings = await evaluate_history_rules(db_session, ctx)
    assert any(f.code == "T15" for f in findings)


async def test_no_burst_below_threshold(db_session) -> None:
    now = dt.datetime.now(dt.UTC)
    _event(db_session, verdict=Verdict.INVALID, submitter_ip_hash="ip-quiet", created_at=now)
    await db_session.commit()
    ctx = await _ctx(verdict=Verdict.INVALID, submitter_ip_hash="ip-quiet", now=now)
    findings = await evaluate_history_rules(db_session, ctx)
    assert not any(f.code == "T15" for f in findings)
