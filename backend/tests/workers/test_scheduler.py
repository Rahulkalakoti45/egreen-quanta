"""Background job functions + the async Scheduler loop."""

from __future__ import annotations

import asyncio
import datetime as dt

import pytest
from app.core.config import settings
from app.models.audit import AuditLog
from app.models.enums import EnvelopeType, EventSource, Verdict
from app.models.verification_event import VerificationEvent
from app.workers import scheduler as sched
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _bind_session(engine, monkeypatch):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(sched, "SessionLocal", maker)
    return maker


async def test_audit_anchor_job_writes_row(_bind_session) -> None:
    await sched.audit_anchor_job()
    async with _bind_session() as s:
        rows = (await s.execute(select(AuditLog))).scalars().all()
    assert any(r.action == "audit.anchor" for r in rows)


async def test_retention_purge_deletes_old_events(_bind_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "retention_days", 30)
    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=90)
    new = dt.datetime.now(dt.UTC)
    async with _bind_session() as s:
        s.add_all(
            [
                VerificationEvent(
                    source=EventSource.API,
                    envelope_type=EnvelopeType.RAW,
                    verdict=Verdict.VALID,
                    created_at=old,
                    summary="old",
                    result_json={},
                ),
                VerificationEvent(
                    source=EventSource.API,
                    envelope_type=EnvelopeType.RAW,
                    verdict=Verdict.VALID,
                    created_at=new,
                    summary="new",
                    result_json={},
                ),
            ]
        )
        await s.commit()

    await sched.retention_purge_job()

    async with _bind_session() as s:
        remaining = (
            await s.execute(select(func.count()).select_from(VerificationEvent))
        ).scalar_one()
    assert remaining == 1


async def test_retention_purge_noop_when_disabled(_bind_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "retention_days", 0)
    await sched.retention_purge_job()  # must not raise


async def test_scheduler_runs_and_stops() -> None:
    hits = {"n": 0}

    async def job() -> None:
        hits["n"] += 1

    s = sched.Scheduler()
    s.start([sched.Job("t", interval_seconds=0.05, func=job)])
    await asyncio.sleep(0.25)
    await s.stop()
    assert hits["n"] >= 2
