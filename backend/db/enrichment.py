"""Enrichment: KEV/EPSS updates, change history, display-field backfills. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from db.cve import (
    _SQLITE_IN_CHUNK,
    _change_value_str,
    _insert_cve_changes_batch,
)
from db.timeutil import utcnow_str
from db.types import DbConnection

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

_WRITE_AUDIT_LOG_SQLITE = (
    "INSERT INTO audit_log (actor, action, target, metadata_json) VALUES (?, ?, ?, ?)"
)
_WRITE_AUDIT_LOG_PG = (
    "INSERT INTO audit_log (actor, action, target, metadata_json) VALUES ($1, $2, $3, $4)"
)

# Keyset pages — avoid one whole-table INSERT…SELECT that can exceed command_timeout.
_SNAPSHOT_EPSS_PAGE_SQLITE = """
INSERT OR REPLACE INTO epss_history (cve_id, score, recorded_date)
SELECT cve_id, epss_score, ?
FROM cves
WHERE epss_score IS NOT NULL
  AND cve_id > ?
ORDER BY cve_id
LIMIT ?
"""

_SNAPSHOT_EPSS_PAGE_PG = """
INSERT INTO epss_history (cve_id, score, recorded_date)
SELECT cve_id, epss_score, $1
FROM cves
WHERE epss_score IS NOT NULL
  AND cve_id > $2
ORDER BY cve_id
LIMIT $3
ON CONFLICT (cve_id, recorded_date) DO UPDATE SET
    score = excluded.score
"""

_SELECT_EPSS_PAGE_CURSOR_SQLITE = """
SELECT cve_id FROM cves
WHERE epss_score IS NOT NULL AND cve_id > ?
ORDER BY cve_id
LIMIT ?
"""

_SELECT_EPSS_PAGE_CURSOR_PG = """
SELECT cve_id FROM cves
WHERE epss_score IS NOT NULL AND cve_id > $1
ORDER BY cve_id
LIMIT $2
"""

_UPDATE_EPSS_SQLITE = (
    "UPDATE cves SET epss_score = ?, epss_percentile = ? WHERE cve_id = ?"
)
_UPDATE_EPSS_PG = (
    "UPDATE cves SET epss_score = $1, epss_percentile = $2 WHERE cve_id = $3"
)

_GET_EPSS_HISTORY_SQLITE = """
SELECT recorded_date AS date, score
FROM epss_history
WHERE cve_id = ?
  AND recorded_date >= ?
ORDER BY recorded_date ASC
"""

_GET_EPSS_HISTORY_PG = """
SELECT recorded_date AS date, score
FROM epss_history
WHERE cve_id = $1
  AND recorded_date >= $2
ORDER BY recorded_date ASC
"""

_BACKFILL_DISPLAY_UPDATE_SQLITE = """
UPDATE cves
SET mitre_technique = COALESCE(?, mitre_technique),
    has_poc = CASE WHEN ? = 1 THEN 1 ELSE has_poc END
WHERE cve_id = ?
"""

_BACKFILL_DISPLAY_UPDATE_PG = """
UPDATE cves
SET mitre_technique = COALESCE($1, mitre_technique),
    has_poc = CASE WHEN $2 = 1 THEN 1 ELSE has_poc END
WHERE cve_id = $3
"""

_CLEAR_SUMMARY_SQLITE = "UPDATE cves SET summary = NULL WHERE cve_id = ?"
_CLEAR_SUMMARY_PG = "UPDATE cves SET summary = NULL WHERE cve_id = $1"

_BACKFILL_HAS_POC_SQLITE = "UPDATE cves SET has_poc = 1 WHERE cve_id = ?"
_BACKFILL_HAS_POC_PG = "UPDATE cves SET has_poc = 1 WHERE cve_id = $1"

_ENRICH_KEV_SUMMARIES_SQLITE = """
UPDATE cves
SET summary = (
    SELECT k.short_description
    FROM kev_deadlines k
    WHERE k.cve_id = cves.cve_id
      AND k.short_description IS NOT NULL
      AND k.short_description != ''
)
WHERE is_kev = 1
  AND (summary IS NULL OR summary = '')
  AND EXISTS (
    SELECT 1 FROM kev_deadlines k
    WHERE k.cve_id = cves.cve_id
      AND k.short_description IS NOT NULL
      AND k.short_description != ''
  )
