import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any

load_dotenv()

BRIEFR_ENV = os.environ.get("BRIEFR_ENV", "development").strip().lower()
BRIEFR_ADMIN_API_KEY = os.environ.get("BRIEFR_ADMIN_API_KEY", "").strip()
_IS_PRODUCTION = BRIEFR_ENV == "production"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from database import (
    get_atlas_case_studies,
    get_atlas_case_studies_for_cve,
    get_atlas_techniques_for_cve,
    get_atlas_techniques_grouped,
    get_db,
    get_cve_count,
    get_epss_history,
    get_ioc_cache,
    get_last_updated,
    get_nvd_sync_watermark,
    get_recent_cve_changes,
    get_related_cves,
    get_techniques_for_cve,
    get_top_techniques,
    count_ai_ml_profile_alerts,
    init_db,
    match_cves_for_assets,
    set_ioc_cache,
)
from feeds.extended import (
    greynoise_scans_for_cve,
    load_public_exploits_for_cve,
)
from feeds.otx import load_otx_pulses_for_cve, load_pulse_iocs, top_pulse_ipv4s
from scheduler import run_weekly_mitre_refresh
from enrichment.ioc import lookup_ioc
from feeds.osv import fetch_osv_by_cve
from scheduler import (
    get_ingest_status,
    get_ingest_intervals,
    get_next_scheduled_refresh_utc,
    get_refresh_schedule,
    maybe_run_on_startup,
    refresh_in_progress,
    run_daily_refresh,
    run_epss_sync,
    run_kev_sync,
    run_nvd_incremental_sync,
    start_scheduler,
    stop_scheduler,
)
from ai.summary import generate_executive_summary, generate_investigation_summary
from tracking import get_ioc_usage_stats, get_usage_stats
from templates.intelligence import (
    epss_sentence_or_fallback,
    exploit_sentence,
    exploits_from_cve,
    greynoise_sentence,
    otx_sentence,
    kev_sentence,
    patch_sentence,
    severity_sentence,
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
    docs_url=None if _IS_PRODUCTION else "/api/docs",
    redoc_url=None if _IS_PRODUCTION else "/api/redoc",
    openapi_url=None if _IS_PRODUCTION else "/api/openapi.json",
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


def _require_admin_key(request: Request) -> None:
    """When BRIEFR_ADMIN_API_KEY is set, admin routes require X-BRIEFR-Admin-Key."""
    if not BRIEFR_ADMIN_API_KEY:
        return
    provided = request.headers.get("X-BRIEFR-Admin-Key", "")
    if provided != BRIEFR_ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Admin API key required")


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


class InvestigationPivotRef(BaseModel):
    type: str | None = None
    id: str | None = None


class InvestigationItemRef(BaseModel):
    type: str
    id: str
    description: str = ""
    pivotFrom: InvestigationPivotRef | None = None


class InvestigationSummaryRequest(BaseModel):
    items: list[InvestigationItemRef]
    duration_minutes: int = Field(default=1, ge=1, le=10080)


class AssetMatchItem(BaseModel):
    product: str = Field(..., max_length=200)
    version: str = Field(default="", max_length=100)
    vendor: str = Field(default="", max_length=100)


class AssetMatchRequest(BaseModel):
    assets: list[AssetMatchItem] = Field(default_factory=list, max_length=500)



class AiSummaryRequest(BaseModel):
    cves: list[dict[str, Any]] = Field(default_factory=list)
    iocs: list[dict[str, Any]] = Field(default_factory=list)
    actors: list[dict[str, Any]] = Field(default_factory=list)
    investigation_duration: int = Field(default=1, ge=1, le=10080)


class IocLookupRequest(BaseModel):
    value: str
    type: str
    greynoise: bool = False


def _row_to_cve_dict(row) -> dict:
    d = dict(row)
    for field in ("affected_products", "source_urls", "cwe_ids"):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    for num_field in ("cvss_score", "epss_score"):
        if d.get(num_field) is not None:
            try:
                d[num_field] = float(d[num_field])
            except (TypeError, ValueError):
                d[num_field] = None
    d["is_kev"] = bool(d.get("is_kev", 0))
    d["has_poc"] = bool(d.get("has_poc", 0))
    d["patch_available"] = bool(d.get("patch_available", 0))
    d["has_ai_context"] = bool(d.get("has_ai_context", 0))
    kev_date = d.get("kev_date_added")
    d["kev_date_added"] = (kev_date or "").strip() or None
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
    ingest = get_ingest_status()

    response: dict = {
        "status": "ok",
        "cve_count": cve_count,
        "last_updated": last_updated,
        "nvd_sync_watermark": nvd_sync_watermark,
        "refresh_in_progress": refresh_in_progress(),
        "ingest": ingest,
        "next_nvd_sync_at_utc": next_refresh_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_nvd_sync_in_user_tz": _format_time_in_tz(next_refresh_utc, display_tz),
        "ingest_intervals": get_ingest_intervals(),
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


@app.get("/api/changes")
async def cve_changes(
    limit: int = Query(default=50, ge=1, le=500),
    field: str | None = Query(default=None, description="Filter: cvss_score, epss_score, is_kev, has_poc"),
    since_hours: int | None = Query(default=24, ge=1, le=168),
):
    """Recent tracked field changes for analyst awareness."""
    allowed = {"cvss_score", "epss_score", "is_kev", "has_poc"}
    if field is not None and field not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"field must be one of: {', '.join(sorted(allowed))}",
        )

    db = await get_db()
    try:
        changes = await get_recent_cve_changes(
            db,
            limit=limit,
            field_name=field,
            since_hours=since_hours,
        )
    finally:
        await db.close()

    return {"data": changes, "count": len(changes)}


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
async def stats(
    frameworks: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated AI/ML framework tokens for ai_ml_alerts count",
    ),
):
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
        fw_list = _parse_framework_list(frameworks)
        ai_ml_alerts = (
            await count_ai_ml_profile_alerts(db, fw_list) if fw_list else 0
        )
    finally:
        await db.close()

    return {
        "critical": rows_critical[0]["cnt"] if rows_critical else 0,
        "high": rows_high[0]["cnt"] if rows_high else 0,
        "kev_count": rows_kev[0]["cnt"] if rows_kev else 0,
        "patched": rows_patched[0]["cnt"] if rows_patched else 0,
        "last_24h": rows_24h[0]["cnt"] if rows_24h else 0,
        "ai_ml_alerts": ai_ml_alerts,
    }


