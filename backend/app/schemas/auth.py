"""Auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import UserRole
from app.schemas.types import Email


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token_type label, not a secret
    expires_in: int
    role: UserRole


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    totp_enabled: bool


class TotpEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TotpVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    detail: str = "TOTP code required"
