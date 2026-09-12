"""Named audit recorders for security-relevant events (best-effort, never raise)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.audit.chain import record

log = get_logger("egreen.audit.events")


async def _safe(session: AsyncSession, **kw) -> None:
    try:
        await record(session, **kw)
    except Exception as exc:
        log.warning("audit_event_failed", action=kw.get("action"), error=str(exc))


async def auth_event(
    session: AsyncSession,
    *,
    action: str,
    email: str,
    actor_id: str | None,
    ip_hash: str | None,
    reason: str | None = None,
) -> None:
    await _safe(
        session,
        action=action,
        actor_id=actor_id,
        actor_type="user" if actor_id else "anon",
        target_type="user",
        target_id=actor_id,
        meta={"email": email, "ip_hash": ip_hash, "reason": reason},
    )


async def config_change(
    session: AsyncSession,
    *,
    action: str,
    actor_id: str | None,
    target_type: str,
    target_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    await _safe(
        session,
        action=action,
        actor_id=actor_id,
        actor_type="user" if actor_id else "system",
        target_type=target_type,
        target_id=target_id,
        meta={"before": before, "after": after},
    )