@app.get("/api/stats/timeline")
async def stats_timeline(
    days: int = Query(default=90, ge=1, le=365),
):
    """Daily CVE counts grouped by published date (calendar day, UTC)."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT DATE(published) AS date,
                   COUNT(*) AS count,
                   SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
                   SUM(CASE WHEN is_kev = 1 THEN 1 ELSE 0 END) AS kev
            FROM cves
            WHERE published IS NOT NULL
              AND published != ''
              AND DATE(published) >= DATE('now', ?)
            GROUP BY DATE(published)
            ORDER BY date ASC
            """,
            (f"-{days - 1} days",),
        )
    finally:
        await db.close()

    by_date = {
        row["date"]: {
            "date": row["date"],
            "count": row["count"],
            "critical": row["critical"],
            "kev": row["kev"],
        }
        for row in rows
        if row["date"]
    }

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    timeline: list[dict] = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        entry = by_date.get(key)
        timeline.append(
            entry
            if entry
            else {"date": key, "count": 0, "critical": 0, "kev": 0}
        )
        cursor += timedelta(days=1)

    return timeline


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


def _is_cve_id(value: str) -> bool:
  import re as _re
  return bool(_re.fullmatch(r"CVE-\d{4}-\d+", value.strip(), _re.IGNORECASE))


def _parse_stack_terms(stack: str | None) -> list[str]:
    if not stack:
        return []
    return [p.strip().lower() for p in stack.split(",") if p.strip()]


def _stack_match_clause(stack: str | None) -> tuple[str, list, list[str]]:
    """Match stack terms: exact CVE ID, otherwise description/products substring."""
    if not stack or not stack.strip():
        return "", [], []

    raw_terms = [p.strip() for p in stack.split(",") if p.strip()]
    if not raw_terms:
        return "", [], []

    parts: list[str] = []
    params: list = []
    terms: list[str] = []
    for raw in raw_terms:
        terms.append(raw.lower())
        if _is_cve_id(raw):
            parts.append("cve_id = ?")
            params.append(raw.strip().upper())
        else:
            term = raw.lower()
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
           has_poc, patch_available, has_ai_context, source_urls, cwe_ids,
           updated_at
    FROM cves
