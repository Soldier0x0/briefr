import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from auth_middleware import session_auth_middleware

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from metrics.request_counter import increment_request_count

load_dotenv()

from settings import production_posture_warnings, settings
from structured_logging import configure_logging, request_id_var

configure_logging()
logger = logging.getLogger(__name__)
access_logger = logging.getLogger("briefr.access")

# Accept a caller-supplied X-Request-ID only when it is shaped like an ID.
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")

from database import init_db, run_postgres_migrations
from db.connection import PoolExhaustedError, close_pool, init_pool
from db.config import is_postgres, resolve_database_url
from resilient_client import close_client
from tracking import flush_api_usage_pending
from webhooks.ssrf import close_webhook_client
from webhooks.destinations import sync_env_destinations_to_db
from routers import admin as admin_router
from routers import atlas as atlas_router
from routers import auth as auth_router
from routers import me as me_router
from routers import notifications_me as notifications_me_router
from routers import brief as brief_router
from routers import correlation as correlation_router
from routers import config as config_router
from routers import cves as cves_router
from routers import forge as forge_router
from routers import health as health_router
from routers import ioc as ioc_router
from routers import meta as meta_router
from routers import detection_backlog as detection_backlog_router
from routers import proof as proof_router
from routers import refresh as refresh_router
from routers import threat_model as threat_model_router
from security_architecture.routers import security_architecture as security_architecture_router
from routers import wallboard as wallboard_router
from routers import watchlist as watchlist_router
from scheduler import (
    maybe_run_on_startup,
    start_scheduler,
    stop_scheduler,
    wait_for_running_jobs,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backup.manager import ensure_db_or_restore

    backend = "postgresql" if is_postgres() else "sqlite"
    logger.info("main.py lifespan: starting backend (%s)", backend)

    if settings.briefr_require_postgres and not is_postgres():
        raise RuntimeError(
            "BRIEFR_REQUIRE_POSTGRES=1 but DATABASE_URL is not set to a postgresql:// DSN. "
            "Migrate via Admin -> Database, apply DATABASE_URL, and restart."
        )

    if not is_postgres():
        recovery = ensure_db_or_restore()
        if recovery.get("status") == "restored":
            logger.warning(
                "Recovered corrupt database from backup: %s",
                recovery.get("archive"),
            )
    else:
        db_target = resolve_database_url()
        host = db_target.split("@")[-1] if "@" in db_target else db_target
        logger.info("main.py lifespan: DATABASE_URL=%s", host)
        try:
            await run_postgres_migrations()
        except Exception:
            logger.error("main.py lifespan: STOPPED — Alembic migrations failed (see database.py log above)")
            raise

    try:
        await init_pool()
    except Exception:
        if is_postgres():
            logger.error(
                "main.py lifespan: STOPPED — cannot open PostgreSQL pool (see db/connection.py log above). "
                "Is Postgres running? Is DATABASE_URL correct?"
            )
        raise

    await init_db()
    from operator_settings import bootstrap_operator_settings

    await bootstrap_operator_settings()
    logger.info("main.py lifespan: database ready")
    if settings.is_production:
        for posture in production_posture_warnings():
            logger.warning(
                "Production posture: %s — %s", posture["flag"], posture["message"]
            )
    await sync_env_destinations_to_db()
    if os.environ.get("BRIEFR_SCHEDULER_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        start_scheduler()
    else:
        logger.info(
            "main.py lifespan: scheduler disabled (BRIEFR_SCHEDULER_ENABLED=0) — API-only worker"
        )
    await maybe_run_on_startup()
    # Q1: durable Procrastinate worker (feature-flagged; Postgres only).
    try:
        from jobs.worker import start_inprocess_worker

        if await start_inprocess_worker():
            logger.info("main.py lifespan: Procrastinate in-process worker started")
    except Exception:
        logger.exception("main.py lifespan: Procrastinate worker failed to start (continuing)")
    logger.info("main.py lifespan: startup complete — accepting requests")
    yield
    logger.info("main.py lifespan: shutting down")
    # PR-R1 (REST-001/REST-002): stop new triggers first, then wait — bounded
    # by SHUTDOWN_DRAIN_TIMEOUT_SECONDS (default 10s) each — for running jobs
    # and fire-and-forget tasks, so an in-flight ingest can finish its commit
    # instead of dying mid-write.
    try:
        from jobs.worker import stop_inprocess_worker

        await stop_inprocess_worker()
    except Exception:
        logger.exception("main.py lifespan: Procrastinate worker stop failed")
    stop_scheduler()
    await wait_for_running_jobs()
    from task_registry import drain_background_tasks

    await drain_background_tasks()
    await flush_api_usage_pending()
    await close_pool()
    await close_client()
    await close_webhook_client()


app = FastAPI(
    title="BRIEFR CVE Intelligence API",
    version="1.5.0",
    description=(
        "CVE intelligence API for BRIEFR. "
        "Licensed under AGPL-3.0-or-later. "
        "Copyright © 2026 Sai Harsha Vardhan."
    ),
    contact={"name": "BRIEFR", "url": "https://projectjupiter.in"},
    license_info={
        "name": "AGPL-3.0-or-later",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None if settings.is_production else "/api/redoc",
    openapi_url=None if settings.is_production else "/api/openapi.json",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)


@app.exception_handler(PoolExhaustedError)
async def pool_exhausted_handler(request: Request, exc: PoolExhaustedError):
    access_logger.warning(
        "Pool exhausted on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Server is busy — please retry in a few seconds."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-BRIEFR-Wallboard-Token",
    ],
)

app.add_middleware(GZipMiddleware, minimum_size=256)

app.include_router(refresh_router.router)


@app.middleware("http")
async def enforce_session_auth(request: Request, call_next):
    return await session_auth_middleware(request, call_next)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
    )
    return response


# Added last so it is the outermost middleware: the request_id contextvar is
# set before any other middleware or route code logs anything (§5.5).
@app.middleware("http")
async def request_context(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "").strip()
    if _REQUEST_ID_RE.fullmatch(incoming):
        request_id = incoming
    else:
        request_id = uuid.uuid4().hex[:16]
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    increment_request_count()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        access_logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    except Exception:
        # Log here, while the request_id contextvar is still set — uvicorn's
        # own traceback is emitted after the finally below has reset it.
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        access_logger.error(
            "%s %s unhandled exception after %.1fms",
            request.method,
            request.url.path,
            duration_ms,
            exc_info=True,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
            },
        )
        raise
    finally:
        request_id_var.reset(token)


# Routers are included in the exact pre-split route registration sequence so
# the OpenAPI route list stays byte-identical (snapshot-tested in
# tests/test_router_split.py) and FastAPI keeps matching
# /api/cves/{cve_id} after literal siblings such as /api/cves/export.
app.include_router(health_router.router)
app.include_router(cves_router.changes_router)
app.include_router(meta_router.info_router)
app.include_router(cves_router.list_router)
app.include_router(atlas_router.router)
app.include_router(cves_router.detail_router)
app.include_router(ioc_router.router)
app.include_router(cves_router.intel_router)
app.include_router(meta_router.router)
app.include_router(config_router.router)
app.include_router(forge_router.router)
app.include_router(threat_model_router.router)
app.include_router(security_architecture_router.router)
app.include_router(proof_router.router)
app.include_router(detection_backlog_router.router)
app.include_router(brief_router.router)
app.include_router(correlation_router.router)
app.include_router(watchlist_router.router)
app.include_router(admin_router.router)
app.include_router(wallboard_router.public_router)
app.include_router(wallboard_router.router)
# Built-in app login (decision 2026-06-11): appended after wallboard_router —
# additive only, see test_router_split.py's EXPECTED_ROUTES comment.
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(notifications_me_router.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
