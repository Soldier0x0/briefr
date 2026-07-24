"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from read_cache import DEFAULT_TTL_SECONDS, cached_read
from db.timeutil import utcnow_str
from database import (
    count_ai_ml_profile_alerts,
    get_db,
    get_top_techniques,
    match_cves_for_assets,
)

from .common import row_to_cve_dict
from .models import AssetMatchRequest

list_router = APIRouter()


@list_router.get("/api/stats")
async def stats(
    frameworks: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated AI/ML framework tokens for ai_ml_alerts count",
    ),
):
    cache_key = f"stats:{frameworks or ''}"

    async def build():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                """
                SELECT
                    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
                    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high,
                    SUM(CASE WHEN is_kev = 1 THEN 1 ELSE 0 END) AS kev_count,
                    SUM(CASE WHEN patch_available = 1 THEN 1 ELSE 0 END) AS patched,
                    SUM(CASE WHEN published >= datetime('now', '-1 day') THEN 1 ELSE 0 END) AS last_24h,
                    SUM(CASE WHEN severity = 'CRITICAL' AND published >= datetime('now', '-1 day') THEN 1 ELSE 0 END)
                      - SUM(CASE WHEN severity = 'CRITICAL' AND published >= datetime('now', '-2 days')
                        AND published < datetime('now', '-1 day') THEN 1 ELSE 0 END) AS critical_delta,
                    SUM(CASE WHEN severity = 'HIGH' AND published >= datetime('now', '-1 day') THEN 1 ELSE 0 END)
                      - SUM(CASE WHEN severity = 'HIGH' AND published >= datetime('now', '-2 days')
                        AND published < datetime('now', '-1 day') THEN 1 ELSE 0 END) AS high_delta,
                    SUM(CASE WHEN is_kev = 1 AND published >= datetime('now', '-1 day') THEN 1 ELSE 0 END)
                      - SUM(CASE WHEN is_kev = 1 AND published >= datetime('now', '-2 days')
                        AND published < datetime('now', '-1 day') THEN 1 ELSE 0 END) AS kev_delta,
                    SUM(CASE WHEN patch_available = 1 AND published >= datetime('now', '-1 day') THEN 1 ELSE 0 END)
                      - SUM(CASE WHEN patch_available = 1 AND published >= datetime('now', '-2 days')
                        AND published < datetime('now', '-1 day') THEN 1 ELSE 0 END) AS patched_delta
                FROM cves
                """
            )
            stats_row = dict(rows[0]) if rows else {}
            fw_list = _parse_framework_list(frameworks)
            ai_ml_alerts = (
                await count_ai_ml_profile_alerts(db, fw_list) if fw_list else 0
            )
        finally:
            await db.close()

        return {
            "critical": stats_row.get("critical") or 0,
            "high": stats_row.get("high") or 0,
            "kev_count": stats_row.get("kev_count") or 0,
            "patched": stats_row.get("patched") or 0,
            "last_24h": stats_row.get("last_24h") or 0,
            "critical_delta": stats_row.get("critical_delta") or 0,
            "high_delta": stats_row.get("high_delta") or 0,
            "kev_delta": stats_row.get("kev_delta") or 0,
            "patched_delta": stats_row.get("patched_delta") or 0,
            "ai_ml_alerts": ai_ml_alerts,
        }

    return await cached_read(cache_key, DEFAULT_TTL_SECONDS, build)


