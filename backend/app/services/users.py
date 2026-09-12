"""User management service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import revoke_all_user_tokens


async def get_user(session: AsyncSession, user_id: str) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    return user


async def list_users(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[User], int]:
    total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        (
            await session.execute(
                select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    email = payload.email.strip().lower()
    exists = (
        await session.execute(select(User.id).where(User.email == email))
    ).scalar_one_or_none()
    if exists:
        raise ConflictError("A user with that email already exists")
    user = User(
        email=email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession, user_id: str, payload: UserUpdate, *, acting_user: User
) -> User:
    user = await get_user(session, user_id)

    if payload.role is not None and payload.role != user.role:
        await _guard_last_admin(session, user, new_role=payload.role)
        user.role = payload.role

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.is_active is not None and payload.is_active != user.is_active:
        if not payload.is_active and user.id == acting_user.id:
            raise ForbiddenError("You cannot deactivate your own account")
        if not payload.is_active:
            await _guard_last_admin(session, user, deactivating=True)
        user.is_active = payload.is_active
        if not payload.is_active:
            await revoke_all_user_tokens(session, user.id)

    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
        await revoke_all_user_tokens(session, user.id)

    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: str, *, acting_user: User) -> None:
    user = await get_user(session, user_id)
    if user.id == acting_user.id:
        raise ForbiddenError("You cannot delete your own account")
    await _guard_last_admin(session, user, deleting=True)
    await revoke_all_user_tokens(session, user.id)
    await session.delete(user)
    await session.commit()


async def _guard_last_admin(
    session: AsyncSession,
    user: User,
    *,
    new_role: UserRole | None = None,
    deactivating: bool = False,
    deleting: bool = False,
) -> None:
    """Refuse the change if it would leave zero active admins."""
    is_demotion = new_role is not None and new_role != UserRole.ADMIN
    if user.role != UserRole.ADMIN or not (is_demotion or deactivating or deleting):
        return
    active_admins = (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True), User.id != user.id)
        )
    ).scalar_one()
    if int(active_admins) == 0:
        raise ConflictError("Refusing to remove the last active administrator")
