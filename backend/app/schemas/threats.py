"""Schemas for detection rules, events, alerts and incidents (Module 3)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertStatus, IncidentStatus

# ---- detection rules ----


class DetectionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str
    category: str
    default_severity: str
    enabled: bool
    weight: float
    config: dict


class DetectionRulePatch(BaseModel):
    enabled: bool | None = None
    weight: float | None = Field(default=None, ge=0, le=5)
    config: dict | None = None


# ---- events / findings ----


class FindingRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_code: str
    title: str
    severity: str
    category: str
    detail: str
    created_at: dt.datetime


class EventListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: dt.datetime
    source: str
    envelope_type: str
    verdict: str
    algo: str | None
    signer_subject: str | None
    chain_status: str | None
    revocation_status: str | None
    risk_score: float
    summary: str


class EventDetail(EventListItem):
    source_ref: str | None
    hash_alg: str | None
    key_type: str | None
    key_bits: int | None
    curve: str | None
    signer_spki_sha256: str | None
    signing_time: dt.datetime | None
    tsa_present: bool
    payload_sha256: str | None
    anomaly_score: float | None
    findings: list[FindingRow]
    result_json: dict


# ---- alerts ----


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    incident_id: str | None
    title: str
    severity: str
    status: AlertStatus
    risk_score: float
    rule_codes: list[str]
    assigned_to: str | None
    triaged_by: str | None
    triaged_at: dt.datetime | None
    notes: str
    created_at: dt.datetime
    updated_at: dt.datetime


class AlertDetail(AlertOut):
    event: EventDetail


class AlertPatch(BaseModel):
    status: AlertStatus | None = None
    assigned_to: str | None = None
    note: str | None = Field(default=None, max_length=2000)


# ---- incidents ----


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: IncidentStatus
    severity: str
    cohesion_score: float
    method: str
    alert_count: int
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    signals: dict
    created_at: dt.datetime


class IncidentDetail(IncidentOut):
    alerts: list[AlertOut]


class IncidentPatch(BaseModel):
    status: IncidentStatus


# ---- dashboard stats ----


class ThreatStats(BaseModel):
    events_24h: int
    events_total: int
    invalid_24h: int
    open_alerts: int
    alerts_by_severity: dict[str, int]
    open_incidents: int
    quantum_vulnerable_events: int
    mean_time_to_triage_seconds: float | None
    timeline: list[dict]
    top_rules: list[dict] = []
    recent_alerts: list[dict] = []
    pqc_by_band: dict[str, int] = {}
