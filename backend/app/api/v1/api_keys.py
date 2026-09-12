"""API-key administration routes (admin + analyst)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, require_min_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedOut, ApiKeyOut
from app.schemas.common import Message, Page
from app.services import api_keys as api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

Manager = Annotated[User, Depends(require_min_role(UserRole.ANALYST))]


@router.get("", response_model=Page[ApiKeyOut])
async def list_api_keys(
    session: SessionDep,
    _: Manager,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[ApiKeyOut]:
    rows, total = await api_key_service.list_api_keys(session, limit=limit, offset=offset)
    return Page(
        items=[ApiKeyOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate, session: SessionDep, acting: Manager
) -> ApiKeyCreatedOut:
    record, full_key = await api_key_service.create_api_key(session, payload, created_by=acting)
    return ApiKeyCreatedOut(**ApiKeyOut.model_validate(record).model_dump(), api_key=full_key)


@router.delete("/{key_id}", response_model=Message)
async def revoke_api_key(key_id: str, session: SessionDep, acting: Manager) -> Message:
    await api_key_service.revoke_api_key(session, key_id, acting_user=acting)
    return Message(detail="API key revoked")
