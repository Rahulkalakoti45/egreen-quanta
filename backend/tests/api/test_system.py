"""Module 0 — system endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_checks_db(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"


async def test_system_info(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Egreen Quanta"
    assert body["environment"] == "test"
    assert body["ml_enabled"] is False


async def test_request_id_echoed(client: AsyncClient) -> None:
    resp = await client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert resp.headers.get("x-request-id") == "abc-123"


async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    # CSP/HSTS are prod-only (they break the Vite dev server); not expected in tests.
    assert "Content-Security-Policy" not in resp.headers


async def test_oversized_request_body_rejected(client: AsyncClient) -> None:
    # BodySizeLimitMiddleware short-circuits on an oversized Content-Length header
    # before routing or auth run, so any path exercises it.
    resp = await client.post(
        "/api/v1/auth/login",
        headers={"content-length": str(500 * 1024 * 1024)},
        content=b"{}",
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"
