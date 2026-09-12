"""score_verification bridge + detection-engine integration."""

from __future__ import annotations

import numpy as np
import pytest
from app.core.config import settings
from app.services.crypto.types import (
    KeyParams,
    SignatureParams,
    Verdict,
    VerificationResult,
)
from app.services.detection.engine import run_detection, sync_rules
from app.services.ml import registry
from app.services.ml.anomaly import train_model
from app.services.ml.features import FEATURE_SCHEMA_VERSION, event_to_vector
from app.services.ml.scorer import score_verification

pytestmark = pytest.mark.asyncio


def _result(verdict: Verdict = Verdict.VALID) -> VerificationResult:
    return VerificationResult(
        verdict=verdict,
        envelope="raw",
        signature=SignatureParams(
            algorithm="sha256-rsa-pss",
            hash_alg="sha256",
            key=KeyParams(key_type="rsa", key_bits=2048),
        ),
        signer=None,
        chain=None,
        revocation=None,
        signing_time=None,
        tsa_present=False,
        tsa_trusted=False,
        findings=[],
        payload_sha256="p",
        summary="",
    )


async def test_scorer_returns_none_when_disabled(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ml_enabled", False)
    score, finding = await score_verification(db_session, _result())
    assert score is None and finding is None


async def _train_active_model(db_session) -> None:
    import datetime as dt

    now = dt.datetime(2026, 9, 1, 12, tzinfo=dt.UTC)
    rows = []
    for _ in range(120):
        rows.append(
            event_to_vector(
                key_type="rsa",
                key_bits=2048,
                curve=None,
                hash_alg="sha256",
                envelope_type="raw",
                verdict="valid",
                chain_status="trusted",
                signing_time=None,
                tsa_present=False,
                created_at=now,
                finding_categories=[],
            )
        )
    for _ in range(8):
        rows.append(
            event_to_vector(
                key_type="dsa",
                key_bits=1024,
                curve=None,
                hash_alg="md5",
                envelope_type="raw",
                verdict="invalid",
                chain_status="error",
                signing_time=None,
                tsa_present=False,
                created_at=now,
                finding_categories=["forgery", "weak_crypto", "chain"],
            )
        )
    x = np.vstack(rows)
    model, metrics = train_model(
        x, algo="isolation_forest", feature_schema_version=FEATURE_SCHEMA_VERSION
    )
    import tempfile
    from pathlib import Path

    from app.models.ml_model import MlModel

    path = Path(tempfile.gettempdir()) / "egq-test-model.joblib"
    sha = model.save(path)
    db_session.add(
        MlModel(
            algo="isolation_forest",
            params=model.params,
            metrics=metrics,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            n_train=int(x.shape[0]),
            threshold=0.7,
            artifact_path=str(path),
            artifact_sha256=sha,
            is_active=True,
            source="test",
        )
    )
    await db_session.commit()
    registry.invalidate_cache()


async def test_scorer_flags_anomalous_event(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ml_enabled", True)
    await _train_active_model(db_session)

    normal_score, _ = await score_verification(db_session, _result(Verdict.VALID))
    assert normal_score is not None
    assert 0.0 <= normal_score <= 1.0

    weird = _result(Verdict.INVALID)
    weird.signature = SignatureParams(
        algorithm="md5-dsa", hash_alg="md5", key=KeyParams(key_type="dsa", key_bits=1024)
    )
    weird.chain = None
    from app.services.crypto.types import ChainResult

    weird.chain = ChainResult(status="error")
    weird.findings = []
    anom_score, _ = await score_verification(db_session, weird)
    assert anom_score is not None
    assert anom_score > normal_score


async def test_engine_populates_anomaly_score(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ml_enabled", True)
    await sync_rules(db_session)
    await _train_active_model(db_session)

    outcome = await run_detection(db_session, _result(Verdict.VALID))
    assert outcome.event.anomaly_score is not None
