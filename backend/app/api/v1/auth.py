"""Authentication routes: login, refresh, logout, me, TOTP enrolment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import CurrentUser, SessionDep, client_ip
from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.rate_limit import AUTH_LOGIN_LIMIT, AUTH_REFRESH_LIMIT, rate_limit
from app.core.security import (
    generate_totp_secret,
    totp_provisioning_uri,
    verify_totp,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
    TotpEnrollResponse,
    TotpVerifyRequest,
)
from app.schemas.common import Message
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "egq_refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl,
        httponly=True,
        secure=settings.is_prod,
        samesite="strict",
        path=settings.api_v1_prefix + "/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_REFRESH_COOKIE, path=settings.api_v1_prefix + "/auth")


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_login", AUTH_LOGIN_LIMIT))],
)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    ip = client_ip(request)
    user = await auth_service.authenticate(
        session,
        email=payload.email,
        password=payload.password,
        totp_code=payload.totp_code,
        ip=ip,
    )
    access, refresh, expires_in = await auth_service.issue_token_pair(
        session, user, user_agent=request.headers.get("user-agent"), ip=ip
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        role=user.role,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_refresh", AUTH_REFRESH_LIMIT))],
)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    payload: RefreshRequest | None = None,
) -> TokenResponse:
    raw = (payload.refresh_token if payload else None) or request.cookies.get(_REFRESH_COOKIE)
    if not raw:
        raise AuthError("No refresh token provided", code="invalid_refresh")
    access, new_refresh, expires_in, user = await auth_service.rotate_refresh(
        session, raw, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=expires_in,
        role=user.role,
    )


@router.post("/logout", response_model=Message)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    payload: LogoutRequest | None = None,
) -> Message:
    raw = (payload.refresh_token if payload else None) or request.cookies.get(_REFRESH_COOKIE)
    if raw:
        await auth_service.revoke_refresh(session, raw)
    _clear_refresh_cookie(response)
    return Message(detail="Logged out")


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        totp_enabled=user.totp_enabled,
    )


@router.post("/totp/enroll", response_model=TotpEnrollResponse)
async def totp_enroll(user: CurrentUser, session: SessionDep) -> TotpEnrollResponse:
    if user.totp_enabled:
        raise AuthError("TOTP already enabled", code="totp_already_enabled")
    secret = generate_totp_secret()
    user.totp_secret = secret
    await session.commit()
    return TotpEnrollResponse(
        secret=secret,
        otpauth_uri=totp_provisioning_uri(secret, user.email),
    )


@router.post("/totp/verify", response_model=Message)
async def totp_verify(body: TotpVerifyRequest, user: CurrentUser, session: SessionDep) -> Message:
    if not user.totp_secret:
        raise AuthError("Start enrolment first", code="totp_not_started")
    if not verify_totp(user.totp_secret, body.code):
        raise AuthError("Invalid TOTP code", code="mfa_invalid")
    user.totp_enabled = True
    await session.commit()
    return Message(detail="TOTP enabled")


@router.post("/totp/disable", response_model=Message)
async def totp_disable(body: TotpVerifyRequest, user: CurrentUser, session: SessionDep) -> Message:
    if not user.totp_enabled or not user.totp_secret:
        raise AuthError("TOTP is not enabled", code="totp_not_enabled")
    if not verify_totp(user.totp_secret, body.code):
        raise AuthError("Invalid TOTP code", code="mfa_invalid")
    user.totp_enabled = False
    user.totp_secret = None
    await session.commit()
    return Message(detail="TOTP disabled")
