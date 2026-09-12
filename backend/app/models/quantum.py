"""Persisted quantum-inspired optimisation runs and per-signature exposure scores."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid


class QuantumRun(Base):
    __tablename__ = "quantum_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wall_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class QuantumExposureScore(Base):
    __tablename__ = "quantum_exposure_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("verification_events.id", ondelete="CASCADE"), index=True, nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    spki_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    algo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    key_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    key_bits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curve: Mapped[str | None] = mapped_column(String(32), nullable=True)

    qes: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    factors: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
