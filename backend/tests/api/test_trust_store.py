"""API — trust-store administration (Module 2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app.models.user import User
from httpx import AsyncClient

from tests.conftest import auth_headers

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gen_test_pki import build_demo_pki  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def pki():
    return build_demo_pki()


async def test_viewer_cannot_add_anchor(client: AsyncClient, viewer: User, pki) -> None:
    resp = await client.post(
        "/api/v1/trust-store/anchors",
        headers=auth_headers(viewer),
        json={"name": "root", "certificate_pem": pki.root.cert_pem},
    )
    assert resp.status_code == 403


async def test_admin_anchor_lifecycle(client: AsyncClient, admin: User, analyst: User, pki) -> None:
    add = await client.post(
        "/api/v1/trust-store/anchors",
        headers=auth_headers(admin),
        json={"name": "Demo Root", "certificate_pem": pki.root.cert_pem},
    )
    assert add.status_code == 201, add.text
    anchor_id = add.json()["id"]
    assert add.json()["enabled"] is True

    # analyst may read
    listed = await client.get("/api/v1/trust-store/anchors", headers=auth_headers(analyst))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # duplicate rejected
    dup = await client.post(
        "/api/v1/trust-store/anchors",
        headers=auth_headers(admin),
        json={"name": "again", "certificate_pem": pki.root.cert_pem},
    )
    assert dup.status_code == 409

    disabled = await client.patch(
        f"/api/v1/trust-store/anchors/{anchor_id}",
        headers=auth_headers(admin),
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    gone = await client.delete(
        f"/api/v1/trust-store/anchors/{anchor_id}", headers=auth_headers(admin)
    )
    assert gone.status_code == 200


async def test_certificate_validate_endpoint(client: AsyncClient, admin: User, pki) -> None:
    await client.post(
        "/api/v1/trust-store/anchors",
        headers=auth_headers(admin),
        json={"name": "Demo Root", "certificate_pem": pki.root.cert_pem},
    )
    resp = await client.post(
        "/api/v1/certificates/validate",
        headers=auth_headers(admin),
        json={"certificate_pem": pki.chain_pem("healthy-rsa")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "valid"
    assert body["chain"]["status"] == "trusted"

    expired = await client.post(
        "/api/v1/certificates/validate",
        headers=auth_headers(admin),
        json={"certificate_pem": pki.chain_pem("expired")},
    )
    assert expired.status_code == 200
    ebody = expired.json()
    assert ebody["verdict"] == "invalid"
    assert any(f["code"] == "T08" for f in ebody["findings"])
