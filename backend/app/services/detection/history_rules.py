"""History-aware rules that the stateless cryptographic core cannot evaluate."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Verdict
from app.models.verification_event import VerificationEvent
from app.services.crypto.types import CryptoFinding, FindingCategory, Severity


@dataclass(slots=True)
class HistoryContext:
    envelope: str
    verdict: Verdict
    payload_sha256: str | None
    signature_sha256: str | None
    signer_spki_sha256: str | None
    submitter_ip_hash: str | None
    now: dt.datetime


async def evaluate_history_rules(
    session: AsyncSession, ctx: HistoryContext, *, config: dict | None = None
) -> list[CryptoFinding]:
    config = config or {}
    findings: list[CryptoFinding] = []
    findings.extend(await _replay(session, ctx))
    findings.extend(await _failure_burst(session, ctx, config))
    return findings


async def _replay(session: AsyncSession, ctx: HistoryContext) -> list[CryptoFinding]:
    if not ctx.signature_sha256:
        return []
    out: list[CryptoFinding] = []

    # Same signature bytes seen before?
    prior = (
        await session.execute(
            select(VerificationEvent)
            .where(VerificationEvent.signature_sha256 == ctx.signature_sha256)
            .order_by(VerificationEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if prior is None:
        return []

    if prior.payload_sha256 == ctx.payload_sha256:
        out.append(
            CryptoFinding(
                code="T14",
                title="Signature replay",
                severity=Severity.HIGH,
                category=FindingCategory.FORGERY,
                detail=f"Identical payload + signature already verified at "
                f"{prior.created_at.isoformat()} (event {prior.id}).",
            )
        )
    else:
        out.append(
            CryptoFinding(
                code="T14",
                title="Signature reused on a different payload",
                severity=Severity.CRITICAL,
                category=FindingCategory.FORGERY,
                detail=f"The same signature was previously bound to a different payload "
                f"(event {prior.id}).",
            )
        )
    return out


async def _failure_burst(
    session: AsyncSession, ctx: HistoryContext, config: dict
) -> list[CryptoFinding]:
    if ctx.verdict != Verdict.INVALID or not ctx.submitter_ip_hash:
        return []
    window_minutes = int(config.get("window_minutes", 10))
    threshold = int(config.get("threshold", 5))
    since = ctx.now - dt.timedelta(minutes=window_minutes)

    count = (
        await session.execute(
            select(func.count())
            .select_from(VerificationEvent)
            .where(
                VerificationEvent.submitter_ip_hash == ctx.submitter_ip_hash,
                VerificationEvent.verdict == Verdict.INVALID.value,
                VerificationEvent.created_at >= since,
            )
        )
    ).scalar_one()

    # +1 for the current (not-yet-persisted) event.
    if int(count) + 1 >= threshold:
        return [
            CryptoFinding(
                code="T15",
                title="Verification-failure burst",
                severity=Severity.MEDIUM,
                category=FindingCategory.FORGERY,
                detail=f"{int(count) + 1} invalid verifications from this source in the last "
                f"{window_minutes} minutes (threshold {threshold}).",
            )
        ]
    return []
