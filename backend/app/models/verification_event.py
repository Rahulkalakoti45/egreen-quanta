"""A persisted record of one verification (signature or certificate)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid
from app.models.enums import EnvelopeType, EventSource, Verdict


class VerificationEvent(Base):
    __tablename__ = "verification_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    source: Mapped[EventSource] = mapped_column(String(16), nullable=False, default=EventSource.API)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    envelope_type: Mapped[EnvelopeType] = mapped_column(String(16), nullable=False)
    verdict: Mapped[Verdict] = mapped_column(String(16), index=True, nullable=False)

    algo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash_alg: Mapped[str | None] = mapped_column(String(16), nullable=True)
    key_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    key_bits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curve: Mapped[str | None] = mapped_column(String(32), nullable=True)

    signer_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    signer_spki_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    signing_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tsa_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    chain_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revocation_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    submitter_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitter_ip_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    payload_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    signature_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    findings: Mapped[list[Finding]] = relationship(
        back_populates="event", cascade="all, delete-orphan", lazy="selectin"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("verification_events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped[VerificationEvent] = relationship(back_populates="findings")
