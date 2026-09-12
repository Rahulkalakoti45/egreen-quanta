"""Dependency-free async background scheduler.

Runs a handful of periodic maintenance jobs on ``asyncio`` timers. The task
*functions* are what a Celery-beat deployment would call too (one code path).
Disabled under ``APP_ENV=test`` and when ``SCHEDULER_ENABLED=false``.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal

log = get_logger("egreen.scheduler")


@dataclass(slots=True)
class Job:
    name: str
    interval_seconds: float
    func: Callable[[], Awaitable[None]]
    enabled: bool = True


class Scheduler:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._stopping = asyncio.Event()

    def start(self, jobs: list[Job]) -> None:
        for job in jobs:
            if job.enabled:
                self._tasks.append(asyncio.create_task(self._loop(job), name=f"job:{job.name}"))
        if self._tasks:
            log.info("scheduler_started", jobs=[t.get_name() for t in self._tasks])

    async def stop(self) -> None:
        self._stopping.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with _suppress_cancel():
                await t
        self._tasks.clear()

    async def _loop(self, job: Job) -> None:
        # small initial delay so jobs don't all fire at boot
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=min(2.0, job.interval_seconds))
            return
        except TimeoutError:
            pass
        while not self._stopping.is_set():
            try:
                await job.func()
            except Exception as exc:  # keep the loop alive
                log.warning("job_failed", job=job.name, error=str(exc))
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=job.interval_seconds)
            except TimeoutError:
                continue


class _suppress_cancel:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, *_: object) -> bool:
        return exc_type is asyncio.CancelledError


# --------------------------------------------------------------------------- jobs


async def audit_anchor_job() -> None:
    from app.services.audit.chain import create_anchor

    async with SessionLocal() as session:
        row = await create_anchor(session)
    log.info("audit_anchor_written", seq=row.seq, head_seq=row.meta.get("head_seq"))


async def retention_purge_job() -> None:
    days = settings.retention_days
    if not days:
        return
    from sqlalchemy import delete

    from app.models.verification_event import VerificationEvent

    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    async with SessionLocal() as session:
        result = await session.execute(
            delete(VerificationEvent).where(VerificationEvent.created_at < cutoff)
        )
        await session.commit()
    deleted = int(result.rowcount or 0)  # type: ignore[attr-defined]
    if deleted:
        log.info("retention_purged", deleted=deleted, older_than_days=days)


def default_jobs() -> list[Job]:
    return [
        Job(
            "audit_anchor",
            interval_seconds=settings.audit_anchor_interval_hours * 3600,
            func=audit_anchor_job,
            enabled=settings.audit_anchor_enabled,
        ),
        Job(
            "retention_purge",
            interval_seconds=6 * 3600,
            func=retention_purge_job,
            enabled=bool(settings.retention_days),
        ),
    ]


scheduler = Scheduler()


async def _run_forever() -> None:
    """Standalone entrypoint: run the scheduler as its own process until signalled.

    Used by the production compose ``worker`` service so the web workers can run
    with ``SCHEDULER_ENABLED=false`` (avoiding N copies of every periodic job).
    """
    import contextlib
    import signal

    from app.core.logging import configure_logging

    configure_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows has no add_signal_handler
            loop.add_signal_handler(sig, stop.set)

    scheduler.start(default_jobs())
    log.info("standalone_scheduler_running")
    await stop.wait()
    log.info("standalone_scheduler_stopping")
    await scheduler.stop()


if __name__ == "__main__":
    asyncio.run(_run_forever())
