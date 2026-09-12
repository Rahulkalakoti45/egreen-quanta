"""Trust store: CA anchors and an optional issuer allow-list."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class TrustAnchor(Base, TimestampMixin):
    __tablename__ = "trust_anchors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    spki_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    not_after: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pem: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CaAllowlistEntry(Base, TimestampMixin):
    """Bind an expected issuer (by SPKI) to subjects matching a pattern → issuer-anomaly (T12)."""

    __tablename__ = "ca_allowlist_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    subject_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_spki_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    added_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
