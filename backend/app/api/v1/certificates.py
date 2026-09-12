"""Certificate validation + observed-certificate browsing (Module 2)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, client_ip
from app.core.security import hash_ip
from app.models.certificate import Certificate
from app.models.enums import EventSource
from app.schemas.common import Page
from app.schemas.crypto import CertificateOut, CertValidateRequest, VerificationOut
from app.services.crypto import engine
from app.services.detection.engine import attach_detection

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("/validate", response_model=VerificationOut)
async def validate_certificate(
    payload: CertValidateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> VerificationOut:
    result = await engine.validate_certificate(
        session,
        certificate_pem=payload.certificate_pem,
        extra_chain_pem=payload.extra_chain_pem,
        expected_eku=payload.expected_eku,
        verify_time=payload.verify_time,
    )
    enriched = await attach_detection(
        session,
        result,
        source=EventSource.API,
        source_ref="certificates/validate",
        submitter_id=user.id,
        ip_hash=hash_ip(client_ip(request)),
    )
    return VerificationOut.model_validate(enriched)


@router.get("", response_model=Page[CertificateOut])
async def list_certificates(
    session: SessionDep,
    _: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    key_reuse_only: bool = Query(False, description="Only SPKIs seen under multiple subjects"),
) -> Page[CertificateOut]:
    total = (await session.execute(select(func.count()).select_from(Certificate))).scalar_one()
    stmt = select(Certificate).order_by(Certificate.last_seen_at.desc())
    if key_reuse_only:
        dupes = (
            select(Certificate.spki_sha256)
            .group_by(Certificate.spki_sha256)
            .having(func.count(func.distinct(Certificate.subject)) > 1)
        )
        stmt = stmt.where(Certificate.spki_sha256.in_(dupes))
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(
        items=[CertificateOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{cert_id}", response_model=CertificateOut)
async def get_certificate(cert_id: str, session: SessionDep, _: CurrentUser) -> CertificateOut:
    from app.core.exceptions import NotFoundError

    row = (
        await session.execute(select(Certificate).where(Certificate.id == cert_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Certificate not found")
    return CertificateOut.model_validate(row)
