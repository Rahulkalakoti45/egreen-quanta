"""Module 1 — API-key lifecycle + verification."""

from __future__ import annotations

import pytest
from app.models.enums import ApiKeyScope
from app.models.user import User
from app.services.api_keys import verify_api_key
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_viewer_cannot_create_api_key(client: AsyncClient, viewer: User) -> None:
    resp = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers(viewer),
        json={"name": "ci", "scopes": ["ingest:events"]},
    )
    assert resp.status_code == 403


async def test_analyst_creates_lists_revokes_key(
    client: AsyncClient, analyst: User, db_session
) -> None:
    h = auth_headers(analyst)

    created = await client.post(
        "/api/v1/api-keys",
        headers=h,
        json={"name": "pipeline", "scopes": ["ingest:events", "ingest:signatures"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    full_key = body["api_key"]
    assert full_key.startswith("egq_")
    assert set(body["scopes"]) == {"ingest:events", "ingest:signatures"}

    # The plaintext verifies against the stored hash + scope.
    record = await verify_api_key(db_session, full_key, required_scope=ApiKeyScope.INGEST_EVENTS)
    assert record.name == "pipeline"

    listed = await client.get("/api/v1/api-keys", headers=h)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert "api_key" not in listed.json()["items"][0]  # never returned again

    key_id = body["id"]
    assert (await client.delete(f"/api/v1/api-keys/{key_id}", headers=h)).status_code == 200

    with pytest.raises(Exception):  # noqa: B017 - AuthError after revocation
        await verify_api_key(db_session, full_key, required_scope=ApiKeyScope.INGEST_EVENTS)


async def test_api_key_scope_enforced(client: AsyncClient, analyst: User, db_session) -> None:
    created = await client.post(
        "/api/v1/api-keys",
        headers=auth_headers(analyst),
        json={"name": "events-only", "scopes": ["ingest:events"]},
    )
    full_key = created.json()["api_key"]
    with pytest.raises(Exception):  # noqa: B017 - ForbiddenError: missing scope
        await verify_api_key(db_session, full_key, required_scope=ApiKeyScope.INGEST_SIGNATURES)
