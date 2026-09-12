"""Authentication primitives: password hashing, JWT, API keys, TOTP, hashing helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any, Literal

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

# ---------------------------------------------------------------- passwords

_ph = PasswordHasher(
    time_cost=settings.password_argon2_time_cost,
    memory_cost=settings.password_argon2_memory_cost,
    parallelism=settings.password_argon2_parallelism,
)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, password)
        return True
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except (InvalidHashError, ValueError):
        return True


# ---------------------------------------------------------------- JWT

TokenType = Literal["access"]


def _jwt_keys() -> tuple[str, str]:
    """Return (signing_key, verifying_key) for the configured algorithm."""
    if settings.jwt_algorithm == "RS256":
        if not settings.jwt_private_key_path or not settings.jwt_public_key_path:
            raise RuntimeError("RS256 requires JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH")
        priv = Path(settings.jwt_private_key_path).read_text()
        pub = Path(settings.jwt_public_key_path).read_text()
        return priv, pub
    return settings.secret_key, settings.secret_key


def create_access_token(
    subject: str,
    *,
    role: str,
    expires_delta: dt.timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = dt.datetime.now(dt.UTC)
    exp = now + (expires_delta or dt.timedelta(seconds=settings.access_token_ttl))
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    signing_key, _ = _jwt_keys()
    return jwt.encode(payload, signing_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode & validate a token. Raises ``jwt.PyJWTError`` subclasses on failure."""
    _, verifying_key = _jwt_keys()
    payload: dict[str, Any] = jwt.decode(
        token,
        verifying_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# ---------------------------------------------------------------- refresh tokens


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """SHA-256 hex digest — used for refresh tokens and API-key secrets."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# ---------------------------------------------------------------- API keys

API_KEY_PREFIX = "egq"


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, secret_hash).

    full_key format: ``egq_<prefix>_<secret>`` — shown to the caller exactly once.
    """
    prefix = secrets.token_hex(4)  # 8 chars
    secret = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}_{prefix}_{secret}"
    return full_key, prefix, hash_token(secret)


def parse_api_key(full_key: str) -> tuple[str, str] | None:
    """Split ``egq_<prefix>_<secret>`` → (prefix, secret_hash); None if malformed."""
    parts = full_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PREFIX:
        return None
    _, prefix, secret = parts
    if not prefix or not secret:
        return None
    return prefix, hash_token(secret)


# ---------------------------------------------------------------- TOTP


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=settings.totp_issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not code or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ---------------------------------------------------------------- misc


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(f"{settings.secret_key}:{ip}".encode()).hexdigest()
