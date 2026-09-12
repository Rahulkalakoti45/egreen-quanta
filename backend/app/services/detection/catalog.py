"""Single source of truth for detection-rule metadata (seeds ``detection_rules``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Severity

C = Severity.CRITICAL
H = Severity.HIGH
M = Severity.MEDIUM
L = Severity.LOW


@dataclass(frozen=True, slots=True)
class RuleSpec:
    code: str
    name: str
    description: str
    category: str
    default_severity: Severity
    default_weight: float = 1.0


RULE_CATALOG: list[RuleSpec] = [
    RuleSpec(
        "T01", "Invalid / forged signature", "Cryptographic verification failed.", "forgery", C, 1.5
    ),
    RuleSpec(
        "T02",
        "Weak digest algorithm",
        "MD5 / SHA-1 in a signature or certificate.",
        "weak_crypto",
        H,
    ),
    RuleSpec(
        "T03",
        "Weak key or parameters",
        "RSA < 2048, DSA, small ECC curve, or dangerous RSA exponent.",
        "weak_crypto",
        H,
    ),
    RuleSpec(
        "T04", "RSA padding downgrade", "PKCS#1 v1.5 where policy requires RSA-PSS.", "policy", M
    ),
    RuleSpec(
        "T05",
        "ECDSA malleability",
        "Signature not in canonical low-S / DER form.",
        "forgery",
        L,
        0.5,
    ),
    RuleSpec(
        "T06",
        "Broken certificate chain",
        "Missing issuer, non-CA issuer, or path-length exceeded.",
        "chain",
        H,
    ),
    RuleSpec(
        "T07",
        "Untrusted trust anchor",
        "Chain terminates outside the configured trust store.",
        "chain",
        H,
    ),
    RuleSpec(
        "T08",
        "Certificate outside validity window",
        "Signing time is before notBefore or after notAfter.",
        "validity",
        H,
    ),
    RuleSpec(
        "T09",
        "Revoked certificate",
        "CRL or OCSP reports the certificate as revoked.",
        "revocation",
        C,
        1.5,
    ),
    RuleSpec(
        "T10",
        "Self-signed in production context",
        "Leaf equals issuer where policy forbids it.",
        "policy",
        M,
    ),
    RuleSpec(
        "T11",
        "Public key reused across identities",
        "One SPKI observed under multiple distinct subjects.",
        "policy",
        H,
    ),
    RuleSpec(
        "T12",
        "Unexpected issuing CA",
        "Issuer not on the allow-list for that subject.",
        "policy",
        H,
    ),
    RuleSpec(
        "T13",
        "Missing trusted timestamp",
        "No RFC 3161 timestamp token / untrusted TSA.",
        "timestamp",
        L,
        0.5,
    ),
    RuleSpec(
        "T14",
        "Signature replay",
        "Payload digest + signature seen before, or signature reused on a new payload.",
        "forgery",
        H,
        1.2,
    ),
    RuleSpec(
        "T15",
        "Verification-failure burst",
        "Many invalid signatures from one source in a short window.",
        "forgery",
        M,
    ),
    RuleSpec(
        "T16",
        "Key-usage / EKU mismatch",
        "Certificate used for a purpose its extensions forbid.",
        "policy",
        H,
    ),
    RuleSpec(
        "T17",
        "Trust-store tampering",
        "A trust anchor was added, disabled, or removed.",
        "policy",
        M,
    ),
    RuleSpec(
        "T18",
        "Quantum exposure",
        "Shor-breakable algorithm protecting long-lived data.",
        "quantum",
        M,
        0.8,
    ),
    RuleSpec(
        "T19",
        "Anomalous event (ML)",
        "The active anomaly model scored this event above threshold.",
        "forgery",
        M,
        0.6,
    ),
]

CATALOG_BY_CODE: dict[str, RuleSpec] = {r.code: r for r in RULE_CATALOG}

# Events with risk_score >= this open an alert (overridable via app_config later).
DEFAULT_ALERT_THRESHOLD = 40.0
