"""Idempotent demo-data seeder.

    python -m app.seeds.seed

Creates one account per role if the users table is empty.

* dev / test: every demo account shares a fixed, documented password so login is
  predictable. Override with SEED_PASSWORD.
* prod: a strong random password is generated per account and printed once.

Never run against production data that has real users.
"""

from __future__ import annotations

import asyncio
import os
import secrets

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User

_DEMO_USERS: list[tuple[str, str, UserRole]] = [
    ("admin@egreen.local", "Ada Admin", UserRole.ADMIN),
    ("analyst@egreen.local", "Nate Analyst", UserRole.ANALYST),
    ("auditor@egreen.local", "Uma Auditor", UserRole.AUDITOR),
    ("viewer@egreen.local", "Vic Viewer", UserRole.VIEWER),
]

# Fixed dev/test password (meets the 12-char policy). Not for production.
DEV_PASSWORD = "EgreenQuanta!2026"  # noqa: S105 - documented dev-only demo credential


def _password_for(role: UserRole) -> str:
    override = os.environ.get("SEED_PASSWORD")
    if override:
        return override
    if settings.is_prod:
        return f"Egq-{role.value}-{secrets.token_urlsafe(12)}"
    return DEV_PASSWORD


async def seed() -> None:
    async with SessionLocal() as session:
        existing = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if existing:
            print(f"[seed] users table already has {existing} rows - nothing to do.")
            return

        creds: list[tuple[str, str, str]] = []
        for email, name, role in _DEMO_USERS:
            password = _password_for(role)
            session.add(
                User(
                    email=email,
                    full_name=name,
                    role=role,
                    hashed_password=hash_password(password),
                )
            )
            creds.append((email, password, role.value))
        await session.commit()

    print("\n[seed] created demo accounts:\n")
    print(f"  {'email':<26} {'password':<26} role")
    print(f"  {'-' * 26} {'-' * 26} ----")
    for email, password, role_name in creds:
        print(f"  {email:<26} {password:<26} {role_name}")
    if settings.is_prod:
        print("\n[seed] production passwords are random and shown ONCE - store them now.\n")
    else:
        print(f"\n[seed] dev/test password is fixed: {DEV_PASSWORD}\n")


if __name__ == "__main__":
    asyncio.run(seed())
