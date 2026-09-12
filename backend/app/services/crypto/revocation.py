"""Revocation checking (CRL + OCSP).

Network egress is opt-in (``OUTBOUND_REVOCATION``), SSRF-guarded, time- and size-bounded.
When disabled, returns ``not_checked`` so the caller can apply a soft-fail policy.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509 import ocsp
from cryptography.x509.oid import AuthorityInformationAccessOID

from app.core.config import settings
from app.core.logging import get_logger
from app.services.crypto.types import (
    CryptoFinding,
    FindingCategory,
    RevocationResult,
    Severity,
)

log = get_logger("egreen.revocation")


def _host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    return _host_is_public(parsed.hostname)


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(settings.revocation_timeout_seconds)


def _max_bytes() -> int:
    return settings.revocation_max_response_kb * 1024


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _ocsp_urls(cert: x509.Certificate) -> list[str]:
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return []
    out: list[str] = []
    for d in aia:
        if d.access_method == AuthorityInformationAccessOID.OCSP:
            loc = getattr(d.access_location, "value", "")
            if isinstance(loc, str):
                out.append(loc)
    return out


def _crl_urls(cert: x509.Certificate) -> list[str]:
    try:
        cdps = cert.extensions.get_extension_for_class(x509.CRLDistributionPoints).value
    except x509.ExtensionNotFound:
        return []
    urls: list[str] = []
    for dp in cdps:
        for name in dp.full_name or []:
            val = getattr(name, "value", "")
            if isinstance(val, str) and val.startswith("http"):
                urls.append(val)
    return urls


def _check_ocsp(cert: x509.Certificate, issuer: x509.Certificate, url: str) -> RevocationResult:
    # RFC 6960 CertID uses SHA-1 by convention; this is an identifier, not a security digest.
    builder = ocsp.OCSPRequestBuilder().add_certificate(cert, issuer, hashes.SHA1())  # noqa: S303
    req = builder.build()
    with httpx.Client(timeout=_timeout(), follow_redirects=False) as client:
        resp = client.post(
            url,
            content=req.public_bytes(serialization.Encoding.DER),
            headers={"Content-Type": "application/ocsp-request"},
        )
    if resp.status_code != 200 or len(resp.content) > _max_bytes():
        return RevocationResult(status="unknown", method="ocsp", detail=f"HTTP {resp.status_code}")
    ocsp_resp = ocsp.load_der_ocsp_response(resp.content)
    if ocsp_resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
        return RevocationResult(
            status="unknown", method="ocsp", detail=str(ocsp_resp.response_status)
        )
    status = ocsp_resp.certificate_status
    if status == ocsp.OCSPCertStatus.GOOD:
        return RevocationResult(status="good", method="ocsp")
    if status == ocsp.OCSPCertStatus.REVOKED:
        return RevocationResult(
            status="revoked",
            method="ocsp",
            detail="OCSP responder reports REVOKED",
            revoked_at=_aware(ocsp_resp.revocation_time_utc),
        )
    return RevocationResult(status="unknown", method="ocsp", detail="OCSP status UNKNOWN")


def _check_crl(cert: x509.Certificate, url: str) -> RevocationResult:
    with httpx.Client(timeout=_timeout(), follow_redirects=False) as client:
        resp = client.get(url)
    if resp.status_code != 200 or len(resp.content) > _max_bytes():
        return RevocationResult(status="unknown", method="crl", detail=f"HTTP {resp.status_code}")
    try:
        crl = x509.load_der_x509_crl(resp.content)
    except ValueError:
        try:
            crl = x509.load_pem_x509_crl(resp.content)
        except ValueError:
            return RevocationResult(status="unknown", method="crl", detail="unparseable CRL")
    entry = crl.get_revoked_certificate_by_serial_number(cert.serial_number)
    if entry is not None:
        return RevocationResult(
            status="revoked",
            method="crl",
            detail="listed in CRL",
            revoked_at=_aware(entry.revocation_date_utc),
        )
    return RevocationResult(status="good", method="crl")


def check_revocation(
    cert: x509.Certificate, issuer: x509.Certificate | None
) -> tuple[RevocationResult, list[CryptoFinding]]:
    if not settings.outbound_revocation:
        return RevocationResult(status="not_checked", detail="outbound revocation disabled"), []

    findings: list[CryptoFinding] = []

    if issuer is not None:
        for url in _ocsp_urls(cert):
            if not _safe_url(url):
                log.warning("revocation_url_blocked", url=url, method="ocsp")
                continue
            try:
                result = _check_ocsp(cert, issuer, url)
            except (httpx.HTTPError, ValueError) as exc:
                result = RevocationResult(status="error", method="ocsp", detail=str(exc))
            if result.status in {"good", "revoked"}:
                _maybe_finding(result, findings)
                return result, findings

    for url in _crl_urls(cert):
        if not _safe_url(url):
            log.warning("revocation_url_blocked", url=url, method="crl")
            continue
        try:
            result = _check_crl(cert, url)
        except (httpx.HTTPError, ValueError) as exc:
            result = RevocationResult(status="error", method="crl", detail=str(exc))
        if result.status in {"good", "revoked"}:
            _maybe_finding(result, findings)
            return result, findings

    return RevocationResult(status="unknown", detail="no usable OCSP/CRL endpoint"), findings


def _maybe_finding(result: RevocationResult, findings: list[CryptoFinding]) -> None:
    if result.status == "revoked":
        findings.append(
            CryptoFinding(
                code="T09",
                title="Certificate is revoked",
                severity=Severity.CRITICAL,
                category=FindingCategory.REVOCATION,
                detail=result.detail or f"revoked via {result.method}",
            )
        )
