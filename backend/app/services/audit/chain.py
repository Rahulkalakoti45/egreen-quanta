"""Hash-chain writer, verifier, anchor and export."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.audit import GENESIS_HASH, AuditLog

log = get_logger("egreen.audit")

# Serialises appends within this process. Multi-worker deployments should route audit
# writes through a single worker or add a DB advisory lock (noted in ARCHITECTURE.md).
_WRITE_LOCK = asyncio.Lock()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _ts_key(ts: dt.datetime) -> str:
    """Whole-second UTC ISO string, stable across a SQLite round-trip (which drops tz)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.UTC)
    return ts.astimezone(dt.UTC).replace(microsecond=0).isoformat()


def compute_row_hash(
    *,
    seq: int,
    ts: dt.datetime,
    actor_id: str | None,
    actor_type: str,
    action: str,
    target_type: str | None,
    target_id: str | None,
    meta: dict,
    prev_hash: str,
) -> str:
    core = {
        "seq": seq,
        "ts": _ts_key(ts),
        "actor_id": actor_id,
        "actor_type": actor_type,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "meta": meta,
    }
    return hashlib.sha256(_canonical(core) + prev_hash.encode()).hexdigest()


async def _head(session: AsyncSession) -> tuple[int, str]:
    row = (
        await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    ).scalar_one_or_none()
    if row is None:
        return 0, GENESIS_HASH
    return row.seq, row.row_hash


async def record(
    session: AsyncSession,
    *,
    action: str,
    actor_id: str | None = None,
    actor_type: str = "system",
    target_type: str | None = None,
    target_id: str | None = None,
    meta: dict | None = None,
) -> AuditLog:
    """Append one hash-chained row. Best-effort — callers should not fail on audit errors."""
    meta = _sanitise(meta or {})
    async with _WRITE_LOCK:
        last_seq, prev_hash = await _head(session)
        now = dt.datetime.now(dt.UTC).replace(microsecond=0)
        seq = last_seq + 1
        row_hash = compute_row_hash(
            seq=seq,
            ts=now,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
            prev_hash=prev_hash,
        )
        row = AuditLog(
            seq=seq,
            ts=now,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


_REDACT_KEYS = {"password", "secret", "token", "api_key", "authorization", "refresh_token"}


def _sanitise(meta: dict) -> dict:
    out: dict = {}
    for k, v in meta.items():
        if k.lower() in _REDACT_KEYS:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _sanitise(v)
        elif isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out


async def verify_chain(session: AsyncSession, *, start_seq: int = 1) -> dict:
    """Recompute the chain from ``start_seq``; report the first mismatch, if any."""
    rows = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.seq >= start_seq).order_by(AuditLog.seq.asc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return {"ok": True, "checked": 0, "break_at": None, "head_hash": None}

    prev = GENESIS_HASH if start_seq <= 1 else rows[0].prev_hash
    break_at: int | None = None
    for row in rows:
        expected = compute_row_hash(
            seq=row.seq,
            ts=row.ts,
            actor_id=row.actor_id,
            actor_type=row.actor_type,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            meta=row.meta,
            prev_hash=prev,
        )
        if expected != row.row_hash or row.prev_hash != prev:
            break_at = row.seq
            break
        prev = row.row_hash

    return {
        "ok": break_at is None,
        "checked": len(rows),
        "break_at": break_at,
        "head_hash": rows[-1].row_hash,
        "head_seq": rows[-1].seq,
    }


def _signing_key():
    raw = settings.audit_signing_key
    if not raw:
        return None
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    seed = base64.b64decode(raw)
    return Ed25519PrivateKey.from_private_bytes(seed[:32])


async def create_anchor(session: AsyncSession, *, actor_id: str | None = None) -> AuditLog:
    head_seq, head_hash = await _head(session)
    meta: dict = {"head_seq": head_seq, "head_hash": head_hash}
    key = _signing_key()
    if key is not None:
        sig = key.sign(head_hash.encode())
        meta["signature"] = base64.b64encode(sig).decode()
        meta["signature_alg"] = "ed25519"
    return await record(
        session,
        action="audit.anchor",
        actor_id=actor_id,
        actor_type="system" if actor_id is None else "user",
        target_type="audit_log",
        target_id=str(head_seq),
        meta=meta,
    )


async def export_range(
    session: AsyncSession, *, start_seq: int = 1, end_seq: int | None = None
) -> dict:
    stmt = select(AuditLog).where(AuditLog.seq >= start_seq).order_by(AuditLog.seq.asc())
    if end_seq is not None:
        stmt = stmt.where(AuditLog.seq <= end_seq)
    rows = (await session.execute(stmt)).scalars().all()

    payload = {
        "start_seq": start_seq,
        "end_seq": end_seq or (rows[-1].seq if rows else start_seq),
        "genesis_hash": GENESIS_HASH,
        "rows": [
            {
                "seq": r.seq,
                "ts": r.ts.astimezone(dt.UTC).isoformat(),
                "actor_id": r.actor_id,
                "actor_type": r.actor_type,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "meta": r.meta,
                "prev_hash": r.prev_hash,
                "row_hash": r.row_hash,
            }
            for r in rows
        ],
    }
    key = _signing_key()
    if key is not None and rows:
        digest = hashlib.sha256(_canonical(payload["rows"])).hexdigest()
        payload["export_sha256"] = digest
        payload["export_signature"] = base64.b64encode(key.sign(digest.encode())).decode()
        payload["export_signature_alg"] = "ed25519"
    return payload
