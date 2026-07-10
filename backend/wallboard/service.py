"""Wallboard aggregated payload (Beta V1.4 Theme 4).

Read-only intel posture tiles built from existing DB state and cached
snapshots — no outbound HTTP, no admin data, no secrets.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from brief.service import build_morning_brief
from database import get_cve_count, get_db, get_feed_cache, get_last_updated, set_feed_cache
from preferences.repo import get_effective_stack_terms
from feeds.case_study_feed import get_incident_feed, get_incident_feed_status
from resilient_client import get_feed_health
from routers.cves import _row_to_cve_dict, _stack_match_clause
from routers.forge import _coverage_status
from scheduler import get_ingest_status, refresh_in_progress
from scoring.risk import calculate_momentum, calculate_risk_score

WALLBOARD_CACHE_KEY = "wallboard:snapshot"
# Short TTL — kiosk polls every 60–120s; keeps repeated polls under 2s.
WALLBOARD_CACHE_MAX_AGE_HOURS = 45 / 3600.0
_TOP_RISK_CANDIDATES = 25
_TOP_RISK_RETURN = 5
_HEADLINE_LIMIT = 12
_GAP_PREVIEW = 5


def _is_postgres_connection(db: Any) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _default_timezone() -> str:
    return os.environ.get("DEFAULT_TIMEZONE", "UTC").strip() or "UTC"


async def get_wallboard_payload() -> dict[str, Any]:
    """Serve the aggregated wallboard payload, using feed_cache when fresh."""
    db = await get_db()
    try:
        cached = await get_feed_cache(
            db, WALLBOARD_CACHE_KEY, WALLBOARD_CACHE_MAX_AGE_HOURS
        )
        if cached:
            return cached

        payload = await _build_wallboard_payload(db)
        await set_feed_cache(db, WALLBOARD_CACHE_KEY, payload)
        await db.commit()
        return payload
    finally:
        await db.close()


async def _build_wallboard_payload(db: Any) -> dict[str, Any]:
    stack = await get_effective_stack_terms(db)
    now = datetime.now(timezone.utc)

    kev_on_stack = await _kev_on_stack_tile(db, stack)
    changes_24h = await _changes_24h_tile(db, stack)
    top_risk = await _top_risk_tile(db, stack)
    ingest_health = await _ingest_health_tile(db)
    ingest_strip = _ingest_strip_tile(ingest_health)
    coverage_gaps = await _coverage_gaps_tile(db, stack)
    headlines = await _headlines_tile()
    kev_due_soon = await _kev_due_soon_tile(db, stack, changes_24h)
    epss_movers = await _epss_movers_tile(db, stack, changes_24h)
    campaigns = await _campaigns_tile(db)
    source_health = _source_health_table(ingest_health)

    return {
        "meta": {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timezone": _default_timezone(),
            "stack_terms": _stack_match_clause(stack)[2],
            "stack_configured": bool(_stack_match_clause(stack)[0]),
            "cached": False,
        },
        "kev_on_stack": kev_on_stack,
        "kev_due_soon": kev_due_soon,
        "changes_24h": changes_24h,
        "top_risk": top_risk,
        "ingest_health": ingest_health,
        "ingest_strip": ingest_strip,
        "coverage_gaps": coverage_gaps,
        "epss_movers": epss_movers,
        "campaigns": campaigns,
        "source_health": source_health,
        "headlines": headlines,
    }


async def _kev_on_stack_tile(db: Any, stack: str) -> dict[str, Any]:
    clause, params, terms = _stack_match_clause(stack)
    if not clause:
        return {
            "count": 0,
            "stack_configured": False,
            "stack_terms": [],
        }

    rows = await db.execute_fetchall(
        f"""
        SELECT COUNT(*) AS n
        FROM cves c
        WHERE c.is_kev = 1 AND {clause}
        """,
        params,
    )
    return {
        "count": int(rows[0]["n"] or 0),
        "stack_configured": True,
        "stack_terms": terms,
    }


async def _changes_24h_tile(db: Any, stack: str) -> dict[str, Any]:
    brief = await build_morning_brief(db, stack=stack or None, since_hours=24, limit=5)
    sections = brief.get("sections") or {}
    section_counts = {
        key: int((sections.get(key) or {}).get("count") or 0)
        for key in ("epss_movers", "new_kev", "kev_due_soon", "stack_matches")
    }
    highlights = []
    for item in (brief.get("action_queue") or [])[:5]:
        highlights.append({
            "cve_id": item.get("cve_id"),
            "severity": item.get("severity"),
            "summary": (item.get("summary") or item.get("description") or "")[:160],
            "reasons": item.get("reasons") or [],
            "is_kev": bool(item.get("is_kev")),
        })
    return {
        "since_hours": 24,
        "section_counts": section_counts,
        "action_queue_count": len(brief.get("action_queue") or []),
        "highlights": highlights,
    }


async def _top_risk_tile(db: Any, stack: str = "") -> dict[str, Any]:
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)
    where_extra = ""
    params: list[Any] = []
    if stack_clause:
        where_extra = f" AND {stack_clause}"
        params = list(stack_params)

    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published,
               c.modified, c.affected_products, c.affected_products_source,
               c.mitre_technique, c.summary, c.is_kev, c.epss_score, c.has_poc,
               c.patch_available, c.has_ai_context, c.source_urls, c.cwe_ids,
               c.updated_at,
               k.date_added AS kev_date_added,
               k.due_date AS kev_due_date
        FROM cves c
        LEFT JOIN kev_deadlines k ON k.cve_id = c.cve_id
        WHERE (c.is_kev = 1
           OR c.epss_score >= 0.05
           OR c.cvss_score >= 7.0){where_extra}
        ORDER BY
          CASE WHEN c.is_kev = 1 THEN 0 ELSE 1 END,
          CASE WHEN c.epss_score IS NOT NULL THEN c.epss_score ELSE -1 END DESC,
          CASE WHEN c.cvss_score IS NOT NULL THEN c.cvss_score ELSE -1 END DESC
        LIMIT ?
        """,
        (*params, _TOP_RISK_CANDIDATES),
    )

    scored: list[dict[str, Any]] = []
    for raw in rows:
        cve = _row_to_cve_dict(raw)
        momentum = await calculate_momentum(cve["cve_id"], db)
        risk = calculate_risk_score(
            cve,
            momentum_score=momentum.get("momentum_score", 0.0),
        )
        total = risk.get("total")
        if total is None:
            continue
        scored.append({
            "cve_id": cve["cve_id"],
            "risk_score": total,
            "severity": cve.get("severity"),
            "summary": (cve.get("summary") or cve.get("description") or "")[:160],
            "is_kev": bool(cve.get("is_kev")),
            "epss_score": cve.get("epss_score"),
        })

    scored.sort(key=lambda item: item["risk_score"], reverse=True)
    return {"items": scored[:_TOP_RISK_RETURN], "stack_filtered": bool(stack_clause), "stack_terms": stack_terms}


