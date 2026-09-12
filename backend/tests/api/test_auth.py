"""Module 1 — authentication flow: login, lockout, refresh rotation, reuse, TOTP, RBAC."""

from __future__ import annotations

import pyotp
import pytest
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import DEFAULT_PASSWORD, UserFactory, auth_headers

pytestmark = pytest.mark.asyncio


async def test_login_success_returns_tokens(client: AsyncClient, viewer: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["role"] == "viewer"
    assert client.cookies.get("egq_refresh")


async def test_login_wrong_password_401(client: AsyncClient, viewer: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": "not-the-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_user_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.local", "password": "whatever12345"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_account_locks_after_max_attempts(
    client: AsyncClient, db_session, viewer: User
) -> None:
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"email": viewer.email, "password": "wrong"},
        )
    # 6th attempt — even with the correct password — is rejected while locked.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "account_locked"
    refreshed = (await db_session.execute(select(User).where(User.id == viewer.id))).scalar_one()
    assert refreshed.locked_until is not None


async def test_me_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_me_returns_identity(client: AsyncClient, analyst: User) -> None:
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(analyst))
    assert resp.status_code == 200
    assert resp.json()["email"] == analyst.email
    assert resp.json()["role"] == "analyst"


async def test_refresh_rotates_and_old_token_is_burned(client: AsyncClient, viewer: User) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": DEFAULT_PASSWORD},
    )
    first_refresh = login.json()["refresh_token"]

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert r1.status_code == 200
    second_refresh = r1.json()["refresh_token"]
    assert second_refresh != first_refresh

    # Reusing the first (now rotated) refresh token is detected as theft.
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "refresh_reuse"

    # And the whole family is dead — the second token no longer works either.
    r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
    assert r3.status_code == 401


async def test_logout_revokes_refresh(client: AsyncClient, viewer: User) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": DEFAULT_PASSWORD},
    )
    refresh = login.json()["refresh_token"]
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401


async def test_totp_enrol_and_login(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(email="mfa@test.local")
    headers = auth_headers(user)

    enroll = await client.post("/api/v1/auth/totp/enroll", headers=headers)
    assert enroll.status_code == 200
    secret = enroll.json()["secret"]

    code = pyotp.TOTP(secret).now()
    verify = await client.post("/api/v1/auth/totp/verify", headers=headers, json={"code": code})
    assert verify.status_code == 200

    # Login now requires the code.
    no_code = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert no_code.status_code == 401
    assert no_code.json()["error"]["code"] == "mfa_required"

    with_code = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": DEFAULT_PASSWORD,
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )
    assert with_code.status_code == 200


async def test_inactive_user_cannot_use_valid_token(
    client: AsyncClient, make_user: UserFactory, db_session
) -> None:
    user = await make_user(email="soon-disabled@test.local")
    headers = auth_headers(user)
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200

    user.is_active = False
    await db_session.commit()

    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "account_disabled"
