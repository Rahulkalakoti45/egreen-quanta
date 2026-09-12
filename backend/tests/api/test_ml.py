"""API — ML anomaly detection (Module 5)."""

from __future__ import annotations

import base64

import pytest
from app.core.config import settings
from app.models.user import User
from app.services.detection.engine import sync_rules
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _rules(db_session):
    await sync_rules(db_session)


async def test_status_disabled_by_default(client: AsyncClient, viewer: User) -> None:
    resp = await client.get("/api/v1/ml/status", headers=auth_headers(viewer))
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["active_model_id"] is None
    assert body["feature_count"] > 20


async def test_score_rejected_when_disabled(client: AsyncClient, analyst: User) -> None:
    resp = await client.post(
        "/api/v1/ml/score", headers=auth_headers(analyst), json={"event_id": "x"}
    )
    assert resp.status_code == 422
    assert "disabled" in resp.json()["error"]["message"].lower()


async def test_train_activate_and_score(
    client: AsyncClient, analyst: User, admin: User, viewer: User, monkeypatch
) -> None:
    train = await client.post(
        "/api/v1/ml/train",
        headers=auth_headers(analyst),
        json={"algo": "isolation_forest", "source": "dataset", "contamination": 0.08},
    )
    assert train.status_code == 200, train.text
    model = train.json()
    assert model["n_train"] >= 100
    assert model["feature_schema_version"] == 1
    assert model["is_active"] is False
    assert "eval_recall" in model["metrics"]

    assert len((await client.get("/api/v1/ml/models", headers=auth_headers(viewer))).json()) == 1

    # analyst cannot activate; admin can
    assert (
        await client.post(
            f"/api/v1/ml/models/{model['id']}/activate", headers=auth_headers(analyst)
        )
    ).status_code == 403
    activated = await client.post(
        f"/api/v1/ml/models/{model['id']}/activate", headers=auth_headers(admin)
    )
    assert activated.status_code == 200 and activated.json()["is_active"] is True

    status = await client.get("/api/v1/ml/status", headers=auth_headers(viewer))
    assert status.json()["active_model_id"] == model["id"]

    # enable ML, run a verification (which now also ML-scores), then /score it
    monkeypatch.setattr(settings, "ml_enabled", True)
    key = ec.generate_private_key(ec.SECP256R1())
    msg = b"ml-api-doc"
    sig = key.sign(msg, ec.ECDSA(hashes.SHA256()))
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    verify = await client.post(
        "/api/v1/signatures/verify",
        headers=auth_headers(analyst),
        json={
            "data_b64": base64.b64encode(msg).decode(),
            "signature_b64": base64.b64encode(sig).decode(),
            "hash_alg": "sha256",
            "public_key_pem": pub,
        },
    )
    assert verify.status_code == 200
    event_id = verify.json()["event_id"]

    scored = await client.post(
        "/api/v1/ml/score", headers=auth_headers(analyst), json={"event_id": event_id}
    )
    assert scored.status_code == 200, scored.text
    body = scored.json()
    assert 0.0 <= body["anomaly_score"] <= 1.0
    assert body["model_id"] == model["id"]


async def test_deactivate_all(client: AsyncClient, analyst: User, admin: User) -> None:
    train = await client.post(
        "/api/v1/ml/train",
        headers=auth_headers(analyst),
        json={"source": "dataset"},
    )
    mid = train.json()["id"]
    await client.post(f"/api/v1/ml/models/{mid}/activate", headers=auth_headers(admin))
    off = await client.post("/api/v1/ml/models/deactivate", headers=auth_headers(admin))
    assert off.status_code == 200
    status = await client.get("/api/v1/ml/status", headers=auth_headers(admin))
    assert status.json()["active_model_id"] is None
