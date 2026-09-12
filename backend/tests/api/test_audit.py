"""API — audit log browsing / verification / export (Module 6)."""

from __future__ import annotations

import json

import pytest
from app.models.user import User
from app.services.audit import chain
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _seed_audit(db_session):
    for i in range(8):
        await chain.record(
            db_session,
            action=f"test.action.{i % 2}",
            actor_id="actor-x" if i % 2 else None,
            actor_type="user" if i % 2 else "system",
            target_type="obj",
            target_id=str(i),
            meta={"i": i},
        )


async def test_viewer_cannot_read_audit(client: AsyncClient, viewer: User) -> None:
    assert (await client.get("/api/v1/audit", headers=auth_headers(viewer))).status_code == 403


async def test_auditor_lists_and_filters(client: AsyncClient, auditor: User) -> None:
    resp = await client.get("/api/v1/audit", headers=auth_headers(auditor))
    assert resp.status_code == 200
    assert resp.json()["total"] == 8
    assert resp.json()["items"][0]["seq"] == 8  # newest first

    filtered = await client.get(
        "/api/v1/audit", headers=auth_headers(auditor), params={"actor_id": "actor-x"}
    )
    assert filtered.json()["total"] == 4

    by_action = await client.get(
        "/api/v1/audit", headers=auth_headers(auditor), params={"action": "test.action.1"}
    )
    assert by_action.json()["total"] == 4


async def test_verify_ok_then_broken(client: AsyncClient, auditor: User, db_session) -> None:
    ok = await client.get("/api/v1/audit/verify", headers=auth_headers(auditor))
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    assert ok.json()["checked"] == 8

    # tamper
    from app.models.audit import AuditLog
    from sqlalchemy import select

    row = (await db_session.execute(select(AuditLog).where(AuditLog.seq == 4))).scalar_one()
    row.action = "tampered"
    await db_session.commit()

    broken = await client.get("/api/v1/audit/verify", headers=auth_headers(auditor))
    assert broken.json()["ok"] is False
    assert broken.json()["break_at"] == 4


async def test_export_is_wellformed(client: AsyncClient, auditor: User) -> None:
    resp = await client.get("/api/v1/audit/export", headers=auth_headers(auditor))
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment")
    payload = json.loads(resp.text)
    assert len(payload["rows"]) == 8
    assert payload["genesis_hash"] == "0" * 64


async def test_admin_creates_anchor(client: AsyncClient, admin: User) -> None:
    resp = await client.post("/api/v1/audit/anchor", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["head_seq"] == 8
    assert resp.json()["signed"] is False  # no signing key in tests
