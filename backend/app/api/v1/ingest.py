"""Machine ingest for external submitters (Module 8). API-key auth, rate-limited."""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import SessionDep, client_ip, require_api_key
from app.core.rate_limit import INGEST_LIMIT, rate_limit
from app.core.security import hash_ip
from app.models.api_key import ApiKey
from app.models.enums import ApiKeyScope, EventSource
from app.schemas.crypto import VerificationOut
from app.schemas.ingest import IngestAck, IngestEventRequest, RawVerifyRequest
from app.services.crypto import engine
from app.services.crypto.types import (
    CertInfo,
    ChainResult,
    CryptoFinding,
    FindingCategory,
    KeyParams,
    RevocationResult,
    Severity,
    SignatureParams,
    Verdict,
    VerificationResult,
)
from app.services.detection.engine import attach_detection, run_detection

router = APIRouter(prefix="/ingest", tags=["ingest"])

_IngestRate = Depends(rate_limit("ingest", INGEST_LIMIT))
SigKey = Annotated[ApiKey, Depends(require_api_key(ApiKeyScope.INGEST_SIGNATURES))]
EventKey = Annotated[ApiKey, Depends(require_api_key(ApiKeyScope.INGEST_EVENTS))]


@router.post("/signatures", response_model=VerificationOut, dependencies=[_IngestRate])
async def ingest_signature(
    payload: RawVerifyRequest, request: Request, session: SessionDep, _: SigKey
) -> VerificationOut:
    result = await engine.verify_raw_signature(
        session,
        data_b64=payload.data_b64,
        signature_b64=payload.signature_b64,
        hash_alg=payload.hash_alg,
        padding=payload.padding,
        certificate_pem=payload.certificate_pem,
        public_key_pem=payload.public_key_pem,
        is_prehashed=payload.is_prehashed,
        verify_time=payload.verify_time,
    )
    try:
        sig_bytes = base64.b64decode(payload.signature_b64, validate=True)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        sig_bytes = None
    enriched = await attach_detection(
        session,
        result,
        source=EventSource.INGEST,
        source_ref="ingest/signatures",
        submitter_id=None,
        ip_hash=hash_ip(client_ip(request)),
        signature_bytes=sig_bytes,
    )
    return VerificationOut.model_validate(enriched)


@router.post("/events", response_model=IngestAck, dependencies=[_IngestRate])
async def ingest_event(
    payload: IngestEventRequest, request: Request, session: SessionDep, _: EventKey
) -> IngestAck:
    signer = (
        CertInfo(
            subject=payload.signer_subject or "",
            issuer="",
            serial_hex="",
            not_before=payload.signing_time or _epoch(),
            not_after=payload.signing_time or _epoch(),
            spki_sha256=payload.signer_spki_sha256 or "",
            sig_algo=payload.algorithm or "",
            key=KeyParams(
                key_type=payload.key_type or "unknown",
                key_bits=payload.key_bits,
                curve=payload.curve,
            ),
            is_ca=False,
            self_signed=False,
        )
        if payload.signer_subject or payload.signer_spki_sha256
        else None
    )
    result = VerificationResult(
        verdict=Verdict(payload.verdict),
        envelope=payload.envelope,
        signature=SignatureParams(
            algorithm=payload.algorithm or "unknown",
            hash_alg=payload.hash_alg,
            key=KeyParams(
                key_type=payload.key_type or "unknown",
                key_bits=payload.key_bits,
                curve=payload.curve,
            ),
        ),
        signer=signer,
        chain=ChainResult(status=payload.chain_status) if payload.chain_status else None,
        revocation=(
            RevocationResult(status=payload.revocation_status)
            if payload.revocation_status
            else None
        ),
        signing_time=payload.signing_time,
        tsa_present=payload.tsa_present,
        tsa_trusted=False,
        findings=[
            CryptoFinding(
                code=f.code,
                title=f.title,
                severity=Severity(f.severity),
                category=_category(f.category),
                detail=f.detail,
            )
            for f in payload.findings
        ],
        payload_sha256=payload.payload_sha256,
        summary=payload.summary or f"ingested {payload.verdict} event",
    )

    outcome = await run_detection(
        session,
        result,
        source=EventSource.INGEST,
        source_ref=payload.source_ref or "ingest/events",
        submitter_id=None,
        ip_hash=hash_ip(client_ip(request)),
        signature_sha256=payload.signature_sha256,
    )
    return IngestAck(
        event_id=outcome.event.id,
        verdict=payload.verdict,
        risk_score=outcome.event.risk_score,
        alert_id=outcome.alert.id if outcome.alert else None,
        incident_id=outcome.incident_id,
    )


def _epoch():
    import datetime as dt

    return dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


def _category(name: str) -> FindingCategory:
    try:
        return FindingCategory(name)
    except ValueError:
        return FindingCategory.POLICY
