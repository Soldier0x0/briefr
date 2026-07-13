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
from notifications.emit import emit_kev_backlog_notification
from preferences.repo import get_effective_stack_terms
from routers.forge import _coverage_status, _derive_priority

logger = logging.getLogger(__name__)

REASON_KEV_GAP = "kev_gap"


async def _notify_new_backlog_items(db: DbConnection, created: list[dict[str, Any]]) -> None:
    """In-app notification per new backlog row (forge-redesign.md §4) —
    scheduler-side only, called from process_new_kev_backlog /
    reconcile_kev_backlog after the backlog insert already committed.
    Failure here must never fail the backlog refresh itself."""
    for item in created:
        try:
            await emit_kev_backlog_notification(
                db,
                cve_id=item["cve_id"],
                technique_id=item["technique_id"],
                technique_name=item.get("technique_name") or item["technique_id"],
                priority=item.get("priority", "medium"),
                dedupe_key=f"kev_backlog:{item['cve_id']}:{item['technique_id']}",
            )
        except Exception as exc:
            logger.warning(
                "KEV backlog notification failed for %s/%s: %s",
                item.get("cve_id"), item.get("technique_id"), exc,
            )
    await db.commit()


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


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


async def upsert_gap_items_for_cves(
    db: DbConnection,
    cve_rows: list[dict[str, Any]],
    *,
    stack_terms: str,
    reason: str = REASON_KEV_GAP,
) -> list[dict[str, Any]]:
    """Create open backlog rows for stack KEV CVEs whose techniques are coverage gaps."""
    if not cve_rows:
        return []

    cve_ids = [c["cve_id"] for c in cve_rows]
    pg = _is_postgres_connection(db)
    placeholders = ",".join(f"${i+1}" if pg else "?" for i in range(len(cve_ids)))

    # 1. Batch fetch techniques for all CVEs
    cve_techniques: dict[str, set[str]] = {cid: set() for cid in cve_ids}
    tech_rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, technique_id AS tid FROM cve_technique_map WHERE cve_id IN ({placeholders})
        UNION
        SELECT cve_id, mitre_technique AS tid FROM cves
        WHERE cve_id IN ({placeholders}) AND COALESCE(mitre_technique, '') != ''
        """,
        tuple(cve_ids) + tuple(cve_ids),
    )
    all_techniques = set()
    for row in tech_rows:
        cid = row["cve_id"]
        tid = (row["tid"] or "").strip().upper()
        if tid:
            cve_techniques.setdefault(cid, set()).add(tid)
            all_techniques.add(tid)

    if not all_techniques:
        return []

    # 2. Batch fetch hunt pack counts for all techniques (to check gaps)
    tech_list = list(all_techniques)
    tech_placeholders = ",".join(f"${i+1}" if pg else "?" for i in range(len(tech_list)))
    pack_rows = await db.execute_fetchall(
        f"""
        SELECT technique_id, COUNT(*) AS n FROM hunt_packs 
        WHERE technique_id IN ({tech_placeholders})
        GROUP BY technique_id
        """,
        tuple(tech_list),
    )
    pack_counts = {r["technique_id"]: int(r["n"]) for r in pack_rows}

    # 3. Batch fetch mitre technique names
    tech_name_rows = await db.execute_fetchall(
        f"""
        SELECT technique_id, name FROM mitre_techniques
        WHERE technique_id IN ({tech_placeholders})
        """,
        tuple(tech_list),
    )
    tech_names = {r["technique_id"]: r["name"] for r in tech_name_rows}

    # 4. Batch fetch existing backlog items to prevent duplicates
    existing_rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, technique_id FROM detection_backlog
        WHERE cve_id IN ({placeholders}) AND reason = {_placeholder(pg, len(cve_ids) + 1)}
        """,
        tuple(cve_ids) + (reason,),
    )
    existing_set = {(r["cve_id"], r["technique_id"]) for r in existing_rows}

    # 5. Insert new items and gather values to insert
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    to_insert = []
    
    for cve in cve_rows:
        cve_id = cve["cve_id"]
        techniques = sorted(cve_techniques.get(cve_id, set()))
        if not techniques:
            continue

        priority = _derive_priority(
            bool(cve.get("is_kev")),
            cve.get("cvss_score"),
            cve.get("epss_score"),
        )

        for technique_id in techniques:
            pack_count = pack_counts.get(technique_id, 0)
            if _coverage_status(pack_count, technique_id) != "gap":
                continue

            if (cve_id, technique_id) in existing_set:
                continue

            technique_name = tech_names.get(technique_id) or technique_id
            to_insert.append((
                cve_id,
                technique_id,
                reason,
                priority,
                "open",
                stack_terms,
                technique_name,
                now,
            ))

    if not to_insert:
        return []

    # Insert in batch using executemany
    sql = """
    INSERT INTO detection_backlog (
        cve_id, technique_id, reason, priority, status,
        stack_terms, technique_name, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """ if pg else """
    INSERT INTO detection_backlog (
        cve_id, technique_id, reason, priority, status,
        stack_terms, technique_name, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    await db.executemany(sql, to_insert)

    # 6. Fetch and return all newly created backlog rows in one query
    created_rows = await db.execute_fetchall(
        f"""
        SELECT id, cve_id, technique_id, reason, priority, status,
               stack_terms, technique_name, created_at, dismissed_at
        FROM detection_backlog
        WHERE cve_id IN ({placeholders}) AND reason = {_placeholder(pg, len(cve_ids) + 1)}
          AND created_at = {_placeholder(pg, len(cve_ids) + 2)}
        """,
        tuple(cve_ids) + (reason, now),
    )
    return [dict(r) for r in created_rows]


async def _enrich_cve_scores(db: DbConnection, cve_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not cve_rows:
        return []
    cve_ids = [c["cve_id"] for c in cve_rows]
    pg = _is_postgres_connection(db)
    placeholders = ",".join(f"${i+1}" if pg else "?" for i in range(len(cve_ids)))
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, is_kev, cvss_score, epss_score
        FROM cves WHERE cve_id IN ({placeholders})
        """,
        tuple(cve_ids),
    )
    return [dict(r) for r in rows]


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
            await _notify_new_backlog_items(db, created)
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
            await _notify_new_backlog_items(db, created)
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
