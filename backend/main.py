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
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from database import (
    get_atlas_case_studies,
    get_atlas_techniques_grouped,
    get_db,
    get_cve_count,
    get_epss_history,
    get_ioc_cache,
    get_last_updated,
    get_nvd_sync_watermark,
    get_related_cves,
    get_techniques_for_cve,
    get_top_techniques,
    init_db,
    set_ioc_cache,
)
from feeds.extended import (
    fetch_circl_cve,
    greynoise_scans_for_cve,
    load_sploitus_exploits_for_cve,
    merge_circl_into_cve,
)
from scheduler import run_weekly_mitre_refresh
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
from investigation_summary import generate_investigation_summary
from tracking import get_ioc_usage_stats, get_usage_stats
from templates.intelligence import (
    epss_sentence_or_fallback,
    exploit_sentence,
    exploits_from_cve,
    greynoise_sentence,
    kev_sentence,
    patch_sentence,
    severity_sentence,
)


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
    duration_minutes: int = 1


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

    end = date.today()
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


def _validate_published_on(value: str) -> str:
    """YYYY-MM-DD for filtering CVEs published on a single calendar day."""
    import re

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise HTTPException(status_code=400, detail="published_on must be YYYY-MM-DD")
    return value


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
        conditions.append(
            "summary IS NOT NULL AND TRIM(summary) != ''"
        )

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
    technique: str | None = Query(default=None, max_length=32),
    published_on: str | None = Query(default=None, max_length=10),
    summary_only: bool = Query(default=False),
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
async def manual_mitre_refresh():
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

        sploitus_exploits = await load_sploitus_exploits_for_cve(db, cve_key)
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

    db2 = await get_db()
    try:
        cve["techniques"] = await get_techniques_for_cve(db2, cve_id.upper())
    finally:
        await db2.close()

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

    db3 = await get_db()
    try:
        cve["public_exploits"] = await load_sploitus_exploits_for_cve(db3, cve_id.upper())
        await db3.commit()
    except Exception as exc:
        logger.error("Sploitus load failed for %s: %s", cve_id, exc)
        cve["public_exploits"] = []
    finally:
        await db3.close()

    try:
        circl = await fetch_circl_cve(cve_id.upper())
        cve = merge_circl_into_cve(cve, circl)
    except Exception as exc:
        logger.error("CIRCL enrichment failed for %s: %s", cve_id, exc)

    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    db4 = await get_db()
    try:
        cve["greynoise_scans"] = await greynoise_scans_for_cve(
            db4,
            cve.get("description"),
            cve.get("source_urls"),
            greynoise_key,
        )
        await db4.commit()
    except Exception as exc:
        logger.error("GreyNoise scan failed for %s: %s", cve_id, exc)
        cve["greynoise_scans"] = []
    finally:
        await db4.close()

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
    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    abusech_key = os.environ.get("ABUSECH_AUTH_KEY", "")

    db = await get_db()
    try:
        cached = await get_ioc_cache(db, value)
        if cached is not None:
            cached["cached"] = True
            if ioc_type == "ip" and greynoise_key:
                from feeds.extended import greynoise_for_ip

                gn = await greynoise_for_ip(db, value, greynoise_key)
                cached["greynoise"] = gn
                cached["greynoise_sentence"] = greynoise_sentence(gn)
            return cached

        result = await lookup_ioc(
            value,
            ioc_type,
            vt_key,
            abuse_key,
            greynoise_key,
            abusech_key,
            db=db,
        )
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


@app.post("/api/investigation/summary")
async def investigation_summary(body: InvestigationSummaryRequest):
    """Executive summary for investigation PDF (Groq if GROQ_API_KEY set)."""
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
    result = await generate_investigation_summary(payload, body.duration_minutes)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
