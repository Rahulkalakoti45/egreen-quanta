"""Machine-ingest API (Module 8)."""

from __future__ import annotations

import base64

import pytest
from app.models.enums import ApiKeyScope
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.services.api_keys import create_api_key
from app.services.detection.engine import sync_rules
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _rules(db_session):
    await sync_rules(db_session)


async def _key(db_session, analyst: User, *scopes: ApiKeyScope) -> str:
    _, full = await create_api_key(
        db_session, ApiKeyCreate(name="ingest", scopes=list(scopes)), created_by=analyst
    )
    return full


async def test_ingest_signatures_requires_key(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ingest/signatures", json={"data_b64": "", "signature_b64": ""}
    )
    assert resp.status_code == 401


async def test_ingest_signature_creates_event(
    client: AsyncClient, analyst: User, db_session
) -> None:
    key = await _key(db_session, analyst, ApiKeyScope.INGEST_SIGNATURES)
    priv = ec.generate_private_key(ec.SECP256R1())
    msg = b"ingest-doc"
    sig = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
    pub = (
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    resp = await client.post(
        "/api/v1/ingest/signatures",
        headers={"X-API-Key": key},
        json={
            "data_b64": base64.b64encode(msg).decode(),
            "signature_b64": base64.b64encode(sig).decode(),
            "hash_alg": "sha256",
            "public_key_pem": pub,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "valid"
    assert resp.json()["event_id"]


async def test_ingest_wrong_scope_rejected(client: AsyncClient, analyst: User, db_session) -> None:
    key = await _key(db_session, analyst, ApiKeyScope.INGEST_EVENTS)  # not signatures
    resp = await client.post(
        "/api/v1/ingest/signatures",
        headers={"X-API-Key": key},
        json={
            "data_b64": "AA==",
            "signature_b64": "AA==",
            "hash_alg": "sha256",
            "public_key_pem": "x",
        },
    )
    assert resp.status_code == 403


async def test_ingest_prebuilt_event_raises_alert(
    client: AsyncClient, analyst: User, db_session
) -> None:
    key = await _key(db_session, analyst, ApiKeyScope.INGEST_EVENTS)
    resp = await client.post(
        "/api/v1/ingest/events",
        headers={"X-API-Key": key},
        json={
            "verdict": "invalid",
            "envelope": "cms",
            "algorithm": "sha256-rsa",
            "key_type": "rsa",
            "key_bits": 2048,
            "findings": [
                {
                    "code": "T01",
                    "title": "Signature does not verify",
                    "severity": "critical",
                    "category": "forgery",
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "invalid"
    assert body["risk_score"] > 0
    assert body["alert_id"]
