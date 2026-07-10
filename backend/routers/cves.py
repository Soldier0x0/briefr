"""CVE endpoints (changes/stats/list/detail/intel/KEV), moved verbatim from
main.py (V1.2 §5.2 router split, phase 3). No behavior change.

Four sub-routers because the CVE routes were interleaved with the ATLAS and
IOC groups in the pre-split main.py — main.py includes them in the exact
pre-split sequence so the OpenAPI route list stays byte-identical (and
/api/cves/{cve_id} keeps matching AFTER its literal siblings like
/api/cves/export, but BEFORE /api/cves/{cve_id}/momentum etc.):

- changes_router: GET /api/changes
- list_router:    /api/stats, /api/stats/timeline, /api/cves, /api/cves/match,
                  /api/cves/export, /api/techniques/top
- detail_router:  /api/cves/{cve_id}/sentences|epss-history|related,
                  /api/cves/{cve_id}
- intel_router:   /api/cves/{cve_id}/momentum|risk|detection|correlation,
                  /api/kev/deadlines

Inline imports were hoisted to module top per house convention
(re, asyncio, scoring.risk, detection.*, correlation.engine,
feeds.extended.enrich_cve_circl). The unused `_parse_stack_terms` helper was
dropped during the move.

Four review fixes on top of the verbatim move (PR #96 review):
- `_sort_by_stack_relevance` no longer crashes on a NULL `affected_products`
  column (was `cve.get(..., [])`, which returns the explicit None value).
- momentum/detection/correlation validate the `CVE-` prefix like their
  sibling detail endpoints (detection previously spent GitHub API quota on
  malformed IDs).
- `/api/stats` runs one conditional-aggregation scan instead of five
  COUNT(*) scans (same response, verified on empty/NULL/edge data).
- `_row_to_cve_dict` normalizes NULL/'' list columns (affected_products,
  source_urls, cwe_ids) to [] — matches the arrays documented in
  API_REFERENCE.md; only legacy rows ever hit this path (ingest always
  writes JSON, column default is '[]').

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from correlation.engine import get_correlation_for_cve
from read_cache import DEFAULT_TTL_SECONDS, cached_read
from db.timeutil import utcnow_str
from routers._validators import require_cve_id
from database import (
    count_ai_ml_profile_alerts,
    get_atlas_case_studies_for_cve,
    get_atlas_techniques_for_cve,
    get_cve_summaries_by_ids,
    get_db,
    get_epss_history,
    get_recent_cve_changes,
    get_related_cves,
    get_techniques_for_cve,
    get_top_techniques,
    get_watchlist_entry,
    match_cves_for_assets,
)
from detection.rule_sources import find_elastic_rules, find_sigma_rules
from detection.siem_queries import get_siem_queries
from detection.sigma_generator import generate_sigma_rule_bundle
from detection.context import get_detection_context
from feeds.extended import (
    enrich_cve_circl,
    greynoise_scans_for_cve,
    load_public_exploits_for_cve,
)
from feeds.osv import fetch_osv_by_cve
from feeds.otx import load_otx_pulses_for_cve
from ml.embeddings import embeddings_enabled, find_similar_cves
from scoring.environment import classify_environment
from intel.provenance import (
    derive_correlation_provenance,
    derive_detection_provenance,
    derive_exploit_provenance,
    otx_configured_from_env,
)
from scoring.priority import correlation_escalation, derive_operational_priority
from scoring.risk import calculate_momentum, calculate_risk_score
from scoring.threat import calculate_threat_score
from templates.intelligence import (
    epss_sentence_or_fallback,
    exploit_sentence,
    exploits_from_cve,
    kev_sentence,
    patch_sentence,
    severity_sentence,
)

logger = logging.getLogger(__name__)

changes_router = APIRouter()
list_router = APIRouter()
detail_router = APIRouter()
intel_router = APIRouter()


class AssetMatchItem(BaseModel):
    product: str = Field(..., max_length=200)
    version: str = Field(default="", max_length=100)
    vendor: str = Field(default="", max_length=100)


class AssetMatchRequest(BaseModel):
    assets: list[AssetMatchItem] = Field(default_factory=list, max_length=500)


class RiskScoreRequest(BaseModel):
    """Optional asset profile for personalised Risk Score v1.1b."""

    profile: dict | None = None
    assets: list[AssetMatchItem] = Field(default_factory=list, max_length=500)


def _row_to_cve_dict(row) -> dict:
    d = dict(row)
    for field in ("affected_products", "source_urls", "cwe_ids"):
        val = d.get(field)
        if val and isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        elif not val:
            # NULL/'' columns surface as a stable [] — API_REFERENCE.md
            # documents these fields as arrays, never null.
            d[field] = []
    for num_field in ("cvss_score", "epss_score", "epss_percentile"):
        if d.get(num_field) is not None:
            try:
                d[num_field] = float(d[num_field])
            except (TypeError, ValueError):
                d[num_field] = None
    d["is_kev"] = bool(d.get("is_kev", 0))
    d["has_poc"] = bool(d.get("has_poc", 0))
    if "affected_products_source" in d:
        # '' = official CPE / unset; 'llm' = LLM-extracted (provenance marker)
        d["affected_products_source"] = d.get("affected_products_source") or ""
    d["patch_available"] = bool(d.get("patch_available", 0))
    d["has_ai_context"] = bool(d.get("has_ai_context", 0))
    d["member_of_campaign"] = bool(d.pop("member_of_campaign", 0))
    lifecycle = d.pop("campaign_lifecycle", None)
    if d["member_of_campaign"] and lifecycle:
        d["campaign_lifecycle"] = str(lifecycle).strip() or None
    kev_date = d.get("kev_date_added")
    d["kev_date_added"] = (kev_date or "").strip() or None
    kev_due = d.get("kev_due_date")
    d["kev_due_date"] = (kev_due or "").strip() or None
    d["kev_ransomware_use"] = bool(d.pop("kev_ransomware_use", 0))
    wl_state = d.pop("watchlist_state", None)
    wl_snooze = d.pop("watchlist_snooze_until", None)
    if wl_state:
        d["watchlist_state"] = wl_state
        d["watchlist_snooze_until"] = (wl_snooze or "").strip() or None
    return d


@changes_router.get("/api/changes")
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
            INNER JOIN watchlist wl_peer
                ON wl_peer.cve_id = cm_peer.cve_id AND wl_peer.state = 'pin'
            WHERE cm_peer.cve_id != cm_self.cve_id
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


def _sort_by_stack_relevance(cve_list: list[dict], stack_products: list[str]) -> list[dict]:
    if not stack_products:
        return cve_list

    def relevance_score(cve: dict) -> int:
        # `or []`, not a .get default: a NULL DB column survives
        # _row_to_cve_dict as an explicit None value under the key.
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
        order_by = CVE_ORDER_BY
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
            params + cursor_params + [fetch_limit, offset],
        )
    finally:
        await db.close()

    cve_list = _sort_by_stack_relevance([_row_to_cve_dict(row) for row in rows], stack_products)
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

    cve_list = _sort_by_stack_relevance([_row_to_cve_dict(row) for row in rows], stack_products)
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


@detail_router.get("/api/cves/{cve_id}/sentences")
async def get_cve_sentences(cve_id: str):
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
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
        "kev_required_action": fix or None,
    }


@detail_router.get("/api/cves/{cve_id}/epss-history")
async def get_cve_epss_history(cve_id: str):
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
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


@detail_router.get("/api/cves/{cve_id}/related")
async def get_cve_related(
    cve_id: str,
    limit: int = Query(default=5, ge=1, le=20),
):
    """Related CVEs — semantic (embeddings) when enabled and vectors exist,
    otherwise the deterministic shared-product heuristic. Additive response:
    `data` keeps its shape; embedding results add a `similarity` field and
    `meta.method` reports which path produced them."""
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
    db = await get_db()
    try:
        exists = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,)
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        related: list[dict] = []
        method = "product_heuristic"
        if embeddings_enabled():
            try:
                # Pure BLOB scan over scheduler-computed vectors — no model
                # inference in the request path (ROADMAP ML placement rules).
                similar = await find_similar_cves(db, cve_key, limit=limit)
            except Exception as exc:
                logger.error("Embedding similarity failed for %s: %s", cve_key, exc)
                similar = None
            if similar:
                summaries = await get_cve_summaries_by_ids(
                    db, [s["cve_id"] for s in similar]
                )
                for s in similar:
                    base = summaries.get(s["cve_id"])
                    if base:
                        related.append({**base, "similarity": s["similarity"]})
                if related:
                    method = "embeddings"

        if not related:
            related = await get_related_cves(db, cve_key, limit=limit)
            method = "product_heuristic"
    finally:
        await db.close()

    return {"data": related, "meta": {"method": method}}


async def _drawer_sentences_payload(db, cve_key: str) -> dict:
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
        raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

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
        "kev_required_action": fix or None,
    }


async def _drawer_related_payload(db, cve_key: str, *, limit: int = 5) -> dict:
    related: list[dict] = []
    method = "product_heuristic"
    if embeddings_enabled():
        try:
            similar = await find_similar_cves(db, cve_key, limit=limit)
        except Exception as exc:
            logger.error("Embedding similarity failed for %s: %s", cve_key, exc)
            similar = None
        if similar:
            summaries = await get_cve_summaries_by_ids(db, [s["cve_id"] for s in similar])
            for s in similar:
                base = summaries.get(s["cve_id"])
                if base:
                    related.append({**base, "similarity": s["similarity"]})
            if related:
                method = "embeddings"

    if not related:
        related = await get_related_cves(db, cve_key, limit=limit)
        method = "product_heuristic"

    return {"data": related, "meta": {"method": method}}


async def _build_cve_drawer_bundle(db, cve_key: str, *, sector: str = "") -> dict:
    exists = await db.execute_fetchall("SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,))
    if not exists:
        raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

    sentences, epss_history, related, correlation, momentum = await asyncio.gather(
        _drawer_sentences_payload(db, cve_key),
        get_epss_history(db, cve_key, days=30),
        _drawer_related_payload(db, cve_key, limit=5),
        get_correlation_for_cve(db, cve_key, user_sector=sector.strip()),
        calculate_momentum(cve_key, db),
    )
    correlation["provenance"] = derive_correlation_provenance(
        correlation,
        otx_configured=otx_configured_from_env(),
    )
    return {
        "cve_id": cve_key,
        "sentences": sentences,
        "epss_history": epss_history,
        "related": related,
        "correlation": correlation,
        "momentum": momentum,
    }


@detail_router.get("/api/cves/{cve_id}/drawer")
async def get_cve_drawer_bundle(
    cve_id: str,
    sector: str = Query(default="", description="User industry sector for correlation actor matching"),
):
    """Aggregate drawer on-open payloads (sentences, EPSS, related, correlation, momentum)."""
    cve_id = require_cve_id(cve_id)
    cve_key = cve_id

    db = await get_db()
    try:
        bundle = await _build_cve_drawer_bundle(db, cve_key, sector=sector)
        await db.commit()
    finally:
        await db.close()

    return bundle


async def _load_cve_detail_from_db(cve_key: str) -> dict:
    """Fast path: DB reads only so the pool connection is not held during I/O."""
    from database import get_feed_cache

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, affected_products_source, mitre_technique,
                   summary, is_kev, epss_score, epss_percentile, has_poc, patch_available,
                   has_ai_context, source_urls, cwe_ids, updated_at
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

        cve = _row_to_cve_dict(rows[0])
        wl = await get_watchlist_entry(db, cve_key)
        if wl:
            cve["watchlist_state"] = wl["state"]
            cve["watchlist_snooze_until"] = (wl.get("snooze_until") or "").strip() or None
        kev_rows = await db.execute_fetchall(
            """
            SELECT date_added, due_date, vendor_project, vulnerability_name,
                   known_ransomware, cwes, required_action
            FROM kev_deadlines WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if kev_rows:
            kev_row = dict(kev_rows[0])
            cve["kev_date_added"] = (kev_row.get("date_added") or "").strip() or None
            cve["kev_due_date"] = (kev_row.get("due_date") or "").strip() or None
            cve["kev_required_action"] = (
                (kev_row.get("required_action") or "").strip() or None
            )
            cve["kev_vendor_project"] = (kev_row.get("vendor_project") or "").strip() or None
            cve["kev_vulnerability_name"] = (
                kev_row.get("vulnerability_name") or ""
            ).strip() or None
            cve["kev_ransomware_use"] = (
                str(kev_row.get("known_ransomware") or "").strip().lower() == "known"
            )
            try:
                parsed_cwes = json.loads(kev_row.get("cwes") or "[]")
                cve["kev_cwes"] = parsed_cwes if isinstance(parsed_cwes, list) else []
            except (json.JSONDecodeError, TypeError):
                cve["kev_cwes"] = []
        ssvc_cached = await get_feed_cache(db, f"ssvc:{cve_key}", max_age_hours=24 * 365)
        if ssvc_cached and isinstance(ssvc_cached.get("decisions"), dict):
            cve["ssvc"] = ssvc_cached
        cve["techniques"] = await get_techniques_for_cve(db, cve_key)
        cve["atlas_techniques"] = await get_atlas_techniques_for_cve(db, cve_key)
        cve["atlas_case_studies"] = await get_atlas_case_studies_for_cve(db, cve_key)
        return cve
    finally:
        await db.close()


