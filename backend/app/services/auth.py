"""Authentication service: credential checks, lockout, token issue/rotation."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_ip,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
    verify_totp,
)
from app.db.base import new_uuid
from app.models.login_attempt import LoginAttempt
from app.models.refresh_token import RefreshToken
from app.models.user import User

log = get_logger("egreen.auth")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _record_attempt(
    session: AsyncSession, email: str, ip: str | None, *, success: bool, reason: str | None
) -> None:
    session.add(
        LoginAttempt(
            email=email.lower(),
            ip_hash=hash_ip(ip),
            success=success,
            reason=reason,
        )
    )
    try:
        from app.services.audit.events import auth_event

        await auth_event(
            session,
            action="auth.login.success" if success else "auth.login.failure",
            email=email.lower(),
            actor_id=None,
            ip_hash=hash_ip(ip),
            reason=reason,
        )
    except Exception:
        log.warning("audit_auth_failed")


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    totp_code: str | None,
    ip: str | None,
) -> User:
    email_norm = email.strip().lower()
    user = (
        await session.execute(select(User).where(User.email == email_norm))
    ).scalar_one_or_none()

    # Uniform work factor whether or not the user exists (mitigates enumeration/timing).
    if user is None:
        verify_password(password, hash_password("dummy-password-for-timing"))
        await _record_attempt(session, email_norm, ip, success=False, reason="no_such_user")
        await session.commit()
        raise AuthError("Invalid email or password", code="invalid_credentials")

    if user.is_locked(_utcnow()):
        await _record_attempt(session, email_norm, ip, success=False, reason="locked")
        await session.commit()
        raise AuthError("Account temporarily locked. Try again later.", code="account_locked")

    if not verify_password(password, user.hashed_password):
        user.failed_login_count += 1
        reason = "bad_password"
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = _utcnow() + dt.timedelta(seconds=settings.login_lockout_seconds)
            user.failed_login_count = 0
            reason = "bad_password_locked"
            log.warning("account_locked", user_id=user.id)
        await _record_attempt(session, email_norm, ip, success=False, reason=reason)
        await session.commit()
        raise AuthError("Invalid email or password", code="invalid_credentials")

    if not user.is_active:
        await _record_attempt(session, email_norm, ip, success=False, reason="disabled")
        await session.commit()
        raise AuthError("Account is disabled", code="account_disabled")

    if user.totp_enabled:
        if not totp_code:
            await _record_attempt(session, email_norm, ip, success=False, reason="mfa_required")
            await session.commit()
            raise AuthError("TOTP code required", code="mfa_required")
        if not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            await _record_attempt(session, email_norm, ip, success=False, reason="mfa_bad")
            await session.commit()
            raise AuthError("Invalid TOTP code", code="mfa_invalid")

    # success
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _utcnow()
    await _record_attempt(session, email_norm, ip, success=True, reason=None)
    await session.commit()
    return user


async def issue_token_pair(
    session: AsyncSession,
    user: User,
    *,
    user_agent: str | None,
    ip: str | None,
    family_id: str | None = None,
) -> tuple[str, str, int]:
    now = _utcnow()
    raw_refresh = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or new_uuid(),
            token_hash=hash_token(raw_refresh),
            issued_at=now,
            expires_at=now + dt.timedelta(seconds=settings.refresh_token_ttl),
            user_agent=(user_agent or "")[:255] or None,
            ip_hash=hash_ip(ip),
        )
    )
    await session.commit()
    access = create_access_token(user.id, role=user.role.value)
    return access, raw_refresh, settings.access_token_ttl


async def rotate_refresh(
    session: AsyncSession,
    raw_refresh: str,
    *,
    user_agent: str | None,
    ip: str | None,
) -> tuple[str, str, int, User]:
    token_hash = hash_token(raw_refresh)
    record = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if record is None:
        raise AuthError("Invalid refresh token", code="invalid_refresh")

    if not record.is_active(_utcnow()):
        # A revoked/expired token being presented ⇒ likely replay/theft. Burn the family.
        await _revoke_family(session, record.family_id)
        await session.commit()
        log.warning("refresh_reuse_detected", family_id=record.family_id, user_id=record.user_id)
        raise AuthError("Refresh token no longer valid", code="refresh_reuse")

    user = (
        await session.execute(select(User).where(User.id == record.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        await _revoke_family(session, record.family_id)
        await session.commit()
        raise AuthError("Account unavailable", code="account_disabled")

    now = _utcnow()
    new_raw = generate_refresh_token()
    new_hash = hash_token(new_raw)
    record.revoked_at = now
    record.replaced_by = new_hash
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=record.family_id,
            token_hash=new_hash,
            issued_at=now,
            expires_at=now + dt.timedelta(seconds=settings.refresh_token_ttl),
            user_agent=(user_agent or "")[:255] or None,
            ip_hash=hash_ip(ip),
        )
    )
    await session.commit()
    access = create_access_token(user.id, role=user.role.value)
    return access, new_raw, settings.access_token_ttl, user


async def revoke_refresh(session: AsyncSession, raw_refresh: str) -> None:
    record = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
        )
    ).scalar_one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = _utcnow()
        await session.commit()


async def _revoke_family(session: AsyncSession, family_id: str) -> None:
    rows = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
        )
    ).scalars()
    now = _utcnow()
    for row in rows:
        row.revoked_at = now


async def revoke_all_user_tokens(session: AsyncSession, user_id: str) -> None:
    rows = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
    ).scalars()
    now = _utcnow()
    for row in rows:
        row.revoked_at = now
    await session.commit()