"""

_ENRICH_KEV_SUMMARIES_PG = """
UPDATE cves AS c
SET summary = k.short_description
FROM kev_deadlines AS k
WHERE c.cve_id = k.cve_id
  AND c.is_kev = 1
  AND (c.summary IS NULL OR c.summary = '')
  AND k.short_description IS NOT NULL
  AND k.short_description != ''
"""

_UPSERT_KEV_SQLITE = """
INSERT INTO kev_deadlines (
    cve_id, product, short_description, required_action, due_date,
    date_added, vendor_project, vulnerability_name, known_ransomware,
    cwes, updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(cve_id) DO UPDATE SET
    product = excluded.product,
    short_description = excluded.short_description,
    required_action = excluded.required_action,
    due_date = excluded.due_date,
    date_added = excluded.date_added,
    vendor_project = excluded.vendor_project,
    vulnerability_name = excluded.vulnerability_name,
    known_ransomware = excluded.known_ransomware,
    cwes = excluded.cwes,
    updated_at = excluded.updated_at
"""

_UPSERT_KEV_PG = """
INSERT INTO kev_deadlines (
    cve_id, product, short_description, required_action, due_date,
    date_added, vendor_project, vulnerability_name, known_ransomware,
    cwes, updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT(cve_id) DO UPDATE SET
    product = excluded.product,
    short_description = excluded.short_description,
    required_action = excluded.required_action,
    due_date = excluded.due_date,
    date_added = excluded.date_added,
    vendor_project = excluded.vendor_project,
    vulnerability_name = excluded.vulnerability_name,
    known_ransomware = excluded.known_ransomware,
    cwes = excluded.cwes,
    updated_at = $11
"""

_INSERT_EPSS_HISTORY_SQLITE = """
INSERT OR IGNORE INTO epss_history (cve_id, score, recorded_date)
VALUES (?, ?, ?)
"""

_INSERT_EPSS_HISTORY_PG = """
INSERT INTO epss_history (cve_id, score, recorded_date)
VALUES ($1, $2, $3)
ON CONFLICT (cve_id, recorded_date) DO NOTHING
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _in_placeholders(count: int, *, pg: bool, start: int = 1) -> str:
    if pg:
        return ", ".join(f"${i}" for i in range(start, start + count))
    return ", ".join("?" for _ in range(count))


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


def _cve_id_filter_clause(
    cve_ids: list[str] | None, *, pg: bool, start: int = 1
) -> tuple[str, list[str]]:
    if not cve_ids:
        return "", []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return "", []
    placeholders = _in_placeholders(len(normalized), pg=pg, start=start)
    return f" AND cve_id IN ({placeholders})", normalized


def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def _cutoff_datetime_hours_ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%d %H:%M:%S")


def _since_hours_cutoff(hours: float, *, pg: bool) -> object:
    """Postgres timestamptz columns need aware datetimes; SQLite keeps TEXT."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    if pg:
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _renumber_qmark_placeholders(sql: str, start: int) -> str:
    """Rewrite ``?`` placeholders to ``$n`` starting at *start*."""
    out: list[str] = []
    n = start
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "?":
            out.append(f"${n}")
            n += 1
            i += 1
        elif ch in ("'", '"'):
            out.append(ch)
            i += 1
            while i < len(sql):
                out.append(sql[i])
                if sql[i] == ch and sql[i - 1] != "\\":
                    i += 1
                    break
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _clean_iso_date(value: str | None) -> str:
    """Keep only values that start with a YYYY-MM-DD date; drop garbage (e.g. stray header text)."""
    if isinstance(value, str) and _ISO_DATE_RE.match(value):
        return value
    return ""


def _normalize_epss_score(value: object) -> float | None:
    """NULL and ~0 are equivalent — matches init_db epss_score NULL normalization."""
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if abs(score) < 1e-9:
        return None
    return score


def _epss_display_percent(score: float | None) -> float:
    """One decimal place in percent — matches WhatChangedPanel EPSS formatting."""
    if score is None:
        return 0.0
    return round(score * 100, 1)


def _epss_scores_differ(old: object, new: object) -> bool:
    """True only when EPSS would display differently to an analyst (0.1% precision)."""
    return _epss_display_percent(_normalize_epss_score(old)) != _epss_display_percent(
        _normalize_epss_score(new)
    )


async def write_audit_log(
    db: DbConnection,
    actor: str | None,
    action: str,
    target: str = "",
    metadata: dict | None = None,
) -> None:
    """Append one audit row (caller commits). Actor is '' when no identity."""
    from redact import redact_audit_metadata

    sql = _WRITE_AUDIT_LOG_PG if _is_postgres_connection(db) else _WRITE_AUDIT_LOG_SQLITE
    safe_meta = redact_audit_metadata(action, metadata)
    metadata_json = json.dumps(safe_meta, separators=(",", ":")) if safe_meta else None
    await db.execute(sql, ((actor or "").strip(), action, target or "", metadata_json))


async def _maybe_bulk_commit(
    db: DbConnection, ops_done: int, commit_every: int | None
) -> None:
    """Commit when *ops_done* hits a multiple of *commit_every* (scheduler bulk paths)."""
    if commit_every and ops_done > 0 and ops_done % commit_every == 0:
        await db.commit()


async def mark_cves_as_kev(
    db: DbConnection,
    cve_ids: list,
    *,
    commit_every: int | None = None,
) -> list[str]:
    """Mark CVEs as KEV; return IDs that transitioned from is_kev=0 to 1.

    When *commit_every* is set (scheduler), commit after that many IN-chunks so large
    CISA KEV catalogs do not hold one transaction across hundreds of statements.
    """
    if not cve_ids:
        return []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return []
    pg = _is_postgres_connection(db)
    newly_kev: list[str] = []
    ops = 0
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, is_kev FROM cves
            WHERE cve_id IN ({placeholders}) AND is_kev = 0
            """,
            tuple(chunk),
        )
        newly_kev.extend(row["cve_id"] for row in rows)
        history = [(row["cve_id"], "is_kev", "0", "1") for row in rows]
        await _insert_cve_changes_batch(db, history)
        await db.execute(
            f"UPDATE cves SET is_kev = 1 WHERE cve_id IN ({placeholders})",
            tuple(chunk),
        )
        ops += 1
        await _maybe_bulk_commit(db, ops, commit_every)
    return newly_kev


async def snapshot_epss_scores(
    db: DbConnection,
    recorded_date: str | None = None,
    *,
    commit_every: int | None = None,
    page_size: int | None = None,
) -> int:
    """Persist current EPSS scores before a bulk update (one row per CVE per day).

    Pages by ``cve_id`` keyset so a full-corpus snapshot cannot exceed Postgres
    ``command_timeout`` on a single INSERT…SELECT. Optional *commit_every* commits
    after that many pages (scheduler).
    """
    day = recorded_date or datetime.now(timezone.utc).date().isoformat()
    pg = _is_postgres_connection(db)
    limit = page_size or _SQLITE_IN_CHUNK
    insert_sql = _SNAPSHOT_EPSS_PAGE_PG if pg else _SNAPSHOT_EPSS_PAGE_SQLITE
    cursor_sql = (
        _SELECT_EPSS_PAGE_CURSOR_PG if pg else _SELECT_EPSS_PAGE_CURSOR_SQLITE
    )
    total = 0
    after = ""
    pages = 0
    while True:
        page_rows = await db.execute_fetchall(cursor_sql, (after, limit))
        if not page_rows:
            break
        cursor = await db.execute(insert_sql, (day, after, limit))
        total += cursor.rowcount or 0
        after = page_rows[-1]["cve_id"]
        pages += 1
        await _maybe_bulk_commit(db, pages, commit_every)
        if len(page_rows) < limit:
            break
    return total


async def update_epss_scores(
    db: DbConnection,
    scores: dict,
    *,
    commit_every: int | None = None,
) -> None:
    """Apply EPSS score (and optional percentile) updates from the daily feed.

    Values may be bare floats (legacy) or ``{"score": float, "percentile": float|None}``.
    When *commit_every* is set, commit after that many UPDATE batches (scheduler).
    """
    if not scores:
        return

    normalized: dict[str, dict] = {}
    for cve_id, value in scores.items():
        if isinstance(value, dict):
            parsed = _parse_epss_feed_record(value)
        else:
            parsed = _parse_epss_feed_record({"score": value})
        if parsed is not None:
            normalized[cve_id.upper()] = parsed

    if not normalized:
        return

    pg = _is_postgres_connection(db)
    needed_list = list(normalized.keys())
    existing: dict[str, tuple[float | None, float | None]] = {}
    for i in range(0, len(needed_list), _SQLITE_IN_CHUNK):
        chunk = needed_list[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, epss_score, epss_percentile
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            tuple(chunk),
        )
        for row in rows:
            existing[row["cve_id"].upper()] = (
                row["epss_score"],
                row["epss_percentile"],
            )

    history: list[tuple[str, str, str, str]] = []
    updates: list[tuple[float, float | None, str]] = []
    for cve_id, record in normalized.items():
        if cve_id not in existing:
            continue
        old_score, old_percentile = existing[cve_id]
        score = record["score"]
        percentile = record.get("percentile")
        if not _epss_scores_differ(old_score, score):
            if old_percentile == percentile or (
                old_percentile is not None
                and percentile is not None
                and float(old_percentile) == float(percentile)
            ):
                continue
        if _epss_scores_differ(old_score, score):
            history.append(
                (
                    cve_id,
                    "epss_score",
                    _change_value_str(old_score),
                    _change_value_str(score),
                )
            )
        updates.append((score, percentile, cve_id))

    await _insert_cve_changes_batch(db, history)
    if updates:
        update_sql = _UPDATE_EPSS_PG if pg else _UPDATE_EPSS_SQLITE
        batches = 0
        for i in range(0, len(updates), _SQLITE_IN_CHUNK):
            batch = updates[i : i + _SQLITE_IN_CHUNK]
            await db.executemany(update_sql, batch)
            batches += 1
            await _maybe_bulk_commit(db, batches, commit_every)


def _parse_epss_feed_record(value: dict) -> dict | None:
    score = value.get("score", value.get("epss"))
    if score is None:
        return None
    try:
        parsed_score = float(score)
    except (TypeError, ValueError):
        return None
    percentile = value.get("percentile")
    if percentile is not None and percentile != "":
        try:
            percentile = float(percentile)
        except (TypeError, ValueError):
            percentile = None
    else:
        percentile = None
    return {"score": parsed_score, "percentile": percentile}


async def get_epss_history(db: DbConnection, cve_id: str, days: int = 30) -> list[dict]:
    cutoff = _cutoff_date_days_ago(days - 1)
    sql = _GET_EPSS_HISTORY_PG if _is_postgres_connection(db) else _GET_EPSS_HISTORY_SQLITE
    rows = await db.execute_fetchall(sql, (cve_id.upper(), cutoff))
    return [{"date": row["date"], "score": row["score"]} for row in rows]


async def backfill_display_fields(
    db: DbConnection, cve_ids: list[str] | None = None
) -> int:
    """Fill MITRE / PoC from stored NVD fields when missing (no auto plain-summary)."""
    from enrichment.cve import extract_mitre_from_urls, has_public_poc_from_urls

    pg = _is_postgres_connection(db)
    id_clause, id_params = _cve_id_filter_clause(cve_ids, pg=pg, start=1)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, source_urls, mitre_technique, has_poc
        FROM cves
        WHERE (mitre_technique IS NULL OR has_poc = 0){id_clause}
        """,
        id_params,
    )
    update_sql = (
        _BACKFILL_DISPLAY_UPDATE_PG if pg else _BACKFILL_DISPLAY_UPDATE_SQLITE
    )
    updated = 0
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        mitre = row["mitre_technique"] or extract_mitre_from_urls(urls)
        poc_flag = row["has_poc"]
        if not poc_flag:
            poc_flag = 1 if has_public_poc_from_urls(urls) else 0
        if not mitre and not poc_flag:
            continue
        await db.execute(update_sql, (mitre, poc_flag, row["cve_id"]))
        updated += 1
    return updated


async def strip_auto_generated_summaries(
    db: DbConnection, cve_ids: list[str] | None = None
) -> int:
    """Remove NVD first-sentence summaries so Plain English filter is meaningful."""
    from enrichment.cve import is_auto_generated_summary

    pg = _is_postgres_connection(db)
    id_clause, id_params = _cve_id_filter_clause(cve_ids, pg=pg, start=1)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, summary
        FROM cves
        WHERE summary IS NOT NULL AND TRIM(summary) != ''{id_clause}
        """,
        id_params,
    )
    clear_sql = _CLEAR_SUMMARY_PG if pg else _CLEAR_SUMMARY_SQLITE
    cleared = 0
    for row in rows:
        if is_auto_generated_summary(row["summary"], row["description"]):
            await db.execute(clear_sql, (row["cve_id"],))
            cleared += 1
    return cleared