async def _detail_enrich_exploits(cve_key: str, cve: dict) -> dict:
    from db.cache import get_cve_exploits_latest_fetched_at, get_feed_cache_timestamp

    pending_provenance = {
        "status": "pending",
        "source": "Sploitus + BRIEFR exploit index",
        "as_of": None,
    }
    try:
        db = await get_db()
        try:
            try:
                public_exploits = await load_public_exploits_for_cve(
                    db,
                    cve_key,
                    has_poc=bool(cve.get("has_poc")),
                    source_urls=cve.get("source_urls"),
                )
                provenance = await derive_exploit_provenance(
                    db,
                    cve_key,
                    used_nvd_fallback=bool(public_exploits)
                    and not await get_cve_exploits_latest_fetched_at(db, cve_key)
                    and not await get_feed_cache_timestamp(db, f"sploitus:{cve_key}"),
                )
                await db.commit()
                return {"public_exploits": public_exploits, "exploit_provenance": provenance}
            except Exception as exc:
                logger.error("Sploitus load failed for %s: %s", cve_key, exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                try:
                    provenance = await derive_exploit_provenance(db, cve_key)
                except Exception:
                    provenance = pending_provenance
                return {"public_exploits": [], "exploit_provenance": provenance}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error(
            "Failed to acquire DB or process exploits for %s: %s", cve_key, outer_exc
        )
        return {"public_exploits": [], "exploit_provenance": pending_provenance}


async def _detail_enrich_otx(cve_key: str, otx_key: str) -> dict:
    if not otx_key:
        return {"otx_pulses": []}
    try:
        db = await get_db()
        try:
            try:
                pulses = await load_otx_pulses_for_cve(db, cve_key, otx_key)
                await db.commit()
                return {"otx_pulses": pulses}
            except Exception as exc:
                logger.error("OTX pulse load failed for %s: %s", cve_key, exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                return {"otx_pulses": []}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error("Failed to acquire DB or process OTX for %s: %s", cve_key, outer_exc)
        return {"otx_pulses": []}


async def _detail_enrich_osv(cve_key: str, existing_summary: str | None) -> dict:
    try:
        osv_data = await fetch_osv_by_cve(cve_key)
        out: dict = {"osv_packages": osv_data}
        if not (existing_summary or "").strip():
            for entry in osv_data:
                osv_summary = (entry.get("summary") or "").strip()
                if osv_summary:
                    out["summary"] = osv_summary
                    break
        return out
    except Exception as exc:
        logger.error("OSV lookup failed for %s: %s", cve_key, exc)
        return {"osv_packages": []}


def _circl_enrichment_patch(enriched: dict | None) -> dict:
    """Return only CIRCL-owned fields so concurrent enrichments are not overwritten."""
    if not isinstance(enriched, dict):
        return {}
    patch: dict = {}
    if "circl" in enriched:
        patch["circl"] = enriched["circl"]
    if "capec_ids" in enriched:
        patch["capec_ids"] = enriched["capec_ids"]
    if "source_urls" in enriched:
        patch["source_urls"] = enriched["source_urls"]
    return patch


async def _detail_enrich_circl(cve: dict) -> dict:
    try:
        db = await get_db()
        try:
            try:
                enriched = await enrich_cve_circl(db, dict(cve))
                await db.commit()
                return _circl_enrichment_patch(enriched)
            except Exception as exc:
                logger.error("CIRCL enrichment failed for %s: %s", cve.get("cve_id"), exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                return {}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error(
            "Failed to acquire DB or process CIRCL for %s: %s", cve.get("cve_id"), outer_exc
        )
        return {}


@detail_router.get("/api/cves/{cve_id}")
async def get_cve(cve_id: str):
    cve_id = require_cve_id(cve_id)
    cve_key = cve_id

    cve = await _load_cve_detail_from_db(cve_key)

    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    cve["greynoise_configured"] = bool(greynoise_key)
    cve["greynoise_scans"] = []

    otx_key = os.environ.get("OTX_API_KEY", "").strip()
    cve["otx_configured"] = bool(otx_key)

    exploit_patch, otx_patch, osv_patch, circl_patch = await asyncio.gather(
        _detail_enrich_exploits(cve_key, cve),
        _detail_enrich_otx(cve_key, otx_key),
        _detail_enrich_osv(cve_key, cve.get("summary")),
        _detail_enrich_circl(cve),
    )
    cve.update(exploit_patch)
    cve.update(otx_patch)
    cve.update(osv_patch)
    cve.update(circl_patch)

    return cve


@intel_router.post("/api/cves/{cve_id}/risk")
async def cve_risk_score(cve_id: str, body: RiskScoreRequest | None = None):
    """
    Operational Priority surface for one CVE (ADR-002).

    Returns Threat Score, Environment tier, Operational Priority band, and
    legacy Risk Score v1.1b under ``legacy_risk_v11b``. Computes momentum and
    optional correlation escalation server-side.
    """
    cve_id = require_cve_id(cve_id)

    body = body or RiskScoreRequest()
    cve_key = cve_id

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published,
                   c.modified, c.affected_products, c.summary, c.is_kev, c.epss_score, c.epss_percentile,
                   c.has_poc, c.source_urls, c.cpe_matches,
                   k.date_added AS kev_date_added,
                   k.due_date AS kev_due_date
            FROM cves c
            LEFT JOIN kev_deadlines k ON k.cve_id = c.cve_id
            WHERE c.cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        cve = _row_to_cve_dict(rows[0])
        cpe_raw = rows[0]["cpe_matches"]
        if cpe_raw and isinstance(cpe_raw, str):
            try:
                cve["cpe_matches"] = json.loads(cpe_raw)
            except (json.JSONDecodeError, TypeError):
                cve["cpe_matches"] = []
        else:
            cve["cpe_matches"] = cpe_raw or []

        try:
            cve["public_exploits"] = await load_public_exploits_for_cve(
                db,
                cve_key,
                has_poc=bool(cve.get("has_poc")),
                source_urls=cve.get("source_urls"),
            )
        except Exception as exc:
            logger.error("Exploit load failed for risk score %s: %s", cve_id, exc)
            cve["public_exploits"] = []

        momentum = await calculate_momentum(cve_key, db)

        profile = body.profile if body.profile else None
        assets = [a.model_dump() for a in body.assets if a.product.strip()]
        if profile and not assets:
            from scoring.asset_match import profile_to_match_assets

            assets = profile_to_match_assets(profile)

        backend_match = None
        if profile and assets:
            from scoring.asset_match import cpe_match_score_for_cve

            backend_match = cpe_match_score_for_cve(cve, assets)

        mom_score = momentum.get("momentum_score", 0.0)
        legacy_risk = calculate_risk_score(
            cve,
            profile=profile,
            backend_match_score=backend_match,
            momentum_score=mom_score,
        )
        threat = calculate_threat_score(cve, momentum_score=mom_score)
        environment = classify_environment(cve, profile, backend_match)
        correlation = await get_correlation_for_cve(db, cve_key)
        await db.commit()
        corr_escalate = correlation_escalation(correlation)
        operational_priority = derive_operational_priority(
            threat.get("band", "LOW"),
            environment.get("tier", "UNKNOWN"),
            corr_escalation=corr_escalate,
        )
    finally:
        await db.close()

    return {
        "cve_id": cve_key,
        "threat": threat,
        "environment": environment,
        "operational_priority": operational_priority,
        "legacy_risk_v11b": legacy_risk,
        "momentum": momentum,
        "hasProfile": legacy_risk.get("hasProfile", False),
        "momentumScore": mom_score,
    }


@intel_router.get("/api/cves/{cve_id}/momentum")
async def cve_momentum(cve_id: str):
    """
    Compute momentum score (0–1) from EPSS trend and OTX pulse recency.
    Returns momentum_score and momentum_signals list for drawer breakdown.
    """
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        result = await calculate_momentum(cve_id, db)
    finally:
        await db.close()
    return result


@intel_router.get("/api/cves/{cve_id}/detection")
async def cve_detection(
    cve_id: str,
    product: str = Query(default="", description="Affected product name for rule title generation"),
):
    """
    Detection engineering resource for a CVE.
    Returns:
    - sigma_rules: community Sigma rules from SigmaHQ (cached 24h)
    - elastic_rules: community Elastic detection rules (cached 24h)
    - generated_sigma: template-based Sigma YAML (supplement; always generated)
    - generated_sigma_meta: briefr_basis, briefr_class, confidence, status
    - siem_queries: 4-platform quick-search queries (Elastic/Splunk/Sentinel/QRadar)
    - log_patterns: plain-English detection patterns from ATT&CK guidance
    """
    cve_id = require_cve_id(cve_id)

    github_token = os.environ.get("GITHUB_TOKEN", "")
    cve_upper = cve_id

    technique_ids: list[str] = []
    sigma_rules: list = []
    elastic_rules: list = []
    has_community_rules = False
    generated_sigma = None
    generated_sigma_meta = None
    detection_context = None
    siem_queries: dict = {}
    yara_rules: list = []
    detection_provenance = None
    db = await get_db()
    try:
        # Get CVE metadata for context
        row = await db.execute_fetchall(
            "SELECT description, mitre_technique, cwe_ids FROM cves WHERE cve_id = ?",
            (cve_upper,),
        )
        cve_desc = ""
        primary_technique = ""
        cwe_ids: list[str] = []
        if row:
            cve_desc = row[0]["description"] or ""
            primary_technique = row[0]["mitre_technique"] or ""
            raw_cwe = row[0]["cwe_ids"]
            if raw_cwe:
                try:
                    parsed = json.loads(raw_cwe) if isinstance(raw_cwe, str) else raw_cwe
                    if isinstance(parsed, list):
                        cwe_ids = [str(c) for c in parsed if str(c).strip()]
                except (json.JSONDecodeError, TypeError):
                    cwe_ids = []

        # Get all linked techniques
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id FROM cve_technique_map WHERE cve_id = ?",
            (cve_upper,),
        )
        technique_ids = [r["technique_id"] for r in tech_rows]
        if primary_technique and primary_technique not in technique_ids:
            technique_ids.insert(0, primary_technique)

        # Sigma + Elastic lookups must not share one asyncpg connection — unlike
        # SQLite, Postgres connections reject concurrent queries on the same
        # session ("another operation is in progress"), which poisoned the pool
        # when close() could not roll back and never released the connection.
        sigma_rules = await find_sigma_rules(db, cve_upper, technique_ids, github_token)
        elastic_rules = await find_elastic_rules(db, technique_ids, github_token)
        await db.commit()

        # Generate Sigma rule if no community rules found
        first_technique = technique_ids[0] if technique_ids else ""
        has_community_rules = bool(sigma_rules or elastic_rules)
        detection_context = await get_detection_context(db, cve_upper)
        generated_sigma, generated_sigma_meta = generate_sigma_rule_bundle(
            cve_id=cve_upper,
            technique_id=first_technique,
            product=product.strip() or "Affected Product",
            description=cve_desc[:200] if cve_desc else "",
            cwe_ids=cwe_ids,
            detection_context=detection_context,
        )

        # SIEM queries based on primary technique
        siem_queries = get_siem_queries(
            technique_id=first_technique,
            cve_id=cve_upper,
            product=product.strip(),
            cwe_ids=cwe_ids,
            detection_context=detection_context,
        )

        from detection.yara_generator import find_yara_rules_for_cve

        yara_rules = await find_yara_rules_for_cve(db, cve_upper)

        detection_provenance = await derive_detection_provenance(
            db,
            cve_upper,
            technique_ids=technique_ids,
        )

    except Exception as exc:
        logger.exception("Detection lookup failed for %s", cve_upper)
        raise HTTPException(
            status_code=500,
            detail="Detection lookup failed",
        ) from exc
    finally:
        await db.close()

    return {
        "cve_id": cve_upper,
        "technique_ids": technique_ids[:5],
        "sigma_rules": sigma_rules,
        "elastic_rules": elastic_rules,
        "has_community_rules": has_community_rules,
        "generated_sigma": generated_sigma,
        "generated_sigma_meta": generated_sigma_meta,
        "detection_context": detection_context,
        "siem_queries": siem_queries,
        "yara_rules": yara_rules,
        "provenance": detection_provenance,
    }


@intel_router.get("/api/cves/{cve_id}/correlation")
async def cve_correlation(
    cve_id: str,
    sector: str = Query(default="", description="User's declared industry sector for actor matching"),
):
    """
    On-demand correlation for a CVE.
    Level 1: shared exploitation indicators with other CVEs (OTX pulse IOCs).
    Level 2: ATT&CK groups linked to this CVE's techniques, matched against user sector.
    Level 3: temporal vendor volume anomalies (pre-computed nightly).
    v2: pulse-centric campaign clusters with evidence receipts.
    Results are cached for 6 hours.
    """
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        result = await get_correlation_for_cve(
            db, cve_id, user_sector=sector.strip()
        )
        result["provenance"] = derive_correlation_provenance(
            result,
            otx_configured=otx_configured_from_env(),
        )
        await db.commit()
    finally:
        await db.close()

    return result


@intel_router.get("/api/cves/{cve_id}/greynoise-scans")
async def cve_greynoise_scans(cve_id: str):
    """
    On-demand GreyNoise scanning context for IPs mentioned in this CVE.
    Not called on drawer open — preserves the 50/week Community API quota.
    """
    cve_id = require_cve_id(cve_id)

    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    if not greynoise_key:
        return {"configured": False, "scans": []}

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT description, source_urls FROM cves WHERE cve_id = ?",
            (cve_id,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
        row = rows[0]
        source_urls = row["source_urls"]
        if source_urls and isinstance(source_urls, str):
            try:
                source_urls = json.loads(source_urls)
            except (json.JSONDecodeError, TypeError):
                source_urls = []
        scans = await greynoise_scans_for_cve(
            db,
            row["description"],
            source_urls if isinstance(source_urls, list) else [],
            greynoise_key,
        )
        await db.commit()
    finally:
        await db.close()

    return {"configured": True, "scans": scans}


class CorrelationSuppressBody(BaseModel):
    scope: str = Field(
        description="campaign_id | cve_pair | pulse_id | infrastructure"
    )
    key: dict = Field(default_factory=dict)
    reason: str = ""
    dismissed_by: str = Field(
        default="",
        description="Analyst identity, free-text until app login ships",
    )


@intel_router.get("/api/cves/{cve_id}/correlation/suppressions")
async def list_correlation_suppressions_for_cve(cve_id: str):
    """List persisted correlation suppressions for analyst review / restore."""
    cve_id = require_cve_id(cve_id)

    from correlation.suppressions import load_suppressions

    db = await get_db()
    try:
        rows = await load_suppressions(db, cve_id)
    finally:
        await db.close()

    return {"cve_id": cve_id.upper(), "suppressions": rows}


@intel_router.post("/api/cves/{cve_id}/correlation/suppress")
async def suppress_correlation_finding(cve_id: str, body: CorrelationSuppressBody):
    """Dismiss a correlation finding for this CVE (persisted across rebuilds)."""
    cve_id = require_cve_id(cve_id)

    from correlation.suppressions import add_suppression
    from database import delete_feed_cache_prefix

    db = await get_db()
    try:
        row = await add_suppression(
            db,
            cve_id,
            body.scope.strip(),
            body.key,
            body.reason.strip(),
            body.dismissed_by.strip(),
        )
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()

    return {"ok": True, "suppression": row}


@intel_router.delete("/api/cves/{cve_id}/correlation/suppress")
async def unsuppress_correlation_finding(
    cve_id: str,
    scope: str = Query(...),
    cve_id_b: str = Query(default=""),
    campaign_id: str = Query(default=""),
    pulse_id: str = Query(default=""),
):
    """Remove a correlation suppression."""
    cve_id = require_cve_id(cve_id)

    from correlation.suppressions import remove_suppression
    from database import delete_feed_cache_prefix

    key: dict = {}
    if scope == "campaign_id":
        key = {"campaign_id": campaign_id}
    elif scope == "cve_pair":
        key = {"cve_id_b": cve_id_b}
    elif scope == "pulse_id":
        key = {"pulse_id": pulse_id}
    elif scope == "infrastructure":
        key = {"cve_id_b": cve_id_b}

    db = await get_db()
    try:
        removed = await remove_suppression(db, cve_id, scope, key)
        if not removed:
            raise HTTPException(status_code=404, detail="Suppression not found")
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    finally:
        await db.close()

    return {"ok": True}


@intel_router.get("/api/kev/deadlines")
async def kev_deadlines(
    sort: str = Query(default="recent", description="Sort order: recent (by dateAdded DESC) or urgent (by dueDate ASC)"),
    limit: int = Query(default=500, ge=1, le=2000, description="Maximum rows returned"),
):
    order_clause = (
        "ORDER BY date_added DESC"
        if sort == "recent"
        else "ORDER BY due_date ASC"
    )
    cache_key = f"kev_deadlines:{sort}:{limit}"

    async def build():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                f"""
                SELECT cve_id, product, short_description, required_action, due_date,
                       date_added, vendor_project, vulnerability_name,
                       known_ransomware, cwes, updated_at
                FROM kev_deadlines
                {order_clause}
                LIMIT ?
                """,
                (limit,),
            )
        finally:
            await db.close()

        entries = []
        for row in rows:
            entry = dict(row)
            try:
                parsed_cwes = json.loads(entry.get("cwes") or "[]")
                entry["cwes"] = parsed_cwes if isinstance(parsed_cwes, list) else []
            except (json.JSONDecodeError, TypeError):
                entry["cwes"] = []
            entry["ransomware_use"] = (
                str(entry.get("known_ransomware") or "").strip().lower() == "known"
            )
            entries.append(entry)

        return {"data": entries}

    return await cached_read(cache_key, DEFAULT_TTL_SECONDS, build)