"""


def _validate_published_on(value: str) -> str:
    """YYYY-MM-DD for filtering CVEs published on a single calendar day."""
    import re

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise HTTPException(status_code=400, detail="published_on must be YYYY-MM-DD")
    return value


def _parse_framework_list(frameworks: str | None) -> list[str]:
    if not frameworks:
        return []
    return [f.strip().lower() for f in frameworks.split(",") if f.strip()]


def _framework_match_clause(frameworks: str | None) -> tuple[str, list]:
    tokens = _parse_framework_list(frameworks)
    if not tokens:
        return "", []
    parts: list[str] = []
    params: list = []
    for token in tokens:
        parts.append(
            "(LOWER(description) LIKE ? OR LOWER(affected_products) LIKE ? OR LOWER(summary) LIKE ?)"
        )
        like = f"%{token}%"
        params.extend([like, like, like])
    return "(" + " OR ".join(parts) + ")", params


def _build_cve_filters(
    severity: str | None,
    kev_only: bool,
    poc_only: bool,
    epss_min: float | None,
    search: str | None,
    stack: str | None,
    vendors: str | None,
    technique: str | None = None,
    published_on: str | None = None,
    summary_only: bool = False,
    ai_context_only: bool = False,
    frameworks: str | None = None,
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
        search_stripped = search.strip()
        if _is_cve_id(search_stripped):
            conditions.append("cve_id = ?")
            params.append(search_stripped.upper())
        else:
            conditions.append("(cve_id LIKE ? OR description LIKE ? OR summary LIKE ?)")
            search_term = f"%{search_stripped}%"
            params.extend([search_term, search_term, search_term])

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

    if technique:
        tid = technique.strip().upper()
        if not tid.startswith("T"):
            raise HTTPException(status_code=400, detail="Invalid ATT&CK technique ID")
        conditions.append(
            "cve_id IN (SELECT cve_id FROM cve_technique_map WHERE technique_id = ?)"
        )
        params.append(tid)

    if published_on:
        day = _validate_published_on(published_on.strip())
        conditions.append("DATE(published) = ?")
        params.append(day)

    if summary_only:
        # Enriched plain-English only (CISA KEV short text, OSV, etc.) — not NVD auto-truncate
        conditions.append(
            "summary IS NOT NULL AND TRIM(summary) != ''"
        )

    if ai_context_only or _parse_framework_list(frameworks):
        conditions.append("has_ai_context = 1")

    fw_clause, fw_params = _framework_match_clause(frameworks)
    if fw_clause:
        conditions.append(fw_clause)
        params.extend(fw_params)

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
    technique: str | None = Query(default=None, max_length=32),
    published_on: str | None = Query(default=None, max_length=10),
    summary_only: bool = Query(default=False),
    ai_context_only: bool = Query(default=False),
    frameworks: str | None = Query(default=None, max_length=500),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
):
    conditions, params, stack_products = _build_cve_filters(
        severity,
        kev_only,
        poc_only,
        epss_min,
        search,
        stack,
        vendors,
        technique,
        published_on,
        summary_only,
        ai_context_only,
        frameworks,
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


@app.post("/api/cves/match")
async def match_cves_to_assets(body: AssetMatchRequest):
    """Pre-calculate CVE exposure scores for analyst assets (POST body only)."""
    assets = [a.model_dump() for a in body.assets if a.product.strip()]
    if not assets:
        return {"matches": {}}

    db = await get_db()
    try:
        scores = await match_cves_for_assets(db, assets)
    finally:
        await db.close()

    return {"matches": scores}


@app.get("/api/cves/export")
async def export_cves(
    severity: str | None = Query(default=None),
    kev_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    epss_min: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    vendors: str | None = Query(default=None, max_length=500),
    technique: str | None = Query(default=None, max_length=32),
    published_on: str | None = Query(default=None, max_length=10),
    summary_only: bool = Query(default=False),
    ai_context_only: bool = Query(default=False),
    frameworks: str | None = Query(default=None, max_length=500),
    max_rows: int = Query(default=500, ge=1, le=500),
):
    """Return up to 500 CVE rows matching filters (for CSV export)."""
    conditions, params, stack_products = _build_cve_filters(
        severity,
        kev_only,
        poc_only,
        epss_min,
        search,
        stack,
        vendors,
        technique,
        published_on,
        summary_only,
        ai_context_only,
        frameworks,
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


@app.get("/api/techniques/top")
async def top_techniques(
    limit: int = Query(default=10, ge=1, le=50),
):
    db = await get_db()
    try:
        data = await get_top_techniques(db, limit=limit)
    finally:
        await db.close()
    return {"data": data}


@app.get("/api/atlas/techniques")
async def atlas_techniques_grouped():
    """MITRE ATLAS techniques grouped by tactic (AI/ML threats — not Enterprise ATT&CK)."""
    db = await get_db()
    try:
        groups = await get_atlas_techniques_grouped(db)
    finally:
        await db.close()
    return {"data": groups, "source": "MITRE ATLAS"}


@app.get("/api/case-studies/news")
async def case_studies_news():
    """Cybersecurity news RSS feeds for the Case Studies tab (server-side fetch)."""
    from feeds.incident_news import fetch_all_incident_news

    db = await get_db()
    try:
        cards, errors = await fetch_all_incident_news(db)
        await db.commit()
    finally:
        await db.close()
    return {"data": cards, "errors": errors}


@app.get("/api/case-studies/feed")
async def case_studies_feed(
    atlas_limit: int = Query(default=80, ge=1, le=100),
):
    """Combined RSS news + ATLAS case studies (single SQLite connection)."""
    from feeds.case_study_feed import fetch_combined_case_study_feed

    cards, errors = await fetch_combined_case_study_feed(atlas_limit=atlas_limit)
    return {"data": cards, "errors": errors}


@app.get("/api/atlas/casestudies")
async def atlas_case_studies(
    limit: int = Query(default=50, ge=1, le=100),
):
    """Recent ATLAS case studies with technique and CVE references."""
    db = await get_db()
    try:
        studies = await get_atlas_case_studies(db, limit=limit)
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id, name FROM atlas_techniques"
        )
        tech_names = {r["technique_id"]: r["name"] for r in tech_rows}
    finally:
        await db.close()

    for study in studies:
        study["technique_details"] = [
            {
                "technique_id": tid,
                "name": tech_names.get(tid, tid),
                "url": f"https://atlas.mitre.org/techniques/{tid}",
            }
            for tid in study.get("techniques", [])
        ]

    return {"data": studies, "source": "MITRE ATLAS"}


@app.post("/api/refresh/mitre")
async def manual_mitre_refresh(request: Request):
    _require_admin_key(request)
    asyncio.create_task(run_weekly_mitre_refresh())
    return {
        "status": "ok",
        "message": "MITRE ATT&CK + ATLAS refresh started in background",
    }


@app.get("/api/cves/{cve_id}/sentences")
async def get_cve_sentences(cve_id: str):
    if not cve_id.upper().startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    cve_key = cve_id.upper()
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, cvss_score, severity, is_kev, epss_score,
                   has_poc, patch_available, source_urls
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        row = dict(rows[0])
        is_kev = bool(row.get("is_kev", 0))
        has_poc = bool(row.get("has_poc", 0))
        patch_available = bool(row.get("patch_available", 0))

        source_urls = row.get("source_urls") or "[]"
        if isinstance(source_urls, str):
            try:
                source_urls = json.loads(source_urls)
            except (json.JSONDecodeError, TypeError):
                source_urls = []

        kev_rows = await db.execute_fetchall(
            """
            SELECT due_date, required_action
            FROM kev_deadlines
            WHERE cve_id = ?
            """,
            (cve_key,),
        )

        sploitus_exploits = await load_public_exploits_for_cve(
            db,
            cve_key,
            has_poc=bool(row.get("has_poc")),
            source_urls=source_urls,
        )
        await db.commit()
    finally:
        await db.close()

    due_date = ""
    fix = ""
    if kev_rows:
        kev_row = dict(kev_rows[0])
        due_date = (kev_row.get("due_date") or "").strip()
        fix = (kev_row.get("required_action") or "").strip()

    exploit_items = [{"type": e.get("type", "poc")} for e in sploitus_exploits]
    if not exploit_items:
        exploit_items = exploits_from_cve(has_poc, source_urls)
    cvss = row.get("cvss_score")

    return {
        "cve_id": cve_key,
        "risk": severity_sentence(row.get("severity"), cvss),
        "exploit_likelihood": epss_sentence_or_fallback(row.get("epss_score"), is_kev),
        "public_exploits": exploit_sentence(exploit_items),
        "patch": patch_sentence(patch_available, fix),
        "kev": kev_sentence(is_kev, due_date),
    }


@app.get("/api/cves/{cve_id}/epss-history")
async def get_cve_epss_history(cve_id: str):
    if not cve_id.upper().startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    cve_key = cve_id.upper()
    db = await get_db()
    try:
        exists = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,)
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
        history = await get_epss_history(db, cve_key, days=30)
    finally:
        await db.close()

    return history


@app.get("/api/cves/{cve_id}/related")
async def get_cve_related(
    cve_id: str,
    limit: int = Query(default=5, ge=1, le=20),
):
    if not cve_id.upper().startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    cve_key = cve_id.upper()
    db = await get_db()
    try:
        exists = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,)
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
        related = await get_related_cves(db, cve_key, limit=limit)
    finally:
        await db.close()

    return {"data": related}


@app.get("/api/cves/{cve_id}")
async def get_cve(cve_id: str):
    if not cve_id.upper().startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    cve_key = cve_id.upper()
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, mitre_technique, summary, is_kev, epss_score,
                   has_poc, patch_available, has_ai_context, source_urls, cwe_ids,
                   updated_at
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        cve = _row_to_cve_dict(rows[0])
        kev_rows = await db.execute_fetchall(
            "SELECT date_added FROM kev_deadlines WHERE cve_id = ?",
            (cve_key,),
        )
        if kev_rows and kev_rows[0]["date_added"]:
            cve["kev_date_added"] = (kev_rows[0]["date_added"] or "").strip() or None
        cve["techniques"] = await get_techniques_for_cve(db, cve_key)
        cve["atlas_techniques"] = await get_atlas_techniques_for_cve(db, cve_key)
        cve["atlas_case_studies"] = await get_atlas_case_studies_for_cve(db, cve_key)

        try:
            cve["public_exploits"] = await load_public_exploits_for_cve(
                db,
                cve_key,
                has_poc=bool(cve.get("has_poc")),
                source_urls=cve.get("source_urls"),
            )
            await db.commit()
        except Exception as exc:
            logger.error("Sploitus load failed for %s: %s", cve_id, exc)
            cve["public_exploits"] = []

        greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
        try:
            cve["greynoise_scans"] = await greynoise_scans_for_cve(
                db,
                cve.get("description"),
                cve.get("source_urls"),
                greynoise_key,
            )
            await db.commit()
        except Exception as exc:
            logger.error("GreyNoise scan failed for %s: %s", cve_id, exc)
            cve["greynoise_scans"] = []

        otx_key = os.environ.get("OTX_API_KEY", "").strip()
        cve["otx_configured"] = bool(otx_key)
        try:
            cve["otx_pulses"] = await load_otx_pulses_for_cve(db, cve_key, otx_key)
            await db.commit()
        except Exception as exc:
            logger.error("OTX pulse load failed for %s: %s", cve_id, exc)
            cve["otx_pulses"] = []
    finally:
        await db.close()

    try:
        osv_data = await fetch_osv_by_cve(cve_key)
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

    try:
        db = await get_db()
        try:
            from feeds.extended import enrich_cve_circl

            cve = await enrich_cve_circl(db, cve)
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:
        logger.error("CIRCL enrichment failed for %s: %s", cve_id, exc)

    return cve



@app.get("/api/otx/pulses/{pulse_id}/iocs")
async def get_otx_pulse_iocs(
    pulse_id: str,
    limit: int = Query(default=10, ge=1, le=50),
):
    otx_key = os.environ.get("OTX_API_KEY", "")
    if not otx_key:
        raise HTTPException(status_code=503, detail="OTX_API_KEY not configured")

    db = await get_db()
    try:
        iocs = await load_pulse_iocs(db, pulse_id, otx_key)
        ips = await top_pulse_ipv4s(db, pulse_id, otx_key, limit=3)
        await db.commit()
    finally:
        await db.close()

    indicators: list[dict[str, str]] = []
    for ip in ips:
        indicators.append({"type": "ip", "value": ip})
    for row in iocs:
        ioc_t = (row.get("ioc_type") or "").upper()
        val = row.get("ioc_value") or ""
        if not val:
            continue
        if ioc_t in ("IPV4", "IPV6"):
            mapped = "ip"
        elif ioc_t in ("DOMAIN", "HOSTNAME"):
            mapped = "domain"
        elif ioc_t.startswith("FILE_HASH") or ioc_t == "FILE":
            mapped = "hash"
        else:
            continue
        entry = {"type": mapped, "value": val}
        if entry not in indicators:
            indicators.append(entry)
        if len(indicators) >= limit:
            break

    return {"data": {"iocs": iocs, "ips": ips, "indicators": indicators[:limit]}}


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
    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    abusech_key = os.environ.get("ABUSECH_AUTH_KEY", "")
    otx_key = os.environ.get("OTX_API_KEY", "")

    db = await get_db()
    try:
        cached = await get_ioc_cache(db, value)
        if cached is not None:
            cached["cached"] = True
            if ioc_type == "ip" and body.greynoise and greynoise_key:
                from feeds.extended import greynoise_for_ip

                gn = await greynoise_for_ip(db, value, greynoise_key)
                cached["greynoise"] = gn
                cached["greynoise_sentence"] = greynoise_sentence(gn)
            elif ioc_type == "ip":
                cached["greynoise"] = None
                cached["greynoise_sentence"] = None
            if otx_key:
                from feeds.otx import lookup_otx_for_ioc

                otx = await lookup_otx_for_ioc(db, value, ioc_type, otx_key)
                cached["otx"] = otx
                cached["otx_sentence"] = otx_sentence(otx)
            return cached

        result = await lookup_ioc(
            value,
            ioc_type,
            vt_key,
            abuse_key,
            greynoise_key,
            abusech_key,
            db=db,
            include_greynoise=body.greynoise,
            otx_key=otx_key,
        )
        result["cached"] = False

        await set_ioc_cache(db, value, ioc_type, result)
        await db.commit()
    finally:
        await db.close()

    return result


@app.get("/api/cves/{cve_id}/momentum")
async def cve_momentum(cve_id: str):
    """
    Compute momentum score (0–1) from EPSS trend and OTX pulse recency.
    Returns momentum_score and momentum_signals list for drawer breakdown.
    """
    from scoring.risk import calculate_momentum
    db = await get_db()
    try:
        result = await calculate_momentum(cve_id.upper(), db)
    finally:
        await db.close()
    return result


@app.get("/api/cves/{cve_id}/detection")
async def cve_detection(
    cve_id: str,
    product: str = Query(default="", description="Affected product name for rule title generation"),
):
    """
    Detection engineering resource for a CVE.
    Returns:
    - sigma_rules: community Sigma rules from SigmaHQ (cached 24h)
    - elastic_rules: community Elastic detection rules (cached 24h)
    - generated_sigma: template-based Sigma YAML (only when no community rules)
    - siem_queries: 4-platform quick-search queries (Elastic/Splunk/Sentinel/QRadar)
    - log_patterns: plain-English detection patterns from ATT&CK guidance
    """
    from detection.rule_sources import find_sigma_rules, find_elastic_rules
    from detection.sigma_generator import generate_sigma_rule
    from detection.siem_queries import get_siem_queries
    import os

    github_token = os.environ.get("GITHUB_TOKEN", "")
    cve_upper = cve_id.upper()

    db = await get_db()
    try:
        # Get CVE metadata for context
        row = await db.execute_fetchall(
            "SELECT description, mitre_technique FROM cves WHERE cve_id = ?",
            (cve_upper,),
        )
        cve_desc = ""
        primary_technique = ""
        if row:
            cve_desc = row[0]["description"] or ""
            primary_technique = row[0]["mitre_technique"] or ""

        # Get all linked techniques
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id FROM cve_technique_map WHERE cve_id = ?",
            (cve_upper,),
        )
        technique_ids = [r["technique_id"] for r in tech_rows]
        if primary_technique and primary_technique not in technique_ids:
            technique_ids.insert(0, primary_technique)

        # Run community rule lookups concurrently
        import asyncio
        sigma_task = asyncio.create_task(
            find_sigma_rules(db, cve_upper, technique_ids, github_token)
        )
        elastic_task = asyncio.create_task(
            find_elastic_rules(db, technique_ids, github_token)
        )
        sigma_rules, elastic_rules = await asyncio.gather(sigma_task, elastic_task)
        await db.commit()

        # Generate Sigma rule if no community rules found
        first_technique = technique_ids[0] if technique_ids else ""
        has_community_rules = bool(sigma_rules or elastic_rules)
        generated_sigma = None
        if not has_community_rules:
            generated_sigma = generate_sigma_rule(
                cve_id=cve_upper,
                technique_id=first_technique,
                product=product.strip() or "Affected Product",
                description=cve_desc[:200] if cve_desc else "",
            )

        # SIEM queries based on primary technique
        siem_queries = get_siem_queries(
            technique_id=first_technique,
            cve_id=cve_upper,
            product=product.strip(),
        )

    finally:
        await db.close()

    return {
        "cve_id": cve_upper,
        "technique_ids": technique_ids[:5],
        "sigma_rules": sigma_rules,
        "elastic_rules": elastic_rules,
        "has_community_rules": has_community_rules,
        "generated_sigma": generated_sigma,
        "siem_queries": siem_queries,
    }


@app.get("/api/cves/{cve_id}/correlation")
async def cve_correlation(
    cve_id: str,
    sector: str = Query(default="", description="User's declared industry sector for actor matching"),
):
    """
    On-demand correlation for a CVE.
    Level 1: shared exploitation IPs with other CVEs (OTX pulse IOCs).
    Level 2: ATT&CK groups linked to this CVE's techniques, matched against user sector.
    Level 3: temporal vendor volume anomalies (pre-computed nightly).
    Results are cached for 6 hours.
    """
    from correlation.engine import get_correlation_for_cve

    db = await get_db()
    try:
        result = await get_correlation_for_cve(
            db, cve_id.upper(), user_sector=sector.strip()
        )
        await db.commit()
    finally:
        await db.close()

    return result


@app.post("/api/refresh")
async def manual_refresh(request: Request):
    _require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(
            status_code=409,
            detail="An ingest job is already running. Wait for it to finish before starting another.",
        )
    asyncio.create_task(run_daily_refresh())
    return {
        "status": "ok",
        "message": "Full ingest started (NVD, then KEV, then EPSS) in background",
    }


@app.post("/api/refresh/nvd")
async def manual_nvd_refresh(request: Request):
    _require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    asyncio.create_task(run_nvd_incremental_sync())
    return {"status": "ok", "message": "NVD incremental sync started in background"}


@app.post("/api/refresh/kev")
async def manual_kev_refresh(request: Request):
    _require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    asyncio.create_task(run_kev_sync())
    return {"status": "ok", "message": "KEV metadata sync started in background"}


@app.post("/api/refresh/epss")
async def manual_epss_refresh(request: Request):
    _require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    asyncio.create_task(run_epss_sync())
    return {"status": "ok", "message": "EPSS score sync started in background"}


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


@app.get("/api/usage/ioc")
async def api_usage_ioc():
    """API quota counters for IOC Lookup enrichment sources."""
    now_utc = datetime.now(timezone.utc)
    stats = await get_ioc_usage_stats()
    return {
        "as_of_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today_date_utc": now_utc.strftime("%Y-%m-%d"),
        "this_month_utc": now_utc.strftime("%Y-%m"),
        "services": stats,
    }


@app.post("/api/ai/summary")
async def ai_summary(body: AiSummaryRequest):
    """AI executive summary for PDF export (Groq → Anthropic → template)."""
    return await generate_executive_summary(
        cves=body.cves,
        iocs=body.iocs,
        actors=body.actors,
        investigation_duration=body.investigation_duration,
    )


@app.get("/api/ai/summary")
async def ai_summary_get():
    """Discovery: summaries require POST with CVE/IOC/actor payloads (PDF export only)."""
    return {
        "detail": "Use POST /api/ai/summary with JSON body: cves, iocs, actors, investigation_duration",
    }


@app.post("/api/investigation/summary")
async def investigation_summary(body: InvestigationSummaryRequest):
    """Executive summary for investigation PDF (legacy; prefer /api/ai/summary)."""
    payload = [
        {
            "type": item.type,
            "id": item.id,
            "description": item.description,
            "pivot_from": (
                {"type": item.pivotFrom.type, "id": item.pivotFrom.id}
                if item.pivotFrom
                else None
            ),
        }
        for item in body.items
    ]
    return await generate_investigation_summary(payload, body.duration_minutes)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