@list_router.get("/api/stats/timeline")
async def stats_timeline(
    days: int = Query(default=90, ge=1, le=365),
):
    """Daily CVE counts grouped by published date (calendar day, UTC)."""
    cache_key = f"stats_timeline:{days}"

    async def build():
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

        by_date: dict[str, dict] = {}
        for row in rows:
            key = _timeline_date_key(row["date"])
            if not key:
                continue
            by_date[key] = {
                "date": key,
                "count": row["count"],
                "critical": row["critical"],
                "kev": row["kev"],
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

    return await cached_read(cache_key, DEFAULT_TTL_SECONDS, build)


@list_router.get("/api/stats/top-vendors")
async def stats_top_vendors(
    limit: int = Query(default=10, ge=1, le=25, description="Maximum vendors returned"),
):
    """KEV catalog rows grouped by vendor_project (product fallback)."""
    cache_key = f"stats_top_vendors:{limit}"

    async def build():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                """
                SELECT vendor, COUNT(*) AS kev_count
                FROM (
                    SELECT
                        CASE
                            WHEN vendor_project IS NOT NULL AND TRIM(vendor_project) != ''
                                THEN TRIM(vendor_project)
                            WHEN product IS NOT NULL AND TRIM(product) != ''
                                THEN TRIM(product)
                            ELSE 'Unknown vendor'
                        END AS vendor
                    FROM kev_deadlines
                ) grouped
                GROUP BY vendor
                ORDER BY kev_count DESC, vendor ASC
                LIMIT ?
                """,
                (limit,),
            )
            total_row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM kev_deadlines")
        finally:
            await db.close()

        total_kev = int(total_row[0]["cnt"]) if total_row else 0
        data = [{"vendor": row["vendor"], "kev_count": int(row["kev_count"])} for row in rows]
        return {"data": data, "total_kev": total_kev}

    return await cached_read(cache_key, DEFAULT_TTL_SECONDS, build)


def _timeline_date_key(value) -> str:
    """Normalize DATE() results to YYYY-MM-DD (asyncpg returns date objects)."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    text = str(value).strip()
    return text[:10] if text else ""


def _text_match_or_clause(terms: list[str]) -> tuple[str, list]:
    """Match any term against description, summary, or affected_products JSON."""
    if not terms:
        return "", []
    parts = []
    bind: list = []
    for term in terms:
        like = f"%{term.lower()}%"
        parts.append(
            "(LOWER(c.cve_id) LIKE ? OR LOWER(c.description) LIKE ? "
            "OR LOWER(c.summary) LIKE ? OR LOWER(c.affected_products) LIKE ?)"
        )
        bind.extend([like, like, like, like])
    return "(" + " OR ".join(parts) + ")", bind


def _is_cve_id(value: str) -> bool:
    return bool(re.fullmatch(r"CVE-\d{4}-\d+", value.strip(), re.IGNORECASE))


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
            parts.append("c.cve_id = ?")
            params.append(raw.strip().upper())
        else:
            term = raw.lower()
            parts.append("(LOWER(c.description) LIKE ? OR LOWER(c.affected_products) LIKE ?)")
            like = f"%{term}%"
            params.extend([like, like])

    return "(" + " OR ".join(parts) + ")", params, terms


CVE_KEYSET_ORDER_BY = """
    ORDER BY c.published DESC, c.cve_id DESC
"""


def _encode_feed_cursor(published: str, cve_id: str) -> str:
    raw = f"{published or ''}\t{cve_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_feed_cursor(cursor: str) -> tuple[str, str]:
    pad = "=" * (-len(cursor) % 4)
    decoded = base64.urlsafe_b64decode((cursor + pad).encode()).decode()
    published, cve_id = decoded.split("\t", 1)
    return published, cve_id


CVE_ORDER_BY = """
    ORDER BY
        CASE WHEN w.state = 'pin' THEN 0 ELSE 1 END,
        CASE WHEN c.cve_id IN (
            SELECT cm_self.cve_id
            FROM correlation_campaign_members cm_self
            INNER JOIN correlation_campaign_members cm_peer
                ON cm_peer.campaign_id = cm_self.campaign_id
            INNER JOIN correlation_campaigns cc
                ON cc.campaign_id = cm_self.campaign_id
            INNER JOIN watchlist wl_peer
                ON wl_peer.cve_id = cm_peer.cve_id AND wl_peer.state = 'pin'
            WHERE cm_peer.cve_id != cm_self.cve_id
              AND cc.retracted_at IS NULL
              AND cc.lifecycle IN ('active', 'emerging')
              AND cc.confidence IN ('medium', 'high')
        ) THEN 0 ELSE 1 END,
        c.published DESC,
        CASE c.severity
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            WHEN 'LOW' THEN 4
            ELSE 5
        END,
        CASE WHEN c.epss_score IS NOT NULL THEN c.epss_score ELSE -1 END DESC
