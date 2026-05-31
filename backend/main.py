import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from database import (
    get_db,
    get_cve_count,
    get_ioc_cache,
    get_last_updated,
    init_db,
    set_ioc_cache,
)
from enrichment.ioc import lookup_ioc
from feeds.osv import fetch_osv_by_cve
from scheduler import maybe_run_on_startup, start_scheduler, stop_scheduler
from tracking import get_usage_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    await maybe_run_on_startup()
    yield
    stop_scheduler()


app = FastAPI(
    title="VEKTOR CVE Intelligence API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


class IocLookupRequest(BaseModel):
    value: str
    type: str


def _row_to_cve_dict(row) -> dict:
    d = dict(row)
    for field in ("affected_products", "source_urls", "cwe_ids"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    d["is_kev"] = bool(d.get("is_kev", 0))
    d["patch_available"] = bool(d.get("patch_available", 0))
    return d


def _format_time_in_tz(dt: datetime, tz_name: str) -> dict:
    try:
        tz = ZoneInfo(tz_name)
        local = dt.astimezone(tz)
        return {
            "iso": local.isoformat(),
            "display": local.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "timezone": tz_name,
            "utc_offset": local.strftime("%z"),
        }
    except (ZoneInfoNotFoundError, Exception):
        return {"error": f"Unknown timezone: {tz_name}"}


@app.get("/api/health")
async def health(
    tz: str | None = Query(
        default=None,
        description="IANA timezone name for local time display (e.g. Asia/Kolkata, America/New_York)",
    ),
):
    db = await get_db()
    try:
        cve_count = await get_cve_count(db)
        last_updated = await get_last_updated(db)
    finally:
        await db.close()

    now_utc = datetime.now(timezone.utc)
    default_tz = os.environ.get("DEFAULT_TIMEZONE", "UTC")
    display_tz = tz or default_tz

    response: dict = {
        "status": "ok",
        "cve_count": cve_count,
        "last_updated": last_updated,
        "server_time_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "server_time_local": _format_time_in_tz(now_utc, display_tz),
    }
    return response


@app.get("/api/time")
async def server_time(
    tz: str | None = Query(
        default=None,
        description="IANA timezone name (e.g. Asia/Kolkata). Defaults to DEFAULT_TIMEZONE env var.",
    ),
):
    now_utc = datetime.now(timezone.utc)
    default_tz = os.environ.get("DEFAULT_TIMEZONE", "UTC")
    display_tz = tz or default_tz

    result = {
        "utc": {
            "iso": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "display": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "epoch": int(now_utc.timestamp()),
        },
        "local": _format_time_in_tz(now_utc, display_tz),
    }

    if tz and tz != default_tz:
        result["default_tz"] = _format_time_in_tz(now_utc, default_tz)

    return result


@app.get("/api/stats")
async def stats():
    db = await get_db()
    try:
        rows_critical = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM cves WHERE severity = 'CRITICAL'"
        )
        rows_high = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM cves WHERE severity = 'HIGH'"
        )
        rows_kev = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM cves WHERE is_kev = 1"
        )
        rows_patched = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM cves WHERE patch_available = 1"
        )
        rows_24h = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM cves WHERE published >= datetime('now', '-1 day')"
        )
    finally:
        await db.close()

    return {
        "critical": rows_critical[0]["cnt"] if rows_critical else 0,
        "high": rows_high[0]["cnt"] if rows_high else 0,
        "kev_count": rows_kev[0]["cnt"] if rows_kev else 0,
        "patched": rows_patched[0]["cnt"] if rows_patched else 0,
        "last_24h": rows_24h[0]["cnt"] if rows_24h else 0,
    }


@app.get("/api/cves")
async def list_cves(
    severity: str | None = Query(default=None, description="CRITICAL/HIGH/MEDIUM/LOW"),
    kev_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    conditions = []
    params: list = []

    if severity:
        severity_upper = severity.upper()
        if severity_upper not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise HTTPException(status_code=400, detail="Invalid severity value")
        conditions.append("severity = ?")
        params.append(severity_upper)

    if kev_only:
        conditions.append("is_kev = 1")

    if poc_only:
        conditions.append("patch_available = 0")

    if search:
        conditions.append("(cve_id LIKE ? OR description LIKE ?)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    stack_products = []
    if stack:
        stack_products = [p.strip().lower() for p in stack.split(",") if p.strip()]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    offset = (page - 1) * limit

    db = await get_db()
    try:
        count_rows = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM cves {where_clause}",
            params,
        )
        total = count_rows[0]["cnt"] if count_rows else 0

        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, mitre_technique, summary, is_kev, epss_score,
                   patch_available, source_urls, cwe_ids, updated_at
            FROM cves
            {where_clause}
            ORDER BY
                CASE WHEN epss_score IS NOT NULL THEN epss_score ELSE 0 END DESC,
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    ELSE 5
                END,
                published DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
    finally:
        await db.close()

    cve_list = [_row_to_cve_dict(row) for row in rows]

    if stack_products:
        def relevance_score(cve: dict) -> int:
            products = [p.lower() for p in cve.get("affected_products", [])]
            score = 0
            for sp in stack_products:
                for p in products:
                    if sp in p:
                        score += 1
                        break
            return score

        cve_list.sort(key=relevance_score, reverse=True)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
        "data": cve_list,
    }


@app.get("/api/cves/{cve_id}")
async def get_cve(cve_id: str):
    if not cve_id.upper().startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, mitre_technique, summary, is_kev, epss_score,
                   patch_available, source_urls, cwe_ids, updated_at
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_id.upper(),),
        )
    finally:
        await db.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

    cve = _row_to_cve_dict(rows[0])

    try:
        osv_data = await fetch_osv_by_cve(cve_id.upper())
        cve["osv_packages"] = osv_data
    except Exception as exc:
        logger.error("OSV lookup failed for %s: %s", cve_id, exc)
        cve["osv_packages"] = []

    return cve


@app.post("/api/ioc/lookup")
async def ioc_lookup(body: IocLookupRequest):
    value = body.value.strip()
    ioc_type = body.type.strip().lower()

    if not value:
        raise HTTPException(status_code=400, detail="value is required")
    if ioc_type not in ("ip", "hash", "domain"):
        raise HTTPException(status_code=400, detail="type must be ip, hash, or domain")
    if len(value) > 512:
        raise HTTPException(status_code=400, detail="value too long")

    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    abuse_key = os.environ.get("ABUSEIPDB_API_KEY", "")

    db = await get_db()
    try:
        cached = await get_ioc_cache(db, value)
        if cached is not None:
            cached["cached"] = True
            return cached

        result = await lookup_ioc(value, ioc_type, vt_key, abuse_key)
        result["cached"] = False

        await set_ioc_cache(db, value, ioc_type, result)
        await db.commit()
    finally:
        await db.close()

    return result


@app.get("/api/kev/deadlines")
async def kev_deadlines():
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, product, short_description, required_action, due_date, updated_at
            FROM kev_deadlines
            WHERE due_date IS NOT NULL AND due_date != ''
            ORDER BY due_date ASC
            """
        )
    finally:
        await db.close()

    return {"data": [dict(row) for row in rows]}


@app.get("/api/usage")
async def api_usage():
    now_utc = datetime.now(timezone.utc)
    stats = await get_usage_stats()
    return {
        "as_of_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today_date_utc": now_utc.strftime("%Y-%m-%d"),
        "this_month_utc": now_utc.strftime("%Y-%m"),
        "services": stats,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
