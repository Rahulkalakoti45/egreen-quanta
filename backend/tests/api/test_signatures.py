"""API — signature verification routes (Module 2)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from app.models.user import User
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient

from tests.conftest import auth_headers

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gen_test_pki import build_demo_pki  # noqa: E402

pytestmark = pytest.mark.asyncio
MSG = b"api verification payload"


@pytest.fixture(scope="module")
def pki():
    return build_demo_pki()


def _sign_ec(key, msg: bytes) -> bytes:
    return key.sign(msg, ec.ECDSA(hashes.SHA256()))


def _pub_pem(key) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


async def test_verify_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/signatures/verify", json={"data_b64": "", "signature_b64": ""}
    )
    assert resp.status_code == 401


async def test_verify_valid_signature(client: AsyncClient, viewer: User, pki) -> None:
    leaf = pki.leaves["healthy-ec"]
    sig = _sign_ec(leaf.key, MSG)
    resp = await client.post(
        "/api/v1/signatures/verify",
        headers=auth_headers(viewer),
        json={
            "data_b64": base64.b64encode(MSG).decode(),
            "signature_b64": base64.b64encode(sig).decode(),
            "hash_alg": "sha256",
            "public_key_pem": _pub_pem(leaf.key),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "valid"
    assert body["signature"]["algorithm"] == "sha256-ecdsa"


async def test_verify_forged_signature(client: AsyncClient, viewer: User, pki) -> None:
    leaf = pki.leaves["healthy-ec"]
    sig = bytearray(_sign_ec(leaf.key, MSG))
    sig[-1] ^= 0x01
    resp = await client.post(
        "/api/v1/signatures/verify",
        headers=auth_headers(viewer),
        json={
            "data_b64": base64.b64encode(MSG).decode(),
            "signature_b64": base64.b64encode(bytes(sig)).decode(),
            "hash_alg": "sha256",
            "certificate_pem": pki.chain_pem("healthy-ec"),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "invalid"
    assert any(f["code"] == "T01" for f in body["findings"])
