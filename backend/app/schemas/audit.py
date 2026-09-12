"""Schemas for the audit-log API (Module 6)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class AuditRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: dt.datetime
    actor_id: str | None
    actor_type: str
    action: str
    target_type: str | None
    target_id: str | None
    meta: dict
    prev_hash: str
    row_hash: str


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int
    limit: int
    offset: int


class ChainVerification(BaseModel):
    ok: bool
    checked: int
    break_at: int | None
    head_hash: str | None = None
    head_seq: int | None = None


class AnchorResult(BaseModel):
    seq: int
    head_seq: int
    head_hash: str
    signed: bool
