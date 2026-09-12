"""Trust-store administration: CA anchors + issuer allow-list (Module 2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import SessionDep, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Message
from app.schemas.crypto import (
    AllowlistCreate,
    AllowlistOut,
    TrustAnchorCreate,
    TrustAnchorOut,
    TrustAnchorPatch,
)
from app.services.crypto import trust_store

router = APIRouter(prefix="/trust-store", tags=["trust-store"])

AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
Reader = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.AUDITOR))]


@router.get("/anchors", response_model=list[TrustAnchorOut])
async def list_anchors(session: SessionDep, _: Reader) -> list[TrustAnchorOut]:
    return [TrustAnchorOut.model_validate(a) for a in await trust_store.list_anchors(session)]


@router.post("/anchors", response_model=TrustAnchorOut, status_code=status.HTTP_201_CREATED)
async def add_anchor(
    payload: TrustAnchorCreate, session: SessionDep, acting: AdminUser
) -> TrustAnchorOut:
    anchor = await trust_store.add_anchor(
        session, name=payload.name, pem=payload.certificate_pem, added_by=acting
    )
    return TrustAnchorOut.model_validate(anchor)


@router.patch("/anchors/{anchor_id}", response_model=TrustAnchorOut)
async def patch_anchor(
    anchor_id: str, payload: TrustAnchorPatch, session: SessionDep, _: AdminUser
) -> TrustAnchorOut:
    anchor = await trust_store.set_anchor_enabled(session, anchor_id, payload.enabled)
    return TrustAnchorOut.model_validate(anchor)


@router.delete("/anchors/{anchor_id}", response_model=Message)
async def delete_anchor(anchor_id: str, session: SessionDep, _: AdminUser) -> Message:
    await trust_store.delete_anchor(session, anchor_id)
    return Message(detail="Trust anchor removed")


@router.get("/allowlist", response_model=list[AllowlistOut])
async def list_allowlist(session: SessionDep, _: Reader) -> list[AllowlistOut]:
    return [AllowlistOut.model_validate(e) for e in await trust_store.list_allowlist(session)]


@router.post("/allowlist", response_model=AllowlistOut, status_code=status.HTTP_201_CREATED)
async def add_allowlist(
    payload: AllowlistCreate, session: SessionDep, acting: AdminUser
) -> AllowlistOut:
    entry = await trust_store.add_allowlist_entry(
        session,
        subject_pattern=payload.subject_pattern,
        issuer_spki_sha256=payload.issuer_spki_sha256,
        note=payload.note,
        added_by=acting,
    )
    return AllowlistOut.model_validate(entry)


@router.delete("/allowlist/{entry_id}", response_model=Message)
async def delete_allowlist(entry_id: str, session: SessionDep, _: AdminUser) -> Message:
    await trust_store.delete_allowlist_entry(session, entry_id)
    return Message(detail="Allow-list entry removed")