async def _ingest_health_tile(db: Any) -> dict[str, Any]:
    cve_count = await get_cve_count(db)
    last_updated = await get_last_updated(db)
    incidents_status = await get_incident_feed_status()
    ingest = get_ingest_status()

    feed_health = get_feed_health()
    open_circuits = sum(
        1 for src in feed_health.values() if src.get("circuit_open")
    )
    stale_sources = sum(
        1 for src in feed_health.values() if src.get("last_success") is None
    )

    return {
        "status": "ok",
        "cve_count": cve_count,
        "last_updated": last_updated,
        "refresh_in_progress": refresh_in_progress(),
        "open_circuit_count": open_circuits,
        "never_synced_source_count": stale_sources,
        "feeds": {
            "incidents": incidents_status,
            "sources": feed_health,
        },
        "ingest": ingest,
    }


def _ingest_strip_tile(ingest_health: dict[str, Any]) -> dict[str, Any]:
    ingest = ingest_health.get("ingest") or {}
    status = "SYNCING" if ingest_health.get("refresh_in_progress") else (
        "DEGRADED" if (ingest_health.get("open_circuit_count") or 0) > 0 else "OK"
    )
    return {
        "status": status,
        "cve_count": ingest_health.get("cve_count"),
        "open_circuits": ingest_health.get("open_circuit_count"),
        "nvd_age_hours": ingest.get("nvd_age_hours"),
        "kev_age_hours": ingest.get("kev_age_hours"),
        "epss_age_hours": ingest.get("epss_age_hours"),
    }


def _source_health_table(ingest_health: dict[str, Any]) -> dict[str, Any]:
    sources = ingest_health.get("feeds", {}).get("sources") or {}
    rows = []
    for name, meta in sorted(sources.items()):
        rows.append({
            "source": name,
            "circuit_open": bool(meta.get("circuit_open")),
            "last_success": meta.get("last_success"),
            "last_error": (meta.get("last_error") or "")[:120] or None,
        })
    return {"rows": rows, "open_count": ingest_health.get("open_circuit_count", 0)}


