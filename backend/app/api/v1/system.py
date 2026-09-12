"""System endpoints: liveness, readiness, build info."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import settings
from app.db.session import get_session

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/system/info", summary="Build & environment info")
async def system_info() -> dict:
    return {
        "name": settings.app_name,
        "version": __version__,
        "environment": settings.app_env,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "ml_enabled": settings.ml_enabled,
        "outbound_revocation": settings.outbound_revocation,
    }


@router.get("/readyz", summary="Readiness probe (checks the database)")
async def readyz(session: SessionDep) -> dict:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
