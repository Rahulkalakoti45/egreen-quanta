"""API — detection rules, alerts, incidents, stats (Module 3)."""

from __future__ import annotations

import base64

import pytest
from app.models.user import User
from app.services.detection.engine import sync_rules
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio
MSG = b"threat-api payload"


@pytest.fixture(autouse=True)
async def _rules(db_session):
    await sync_rules(db_session)


async def _verify_forged(client: AsyncClient, user: User, pki) -> dict:
    leaf = pki.leaves["healthy-ec"]
    sig = bytearray(leaf.key.sign(MSG, ec.ECDSA(hashes.SHA256())))
    sig[-1] ^= 0x01
    resp = await client.post(
        "/api/v1/signatures/verify",
        headers=auth_headers(user),
        json={
            "data_b64": base64.b64encode(MSG).decode(),
            "signature_b64": base64.b64encode(bytes(sig)).decode(),
            "hash_alg": "sha256",
            "public_key_pem": leaf.key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode(),
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_rules_listed_and_patchable(
    client: AsyncClient, admin: User, analyst: User, viewer: User
) -> None:
    rules = await client.get("/api/v1/detections/rules", headers=auth_headers(admin))
    assert rules.status_code == 200
    codes = {r["code"] for r in rules.json()}
    assert {"T01", "T14", "T15"} <= codes

    patched = await client.patch(
        "/api/v1/detections/rules/T05",
        headers=auth_headers(analyst),
        json={"enabled": False, "weight": 0.2},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["weight"] == 0.2

    denied = await client.patch(
        "/api/v1/detections/rules/T05",
        headers=auth_headers(viewer),
        json={"enabled": True},
    )
    assert denied.status_code == 403


async def test_forged_verification_creates_alert(
    client: AsyncClient, analyst: User, viewer: User, demo_pki
) -> None:
    body = await _verify_forged(client, viewer, demo_pki)
    assert body["verdict"] == "invalid"
    assert body["risk_score"] > 0
    assert body["alert_id"]

    alerts = await client.get("/api/v1/threats/alerts", headers=auth_headers(viewer))
    assert alerts.status_code == 200
    assert alerts.json()["total"] >= 1
    alert = alerts.json()["items"][0]
    assert alert["severity"] == "critical"
    assert "T01" in alert["rule_codes"]

    # triage it
    patched = await client.patch(
        f"/api/v1/threats/alerts/{alert['id']}",
        headers=auth_headers(analyst),
        json={"status": "triaged", "note": "confirmed forgery attempt"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "triaged"
    assert patched.json()["triaged_by"] == analyst.id

    # viewer cannot triage
    denied = await client.patch(
        f"/api/v1/threats/alerts/{alert['id']}",
        headers=auth_headers(viewer),
        json={"status": "closed"},
    )
    assert denied.status_code == 403


async def test_incident_grouping_and_stats(client: AsyncClient, viewer: User, demo_pki) -> None:
    await _verify_forged(client, viewer, demo_pki)
    await _verify_forged(client, viewer, demo_pki)

    incidents = await client.get("/api/v1/threats/incidents", headers=auth_headers(viewer))
    assert incidents.status_code == 200
    assert incidents.json()["total"] == 1
    inc = incidents.json()["items"][0]
    assert inc["alert_count"] == 2

    detail = await client.get(
        f"/api/v1/threats/incidents/{inc['id']}", headers=auth_headers(viewer)
    )
    assert detail.status_code == 200
    assert len(detail.json()["alerts"]) == 2

    stats = await client.get("/api/v1/threats/stats", headers=auth_headers(viewer))
    assert stats.status_code == 200
    s = stats.json()
    assert s["events_total"] >= 2
    assert s["invalid_24h"] >= 2
    assert s["open_alerts"] >= 1