async def backfill_has_poc(db: DbConnection, cve_ids: list[str] | None = None) -> int:
    """Set has_poc from stored reference URLs (no NVD re-fetch)."""
    from enrichment.cve import has_public_poc_from_urls

    pg = _is_postgres_connection(db)
    id_clause, id_params = _cve_id_filter_clause(cve_ids, pg=pg, start=1)
    rows = await db.execute_fetchall(
        f"SELECT cve_id, source_urls FROM cves WHERE has_poc = 0{id_clause}",
        id_params,
    )
    history: list[tuple[str, str, str, str]] = []
    updates: list[tuple[str]] = []
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        if not has_public_poc_from_urls(urls):
            continue
        history.append((row["cve_id"], "has_poc", "0", "1"))
        updates.append((row["cve_id"],))
    await _insert_cve_changes_batch(db, history)
    if updates:
        update_sql = _BACKFILL_HAS_POC_PG if pg else _BACKFILL_HAS_POC_SQLITE
        await db.executemany(update_sql, updates)
    return len(updates)


async def get_recent_cve_changes(
    db: DbConnection,
    *,
    limit: int = 100,
    field_name: str | None = None,
    since_hours: int | None = None,
) -> list[dict]:
    pg = _is_postgres_connection(db)
    clauses: list[str] = []
    params: list[object] = []
    pg_n = 1
    if field_name:
        clauses.append(f"ch.field_name = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(field_name)
    if since_hours is not None and since_hours > 0:
        clauses.append(f"ch.detected_at >= {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(_since_hours_cutoff(since_hours, pg=pg))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_ph = _placeholder(pg, pg_n)
    params.append(limit)
    rows = await db.execute_fetchall(
        f"""
        SELECT ch.id, ch.cve_id, ch.field_name, ch.old_value, ch.new_value,
               ch.detected_at, c.severity
        FROM cve_change_history ch
        LEFT JOIN cves c ON c.cve_id = ch.cve_id
        {where}
        ORDER BY ch.detected_at DESC, ch.id DESC
        LIMIT {limit_ph}
        """,
        params,
    )
    return [dict(r) for r in rows]


async def enrich_kev_summaries(db: DbConnection) -> int:
    """Fill plain-English summary from CISA KEV short descriptions."""
    sql = (
        _ENRICH_KEV_SUMMARIES_PG
        if _is_postgres_connection(db)
        else _ENRICH_KEV_SUMMARIES_SQLITE
    )
    cursor = await db.execute(sql)
    return cursor.rowcount


async def upsert_kev(db: DbConnection, entry: dict) -> None:
    sql = _UPSERT_KEV_PG if _is_postgres_connection(db) else _UPSERT_KEV_SQLITE
    await db.execute(sql, _kev_upsert_params(entry))


def _kev_upsert_params(entry: dict) -> tuple:
    cwes = entry.get("cwes") or []
    if not isinstance(cwes, list):
        cwes = []
    return (
        entry.get("cveID", ""),
        entry.get("product", ""),
        entry.get("shortDescription", ""),
        entry.get("requiredAction", ""),
        _clean_iso_date(entry.get("dueDate", "")),
        _clean_iso_date(entry.get("dateAdded", "")),
        entry.get("vendorProject", ""),
        entry.get("vulnerabilityName", ""),
        entry.get("knownRansomwareCampaignUse", ""),
        json.dumps(cwes),
        utcnow_str(),
    )


async def upsert_kev_batch(db: DbConnection, entries: list[dict]) -> int:
    """PR-P4 (DB-004): batch the full-catalog KEV upsert instead of one
    execute() round-trip per row (~1,300 entries per sync)."""
    valid = [e for e in entries if e.get("cveID")]
    if not valid:
        return 0
    sql = _UPSERT_KEV_PG if _is_postgres_connection(db) else _UPSERT_KEV_SQLITE
    params_batch = [_kev_upsert_params(e) for e in valid]
    chunk_size = 500
    for i in range(0, len(params_batch), chunk_size):
        await db.executemany(sql, params_batch[i : i + chunk_size])
    return len(valid)


async def filter_cves_matching_assets(
    db: DbConnection,
    cve_ids: list[str],
    assets: list[dict[str, str]],
) -> list[dict]:
    """Return CVE rows that match stack assets via CPE / affected_products (not description)."""
    from matching.stack_assets import cve_matches_assets

    normalized = [c.upper() for c in cve_ids if c]
    if not normalized or not assets:
        return []
    pg = _is_postgres_connection(db)
    in_placeholders = _in_placeholders(len(normalized), pg=pg, start=1)
    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.severity, c.summary,
               c.cpe_matches, c.affected_products,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = c.cve_id) AS kev_due_date
        FROM cves c
        WHERE c.cve_id IN ({in_placeholders})
        """,
        tuple(normalized),
    )
    matched: list[dict] = []
    for row in rows:
        data = dict(row)
        if cve_matches_assets(
            data.get("cpe_matches"),
            data.get("affected_products"),
            assets,
        ):
            matched.append(data)
    return matched


async def filter_cves_matching_stack(
    db: DbConnection, cve_ids: list[str], stack: str
) -> list[dict]:
    """Return CVE rows from cve_ids that match the comma-separated stack terms."""
    from routers.cves import _stack_match_clause

    normalized = [c.upper() for c in cve_ids if c]
    if not normalized or not stack.strip():
        return []
    clause, stack_params, _terms = _stack_match_clause(stack)
    if not clause:
        return []
    pg = _is_postgres_connection(db)
    in_placeholders = _in_placeholders(len(normalized), pg=pg, start=1)
    stack_start = len(normalized) + 1
    stack_clause = _renumber_qmark_placeholders(clause, stack_start) if pg else clause
    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.severity, c.summary,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = c.cve_id) AS kev_due_date
        FROM cves c
        WHERE c.cve_id IN ({in_placeholders}) AND {stack_clause}
        """,
        tuple(normalized) + tuple(stack_params),
    )
    return [dict(row) for row in rows]


