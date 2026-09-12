"""Tunable detection-rule configuration (one row per threat-model code)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DetectionRule(Base, TimestampMixin):
    __tablename__ = "detection_rules"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    default_severity: Mapped[str] = mapped_column(String(16), nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
