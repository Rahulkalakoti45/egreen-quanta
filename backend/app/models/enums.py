"""Enumerations shared across models and schemas."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]


# Higher rank ⇒ strictly more capability. Used for "at least this role" checks.
_ROLE_RANK: dict[UserRole, int] = {
    UserRole.VIEWER: 0,
    UserRole.AUDITOR: 1,
    UserRole.ANALYST: 2,
    UserRole.ADMIN: 3,
}


class ApiKeyScope(StrEnum):
    INGEST_EVENTS = "ingest:events"
    INGEST_SIGNATURES = "ingest:signatures"


# ---- Module 2/3 shared ----


class Verdict(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> float:
        return _SEVERITY_WEIGHT[self]


_SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.INFO: 2.0,
    Severity.LOW: 8.0,
    Severity.MEDIUM: 20.0,
    Severity.HIGH: 45.0,
    Severity.CRITICAL: 90.0,
}


class EventSource(StrEnum):
    API = "api"
    UPLOAD = "upload"
    INGEST = "ingest"
    CONNECTOR = "connector"


class EnvelopeType(StrEnum):
    RAW = "raw"
    PDF = "pdf"
    CMS = "cms"
    JWS = "jws"
    CERTIFICATE = "certificate"


class AlertStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    CLOSED = "closed"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    CLOSED = "closed"
