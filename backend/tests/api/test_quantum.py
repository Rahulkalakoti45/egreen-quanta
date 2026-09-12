"""API — quantum-inspired optimisation (Module 4)."""

from __future__ import annotations

import base64

import pytest
from app.models.user import User
from app.services.detection.engine import sync_rules
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _rules(db_session):
    await sync_rules(db_session)


async def _rsa_pub_pem(bits: int) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


async def test_qes_score_endpoint(client: AsyncClient, viewer: User) -> None:
    resp = await client.post(
        "/api/v1/quantum/pq-risk/score",
        headers=auth_headers(viewer),
        json={"algo": "rsa", "key_bits": 2048, "data_lifetime_years": 10, "exposure": "public"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["band"] in {"plan", "immediate"}
    assert body["algo_factor"] == 1.0

    pq = await client.post(
        "/api/v1/quantum/pq-risk/score",
        headers=auth_headers(viewer),
        json={"algo": "ml-dsa", "data_lifetime_years": 20},
    )
    assert pq.json()["qes"] == 0.0


async def test_migration_plan_endpoint_persists_run(client: AsyncClient, analyst: User) -> None:
    resp = await client.post(
        "/api/v1/quantum/pq-risk/plan",
        headers=auth_headers(analyst),
        json={
            "identities": [
                {"name": "signing-ca", "qes": 88, "criticality": 5, "effort": 3},
                {"name": "code-signer", "qes": 72, "criticality": 4, "effort": 2},
                {"name": "email-cert", "qes": 40, "criticality": 2, "effort": 1},
                {"name": "test-cert", "qes": 20, "criticality": 1, "effort": 1},
            ],
            "waves": 3,
            "seed": 7,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run_id"]
    assert len(body["waves"]) == 3
    assert body["improvement_pct"] >= 0

    runs = await client.get(
        "/api/v1/quantum/runs", headers=auth_headers(analyst), params={"run_type": "migration_plan"}
    )
    assert runs.json()["total"] == 1
    detail = await client.get(
        f"/api/v1/quantum/runs/{body['run_id']}", headers=auth_headers(analyst)
    )
    assert detail.status_code == 200
    assert detail.json()["result"]["total_waves"] == 3


async def test_viewer_cannot_run_planner(client: AsyncClient, viewer: User) -> None:
    resp = await client.post(
        "/api/v1/quantum/pq-risk/plan",
        headers=auth_headers(viewer),
        json={"identities": [{"name": "a", "qes": 50}], "waves": 2},
    )
    assert resp.status_code == 403


async def test_tuning_run_and_apply(client: AsyncClient, analyst: User, admin: User) -> None:
    run = await client.post(
        "/api/v1/quantum/tuning/run",
        headers=auth_headers(analyst),
        json={"synthetic": True, "seed": 7},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["source"] == "synthetic"
    assert body["after"]["f1"] >= body["before"]["f1"]

    applied = await client.post(
        "/api/v1/quantum/tuning/apply",
        headers=auth_headers(admin),
        json={"run_id": body["run_id"]},
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] >= 0

    # analyst cannot apply
    denied = await client.post(
        "/api/v1/quantum/tuning/apply",
        headers=auth_headers(analyst),
        json={"run_id": body["run_id"]},
    )
    assert denied.status_code == 403


async def test_portfolio_and_correlation_over_live_events(
    client: AsyncClient, analyst: User
) -> None:
    # create a few verification events by verifying bad signatures
    pub = await _rsa_pub_pem(2048)
    for i in range(4):
        msg = f"doc-{i}".encode()
        sig = base64.b64encode(b"\x00" * 32).decode()
        await client.post(
            "/api/v1/signatures/verify",
            headers=auth_headers(analyst),
            json={
                "data_b64": base64.b64encode(msg).decode(),
                "signature_b64": sig,
                "hash_alg": "sha256",
                "public_key_pem": pub,
            },
        )
    ec_key = ec.generate_private_key(ec.SECP256R1())
    for i in range(3):
        msg = f"ec-{i}".encode()
        s = bytearray(ec_key.sign(msg, ec.ECDSA(hashes.SHA256())))
        s[-1] ^= 1
        await client.post(
            "/api/v1/signatures/verify",
            headers=auth_headers(analyst),
            json={
                "data_b64": base64.b64encode(msg).decode(),
                "signature_b64": base64.b64encode(bytes(s)).decode(),
                "hash_alg": "sha256",
                "public_key_pem": ec_key.public_key()
                .public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                .decode(),
            },
        )

    portfolio = await client.post(
        "/api/v1/quantum/pq-risk/portfolio",
        headers=auth_headers(analyst),
        json={"lookback_days": 30, "data_lifetime_years": 10, "exposure": "public"},
    )
    assert portfolio.status_code == 200, portfolio.text
    assert portfolio.json()["scored"] >= 1
    assert portfolio.json()["mean_qes"] > 0

    corr = await client.post(
        "/api/v1/quantum/correlation/run",
        headers=auth_headers(analyst),
        json={"lookback_hours": 24, "seed": 7},
    )
    assert corr.status_code == 200, corr.text
    cbody = corr.json()
    assert cbody["event_count"] >= 5
    assert "qubo_modularity" in cbody and "baseline_modularity" in cbody
