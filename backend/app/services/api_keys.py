"""API-key management + verification service."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError, NotFoundError
from app.core.security import generate_api_key, parse_api_key
from app.models.api_key import ApiKey
from app.models.enums import ApiKeyScope
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def create_api_key(
    session: AsyncSession, payload: ApiKeyCreate, *, created_by: User
) -> tuple[ApiKey, str]:
    full_key, prefix, key_hash = generate_api_key()
    expires_at = (
        _utcnow() + dt.timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
    )
    record = ApiKey(
        name=payload.name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=",".join(sorted({s.value for s in payload.scopes})),
        created_by=created_by.id,
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record, full_key


async def list_api_keys(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[ApiKey], int]:
    total = (await session.execute(select(func.count()).select_from(ApiKey))).scalar_one()
    rows = (
        (
            await session.execute(
                select(ApiKey).order_by(ApiKey.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def revoke_api_key(session: AsyncSession, key_id: str, *, acting_user: User) -> None:
    record = (await session.execute(select(ApiKey).where(ApiKey.id == key_id))).scalar_one_or_none()
    if record is None:
        raise NotFoundError("API key not found")
    if record.revoked_at is None:
        record.revoked_at = _utcnow()
        await session.commit()
    _ = acting_user  # reserved for per-owner restrictions


async def verify_api_key(
    session: AsyncSession, full_key: str, *, required_scope: ApiKeyScope
) -> ApiKey:
    parsed = parse_api_key(full_key)
    if parsed is None:
        raise AuthError("Malformed API key", code="invalid_api_key")
    prefix, secret_hash = parsed
    record = (
        await session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
    ).scalar_one_or_none()
    if record is None or record.key_hash != secret_hash:
        raise AuthError("Invalid API key", code="invalid_api_key")
    if not record.is_valid(_utcnow()):
        raise AuthError("API key expired or revoked", code="api_key_inactive")
    if required_scope.value not in record.scope_list:
        raise ForbiddenError(f"API key lacks required scope: {required_scope.value}")
    record.last_used_at = _utcnow()
    await session.commit()
    return record