"""

CVE_SELECT = """
    SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published, c.modified,
           c.affected_products, c.affected_products_source, c.mitre_technique,
           c.summary, c.is_kev, c.epss_score, c.epss_percentile, c.has_poc, c.patch_available,
           c.has_ai_context, c.source_urls, c.cwe_ids, c.updated_at,
           k.due_date AS kev_due_date,
           CASE
               WHEN LOWER(TRIM(COALESCE(k.known_ransomware, ''))) = 'known' THEN 1
               ELSE 0
           END AS kev_ransomware_use,
           w.state AS watchlist_state,
           w.snooze_until AS watchlist_snooze_until,
           EXISTS (
               SELECT 1 FROM correlation_campaign_members cm
               WHERE cm.cve_id = c.cve_id
           ) AS member_of_campaign,
           (
               SELECT cc.lifecycle
               FROM correlation_campaign_members cm
               INNER JOIN correlation_campaigns cc ON cc.campaign_id = cm.campaign_id
               WHERE cm.cve_id = c.cve_id
               ORDER BY CASE cc.lifecycle
                   WHEN 'active' THEN 1
                   WHEN 'emerging' THEN 2
                   WHEN 'declining' THEN 3
                   WHEN 'stale' THEN 4
                   ELSE 5
               END
               LIMIT 1
           ) AS campaign_lifecycle
    FROM cves c
    LEFT JOIN kev_deadlines k ON k.cve_id = c.cve_id
    LEFT JOIN watchlist w ON w.cve_id = c.cve_id
        AND (
            w.state = 'pin'
            OR (w.state = 'snooze'
                AND w.snooze_until IS NOT NULL
                AND TRIM(w.snooze_until) != ''
                AND datetime(w.snooze_until) > datetime('now'))
        )
"""


def _cve_count_cache_key(where_clause: str, params: list) -> str:
    raw = where_clause + "\0" + repr(tuple(params))
    return "cves_count:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


_WATCHLIST_ACTIVE_IN = """
    c.cve_id IN (
        SELECT cve_id FROM watchlist
        WHERE state = 'pin'
           OR (state = 'snooze'
               AND snooze_until IS NOT NULL
               AND TRIM(snooze_until) != ''
               AND datetime(snooze_until) > datetime('now'))
    )
"""

_ACTIVE_SNOOZE_EXCLUDE = """
    c.cve_id NOT IN (
        SELECT cve_id FROM watchlist
        WHERE state = 'snooze'
          AND snooze_until IS NOT NULL
          AND TRIM(snooze_until) != ''
          AND datetime(snooze_until) > datetime('now')
    )
