"""Exceptions raised by the cryptographic core."""

from __future__ import annotations

from app.core.exceptions import AppError


class CryptoError(AppError):
    """Client-facing crypto/verification error (bad input, unparseable material)."""

    status_code = 422
    code = "crypto_error"


class UnsupportedAlgorithmError(CryptoError):
    code = "unsupported_algorithm"


class MaterialParseError(CryptoError):
    code = "material_parse_error"
