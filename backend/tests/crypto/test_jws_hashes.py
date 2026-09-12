"""JWS compact verification + hash helpers."""

from __future__ import annotations

import base64
import json

import jwt
import pytest
from app.services.crypto.errors import UnsupportedAlgorithmError
from app.services.crypto.hashes import digest, is_weak_hash, normalize_hash_name
from app.services.crypto.jws import verify_compact


def test_hash_normalisation() -> None:
    assert normalize_hash_name("SHA-256") == "sha256"
    assert normalize_hash_name("sha3_256") == "sha3-256"
    with pytest.raises(UnsupportedAlgorithmError):
        normalize_hash_name("whirlpool")


def test_weak_hash_registry() -> None:
    assert is_weak_hash("md5")
    assert is_weak_hash("sha1")
    assert not is_weak_hash("sha256")


def test_digest_known_vector() -> None:
    # SHA-256("abc")
    assert digest(b"abc", "sha256").hex() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_jws_roundtrip(demo_pki) -> None:
    key = demo_pki.leaves["healthy-ec"].key
    token = jwt.encode({"sub": "svc-42", "scope": "sign"}, key, algorithm="ES256")
    out = verify_compact(token, key.public_key())
    assert out.verified
    assert json.loads(out.payload)["sub"] == "svc-42"


def test_jws_tampered_payload_fails(demo_pki) -> None:
    key = demo_pki.leaves["healthy-ec"].key
    token = jwt.encode({"sub": "svc-42"}, key, algorithm="ES256")
    head, _payload, sig = token.split(".")
    forged = ".".join(
        [head, base64.urlsafe_b64encode(b'{"sub":"admin"}').rstrip(b"=").decode(), sig]
    )
    out = verify_compact(forged, key.public_key())
    assert not out.verified


def test_jws_alg_none_rejected(demo_pki) -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(b'{"sub":"x"}').rstrip(b"=").decode()
    out = verify_compact(f"{header}.{body}.", demo_pki.leaves["healthy-ec"].key.public_key())
    assert not out.verified
    assert "none" in (out.error or "")
