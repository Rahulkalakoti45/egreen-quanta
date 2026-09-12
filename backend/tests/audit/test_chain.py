"""Hash-chain writer / verifier / anchor / export."""

from __future__ import annotations

import base64
from itertools import pairwise

import pytest
from app.core.config import settings
from app.models.audit import GENESIS_HASH, AuditLog
from app.services.audit import chain
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def _seed(session, n: int = 5) -> None:
    for i in range(n):
        await chain.record(
            session,
            action=f"test.event.{i}",
            actor_id="u1",
            actor_type="user",
            target_type="thing",
            target_id=str(i),
            meta={"i": i},
        )


async def test_chain_links_and_verifies(db_session) -> None:
    await _seed(db_session, 6)
    rows = (await db_session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
    assert rows[0].prev_hash == GENESIS_HASH
    for a, b in pairwise(rows):
        assert b.prev_hash == a.row_hash

    v = await chain.verify_chain(db_session)
    assert v["ok"] is True
    assert v["checked"] == 6
    assert v["break_at"] is None
    assert v["head_hash"] == rows[-1].row_hash


async def test_tamper_is_detected_and_located(db_session) -> None:
    await _seed(db_session, 6)
    row3 = (await db_session.execute(select(AuditLog).where(AuditLog.seq == 3))).scalar_one()
    row3.meta = {"i": 3, "tampered": True}
    await db_session.commit()

    v = await chain.verify_chain(db_session)
    assert v["ok"] is False
    assert v["break_at"] == 3


async def test_tamper_with_hash_field_detected(db_session) -> None:
    await _seed(db_session, 4)
    row2 = (await db_session.execute(select(AuditLog).where(AuditLog.seq == 2))).scalar_one()
    row2.row_hash = "f" * 64
    await db_session.commit()
    v = await chain.verify_chain(db_session)
    assert v["ok"] is False
    assert v["break_at"] == 2


async def test_secrets_are_redacted_in_meta(db_session) -> None:
    row = await chain.record(
        db_session,
        action="test.secret",
        meta={"password": "hunter2", "nested": {"token": "abc"}, "ok": "fine"},
    )
    assert row.meta["password"] == "***"
    assert row.meta["nested"]["token"] == "***"
    assert row.meta["ok"] == "fine"


async def test_anchor_records_head(db_session) -> None:
    await _seed(db_session, 3)
    anchor = await chain.create_anchor(db_session)
    assert anchor.action == "audit.anchor"
    assert anchor.meta["head_seq"] == 3
    # the anchor row is itself chained
    v = await chain.verify_chain(db_session)
    assert v["ok"] is True


async def test_signed_anchor_and_export(db_session, monkeypatch) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    monkeypatch.setattr(settings, "audit_signing_key", base64.b64encode(seed).decode())

    await _seed(db_session, 4)
    anchor = await chain.create_anchor(db_session)
    assert "signature" in anchor.meta

    sig = base64.b64decode(anchor.meta["signature"])
    key.public_key().verify(sig, anchor.meta["head_hash"].encode())  # raises on bad sig

    export = await chain.export_range(db_session, start_seq=1)
    assert len(export["rows"]) == 5
    assert "export_signature" in export
