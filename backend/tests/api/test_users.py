"""Module 1 — user administration + RBAC matrix."""

from __future__ import annotations

import pytest
from app.models.user import User
from httpx import AsyncClient

from tests.conftest import UserFactory, auth_headers

pytestmark = pytest.mark.asyncio


async def test_viewer_cannot_list_users(client: AsyncClient, viewer: User) -> None:
    resp = await client.get("/api/v1/users", headers=auth_headers(viewer))
    assert resp.status_code == 403


async def test_analyst_cannot_manage_users(client: AsyncClient, analyst: User) -> None:
    resp = await client.get("/api/v1/users", headers=auth_headers(analyst))
    assert resp.status_code == 403


async def test_admin_crud_user(client: AsyncClient, admin: User) -> None:
    h = auth_headers(admin)

    created = await client.post(
        "/api/v1/users",
        headers=h,
        json={
            "email": "new.analyst@test.local",
            "full_name": "New Analyst",
            "role": "analyst",
            "password": "a-strong-passphrase-1",
        },
    )
    assert created.status_code == 201, created.text
    uid = created.json()["id"]
    assert created.json()["role"] == "analyst"

    listed = await client.get("/api/v1/users", headers=h)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    patched = await client.patch(
        f"/api/v1/users/{uid}", headers=h, json={"role": "auditor", "is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "auditor"
    assert patched.json()["is_active"] is False

    deleted = await client.delete(f"/api/v1/users/{uid}", headers=h)
    assert deleted.status_code == 200
    assert (await client.get(f"/api/v1/users/{uid}", headers=h)).status_code == 404


async def test_duplicate_email_conflict(client: AsyncClient, admin: User) -> None:
    h = auth_headers(admin)
    payload = {
        "email": "dupe@test.local",
        "role": "viewer",
        "password": "a-strong-passphrase-1",
    }
    assert (await client.post("/api/v1/users", headers=h, json=payload)).status_code == 201
    dup = await client.post("/api/v1/users", headers=h, json=payload)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"


async def test_admin_cannot_delete_self(client: AsyncClient, admin: User) -> None:
    resp = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403


async def test_cannot_demote_last_admin(
    client: AsyncClient, admin: User, make_user: UserFactory
) -> None:
    resp = await client.patch(
        f"/api/v1/users/{admin.id}", headers=auth_headers(admin), json={"role": "viewer"}
    )
    assert resp.status_code == 409
    assert "administrator" in resp.json()["error"]["message"].lower()


async def test_weak_password_rejected(client: AsyncClient, admin: User) -> None:
    resp = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin),
        json={"email": "weak@test.local", "role": "viewer", "password": "short"},
    )
    assert resp.status_code == 422
