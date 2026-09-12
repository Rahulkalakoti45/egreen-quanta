"""Risk scoring: blend finding severities, rule weights and the optional ML score."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import Severity
from app.services.crypto.types import CryptoFinding
from app.services.detection.catalog import CATALOG_BY_CODE


def risk_score(
    findings: Iterable[CryptoFinding],
    *,
    rule_weights: dict[str, float] | None = None,
    disabled_codes: set[str] | None = None,
    anomaly_score: float | None = None,
    anomaly_weight: float = 0.0,
) -> float:
    """Return a 0-100 risk score.

    Each finding contributes ``severity_weight * rule_weight``; contributions combine
    with a diminishing-returns (noisy-OR style) aggregation so a single critical finding
    is decisive but many low findings cannot trivially exceed it.
    """
    rule_weights = rule_weights or {}
    disabled_codes = disabled_codes or set()

    remaining = 1.0
    for f in findings:
        if f.code in disabled_codes:
            continue
        sev = Severity(f.severity.value if hasattr(f.severity, "value") else f.severity)
        base = sev.weight / 100.0
        w = rule_weights.get(
            f.code, CATALOG_BY_CODE[f.code].default_weight if f.code in CATALOG_BY_CODE else 1.0
        )
        contribution = min(0.99, base * w)
        remaining *= 1.0 - contribution

    score = (1.0 - remaining) * 100.0

    if anomaly_score is not None and anomaly_weight > 0:
        score = min(100.0, score + anomaly_weight * anomaly_score * 100.0)

    return round(score, 1)


def alert_severity(findings: Iterable[CryptoFinding]) -> str:
    order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    present = {
        Severity(f.severity.value if hasattr(f.severity, "value") else f.severity) for f in findings
    }
    for sev in order:
        if sev in present:
            return sev.value
    return Severity.INFO.value