async def insert_epss_history_rows(db: DbConnection, rows: list[dict]) -> int:
    """Bulk-insert EPSS history rows, skipping already-present (cve_id, date) pairs.

    Each dict must have keys ``cve_id`` (str), ``score`` (float), ``date`` (str).
    Returns the number of rows actually written.
    """
    if not rows:
        return 0
    tuples = [
        (r["cve_id"].upper(), r["score"], r["date"])
        for r in rows
        if r.get("cve_id") and r.get("date") and r.get("score") is not None
    ]
    if not tuples:
        return 0
    sql = _INSERT_EPSS_HISTORY_PG if _is_postgres_connection(db) else _INSERT_EPSS_HISTORY_SQLITE
    inserted = 0
    for tup in tuples:
        cursor = await db.execute(sql, tup)
        inserted += cursor.rowcount or 0
    return inserted


async def sync_vulncheck_exploited_flags(
    db: DbConnection,
    cve_ids: list[str],
    *,
    commit_every: int | None = None,
) -> int:
    """Mark CVEs present in VulnCheck KEV catalog (clears stale flags via indexed lookup).

    When *commit_every* is set (scheduler), commit after that many UPDATE chunks so
    large catalogs do not trip Postgres ``command_timeout`` on one long transaction.
    """
    catalog = sorted({(c or "").strip().upper() for c in cve_ids if c})
    pg = _is_postgres_connection(db)

    flagged_rows = await db.execute_fetchall(
        "SELECT cve_id FROM cves WHERE is_vulncheck_exploited = 1"
    )
    currently_flagged = {row["cve_id"] for row in flagged_rows}
    catalog_set = set(catalog)
    to_clear = sorted(currently_flagged - catalog_set)

    ops = 0
    for i in range(0, len(to_clear), _SQLITE_IN_CHUNK):
        chunk = to_clear[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        await db.execute(
            f"UPDATE cves SET is_vulncheck_exploited = 0 WHERE cve_id IN ({placeholders})",
            tuple(chunk),
        )
        ops += 1
        await _maybe_bulk_commit(db, ops, commit_every)

    updated = 0
    for i in range(0, len(catalog), _SQLITE_IN_CHUNK):
        chunk = catalog[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        cursor = await db.execute(
            f"UPDATE cves SET is_vulncheck_exploited = 1 WHERE cve_id IN ({placeholders})",
            tuple(chunk),
        )
        updated += cursor.rowcount or 0
        ops += 1
        await _maybe_bulk_commit(db, ops, commit_every)
    return updated
