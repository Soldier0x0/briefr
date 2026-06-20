import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from settings import settings
from structured_logging import configure_logging, request_id_var

configure_logging()
logger = logging.getLogger(__name__)
access_logger = logging.getLogger("briefr.access")

# Accept a caller-supplied X-Request-ID only when it is shaped like an ID.
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")

from database import init_db
from db.connection import close_pool, init_pool
from resilient_client import close_client
from routers import admin as admin_router
from routers import atlas as atlas_router
from routers import brief as brief_router
from routers import config as config_router
from routers import cves as cves_router
from routers import forge as forge_router
from routers import health as health_router
from routers import ioc as ioc_router
from routers import meta as meta_router
from routers import refresh as refresh_router
from routers import watchlist as watchlist_router
from scheduler import (
    maybe_run_on_startup,
    start_scheduler,
    stop_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backup.manager import ensure_db_or_restore
    from db.config import is_postgres

    if not is_postgres():
        recovery = ensure_db_or_restore()
        if recovery.get("status") == "restored":
            logger.warning(
                "Recovered corrupt database from backup: %s",
                recovery.get("archive"),
            )
    await init_pool()
    await init_db()
    start_scheduler()
    await maybe_run_on_startup()
    yield
    stop_scheduler()
    await close_pool()
    await close_client()


app = FastAPI(
    title="BRIEFR CVE Intelligence API",
    version="1.0.0",
    description=(
        "Proprietary CVE intelligence API. "
        "Copyright © 2026 Sai Harsha Vardhan. All rights reserved."
    ),
    contact={"name": "BRIEFR", "url": "https://projectjupiter.in"},
    license_info={
        "name": "Proprietary — All Rights Reserved",
        "url": "https://projectjupiter.in/terms",
    },
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None if settings.is_production else "/api/redoc",
    openapi_url=None if settings.is_production else "/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-BRIEFR-Admin-Key"],
)

app.include_router(refresh_router.router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
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
                "client": request.client.host if request.client else "",
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
                "client": request.client.host if request.client else "",
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
app.include_router(brief_router.router)
app.include_router(watchlist_router.router)
app.include_router(admin_router.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