async def _kev_due_soon_tile(
    db: Any,
    stack: str,
    changes_24h: dict[str, Any],
) -> dict[str, Any]:
    clause, params, terms = _stack_match_clause(stack)
    if not clause:
        return {"count": 0, "items": [], "stack_configured": False, "stack_terms": []}

    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, k.due_date, c.summary, c.description
        FROM cves c
        JOIN kev_deadlines k ON k.cve_id = c.cve_id
        WHERE c.is_kev = 1
          AND k.due_date IS NOT NULL
          AND k.due_date <= {"CURRENT_DATE + INTERVAL '7 days'" if _is_postgres_connection(db) else "date('now', '+7 days')"}
          AND {clause}
        ORDER BY k.due_date ASC
        LIMIT 5
        """,
        params,
    )
    items = [{
        "cve_id": r["cve_id"],
        "due_date": r["due_date"],
        "summary": (r["summary"] or r["description"] or "")[:120],
    } for r in rows]
    return {
        "count": int((changes_24h.get("section_counts") or {}).get("kev_due_soon") or len(items)),
        "items": items,
        "stack_configured": True,
        "stack_terms": terms,
    }


async def _epss_movers_tile(
    db: Any,
    stack: str,
    changes_24h: dict[str, Any],
) -> dict[str, Any]:
    brief_section = (changes_24h.get("section_counts") or {}).get("epss_movers", 0)
    clause, params, _ = _stack_match_clause(stack)
    if clause:
        where = f"WHERE {clause}"
        from_table = "cves c"
    else:
        where = ""
        from_table = "cves"
    order = "epss_score DESC NULLS LAST" if _is_postgres_connection(db) else "epss_score DESC"
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, epss_score, summary, description
        FROM {from_table}
        {where}
        ORDER BY {order}
        LIMIT 5
        """,
        params if clause else [],
    )
    items = [{
        "cve_id": r["cve_id"],
        "epss_score": r["epss_score"],
        "summary": (r["summary"] or r["description"] or "")[:120],
    } for r in rows if r["epss_score"] is not None]
    return {"count": int(brief_section or len(items)), "items": items[:5]}


async def _campaigns_tile(db: Any) -> dict[str, Any]:
    try:
        rows = await db.execute_fetchall(
            """
            SELECT campaign_id, label, member_count, confidence
            FROM correlation_campaigns
            WHERE lifecycle = 'active' OR lifecycle IS NULL OR lifecycle = ''
            ORDER BY member_count DESC, label ASC
            LIMIT 5
            """
        )
    except Exception:
        return {"active_count": 0, "items": []}
    items = [{
        "campaign_id": r["campaign_id"],
        "name": r["label"] or r["campaign_id"],
        "member_count": int(r["member_count"] or 0),
        "confidence": r["confidence"],
    } for r in rows]
    count_row = await db.execute_fetchall("SELECT COUNT(*) AS n FROM correlation_campaigns")
    active = int(count_row[0]["n"] or 0) if count_row else len(items)
    return {"active_count": active, "items": items}


async def _coverage_gaps_tile(db: Any, stack: str) -> dict[str, Any]:
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)
    cve_filter = ""
    params: list = []
    if stack_clause:
        cve_filter = (
            f"WHERE m.cve_id IN (SELECT cve_id FROM cves WHERE {stack_clause})"
        )
        params = list(stack_params)

    exposure_rows = await db.execute_fetchall(
        f"""
        SELECT m.technique_id,
               COUNT(DISTINCT m.cve_id) AS cve_count,
               SUM(CASE WHEN c.is_kev = 1 THEN 1 ELSE 0 END) AS kev_count
        FROM cve_technique_map m
        JOIN cves c ON c.cve_id = m.cve_id
        {cve_filter}
        GROUP BY m.technique_id
        """,
        params,
    )
    pack_rows = await db.execute_fetchall(
        "SELECT technique_id, COUNT(*) AS pack_count FROM hunt_packs GROUP BY technique_id"
    )
    technique_rows = await db.execute_fetchall(
        "SELECT technique_id, name, tactic FROM mitre_techniques"
    )

    packs_by_technique = {r["technique_id"]: r["pack_count"] for r in pack_rows}
    meta_by_technique = {
        r["technique_id"]: {"name": r["name"], "tactic": r["tactic"]}
        for r in technique_rows
    }

    status_counts = {"yours": 0, "community": 0, "gap": 0}
    gap_items: list[dict[str, Any]] = []

    for row in exposure_rows:
        tid = row["technique_id"]
        pack_count = packs_by_technique.get(tid, 0)
        status = _coverage_status(pack_count, tid)
        status_counts[status] += 1
        if status != "gap":
            continue
        meta = meta_by_technique.get(tid, {})
        gap_items.append({
            "technique_id": tid,
            "name": meta.get("name", ""),
            "tactic": meta.get("tactic", ""),
            "cve_count": int(row["cve_count"] or 0),
            "kev_count": int(row["kev_count"] or 0),
        })

    gap_items.sort(
        key=lambda item: (-(item["kev_count"]), -(item["cve_count"]), item["technique_id"])
    )

    return {
        "counts": status_counts,
        "gap_count": status_counts["gap"],
        "top_gaps": gap_items[:_GAP_PREVIEW],
        "stack_terms": stack_terms,
    }


async def _headlines_tile() -> dict[str, Any]:
    cards, errors, meta = await get_incident_feed(atlas_limit=40)
    items = []
    for card in (cards or [])[:_HEADLINE_LIMIT]:
        title = (card.get("title") or "").strip()
        if not title:
            continue
        items.append({
            "title": title,
            "source": card.get("source") or card.get("sourceId") or "",
            "published_at": card.get("publishedAt") or "",
        })
    return {
        "items": items,
        "meta": meta,
        "error_count": len(errors or []),
    }
