"""Raw signature verification for RSA, ECDSA and EdDSA, plus malleability checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)

from app.services.crypto.errors import UnsupportedAlgorithmError
from app.services.crypto.hashes import cryptography_hash, normalize_hash_name
from app.services.crypto.types import KeyParams, SignatureParams
from app.services.crypto.x509_utils import key_params

# Curve name -> order n (for ECDSA low-S / malleability checks).
_CURVE_ORDER: dict[str, int] = {
    "secp256r1": 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551,
    "secp384r1": (0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF << 192)
    | 0x581A0DB248B0A77AECEC196ACCC52973,
    "secp521r1": (0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFA << 256)
    | 0x51868783BF2F966B7FCC0148F709A5D03BB5C9B8899C47AEBB6FB71E91386409,
    "secp256k1": 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141,
}


@dataclass(slots=True)
class RawVerifyOutcome:
    verified: bool
    params: SignatureParams
    error: str | None = None


def _ec_order(curve_name: str) -> int | None:
    return _CURVE_ORDER.get(curve_name)


def _check_ecdsa_malleability(signature: bytes, curve_name: str) -> tuple[bool | None, bool | None]:
    """Return (low_s, der_canonical)."""
    order = _ec_order(curve_name)
    try:
        r, s = decode_dss_signature(signature)
    except ValueError:
        return None, False
    der_canonical = encode_dss_signature(r, s) == signature
    if order is None:
        return None, der_canonical
    return (s <= order // 2), der_canonical


def verify_raw(
    *,
    public_key,
    message: bytes | None = None,
    prehashed_digest: bytes | None = None,
    hash_alg: str | None,
    signature: bytes,
    padding_mode: str | None = None,
) -> RawVerifyOutcome:
    """Verify a detached signature.

    Exactly one of ``message`` / ``prehashed_digest`` must be given (EdDSA ignores
    ``hash_alg`` and requires ``message``).
    """
    kp: KeyParams = key_params(public_key)

    # ---- EdDSA -------------------------------------------------------------
    if isinstance(public_key, ed25519.Ed25519PublicKey | ed448.Ed448PublicKey):
        params = SignatureParams(
            algorithm="ed25519" if kp.key_type == "ed25519" else "ed448",
            hash_alg=None,
            padding=None,
            key=kp,
        )
        if message is None:
            return RawVerifyOutcome(False, params, "EdDSA requires the full message")
        try:
            public_key.verify(signature, message)
            return RawVerifyOutcome(True, params)
        except InvalidSignature:
            return RawVerifyOutcome(False, params, "signature does not verify")

    if hash_alg is None:
        raise UnsupportedAlgorithmError("hash_alg is required for RSA/ECDSA verification")
    hash_norm = normalize_hash_name(hash_alg)
    halg = cryptography_hash(hash_norm)

    algo_hash: Any
    if message is not None:
        signed: bytes = message
        algo_hash = halg
    elif prehashed_digest is not None:
        signed = prehashed_digest
        algo_hash = Prehashed(halg)
    else:
        raise UnsupportedAlgorithmError("message or prehashed_digest must be supplied")

    # ---- RSA -------------------------------------------------------------
    if isinstance(public_key, rsa.RSAPublicKey):
        mode = (padding_mode or "pkcs1v15").lower()
        pad: Any
        if mode in {"pss", "rsa-pss", "rsassa-pss"}:
            pad = padding.PSS(mgf=padding.MGF1(halg), salt_length=padding.PSS.DIGEST_LENGTH)
            pad_label = "pss"
        elif mode in {"pkcs1v15", "pkcs1", "rsa", "rsassa-pkcs1-v1_5"}:
            pad = padding.PKCS1v15()
            pad_label = "pkcs1v15"
        else:
            raise UnsupportedAlgorithmError(f"Unknown RSA padding: {padding_mode}")
        params = SignatureParams(
            algorithm=f"{hash_norm}-rsa-{pad_label}", hash_alg=hash_norm, padding=pad_label, key=kp
        )
        try:
            public_key.verify(signature, signed, pad, algo_hash)
            return RawVerifyOutcome(True, params)
        except InvalidSignature:
            return RawVerifyOutcome(False, params, "signature does not verify")

    # ---- ECDSA --------------------------------------------------------------
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        low_s, der_canonical = _check_ecdsa_malleability(signature, kp.curve or "")
        params = SignatureParams(
            algorithm=f"{hash_norm}-ecdsa",
            hash_alg=hash_norm,
            padding=None,
            key=kp,
            low_s=low_s,
            der_canonical=der_canonical,
        )
        try:
            public_key.verify(signature, signed, ec.ECDSA(algo_hash))
            return RawVerifyOutcome(True, params)
        except InvalidSignature:
            return RawVerifyOutcome(False, params, "signature does not verify")

    raise UnsupportedAlgorithmError(f"Unsupported public key type: {type(public_key).__name__}")
