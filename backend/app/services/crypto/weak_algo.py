"""Map extracted signature / certificate parameters to threat findings.

Covers threat-model IDs T02-T05, T16 (see docs/ARCHITECTURE.md section 2.3).
"""

from __future__ import annotations

from app.services.crypto.hashes import is_weak_hash
from app.services.crypto.types import (
    CertInfo,
    CryptoFinding,
    FindingCategory,
    Severity,
    SignatureParams,
)

_STRONG_CURVES = {"secp256r1", "secp384r1", "secp521r1", "secp256k1"}
_RSA_MIN_BITS = 2048
_RSA_RECOMMENDED_BITS = 3072


def signature_findings(
    params: SignatureParams, *, policy_padding: str | None = None
) -> list[CryptoFinding]:
    out: list[CryptoFinding] = []

    if params.hash_alg and is_weak_hash(params.hash_alg):
        out.append(
            CryptoFinding(
                code="T02",
                title="Weak digest algorithm",
                severity=Severity.HIGH,
                category=FindingCategory.WEAK_CRYPTO,
                detail=f"Signature digest {params.hash_alg} is collision-broken or deprecated.",
            )
        )

    key = params.key
    if key:
        if key.key_type == "rsa":
            if key.key_bits and key.key_bits < _RSA_MIN_BITS:
                out.append(
                    CryptoFinding(
                        code="T03",
                        title="Undersized RSA key",
                        severity=Severity.HIGH,
                        category=FindingCategory.WEAK_CRYPTO,
                        detail=f"RSA-{key.key_bits} is below the {_RSA_MIN_BITS}-bit minimum.",
                    )
                )
            elif key.key_bits and key.key_bits < _RSA_RECOMMENDED_BITS:
                out.append(
                    CryptoFinding(
                        code="T03",
                        title="RSA key below recommended size",
                        severity=Severity.LOW,
                        category=FindingCategory.WEAK_CRYPTO,
                        detail=f"RSA-{key.key_bits}; {_RSA_RECOMMENDED_BITS}-bit is recommended.",
                    )
                )
            if key.rsa_exponent is not None and key.rsa_exponent < 3:
                out.append(
                    CryptoFinding(
                        code="T03",
                        title="Dangerous RSA public exponent",
                        severity=Severity.CRITICAL,
                        category=FindingCategory.WEAK_CRYPTO,
                        detail=f"RSA public exponent e={key.rsa_exponent}.",
                    )
                )
        elif key.key_type == "dsa":
            out.append(
                CryptoFinding(
                    code="T03",
                    title="DSA signature",
                    severity=Severity.HIGH,
                    category=FindingCategory.WEAK_CRYPTO,
                    detail="DSA is deprecated for new signatures.",
                )
            )
        elif key.key_type == "ec" and key.curve and key.curve not in _STRONG_CURVES:
            out.append(
                CryptoFinding(
                    code="T03",
                    title="Non-standard or weak elliptic curve",
                    severity=Severity.MEDIUM,
                    category=FindingCategory.WEAK_CRYPTO,
                    detail=f"Curve {key.curve} is not in the approved set.",
                )
            )

    if params.padding == "pkcs1v15" and policy_padding == "pss":
        out.append(
            CryptoFinding(
                code="T04",
                title="RSA padding downgrade",
                severity=Severity.MEDIUM,
                category=FindingCategory.POLICY,
                detail="PKCS#1 v1.5 padding used where policy requires RSA-PSS.",
            )
        )

    if params.low_s is False:
        out.append(
            CryptoFinding(
                code="T05",
                title="Malleable ECDSA signature (high-S)",
                severity=Severity.LOW,
                category=FindingCategory.FORGERY,
                detail="ECDSA signature is not in canonical low-S form; a third party can "
                "produce a second valid encoding of the same signature.",
            )
        )
    if params.der_canonical is False:
        out.append(
            CryptoFinding(
                code="T05",
                title="Non-canonical DER encoding",
                severity=Severity.MEDIUM,
                category=FindingCategory.FORGERY,
                detail="Signature DER encoding is not canonical.",
            )
        )

    return out


def certificate_findings(info: CertInfo, *, expected_eku: str | None = None) -> list[CryptoFinding]:
    out: list[CryptoFinding] = []

    if is_weak_hash(_hash_from_sig_algo(info.sig_algo)):
        out.append(
            CryptoFinding(
                code="T02",
                title="Certificate signed with a weak digest",
                severity=Severity.HIGH,
                category=FindingCategory.WEAK_CRYPTO,
                detail=f"Certificate signature algorithm: {info.sig_algo}.",
            )
        )

    key = info.key
    if key.key_type == "rsa" and key.key_bits and key.key_bits < _RSA_MIN_BITS:
        out.append(
            CryptoFinding(
                code="T03",
                title="Certificate uses an undersized RSA key",
                severity=Severity.HIGH,
                category=FindingCategory.WEAK_CRYPTO,
                detail=f"RSA-{key.key_bits} in {info.subject}.",
            )
        )
    if key.key_type == "ec" and key.curve and key.curve not in _STRONG_CURVES:
        out.append(
            CryptoFinding(
                code="T03",
                title="Certificate uses a weak elliptic curve",
                severity=Severity.MEDIUM,
                category=FindingCategory.WEAK_CRYPTO,
                detail=f"Curve {key.curve} in {info.subject}.",
            )
        )

    if expected_eku and info.ext_key_usage and expected_eku not in info.ext_key_usage:
        out.append(
            CryptoFinding(
                code="T16",
                title="Certificate lacks the required extended key usage",
                severity=Severity.HIGH,
                category=FindingCategory.POLICY,
                detail=f"Expected EKU '{expected_eku}', certificate has {info.ext_key_usage}.",
            )
        )

    return out


def _hash_from_sig_algo(sig_algo: str) -> str:
    s = sig_algo.lower()
    for name in ("sha512", "sha384", "sha256", "sha224", "sha1", "md5"):
        if name in s:
            return name
    return "sha256"
