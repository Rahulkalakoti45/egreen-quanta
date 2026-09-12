"""Audit-log browsing, integrity verification and signed export (Module 6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_role
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.audit import AnchorResult, AuditPage, AuditRow, ChainVerification
from app.services.audit import chain

router = APIRouter(prefix="/audit", tags=["audit"])

Auditor = Annotated[User, Depends(require_role(UserRole.AUDITOR, UserRole.ADMIN))]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("", response_model=AuditPage)
async def list_audit(
    session: SessionDep,
    _: Auditor,
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    target_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditPage:
    stmt = select(AuditLog).order_by(AuditLog.seq.desc())
    count_stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
        count_stmt = count_stmt.where(AuditLog.action.like(f"{action}%"))
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
        count_stmt = count_stmt.where(AuditLog.target_id == target_id)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return AuditPage(
        items=[AuditRow.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/verify", response_model=ChainVerification)
async def verify(
    session: SessionDep, _: Auditor, start_seq: int = Query(1, ge=1)
) -> ChainVerification:
    return ChainVerification(**await chain.verify_chain(session, start_seq=start_seq))


@router.get("/export")
async def export(
    session: SessionDep,
    _: Auditor,
    start_seq: int = Query(1, ge=1),
    end_seq: int | None = Query(None, ge=1),
) -> Response:
    payload = await chain.export_range(session, start_seq=start_seq, end_seq=end_seq)
    import json

    body = json.dumps(payload, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="audit-{start_seq}-export.json"'},
    )


@router.post("/anchor", response_model=AnchorResult)
async def anchor(session: SessionDep, actor: Admin) -> AnchorResult:
    row = await chain.create_anchor(session, actor_id=actor.id)
    return AnchorResult(
        seq=row.seq,
        head_seq=int(row.meta["head_seq"]),
        head_hash=row.meta["head_hash"],
        signed="signature" in row.meta,
    )
