"""Bridge from the detection engine to the active anomaly model."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.ml_model import MlModel
from app.services.crypto.types import (
    CryptoFinding,
    FindingCategory,
    Severity,
    VerificationResult,
)
from app.services.ml import registry
from app.services.ml.features import event_to_vector

log = get_logger("egreen.ml.scorer")


async def score_verification(
    session: AsyncSession,
    result: VerificationResult,
    *,
    created_at: dt.datetime | None = None,
) -> tuple[float | None, CryptoFinding | None]:
    """Return (anomaly_score in [0,1] or None, optional advisory T19 finding).

    Returns ``(None, None)`` when ML is disabled or no compatible model is active.
    """
    if not settings.ml_enabled:
        return None, None
    model = await registry.get_active_model(session)
    if model is None:
        return None, None

    sig = result.signature
    finding_cats = [
        f.category.value if hasattr(f.category, "value") else str(f.category)
        for f in result.findings
    ]
    vec = event_to_vector(
        key_type=(sig.key.key_type if sig and sig.key else None),
        key_bits=(sig.key.key_bits if sig and sig.key else None),
        curve=(sig.key.curve if sig and sig.key else None),
        hash_alg=(sig.hash_alg if sig else None),
        envelope_type=result.envelope,
        verdict=result.verdict.value,
        chain_status=(result.chain.status if result.chain else None),
        signing_time=result.signing_time,
        tsa_present=result.tsa_present,
        created_at=created_at or dt.datetime.now(dt.UTC),
        finding_categories=finding_cats,
    )
    try:
        score = float(model.score(vec)[0])
    except Exception as exc:  # never let ML break verification
        log.warning("ml_score_failed", error=str(exc))
        return None, None

    finding: CryptoFinding | None = None
    if score >= _threshold():
        finding = CryptoFinding(
            code="T19",
            title="Anomalous verification event (ML)",
            severity=Severity.MEDIUM,
            category=FindingCategory.FORGERY,
            detail=f"Local anomaly model scored this event {score:.2f} "
            f"(threshold {_threshold():.2f}); advisory only.",
        )
    return round(score, 4), finding


def _threshold() -> float:
    return 0.7


async def active_model_row(session: AsyncSession) -> MlModel | None:
    from sqlalchemy import select

    return (
        await session.execute(select(MlModel).where(MlModel.is_active.is_(True)))
    ).scalar_one_or_none()


def matrix_rows_from_events(events: Sequence) -> list[dict]:
    """Turn ``VerificationEvent`` ORM rows + preloaded finding categories into feature dicts."""
    rows: list[dict] = []
    for ev in events:
        cats = [f.category for f in getattr(ev, "findings", [])]
        rows.append(
            {
                "key_type": ev.key_type,
                "key_bits": ev.key_bits,
                "curve": ev.curve,
                "hash_alg": ev.hash_alg,
                "envelope_type": ev.envelope_type,
                "verdict": ev.verdict,
                "chain_status": ev.chain_status,
                "signing_time": ev.signing_time,
                "tsa_present": ev.tsa_present,
                "created_at": ev.created_at,
                "finding_categories": cats,
            }
        )
    return rows
