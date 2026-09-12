"""Observed certificates — populated as verification runs; enables key-reuse detection (T11)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class Certificate(Base, TimestampMixin):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    spki_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str] = mapped_column(Text, nullable=False)
    serial_hex: Mapped[str] = mapped_column(String(80), nullable=False)

    not_before: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    not_after: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sig_algo: Mapped[str] = mapped_column(String(64), nullable=False)
    key_type: Mapped[str] = mapped_column(String(16), nullable=False)
    key_bits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curve: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_ca: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    self_signed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    times_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pem: Mapped[str] = mapped_column(Text, nullable=False)
