"""Registry of trained local anomaly-detection models (Module 5)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid


class MlModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # "isolation_forest" | "one_class_svm"
    algo: Mapped[str] = mapped_column(String(24), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    feature_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    n_train: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold: Mapped[float] = mapped_column(nullable=False, default=0.7)

    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="history")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    trained_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trained_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
