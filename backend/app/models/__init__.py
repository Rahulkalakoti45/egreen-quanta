"""SQLAlchemy models.

Importing this package imports every model module so that ``Base.metadata`` is fully
populated for Alembic autogenerate. Model modules are appended here as each build module lands.
"""

from __future__ import annotations

from app.db.base import Base
from app.models.alert import Alert, AlertNote, Incident
from app.models.api_key import ApiKey
from app.models.audit import AuditLog
from app.models.certificate import Certificate
from app.models.detection_rule import DetectionRule
from app.models.enums import ApiKeyScope, UserRole
from app.models.login_attempt import LoginAttempt
from app.models.ml_model import MlModel
from app.models.quantum import QuantumExposureScore, QuantumRun
from app.models.refresh_token import RefreshToken
from app.models.trust_anchor import CaAllowlistEntry, TrustAnchor
from app.models.user import User
from app.models.verification_event import Finding, VerificationEvent

__all__ = [
    "Alert",
    "AlertNote",
    "ApiKey",
    "ApiKeyScope",
    "AuditLog",
    "Base",
    "CaAllowlistEntry",
    "Certificate",
    "DetectionRule",
    "Finding",
    "Incident",
    "LoginAttempt",
    "MlModel",
    "QuantumExposureScore",
    "QuantumRun",
    "RefreshToken",
    "TrustAnchor",
    "User",
    "UserRole",
    "VerificationEvent",
]
