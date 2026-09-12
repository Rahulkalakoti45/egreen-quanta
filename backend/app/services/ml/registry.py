"""Model registry: train + persist + activate local anomaly models."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.ml_model import MlModel
from app.services.ml.anomaly import TrainedModel, train_model
from app.services.ml.features import FEATURE_SCHEMA_VERSION

log = get_logger("egreen.ml")

# process-local cache of the active model: (model_id, TrainedModel)
_ACTIVE: tuple[str, TrainedModel] | None = None


def _model_dir() -> Path:
    d = settings.model_dir_path
    d.mkdir(parents=True, exist_ok=True)
    return d


def invalidate_cache() -> None:
    global _ACTIVE
    _ACTIVE = None


async def train_and_register(
    session: AsyncSession,
    x: np.ndarray,
    *,
    algo: str,
    contamination: float,
    source: str,
    trained_by: str | None,
    notes: str = "",
) -> MlModel:
    model, metrics = train_model(
        x, algo=algo, feature_schema_version=FEATURE_SCHEMA_VERSION, contamination=contamination
    )
    model_id = uuid.uuid4().hex
    path = _model_dir() / f"{algo}-{model_id}.joblib"
    sha = model.save(path)

    row = MlModel(
        id=model_id,
        algo=algo,
        params=model.params,
        metrics=metrics,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        n_train=int(x.shape[0]),
        threshold=0.7,
        artifact_path=str(path),
        artifact_sha256=sha,
        is_active=False,
        source=source,
        notes=notes,
        trained_by=trained_by,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    log.info("ml_model_trained", model_id=model_id, algo=algo, **metrics)
    return row


async def activate(session: AsyncSession, model_id: str) -> MlModel:
    row = (
        await session.execute(select(MlModel).where(MlModel.id == model_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("ML model not found")
    if row.feature_schema_version != FEATURE_SCHEMA_VERSION:
        raise ValidationAppError(
            f"model feature schema v{row.feature_schema_version} "
            f"!= current v{FEATURE_SCHEMA_VERSION}"
        )
    if not Path(row.artifact_path).exists():
        raise ValidationAppError("model artifact is missing on disk")

    await session.execute(update(MlModel).values(is_active=False))
    row.is_active = True
    await session.commit()
    await session.refresh(row)
    invalidate_cache()
    return row


async def deactivate_all(session: AsyncSession) -> None:
    await session.execute(update(MlModel).values(is_active=False))
    await session.commit()
    invalidate_cache()


async def delete_model(session: AsyncSession, model_id: str) -> None:
    row = (
        await session.execute(select(MlModel).where(MlModel.id == model_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("ML model not found")
    Path(row.artifact_path).unlink(missing_ok=True)
    was_active = row.is_active
    await session.delete(row)
    await session.commit()
    if was_active:
        invalidate_cache()


async def get_active_model(session: AsyncSession) -> TrainedModel | None:
    """Load (and cache) the active model, or None if ML is disabled / none active."""
    global _ACTIVE
    if not settings.ml_enabled:
        return None
    row = (
        await session.execute(select(MlModel).where(MlModel.is_active.is_(True)))
    ).scalar_one_or_none()
    if row is None:
        return None
    if _ACTIVE is not None and _ACTIVE[0] == row.id:
        return _ACTIVE[1]
    try:
        model = TrainedModel.load(row.artifact_path)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        log.warning("ml_model_load_failed", model_id=row.id, error=str(exc))
        return None
    if model.feature_schema_version != FEATURE_SCHEMA_VERSION:
        log.warning("ml_model_schema_stale", model_id=row.id)
        return None
    _ACTIVE = (row.id, model)
    return model


async def list_models(session: AsyncSession) -> list[MlModel]:
    rows = await session.execute(select(MlModel).order_by(MlModel.trained_at.desc()))
    return list(rows.scalars().all())


async def prune_orphans(session: AsyncSession) -> int:
    """Delete registry rows whose artifact vanished (best-effort housekeeping)."""
    removed = 0
    for row in await list_models(session):
        if not Path(row.artifact_path).exists():
            await session.delete(row)
            removed += 1
    if removed:
        await session.commit()
        invalidate_cache()
    return removed
