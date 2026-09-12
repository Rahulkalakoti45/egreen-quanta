"""Training orchestration: assemble a feature matrix from history or the CSV dataset."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import REPO_ROOT
from app.core.exceptions import ValidationAppError
from app.models.ml_model import MlModel
from app.models.verification_event import VerificationEvent
from app.services.ml import registry
from app.services.ml.features import FEATURE_NAMES, event_to_vector, events_to_matrix
from app.services.ml.scorer import matrix_rows_from_events

_DATASET = REPO_ROOT / "datasets" / "labeled_events.csv"


async def _matrix_from_history(session: AsyncSession, lookback_days: int) -> np.ndarray:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=lookback_days)
    rows = (
        (
            await session.execute(
                select(VerificationEvent)
                .options(selectinload(VerificationEvent.findings))
                .where(VerificationEvent.created_at >= since)
            )
        )
        .scalars()
        .all()
    )
    return events_to_matrix(matrix_rows_from_events(rows))


def _matrix_from_dataset() -> tuple[np.ndarray, np.ndarray]:
    path = Path(_DATASET)
    if not path.exists():
        raise ValidationAppError(
            "datasets/labeled_events.csv not found - run scripts/gen_ml_dataset.py"
        )
    x_rows: list[np.ndarray] = []
    labels: list[int] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            x_rows.append(
                event_to_vector(
                    key_type=r["key_type"] or None,
                    key_bits=int(r["key_bits"]) if r["key_bits"] else None,
                    curve=r["curve"] or None,
                    hash_alg=r["hash_alg"] or None,
                    envelope_type=r["envelope_type"] or None,
                    verdict=r["verdict"] or None,
                    chain_status=r["chain_status"] or None,
                    signing_time=(
                        dt.datetime.fromisoformat(r["signing_time"])
                        if r.get("signing_time")
                        else None
                    ),
                    tsa_present=r.get("tsa_present", "0") in ("1", "true", "True"),
                    created_at=dt.datetime.fromisoformat(r["created_at"]),
                    finding_categories=[c for c in r.get("finding_categories", "").split("|") if c],
                )
            )
            labels.append(int(r.get("is_anomaly", 0)))
    return np.vstack(x_rows), np.asarray(labels)


async def train(
    session: AsyncSession,
    *,
    algo: str,
    source: str,
    lookback_days: int,
    contamination: float,
    trained_by: str | None,
    activate: bool,
) -> MlModel:
    labels: np.ndarray | None = None
    if source == "dataset":
        x, labels = _matrix_from_dataset()
        notes = f"trained from labeled_events.csv ({x.shape[0]} rows)"
    else:
        x = await _matrix_from_history(session, lookback_days)
        notes = f"trained from {x.shape[0]} events in the last {lookback_days} days"

    if x.shape[0] < 20:
        raise ValidationAppError(
            f"only {x.shape[0]} samples available; need >= 20. Use source='dataset' or "
            "run more verifications."
        )

    row = await registry.train_and_register(
        session,
        x,
        algo=algo,
        contamination=contamination,
        source=source,
        trained_by=trained_by,
        notes=notes,
    )

    if labels is not None and labels.sum() > 0:
        model = registry.TrainedModel.load(row.artifact_path)
        scores = model.score(x)
        flagged = scores >= row.threshold
        tp = int((flagged & (labels == 1)).sum())
        fp = int((flagged & (labels == 0)).sum())
        fn = int((~flagged & (labels == 1)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        row.metrics = {
            **row.metrics,
            "eval_precision": round(precision, 3),
            "eval_recall": round(recall, 3),
            "eval_anomalies": int(labels.sum()),
        }
        await session.commit()
        await session.refresh(row)

    if activate:
        row = await registry.activate(session, row.id)
    return row


def feature_names() -> list[str]:
    return list(FEATURE_NAMES)
