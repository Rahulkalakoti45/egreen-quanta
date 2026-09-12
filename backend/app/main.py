"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import defusedxml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.audit.middleware import AuditMiddleware

# Defence in depth: neutralise the stdlib XML parsers against entity-expansion /
# external-entity attacks before anything (pyHanko, asn1crypto) touches untrusted XML.
defusedxml.defuse_stdlib()

log = get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    log.info(
        "startup",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
        db="sqlite" if settings.is_sqlite else "postgresql",
    )
    await _sync_detection_rules()

    started_scheduler = False
    if settings.scheduler_enabled and not settings.is_test:
        try:
            from app.workers.scheduler import default_jobs, scheduler

            scheduler.start(default_jobs())
            started_scheduler = True
        except Exception as exc:  # pragma: no cover
            log.warning("scheduler_start_failed", error=str(exc))

    yield

    if started_scheduler:
        from app.workers.scheduler import scheduler

        await scheduler.stop()
    log.info("shutdown")


async def _sync_detection_rules() -> None:
    """Ensure the detection_rules table has a row for every catalog entry."""
    try:
        from sqlalchemy import inspect as sa_inspect

        from app.db.session import SessionLocal, engine
        from app.services.detection.engine import sync_rules

        async with engine.connect() as conn:
            has_table = await conn.run_sync(
                lambda sync_conn: sa_inspect(sync_conn).has_table("detection_rules")
            )
        if not has_table:
            log.warning("detection_rules table missing - run migrations")
            return
        async with SessionLocal() as session:
            await sync_rules(session)
    except Exception as exc:
        log.warning("detection_rule_sync_failed", error=str(exc))


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Quantum-inspired cyber threat detection for digital signature security",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- middleware ---
    # Starlette applies the LAST-added middleware as the outermost layer, so the
    # effective request path is: TrustedHost -> BodySizeLimit -> Audit ->
    # RequestContext -> SecurityHeaders -> CORS -> router.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    if not settings.is_test:
        app.add_middleware(AuditMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    allow_hosts = [h for h in settings.allowed_hosts if h]
    if settings.is_prod and allow_hosts and allow_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allow_hosts)

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/healthz", tags=["system"], summary="Liveness probe")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": settings.app_name, "docs": "/docs", "api": settings.api_v1_prefix}

    return app


app = create_app()
