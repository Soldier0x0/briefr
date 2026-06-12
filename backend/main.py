import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from database import init_db
from resilient_client import close_client
from routers import atlas as atlas_router
from routers import config as config_router
from routers import cves as cves_router
from routers import health as health_router
from routers import ioc as ioc_router
from routers import meta as meta_router
from routers import refresh as refresh_router
from scheduler import (
    maybe_run_on_startup,
    start_scheduler,
    stop_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backup.manager import ensure_db_or_restore

    recovery = ensure_db_or_restore()
    if recovery.get("status") == "restored":
        logger.warning(
            "Recovered corrupt database from backup: %s",
            recovery.get("archive"),
        )
    await init_db()
    start_scheduler()
    await maybe_run_on_startup()
    yield
    stop_scheduler()
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
