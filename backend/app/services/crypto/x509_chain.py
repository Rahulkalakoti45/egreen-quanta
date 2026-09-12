"""X.509 path building and validation against a configured trust store.

Hand-rolled on top of ``cryptography`` for deterministic, testable behaviour:
issuer/signature linkage, validity window, and CA constraints. Revocation is a
separate concern (see ``revocation.py``).
"""

from __future__ import annotations

import datetime as dt

from cryptography import x509

from app.services.crypto.types import (
    ChainResult,
    CryptoFinding,
    FindingCategory,
    Severity,
)
from app.services.crypto.x509_utils import cert_info, spki_sha256

_MAX_DEPTH = 12


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _basic_constraints(cert: x509.Certificate) -> x509.BasicConstraints | None:
    try:
        return cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound:
        return None


def _is_ca(cert: x509.Certificate) -> bool:
    bc = _basic_constraints(cert)
    return bool(bc.ca) if bc else False


def _path_length(cert: x509.Certificate) -> int | None:
    bc = _basic_constraints(cert)
    return bc.path_length if bc else None


def _can_sign_certs(cert: x509.Certificate) -> bool:
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        return bool(ku.key_cert_sign)
    except x509.ExtensionNotFound:
        return True  # absent KeyUsage ⇒ unconstrained


def build_and_validate(
    leaf: x509.Certificate,
    *,
    extra_certs: list[x509.Certificate],
    trust_anchors: list[x509.Certificate],
    at_time: dt.datetime | None = None,
) -> tuple[ChainResult, list[CryptoFinding]]:
    at_time = at_time or dt.datetime.now(dt.UTC)
    findings: list[CryptoFinding] = []

    anchor_spki = {spki_sha256(a.public_key()): a for a in trust_anchors}
    pool = list(extra_certs) + list(trust_anchors)

    chain: list[x509.Certificate] = [leaf]
    current = leaf
    matched_anchor: str | None = None

    for depth in range(_MAX_DEPTH):
        cur_spki = spki_sha256(current.public_key())
        if cur_spki in anchor_spki:
            matched_anchor = cur_spki
            break

        # A self-signed cert that is not a configured anchor ends the chain untrusted.
        self_signed = current.subject == current.issuer
        issuer: x509.Certificate | None = None
        if not self_signed:
            for cand in pool:
                if cand.subject != current.issuer or spki_sha256(cand.public_key()) == cur_spki:
                    continue
                try:
                    current.verify_directly_issued_by(cand)
                    issuer = cand
                    break
                except Exception:  # noqa: S112 - any linkage failure ⇒ not this issuer
                    continue

        if issuer is None:
            if self_signed:
                findings.append(
                    CryptoFinding(
                        code="T07",
                        title="Chain terminates at an untrusted root",
                        severity=Severity.HIGH,
                        category=FindingCategory.CHAIN,
                        detail=f"Self-signed root '{current.subject.rfc4514_string()}' "
                        "is not in the trust store.",
                    )
                )
                status = "untrusted"
            else:
                findings.append(
                    CryptoFinding(
                        code="T06",
                        title="Incomplete certificate chain",
                        severity=Severity.HIGH,
                        category=FindingCategory.CHAIN,
                        detail=f"No issuer found for '{current.subject.rfc4514_string()}'.",
                    )
                )
                status = "incomplete"
            return (
                ChainResult(
                    status=status,
                    chain=[cert_info(c) for c in chain],
                    error=findings[-1].detail,
                ),
                findings,
            )

        # constraint checks on the issuer (a CA)
        if not _is_ca(issuer):
            findings.append(
                CryptoFinding(
                    code="T06",
                    title="Issuer is not a CA",
                    severity=Severity.CRITICAL,
                    category=FindingCategory.CHAIN,
                    detail=f"'{issuer.subject.rfc4514_string()}' lacks basicConstraints CA:TRUE.",
                )
            )
        if not _can_sign_certs(issuer):
            findings.append(
                CryptoFinding(
                    code="T16",
                    title="Issuer lacks keyCertSign",
                    severity=Severity.HIGH,
                    category=FindingCategory.CHAIN,
                    detail=f"'{issuer.subject.rfc4514_string()}' KeyUsage omits keyCertSign.",
                )
            )
        plen = _path_length(issuer)
        intermediates_below = depth  # number of CAs between issuer and leaf
        if plen is not None and plen < intermediates_below:
            findings.append(
                CryptoFinding(
                    code="T06",
                    title="Path length constraint exceeded",
                    severity=Severity.HIGH,
                    category=FindingCategory.CHAIN,
                    detail=f"pathLenConstraint={plen} exceeded at depth {intermediates_below}.",
                )
            )

        chain.append(issuer)
        current = issuer
    else:
        return (
            ChainResult(
                status="error", chain=[cert_info(c) for c in chain], error="chain too long"
            ),
            findings,
        )

    # validity window across the whole chain
    for cert in chain:
        nb, na = _aware(cert.not_valid_before_utc), _aware(cert.not_valid_after_utc)
        if at_time < nb or at_time > na:
            findings.append(
                CryptoFinding(
                    code="T08",
                    title="Certificate outside its validity window",
                    severity=Severity.HIGH,
                    category=FindingCategory.VALIDITY,
                    detail=f"'{cert.subject.rfc4514_string()}' valid {nb.date()} to "
                    f"{na.date()}, checked at {at_time.date()}.",
                )
            )

    return (
        ChainResult(
            status="trusted",
            chain=[cert_info(c) for c in chain],
            trust_anchor_spki=matched_anchor,
        ),
        findings,
    )
