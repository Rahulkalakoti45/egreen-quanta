"""Fixtures for the cryptographic-core tests: a reusable in-memory demo PKI."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gen_test_pki import DemoPKI, build_demo_pki  # noqa: E402


@pytest.fixture(scope="session")
def demo_pki() -> DemoPKI:
    return build_demo_pki()


def sign_message(
    key, message: bytes, *, hash_name: str = "sha256", rsa_padding: str = "pss"
) -> bytes:
    halg = {
        "sha256": hashes.SHA256(),
        "sha384": hashes.SHA384(),
        "sha512": hashes.SHA512(),
        "sha1": hashes.SHA1(),
    }[hash_name]
    if isinstance(key, rsa.RSAPrivateKey):
        if rsa_padding == "pss":
            pad = padding.PSS(mgf=padding.MGF1(halg), salt_length=padding.PSS.DIGEST_LENGTH)
        else:
            pad = padding.PKCS1v15()
        return key.sign(message, pad, halg)
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return key.sign(message, ec.ECDSA(halg))
    if isinstance(key, ed25519.Ed25519PrivateKey):
        return key.sign(message)
    raise TypeError(f"unsupported key type {type(key)}")


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def pem_public_key(key) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
