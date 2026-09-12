"""Append-only, hash-chained audit log (Module 6).

Each row's ``row_hash`` covers its own core fields plus the previous row's ``row_hash``,
so any tampering with historic rows is detectable and can be located by sequence number.
Rows are never updated or deleted in normal operation.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

GENESIS_HASH = "0" * 64


class AuditLog(Base):
    __tablename__ = "audit_logs"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
