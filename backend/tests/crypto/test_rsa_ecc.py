"""Raw signature verification: RSA-PSS/PKCS1v15, ECDSA, EdDSA + malleability."""

from __future__ import annotations

from app.services.crypto.rsa_ecc import verify_raw
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from tests.crypto.conftest import sign_message

MSG = b"egreen-quanta verification vector"


def test_rsa_pss_roundtrip(demo_pki) -> None:
    key = demo_pki.leaves["healthy-rsa"].key
    sig = sign_message(key, MSG, rsa_padding="pss")
    out = verify_raw(
        public_key=key.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=sig,
        padding_mode="pss",
    )
    assert out.verified
    assert out.params.algorithm == "sha256-rsa-pss"
    assert out.params.key.key_type == "rsa"


def test_rsa_pkcs1v15_roundtrip(demo_pki) -> None:
    key = demo_pki.leaves["healthy-rsa"].key
    sig = sign_message(key, MSG, rsa_padding="pkcs1v15")
    out = verify_raw(
        public_key=key.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=sig,
        padding_mode="pkcs1v15",
    )
    assert out.verified
    assert out.params.padding == "pkcs1v15"


def test_rsa_wrong_padding_fails(demo_pki) -> None:
    key = demo_pki.leaves["healthy-rsa"].key
    sig = sign_message(key, MSG, rsa_padding="pss")
    out = verify_raw(
        public_key=key.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=sig,
        padding_mode="pkcs1v15",
    )
    assert not out.verified


def test_tampered_message_fails(demo_pki) -> None:
    key = demo_pki.leaves["healthy-rsa"].key
    sig = sign_message(key, MSG)
    out = verify_raw(
        public_key=key.public_key(),
        message=MSG + b"x",
        hash_alg="sha256",
        signature=sig,
        padding_mode="pss",
    )
    assert not out.verified


def test_wrong_key_fails(demo_pki) -> None:
    signer = demo_pki.leaves["healthy-rsa"].key
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sig = sign_message(signer, MSG)
    out = verify_raw(
        public_key=other.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=sig,
        padding_mode="pss",
    )
    assert not out.verified


def test_ecdsa_roundtrip(demo_pki) -> None:
    key = demo_pki.leaves["healthy-ec"].key
    sig = sign_message(key, MSG)
    out = verify_raw(public_key=key.public_key(), message=MSG, hash_alg="sha256", signature=sig)
    assert out.verified
    assert out.params.algorithm == "sha256-ecdsa"
    assert out.params.low_s in (True, False)  # computed either way
    assert out.params.der_canonical is True


def test_ecdsa_low_s_detector(demo_pki) -> None:
    """The malleability detector must classify low-S vs high-S correctly (T05)."""
    key = demo_pki.leaves["healthy-ec"].key
    sig = sign_message(key, MSG)
    r, s = decode_dss_signature(sig)
    order = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)
    s_low, s_high = min(s, order - s), max(s, order - s)

    low = verify_raw(
        public_key=key.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=encode_dss_signature(r, s_low),
    )
    high = verify_raw(
        public_key=key.public_key(),
        message=MSG,
        hash_alg="sha256",
        signature=encode_dss_signature(r, s_high),
    )
    assert low.params.low_s is True
    assert high.params.low_s is False


def test_ed25519_roundtrip(demo_pki) -> None:
    key = demo_pki.leaves["healthy-ed25519"].key
    sig = sign_message(key, MSG)
    out = verify_raw(public_key=key.public_key(), message=MSG, hash_alg=None, signature=sig)
    assert out.verified
    assert out.params.algorithm == "ed25519"


def test_ed25519_tampered_fails(demo_pki) -> None:
    key = demo_pki.leaves["healthy-ed25519"].key
    sig = bytearray(sign_message(key, MSG))
    sig[0] ^= 0x01
    out = verify_raw(public_key=key.public_key(), message=MSG, hash_alg=None, signature=bytes(sig))
    assert not out.verified
