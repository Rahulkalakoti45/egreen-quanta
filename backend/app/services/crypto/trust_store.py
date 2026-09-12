"""Trust-store service: CA anchors and issuer allow-list CRUD + lookups."""

from __future__ import annotations

import datetime as dt
import hashlib

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.trust_anchor import CaAllowlistEntry, TrustAnchor
from app.models.user import User
from app.services.crypto.x509_utils import load_certificate, spki_sha256


def _aware(v: dt.datetime) -> dt.datetime:
    return v if v.tzinfo else v.replace(tzinfo=dt.UTC)


async def list_anchors(session: AsyncSession) -> list[TrustAnchor]:
    rows = await session.execute(select(TrustAnchor).order_by(TrustAnchor.created_at.desc()))
    return list(rows.scalars().all())


async def enabled_anchor_certs(session: AsyncSession) -> list[x509.Certificate]:
    rows = await session.execute(select(TrustAnchor).where(TrustAnchor.enabled.is_(True)))
    return [load_certificate(a.pem.encode()) for a in rows.scalars().all()]


async def add_anchor(session: AsyncSession, *, name: str, pem: str, added_by: User) -> TrustAnchor:
    cert = load_certificate(pem.encode())
    fp = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    spki = spki_sha256(cert.public_key())

    dupe = (
        await session.execute(select(TrustAnchor).where(TrustAnchor.spki_sha256 == spki))
    ).scalar_one_or_none()
    if dupe:
        raise ConflictError("A trust anchor with that key is already present")

    anchor = TrustAnchor(
        name=name,
        subject=cert.subject.rfc4514_string(),
        spki_sha256=spki,
        fingerprint_sha256=fp,
        not_after=_aware(cert.not_valid_after_utc),
        pem=cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        added_by=added_by.id,
    )
    session.add(anchor)
    await session.commit()
    await session.refresh(anchor)
    return anchor


async def set_anchor_enabled(session: AsyncSession, anchor_id: str, enabled: bool) -> TrustAnchor:
    anchor = (
        await session.execute(select(TrustAnchor).where(TrustAnchor.id == anchor_id))
    ).scalar_one_or_none()
    if anchor is None:
        raise NotFoundError("Trust anchor not found")
    anchor.enabled = enabled
    await session.commit()
    await session.refresh(anchor)
    return anchor


async def delete_anchor(session: AsyncSession, anchor_id: str) -> None:
    anchor = (
        await session.execute(select(TrustAnchor).where(TrustAnchor.id == anchor_id))
    ).scalar_one_or_none()
    if anchor is None:
        raise NotFoundError("Trust anchor not found")
    await session.delete(anchor)
    await session.commit()


async def list_allowlist(session: AsyncSession) -> list[CaAllowlistEntry]:
    rows = await session.execute(
        select(CaAllowlistEntry).order_by(CaAllowlistEntry.created_at.desc())
    )
    return list(rows.scalars().all())


async def add_allowlist_entry(
    session: AsyncSession,
    *,
    subject_pattern: str,
    issuer_spki_sha256: str,
    note: str,
    added_by: User,
) -> CaAllowlistEntry:
    entry = CaAllowlistEntry(
        subject_pattern=subject_pattern,
        issuer_spki_sha256=issuer_spki_sha256,
        note=note,
        added_by=added_by.id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def delete_allowlist_entry(session: AsyncSession, entry_id: str) -> None:
    entry = (
        await session.execute(select(CaAllowlistEntry).where(CaAllowlistEntry.id == entry_id))
    ).scalar_one_or_none()
    if entry is None:
        raise NotFoundError("Allow-list entry not found")
    await session.delete(entry)
    await session.commit()


async def anchor_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(TrustAnchor))).scalar_one())
