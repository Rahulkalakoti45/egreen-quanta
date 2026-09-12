"""Shared FastAPI dependencies: DB session, current user, RBAC, API-key principals."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.enums import ApiKeyScope, UserRole
from app.models.user import User

__all__ = [
    "CurrentUser",
    "SessionDep",
    "client_ip",
    "get_current_user",
    "get_session",
    "require_api_key",
    "require_min_role",
    "require_role",
]

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="JWT access token")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def get_current_user(session: SessionDep, creds: BearerDep) -> User:
    if creds is None or not creds.credentials:
        raise AuthError("Not authenticated", code="not_authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid access token", code="token_invalid") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Invalid access token", code="token_invalid")

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("Account unavailable", code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """Dependency factory: allow only the listed roles."""
    allowed = set(roles)

    async def _dep(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Insufficient role for this operation")
        return user

    return _dep


def require_min_role(minimum: UserRole):
    """Dependency factory: allow the given role or any higher-ranked role."""

    async def _dep(user: CurrentUser) -> User:
        if user.role.rank < minimum.rank:
            raise ForbiddenError("Insufficient role for this operation")
        return user

    return _dep


def require_api_key(scope: ApiKeyScope):
    """Dependency factory for machine ingest endpoints (X-API-Key header)."""

    async def _dep(request: Request, session: SessionDep):
        from app.services.api_keys import verify_api_key  # local import avoids cycle

        raw = request.headers.get("x-api-key", "")
        if not raw:
            raise AuthError("Missing X-API-Key header", code="not_authenticated")
        return await verify_api_key(session, raw, required_scope=scope)

    return _dep
