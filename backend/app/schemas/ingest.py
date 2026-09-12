"""Schemas for the machine-ingest API (Module 8)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.schemas.crypto import RawVerifyRequest  # re-used for /ingest/signatures


class IngestFinding(BaseModel):
    code: str = Field(pattern=r"^T\d{2}$")
    title: str
    severity: str = Field(pattern="^(critical|high|medium|low|info)$")
    category: str = "policy"
    detail: str = ""


class IngestEventRequest(BaseModel):
    verdict: str = Field(pattern="^(valid|invalid|indeterminate)$")
    envelope: str = Field(default="raw", pattern="^(raw|pdf|cms|jws|certificate)$")
    source_ref: str | None = Field(default=None, max_length=255)

    algorithm: str | None = None
    hash_alg: str | None = None
    key_type: str | None = None
    key_bits: int | None = Field(default=None, ge=1)
    curve: str | None = None

    signer_subject: str | None = None
    signer_spki_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    signing_time: dt.datetime | None = None
    tsa_present: bool = False
    chain_status: str | None = None
    revocation_status: str | None = None
    payload_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    signature_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    findings: list[IngestFinding] = Field(default_factory=list, max_length=50)
    summary: str = ""


class IngestAck(BaseModel):
    event_id: str
    verdict: str
    risk_score: float
    alert_id: str | None
    incident_id: str | None


__all__ = ["IngestAck", "IngestEventRequest", "IngestFinding", "RawVerifyRequest"]
