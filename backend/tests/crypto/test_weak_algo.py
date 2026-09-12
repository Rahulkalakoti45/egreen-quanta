"""Weak-parameter detection (T02-T05, T16)."""

from __future__ import annotations

import datetime as dt

from app.services.crypto.types import CertInfo, KeyParams, SignatureParams
from app.services.crypto.weak_algo import certificate_findings, signature_findings
from app.services.crypto.x509_utils import cert_info


def _fake_cert_info(**overrides) -> CertInfo:
    base = {
        "subject": "CN=Signer",
        "issuer": "CN=Issuing CA",
        "serial_hex": "01",
        "not_before": dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        "not_after": dt.datetime(2030, 1, 1, tzinfo=dt.UTC),
        "spki_sha256": "0" * 64,
        "sig_algo": "sha256WithRSAEncryption",
        "key": KeyParams(key_type="rsa", key_bits=3072),
        "is_ca": False,
        "self_signed": False,
    }
    base.update(overrides)
    return CertInfo(**base)  # type: ignore[arg-type]


def test_sha1_signature_flagged() -> None:
    params = SignatureParams(
        algorithm="sha1-rsa", hash_alg="sha1", key=KeyParams(key_type="rsa", key_bits=2048)
    )
    codes = {f.code for f in signature_findings(params)}
    assert "T02" in codes


def test_small_rsa_key_flagged() -> None:
    params = SignatureParams(
        algorithm="sha256-rsa", hash_alg="sha256", key=KeyParams(key_type="rsa", key_bits=1024)
    )
    findings = signature_findings(params)
    assert any(f.code == "T03" and f.severity.value == "high" for f in findings)


def test_bad_exponent_flagged() -> None:
    params = SignatureParams(
        algorithm="sha256-rsa",
        hash_alg="sha256",
        key=KeyParams(key_type="rsa", key_bits=2048, rsa_exponent=1),
    )
    findings = signature_findings(params)
    assert any(f.code == "T03" and f.severity.value == "critical" for f in findings)


def test_padding_downgrade_flagged() -> None:
    params = SignatureParams(
        algorithm="sha256-rsa-pkcs1v15",
        hash_alg="sha256",
        padding="pkcs1v15",
        key=KeyParams(key_type="rsa", key_bits=3072),
    )
    findings = signature_findings(params, policy_padding="pss")
    assert any(f.code == "T04" for f in findings)


def test_high_s_flagged() -> None:
    params = SignatureParams(algorithm="sha256-ecdsa", hash_alg="sha256", low_s=False)
    assert any(f.code == "T05" for f in signature_findings(params))


def test_healthy_signature_clean(demo_pki) -> None:
    params = SignatureParams(
        algorithm="sha256-ecdsa",
        hash_alg="sha256",
        key=KeyParams(key_type="ec", curve="secp256r1", key_bits=256),
        low_s=True,
        der_canonical=True,
    )
    assert signature_findings(params) == []


def test_weak_digest_certificate_flagged() -> None:
    info = _fake_cert_info(sig_algo="sha1WithRSAEncryption")
    assert any(f.code == "T02" for f in certificate_findings(info))


def test_weak_key_certificate_flagged(demo_pki) -> None:
    info = cert_info(demo_pki.leaves["weak-key-rsa1024"].cert)
    assert any(f.code == "T03" for f in certificate_findings(info))


def test_missing_eku_flagged(demo_pki) -> None:
    info = cert_info(demo_pki.leaves["healthy-ec"].cert)
    findings = certificate_findings(info, expected_eku="timeStamping")
    assert any(f.code == "T16" for f in findings)
