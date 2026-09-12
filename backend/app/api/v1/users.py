"""User administration routes (admin only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("", response_model=Page[UserOut])
async def list_users(
    session: SessionDep,
    _: AdminUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[UserOut]:
    rows, total = await user_service.list_users(session, limit=limit, offset=offset)
    return Page(
        items=[UserOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, _: AdminUser) -> UserOut:
    user = await user_service.create_user(session, payload)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, session: SessionDep, _: AdminUser) -> UserOut:
    user = await user_service.get_user(session, user_id)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, payload: UserUpdate, session: SessionDep, acting: AdminUser
) -> UserOut:
    user = await user_service.update_user(session, user_id, payload, acting_user=acting)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
async def delete_user(user_id: str, session: SessionDep, acting: AdminUser) -> Message:
    await user_service.delete_user(session, user_id, acting_user=acting)
    return Message(detail="User deleted")
