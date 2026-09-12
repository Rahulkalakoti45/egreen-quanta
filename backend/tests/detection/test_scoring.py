"""Risk-scoring behaviour."""

from __future__ import annotations

from app.services.crypto.types import CryptoFinding, FindingCategory, Severity
from app.services.detection.scoring import alert_severity, risk_score


def _f(code: str, sev: Severity) -> CryptoFinding:
    return CryptoFinding(code=code, title=code, severity=sev, category=FindingCategory.FORGERY)


def test_no_findings_is_zero() -> None:
    assert risk_score([]) == 0.0


def test_single_critical_dominates() -> None:
    score = risk_score([_f("T01", Severity.CRITICAL)])
    assert score >= 80


def test_more_findings_never_decrease_score() -> None:
    base = risk_score([_f("T02", Severity.HIGH)])
    more = risk_score([_f("T02", Severity.HIGH), _f("T13", Severity.LOW)])
    assert more >= base


def test_disabled_code_is_ignored() -> None:
    with_disabled = risk_score([_f("T01", Severity.CRITICAL)], disabled_codes={"T01"})
    assert with_disabled == 0.0


def test_weight_scales_contribution() -> None:
    low = risk_score([_f("T05", Severity.LOW)], rule_weights={"T05": 0.1})
    high = risk_score([_f("T05", Severity.LOW)], rule_weights={"T05": 5.0})
    assert high > low


def test_alert_severity_picks_highest() -> None:
    assert alert_severity([_f("T13", Severity.LOW), _f("T09", Severity.CRITICAL)]) == "critical"
    assert alert_severity([_f("T13", Severity.LOW)]) == "low"
