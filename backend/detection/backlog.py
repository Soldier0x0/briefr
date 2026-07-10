"""KEV-driven detection backlog (V1.5 Theme 3).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from database import get_db
from db.enrichment import filter_cves_matching_stack
from db.types import DbConnection
from preferences.repo import get_effective_stack_terms
from routers.forge import _coverage_status, _derive_priority

logger = logging.getLogger(__name__)

REASON_KEV_GAP = "kev_gap"


async def _fetchone(db: DbConnection, sql: str, params: tuple = ()) -> Any | None:
    rows = await db.execute_fetchall(sql, params)
    return rows[0] if rows else None


async def _techniques_for_cve(db: DbConnection, cve_id: str) -> list[str]:
    rows = await db.execute_fetchall(
        """
        SELECT DISTINCT technique_id AS tid FROM cve_technique_map WHERE cve_id = ?
        UNION
        SELECT mitre_technique AS tid FROM cves
        WHERE cve_id = ? AND COALESCE(mitre_technique, '') != ''
        """,
        (cve_id, cve_id),
    )
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        tid = (row["tid"] or "").strip().upper()
        if tid and tid not in seen:
            seen.add(tid)
            out.append(tid)
    return out


async def _pack_count(db: DbConnection, technique_id: str) -> int:
    row = await _fetchone(
        db,
        "SELECT COUNT(*) AS n FROM hunt_packs WHERE technique_id = ?",
        (technique_id,),
    )
    return int(row["n"]) if row else 0


async def _technique_name(db: DbConnection, technique_id: str) -> str:
    row = await _fetchone(
        db,
        "SELECT name FROM mitre_techniques WHERE technique_id = ?",
        (technique_id,),
    )
    if row and row["name"]:
        return str(row["name"])
    return technique_id


async def upsert_gap_items_for_cves(
    db: DbConnection,
    cve_rows: list[dict[str, Any]],
    *,
    stack_terms: str,
    reason: str = REASON_KEV_GAP,
) -> list[dict[str, Any]]:
    """Create open backlog rows for stack KEV CVEs whose techniques are coverage gaps."""
    created: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for cve in cve_rows:
        cve_id = cve["cve_id"]
        techniques = await _techniques_for_cve(db, cve_id)
        if not techniques:
            continue

        priority = _derive_priority(
            bool(cve.get("is_kev")),
            cve.get("cvss_score"),
            cve.get("epss_score"),
        )

        for technique_id in techniques:
            pack_count = await _pack_count(db, technique_id)
            if _coverage_status(pack_count, technique_id) != "gap":
                continue

            existing = await _fetchone(
                db,
                """
                SELECT id, status FROM detection_backlog
                WHERE cve_id = ? AND technique_id = ? AND reason = ?
                """,
                (cve_id, technique_id, reason),
            )
            if existing:
                continue

            technique_name = await _technique_name(db, technique_id)
            await db.execute(
                """
                INSERT INTO detection_backlog (
                    cve_id, technique_id, reason, priority, status,
                    stack_terms, technique_name, created_at
                ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
                """,
                (
                    cve_id,
                    technique_id,
                    reason,
                    priority,
                    stack_terms,
                    technique_name,
                    now,
                ),
            )
            row = await _fetchone(
                db,
                """
                SELECT id, cve_id, technique_id, reason, priority, status,
                       stack_terms, technique_name, created_at, dismissed_at
                FROM detection_backlog
                WHERE cve_id = ? AND technique_id = ? AND reason = ?
                """,
                (cve_id, technique_id, reason),
            )
            if row:
                created.append(dict(row))

    return created


async def _enrich_cve_scores(db: DbConnection, cve_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cve in cve_rows:
        row = await _fetchone(
            db,
            """
            SELECT cve_id, is_kev, cvss_score, epss_score
            FROM cves WHERE cve_id = ?
            """,
            (cve["cve_id"],),
        )
        if row:
            out.append(dict(row))
    return out


async def process_new_kev_backlog(newly_kev_ids: list[str]) -> list[dict[str, Any]]:
    """Create backlog items when CVEs newly enter KEV and match the operator stack."""
    if not newly_kev_ids:
        return []

    db = await get_db()
    try:
        stack = await get_effective_stack_terms(db)
        if not stack.strip():
            logger.debug("KEV backlog skipped: no stack terms configured")
            return []

        matches = await filter_cves_matching_stack(db, newly_kev_ids, stack)
        if not matches:
            return []

        enriched = await _enrich_cve_scores(db, matches)
        created = await upsert_gap_items_for_cves(db, enriched, stack_terms=stack)
        if created:
            await db.commit()
            logger.info("KEV backlog: %d new gap item(s)", len(created))
        return created
    finally:
        await db.close()


async def reconcile_kev_backlog() -> int:
    """Weekly safety net: backlog rows for all stack-matched KEV CVEs with gap techniques."""
    db = await get_db()
    try:
        from routers.cves import _stack_match_clause

        stack = await get_effective_stack_terms(db)
        clause, params, _terms = _stack_match_clause(stack)
        if not clause:
            return 0

        rows = await db.execute_fetchall(
            f"""
            SELECT c.cve_id, c.is_kev, c.cvss_score, c.epss_score
            FROM cves c
            WHERE c.is_kev = 1 AND {clause}
            """,
            tuple(params),
        )
        if not rows:
            return 0

        created = await upsert_gap_items_for_cves(
            db,
            [dict(r) for r in rows],
            stack_terms=stack,
        )
        if created:
            await db.commit()
            logger.info("KEV backlog reconcile: %d new gap item(s)", len(created))
        return len(created)
    finally:
        await db.close()


async def list_backlog_items(
    db: DbConnection,
    *,
    status: str = "open",
    stack: str | None = None,
) -> list[dict[str, Any]]:
    status_norm = (status or "open").strip().lower()
    if status_norm not in {"open", "dismissed", "all"}:
        status_norm = "open"

    params: list[Any] = []
    clauses = ["1=1"]
    if status_norm != "all":
        clauses.append("status = ?")
        params.append(status_norm)

    stack_filter = (stack or "").strip()
    if stack_filter:
        clauses.append("stack_terms = ?")
        params.append(stack_filter)

    rows = await db.execute_fetchall(
        f"""
        SELECT b.id, b.cve_id, b.technique_id, b.reason, b.priority, b.status,
               b.stack_terms, b.technique_name, b.created_at, b.dismissed_at,
               c.severity, c.cvss_score, c.epss_score, c.is_kev,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = b.cve_id) AS kev_due_date
        FROM detection_backlog b
        LEFT JOIN cves c ON c.cve_id = b.cve_id
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE b.priority
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                ELSE 3
            END,
            b.created_at DESC
        """,
        tuple(params),
    )
    return [dict(row) for row in rows]


async def dismiss_backlog_item(db: DbConnection, item_id: int) -> dict[str, Any] | None:
    row = await _fetchone(
        db,
        "SELECT id, status FROM detection_backlog WHERE id = ?",
        (item_id,),
    )
    if not row:
        return None
    if row["status"] == "dismissed":
        return dict(row)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """
        UPDATE detection_backlog
        SET status = 'dismissed', dismissed_at = ?
        WHERE id = ?
        """,
        (now, item_id),
    )
    updated = await _fetchone(
        db,
        """
        SELECT id, cve_id, technique_id, reason, priority, status,
               stack_terms, technique_name, created_at, dismissed_at
        FROM detection_backlog WHERE id = ?
        """,
        (item_id,),
    )
    return dict(updated) if updated else None