"""


def _validate_published_on(value: str) -> str:
    """YYYY-MM-DD for filtering CVEs published on a single calendar day."""
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
            "(LOWER(c.description) LIKE ? OR LOWER(c.affected_products) LIKE ? OR LOWER(c.summary) LIKE ?)"
        )
        like = f"%{token}%"
        params.extend([like, like, like])
    return "(" + " OR ".join(parts) + ")", params


def _build_cve_filters(
    severity: str | None,
    kev_only: bool,
    kev_overdue_only: bool,
    poc_only: bool,
    patch_only: bool,
    epss_min: float | None,
    search: str | None,
    stack: str | None,
    vendors: str | None,
    technique: str | None = None,
    published_on: str | None = None,
    summary_only: bool = False,
    ai_context_only: bool = False,
    frameworks: str | None = None,
    watchlist_only: bool = False,
    hide_snoozed: bool = True,
) -> tuple[list[str], list, list[str]]:
    conditions: list[str] = []
    params: list = []

    if severity:
        severity_upper = severity.upper()
        if severity_upper not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise HTTPException(status_code=400, detail="Invalid severity value")
        conditions.append("c.severity = ?")
        params.append(severity_upper)

    if kev_only:
        conditions.append("c.is_kev = 1")

    if kev_overdue_only:
        conditions.append("c.is_kev = 1")
        conditions.append(
            "EXISTS (SELECT 1 FROM kev_deadlines k WHERE k.cve_id = c.cve_id "
            "AND k.due_date IS NOT NULL AND TRIM(k.due_date) != '' "
            "AND LENGTH(k.due_date) >= 10 "
            "AND k.due_date < ?)"
        )
        params.append(utcnow_str()[:10])

    if poc_only:
        conditions.append("c.has_poc = 1")

    if patch_only:
        conditions.append("c.patch_available = 1")

    if epss_min is not None:
        conditions.append("c.epss_score IS NOT NULL AND c.epss_score >= ?")
        params.append(epss_min)

    if search:
        search_stripped = search.strip()
        if _is_cve_id(search_stripped):
            conditions.append("c.cve_id = ?")
            params.append(search_stripped.upper())
        else:
            conditions.append(
                "(LOWER(c.cve_id) LIKE ? OR LOWER(c.description) LIKE ? OR LOWER(c.summary) LIKE ?)"
            )
            search_term = f"%{search_stripped.lower()}%"
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
            "c.cve_id IN (SELECT cve_id FROM cve_technique_map WHERE technique_id = ?)"
        )
        params.append(tid)

    if published_on:
        day = _validate_published_on(published_on.strip())
        conditions.append("DATE(c.published) = ?")
        params.append(day)

    if summary_only:
        # Enriched plain-English only (CISA KEV short text, OSV, etc.) — not NVD auto-truncate
        conditions.append(
            "c.summary IS NOT NULL AND TRIM(c.summary) != ''"
        )

    if ai_context_only or _parse_framework_list(frameworks):
        conditions.append("c.has_ai_context = 1")

    fw_clause, fw_params = _framework_match_clause(frameworks)
    if fw_clause:
        conditions.append(fw_clause)
        params.extend(fw_params)

    if watchlist_only:
        conditions.append(_WATCHLIST_ACTIVE_IN)
    elif hide_snoozed:
        conditions.append(_ACTIVE_SNOOZE_EXCLUDE)

    return conditions, params, stack_products


def _stack_relevance_sql(stack_products: list[str]) -> tuple[str, list]:
    """ORDER BY expression: higher = more stack term hits (I16 server-side sort)."""
    if not stack_products:
        return "", []
    parts: list[str] = []
    params: list = []
    for term in stack_products:
        like = f"%{term.lower()}%"
        parts.append(
            "(CASE WHEN LOWER(c.description) LIKE ? OR LOWER(COALESCE(c.summary, '')) LIKE ? "
            "OR LOWER(COALESCE(c.affected_products, '')) LIKE ? THEN 1 ELSE 0 END)"
        )
        params.extend([like, like, like])
    expr = " + ".join(parts)
    return f"({expr}) DESC,", params


def _sort_by_stack_relevance(cve_list: list[dict], stack_products: list[str]) -> list[dict]:
    if not stack_products:
        return cve_list

    def relevance_score(cve: dict) -> int:
        # `or []`, not a .get default: a NULL DB column survives
        # row_to_cve_dict as an explicit None value under the key.
        products = [p.lower() for p in (cve.get("affected_products") or [])]
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


@list_router.get("/api/cves")
async def list_cves(
    severity: str | None = Query(default=None, description="CRITICAL/HIGH/MEDIUM/LOW"),
    kev_only: bool = Query(default=False),
    kev_overdue_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    patch_only: bool = Query(default=False),
    epss_min: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    vendors: str | None = Query(default=None, max_length=500),
    technique: str | None = Query(default=None, max_length=32),
    published_on: str | None = Query(default=None, max_length=10),
    summary_only: bool = Query(default=False),
    ai_context_only: bool = Query(default=False),
    frameworks: str | None = Query(default=None, max_length=500),
    watchlist_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    pagination: str | None = Query(
        default=None,
        description="Set to 'keyset' for cursor-based feed pagination (chronological order).",
    ),
    cursor: str | None = Query(
        default=None,
        max_length=256,
        description="Keyset cursor (published+cve_id). Use with pagination=keyset.",
    ),
):
    conditions, params, stack_products = _build_cve_filters(
        severity,
        kev_only,
        kev_overdue_only,
        poc_only,
        patch_only,
        epss_min,
        search,
        stack,
        vendors,
        technique,
        published_on,
        summary_only,
        ai_context_only,
        frameworks,
        watchlist_only=watchlist_only,
        hide_snoozed=not watchlist_only,
    )

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    keyset_mode = (pagination or "").strip().lower() == "keyset"
    cursor_params: list = []
    order_params: list = []
    if keyset_mode:
        order_by = CVE_KEYSET_ORDER_BY
        fetch_limit = limit + 1
        offset = 0
        page = 1
        if (cursor or "").strip():
            try:
                cursor_published, cursor_cve_id = _decode_feed_cursor(cursor.strip())
            except (ValueError, UnicodeDecodeError) as exc:
                raise HTTPException(status_code=400, detail="Invalid feed cursor") from exc
            cursor_predicate = (
                " AND (c.published < ? OR (c.published = ? AND c.cve_id < ?))"
            )
            if where_clause:
                where_clause += cursor_predicate
            else:
                where_clause = "WHERE 1=1" + cursor_predicate
            cursor_params = [cursor_published, cursor_published, cursor_cve_id]
    else:
        offset = (page - 1) * limit
        stack_order_sql, stack_order_params = _stack_relevance_sql(stack_products)
        if stack_order_sql:
            order_by = CVE_ORDER_BY.replace("ORDER BY", f"ORDER BY {stack_order_sql}", 1)
            order_params = stack_order_params
        else:
            order_by = CVE_ORDER_BY
            order_params = []
        fetch_limit = limit

    db = await get_db()
    try:
        async def _fetch_total() -> int:
            count_rows = await db.execute_fetchall(
                f"SELECT COUNT(*) as cnt FROM cves c {where_clause}",
                params + cursor_params,
            )
            return count_rows[0]["cnt"] if count_rows else 0

        cache_key = _cve_count_cache_key(where_clause, params + cursor_params)
        total = await cached_read(cache_key, 45.0, _fetch_total) if not keyset_mode else None

        rows = await db.execute_fetchall(
            f"{CVE_SELECT} {where_clause} {order_by} LIMIT ? OFFSET ?",
            params + cursor_params + order_params + [fetch_limit, offset],
        )
    finally:
        await db.close()

    cve_list = [row_to_cve_dict(row) for row in rows]
    if not order_params:
        cve_list = _sort_by_stack_relevance(cve_list, stack_products)
    next_cursor = None
    if keyset_mode:
        has_more = len(rows) > limit
        if has_more:
            cve_list = cve_list[:limit]
        if has_more and cve_list:
            last = cve_list[-1]
            next_cursor = _encode_feed_cursor(last.get("published") or "", last["cve_id"])

    payload = {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total and total > 0 else 0,
        "data": cve_list,
    }
    if keyset_mode:
        payload["pagination"] = "keyset"
        payload["next_cursor"] = next_cursor
    return payload


@list_router.post("/api/cves/match")
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


@list_router.get("/api/cves/export")
async def export_cves(
    severity: str | None = Query(default=None),
    kev_only: bool = Query(default=False),
    kev_overdue_only: bool = Query(default=False),
    poc_only: bool = Query(default=False),
    patch_only: bool = Query(default=False),
    epss_min: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, max_length=200),
    stack: str | None = Query(default=None, max_length=500),
    vendors: str | None = Query(default=None, max_length=500),
    technique: str | None = Query(default=None, max_length=32),
    published_on: str | None = Query(default=None, max_length=10),
    summary_only: bool = Query(default=False),
    ai_context_only: bool = Query(default=False),
    frameworks: str | None = Query(default=None, max_length=500),
    watchlist_only: bool = Query(default=False),
    max_rows: int = Query(default=500, ge=1, le=500),
):
    """Return up to 500 CVE rows matching filters (for CSV export)."""
    conditions, params, stack_products = _build_cve_filters(
        severity,
        kev_only,
        kev_overdue_only,
        poc_only,
        patch_only,
        epss_min,
        search,
        stack,
        vendors,
        technique,
        published_on,
        summary_only,
        ai_context_only,
        frameworks,
        watchlist_only=watchlist_only,
        hide_snoozed=not watchlist_only,
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

    cve_list = _sort_by_stack_relevance([row_to_cve_dict(row) for row in rows], stack_products)
    return {"total": len(cve_list), "data": cve_list}


@list_router.get("/api/techniques/top")
async def top_techniques(
    limit: int = Query(default=10, ge=1, le=50),
):
    db = await get_db()
    try:
        data = await get_top_techniques(db, limit=limit)
    finally:
        await db.close()
    return {"data": data}
