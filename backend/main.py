import asyncio
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
    get_nvd_sync_watermark,
    init_db,
    set_ioc_cache,
)
from enrichment.ioc import lookup_ioc
from feeds.osv import fetch_osv_by_cve
from scheduler import (
    get_next_scheduled_refresh_utc,
    get_refresh_schedule,
    maybe_run_on_startup,
    refresh_in_progress,
    run_daily_refresh,
    start_scheduler,
    stop_scheduler,
)
from tracking import get_usage_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    await maybe_run_on_startup()
    yield
    stop_scheduler()


app = FastAPI(
    title="BRIEFR CVE Intelligence API",
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
    d["has_poc"] = bool(d.get("has_poc", 0))
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
        nvd_sync_watermark = await get_nvd_sync_watermark(db)
    finally:
        await db.close()

    now_utc = datetime.now(timezone.utc)
    default_tz = os.environ.get("DEFAULT_TIMEZONE", "UTC")
    display_tz = tz or default_tz

    next_refresh_utc = get_next_scheduled_refresh_utc()
    refresh_schedule = get_refresh_schedule()

    response: dict = {
        "status": "ok",
        "cve_count": cve_count,
        "last_updated": last_updated,
        "nvd_sync_watermark": nvd_sync_watermark,
        "refresh_in_progress": refresh_in_progress(),
        "next_refresh_at_utc": next_refresh_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_refresh_in_user_tz": _format_time_in_tz(next_refresh_utc, display_tz),
        "next_refresh_in_scheduler_tz": _format_time_in_tz(
            next_refresh_utc, refresh_schedule["timezone"]
        ),
        "refresh_schedule": refresh_schedule,
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


def _text_match_or_clause(terms: list[str]) -> tuple[str, list]:
    """Match any term against description, summary, or affected_products JSON."""
    if not terms:
        return "", []
    parts = []
    bind: list = []
    for term in terms:
        like = f"%{term.lower()}%"
        parts.append(
            "(LOWER(cve_id) LIKE ? OR LOWER(description) LIKE ? "
            "OR LOWER(summary) LIKE ? OR LOWER(affected_products) LIKE ?)"
        )
        bind.extend([like, like, like, like])
    return "(" + " OR ".join(parts) + ")", bind


def _parse_stack_terms(stack: str | None) -> list[str]:
    if not stack:
        return []
    return [p.strip().lower() for p in stack.split(",") if p.strip()]


def _stack_match_clause(stack: str | None) -> tuple[str, list, list[str]]:
    """Match stack terms against description or affected_products (parameterised)."""
    terms = _parse_stack_terms(stack)
    if not terms:
        return "", [], []

    parts: list[str] = []
    params: list = []
    for term in terms:
        parts.append("(LOWER(description) LIKE ? OR LOWER(affected_products) LIKE ?)")
        like = f"%{term}%"
        params.extend([like, like])

    return "(" + " OR ".join(parts) + ")", params, terms


CVE_ORDER_BY = """
    ORDER BY
        published DESC,
        CASE severity
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            WHEN 'LOW' THEN 4
            ELSE 5
        END,
        CASE WHEN epss_score IS NOT NULL THEN epss_score ELSE -1 END DESC
"""

CVE_SELECT = """
    SELECT cve_id, description, cvss_score, severity, published, modified,
           affected_products, mitre_technique, summary, is_kev, epss_score,
           has_poc, patch_available, source_urls, cwe_ids, updated_at
    FROM cves
"""


def _build_cve_filters(
    severity: str | None,
    kev_only: bool,
    poc_only: bool,
    epss_min: float | None,
    search: str | None,
    stack: str | None,
    vendors: str | None,
) -> tuple[list[str], list, list[str]]:
    conditions: list[str] = []
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
        conditions.append("has_poc = 1")

    if epss_min is not None:
        conditions.append("epss_score IS NOT NULL AND epss_score >= ?")
        params.append(epss_min)

    if search:
        conditions.append("(cve_id LIKE ? OR description LIKE ?)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    stack_clause, stack_params, stack_products = _stack_match_clause(stack)
    if stack_clause:
        conditions.append(stack_clause)
        params.extend(stack_params)

    if vendors:
        vendor_list = [v.strip() for v in vendors.split(",") if v.strip()]
        vendor_clause, vendor_params = _text_match_or_clause(vendor_list)
        if vendor_clause:
            conditions.append(vendor_clause)
            params.extend(vendor_params)

    return conditions, params, stack_products


def _sort_by_stack_relevance(cve_list: list[dict], stack_products: list[str]) -> list[dict]:
    if not stack_products:
        return cve_list

    def relevance_score(cve: dict) -> int:
        products = [p.lower() for p in cve.get("affected_products", [])]
        desc = (cve.get("description") or "").lower()
        summary = (cve.get("summary") or "").lower()
        score = 0
        for sp in stack_products:
            if sp in desc or sp in summary:
                score += 1
                continue
            for p in products:
                if sp in p:
                    score += 1
                    break
        return score

    return sorted(cve_list, key=relevance_score, reverse=True)


@app.get("/api/cves")
async def list_cves(
    severity: str | None = Query(default=None, description="CRITICAL/HIGH/MEDIUM/LOW"),
    kev_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    epss_min: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    vendors: str | None = Query(default=None, max_length=500),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    conditions, params, stack_products = _build_cve_filters(
        severity, kev_only, poc_only, epss_min, search, stack, vendors
    )

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
            f"{CVE_SELECT} {where_clause} {CVE_ORDER_BY} LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
    finally:
        await db.close()

    cve_list = _sort_by_stack_relevance([_row_to_cve_dict(row) for row in rows], stack_products)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
        "data": cve_list,
    }


@app.get("/api/cves/export")
async def export_cves(
    severity: str | None = Query(default=None),
    kev_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    epss_min: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    vendors: str | None = Query(default=None, max_length=500),
    max_rows: int = Query(default=500, ge=1, le=500),
):
    """Return up to 500 CVE rows matching filters (for CSV export)."""
    conditions, params, stack_products = _build_cve_filters(
        severity, kev_only, poc_only, epss_min, search, stack, vendors
    )

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            f"{CVE_SELECT} {where_clause} {CVE_ORDER_BY} LIMIT ?",
            params + [max_rows],
        )
    finally:
        await db.close()

    cve_list = _sort_by_stack_relevance([_row_to_cve_dict(row) for row in rows], stack_products)
    return {"total": len(cve_list), "data": cve_list}


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
                   has_poc, patch_available, source_urls, cwe_ids, updated_at
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
        if not cve.get("summary"):
            for entry in osv_data:
                osv_summary = (entry.get("summary") or "").strip()
                if osv_summary:
                    cve["summary"] = osv_summary
                    break
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


@app.post("/api/refresh")
async def manual_refresh():
    if refresh_in_progress():
        raise HTTPException(
            status_code=409,
            detail="A refresh is already running. Wait for it to finish before starting another.",
        )
    asyncio.create_task(run_daily_refresh())
    return {"status": "ok", "message": "Refresh started in background"}


@app.get("/api/kev/deadlines")
async def kev_deadlines(
    sort: str = Query(default="recent", description="Sort order: recent (by dateAdded DESC) or urgent (by dueDate ASC)"),
):
    order_clause = (
        "ORDER BY date_added DESC"
        if sort == "recent"
        else "ORDER BY due_date ASC"
    )
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, product, short_description, required_action, due_date, date_added, updated_at
            FROM kev_deadlines
            {order_clause}
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
