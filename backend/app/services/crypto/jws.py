"""JWS (JSON Web Signature) verification — compact serialisation."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import jwt
from jwt import PyJWS
from jwt.exceptions import InvalidSignatureError, PyJWTError

from app.services.crypto.errors import MaterialParseError
from app.services.crypto.types import KeyParams, SignatureParams
from app.services.crypto.x509_utils import key_params

_ALG_TO_PARAMS = {
    "RS256": ("sha256", "pkcs1v15"),
    "RS384": ("sha384", "pkcs1v15"),
    "RS512": ("sha512", "pkcs1v15"),
    "PS256": ("sha256", "pss"),
    "PS384": ("sha384", "pss"),
    "PS512": ("sha512", "pss"),
    "ES256": ("sha256", None),
    "ES384": ("sha384", None),
    "ES512": ("sha512", None),
    "EdDSA": (None, None),
}


@dataclass(slots=True)
class JwsResult:
    verified: bool
    algorithm: str
    params: SignatureParams
    payload: bytes | None
    header: dict
    error: str | None = None


def _b64url_json(segment: str) -> dict:
    pad = "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment + pad))


def parse_header(token: str) -> dict:
    try:
        return jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise MaterialParseError(f"Invalid JWS header: {exc}") from exc


def verify_compact(token: str, public_key) -> JwsResult:
    token = token.strip()
    if token.count(".") != 2:
        raise MaterialParseError("Not a compact JWS (expected three dot-separated segments)")

    header = parse_header(token)
    alg = header.get("alg", "")
    if alg == "none":
        params = SignatureParams(algorithm="none", hash_alg=None)
        return JwsResult(False, alg, params, None, header, error="'none' algorithm is not accepted")
    if alg not in _ALG_TO_PARAMS:
        params = SignatureParams(algorithm=alg or "unknown", hash_alg=None)
        return JwsResult(False, alg, params, None, header, error=f"unsupported JWS alg '{alg}'")

    hash_alg, padding = _ALG_TO_PARAMS[alg]
    kp: KeyParams = key_params(public_key)
    params = SignatureParams(
        algorithm=f"jws-{alg.lower()}", hash_alg=hash_alg, padding=padding, key=kp
    )

    jws = PyJWS()
    try:
        payload = jws.decode(token, key=public_key, algorithms=[alg])
        return JwsResult(True, alg, params, payload, header)
    except InvalidSignatureError:
        return JwsResult(False, alg, params, None, header, error="signature does not verify")
    except PyJWTError as exc:
        return JwsResult(False, alg, params, None, header, error=str(exc))
