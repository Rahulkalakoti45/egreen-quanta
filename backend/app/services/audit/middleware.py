"""Records every mutating API request into the audit chain (best-effort)."""

from __future__ import annotations

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.security import decode_access_token

log = get_logger("egreen.audit.mw")

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# these get richer, explicit audit rows from the service layer - skip the generic one
_SKIP_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/refresh")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.method not in _MUTATING:
            return response
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response
        if response.status_code >= 500:
            return response

        actor_id: str | None = None
        actor_type = "anon"
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                payload = decode_access_token(auth.split(" ", 1)[1])
                actor_id, actor_type = payload.get("sub"), "user"
            except jwt.PyJWTError:
                actor_type = "anon"
        elif request.headers.get("x-api-key"):
            actor_type = "api_key"

        try:
            from app.db.session import SessionLocal
            from app.services.audit.chain import record

            async with SessionLocal() as session:
                await record(
                    session,
                    action=f"{request.method} {path}",
                    actor_id=actor_id,
                    actor_type=actor_type,
                    target_type="http",
                    target_id=request.headers.get("x-request-id"),
                    meta={
                        "status": response.status_code,
                        "path": path,
                        "query": str(request.url.query)[:200] or None,
                    },
                )
        except Exception as exc:
            log.warning("audit_write_failed", path=path, error=str(exc))

        return response
