"""Enrichment: KEV/EPSS updates, change history, display-field backfills. Split from database.py (Phase 3)."""

import json
import re
import aiosqlite
from db.dialect import utcnow_str

from db.cve import _insert_cve_changes_batch, _change_value_str, _cve_id_filter_clause, _SQLITE_IN_CHUNK


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

def _clean_iso_date(value: str | None) -> str:
    """Keep only values that start with a YYYY-MM-DD date; drop garbage (e.g. stray header text)."""
    if isinstance(value, str) and _ISO_DATE_RE.match(value):
        return value
    return ""

async def write_audit_log(
    db: aiosqlite.Connection,
    actor: str | None,
    action: str,
    target: str = "",
) -> None:
    """Append one audit row (caller commits). Actor is '' when no identity."""
    await db.execute(
        "INSERT INTO audit_log (actor, action, target) VALUES (?, ?, ?)",
        ((actor or "").strip(), action, target or ""),
    )

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

async def mark_cves_as_kev(db: aiosqlite.Connection, cve_ids: list) -> list[str]:
    """Mark CVEs as KEV; return IDs that transitioned from is_kev=0 to 1."""
    if not cve_ids:
        return []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return []
    placeholders = ",".join("?" * len(normalized))
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, is_kev FROM cves
        WHERE cve_id IN ({placeholders}) AND is_kev = 0
        """,
        normalized,
    )
    newly_kev = [row["cve_id"] for row in rows]
    history = [(row["cve_id"], "is_kev", "0", "1") for row in rows]
    await _insert_cve_changes_batch(db, history)
    await db.execute(
        f"UPDATE cves SET is_kev = 1 WHERE cve_id IN ({placeholders})",
        normalized,
    )
    return newly_kev

async def snapshot_epss_scores(db: aiosqlite.Connection, recorded_date: str | None = None) -> int:
    """Persist current EPSS scores before a bulk update (one row per CVE per day)."""
    from datetime import date

    day = recorded_date or date.today().isoformat()
    cursor = await db.execute(
        """
        INSERT OR REPLACE INTO epss_history (cve_id, score, recorded_date)
        SELECT cve_id, epss_score, ?
        FROM cves
        WHERE epss_score IS NOT NULL
        """,
        (day,),
    )
    return cursor.rowcount

async def update_epss_scores(db: aiosqlite.Connection, scores: dict) -> None:
    """Apply EPSS score (and optional percentile) updates from the daily feed.

    Values may be bare floats (legacy) or ``{"score": float, "percentile": float|None}``.
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

    needed_list = list(normalized.keys())
    existing: dict[str, tuple[float | None, float | None]] = {}
    for i in range(0, len(needed_list), _SQLITE_IN_CHUNK):
        chunk = needed_list[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, epss_score, epss_percentile
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            chunk,
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
        await db.executemany(
            "UPDATE cves SET epss_score = ?, epss_percentile = ? WHERE cve_id = ?",
            updates,
        )


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

async def get_epss_history(
    db: aiosqlite.Connection, cve_id: str, days: int = 30
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT recorded_date AS date, score
        FROM epss_history
        WHERE cve_id = ?
          AND DATE(recorded_date) >= DATE('now', ?)
        ORDER BY recorded_date ASC
        """,
        (cve_id.upper(), f"-{days - 1} days"),
    )
    return [{"date": row["date"], "score": row["score"]} for row in rows]

async def backfill_display_fields(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Fill MITRE / PoC from stored NVD fields when missing (no auto plain-summary)."""
    from enrichment.cve import extract_mitre_from_urls, has_public_poc_from_urls

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, source_urls, mitre_technique, has_poc
        FROM cves
        WHERE (mitre_technique IS NULL OR has_poc = 0){id_clause}
        """,
        id_params,
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
        await db.execute(
            """
            UPDATE cves
            SET mitre_technique = COALESCE(?, mitre_technique),
                has_poc = CASE WHEN ? = 1 THEN 1 ELSE has_poc END
            WHERE cve_id = ?
            """,
            (mitre, poc_flag, row["cve_id"]),
        )
        updated += 1
    return updated

async def strip_auto_generated_summaries(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Remove NVD first-sentence summaries so Plain English filter is meaningful."""
    from enrichment.cve import is_auto_generated_summary

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, summary
        FROM cves
        WHERE summary IS NOT NULL AND TRIM(summary) != ''{id_clause}
        """,
        id_params,
    )
    cleared = 0
    for row in rows:
        if is_auto_generated_summary(row["summary"], row["description"]):
            await db.execute(
                "UPDATE cves SET summary = NULL WHERE cve_id = ?",
                (row["cve_id"],),
            )
            cleared += 1
    return cleared

async def backfill_has_poc(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Set has_poc from stored reference URLs (no NVD re-fetch)."""
    from enrichment.cve import has_public_poc_from_urls

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
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
        await db.executemany(
            "UPDATE cves SET has_poc = 1 WHERE cve_id = ?",
            updates,
        )
    return len(updates)

async def get_recent_cve_changes(
    db: aiosqlite.Connection,
    *,
    limit: int = 100,
    field_name: str | None = None,
    since_hours: int | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if field_name:
        clauses.append("field_name = ?")
        params.append(field_name)
    if since_hours is not None and since_hours > 0:
        clauses.append("detected_at >= datetime('now', ?)")
        params.append(f"-{since_hours} hours")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = await db.execute_fetchall(
        f"""
        SELECT id, cve_id, field_name, old_value, new_value, detected_at
        FROM cve_change_history
        {where}
        ORDER BY detected_at DESC, id DESC
        LIMIT ?
        """,
        params,
    )
    return [dict(r) for r in rows]

async def enrich_kev_summaries(db: aiosqlite.Connection) -> int:
    """Fill plain-English summary from CISA KEV short descriptions."""
    cursor = await db.execute(
        """
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
    )
    return cursor.rowcount

async def upsert_kev(db: aiosqlite.Connection, entry: dict) -> None:
    cwes = entry.get("cwes") or []
    if not isinstance(cwes, list):
        cwes = []
    await db.execute(
        """
        INSERT INTO kev_deadlines (
            cve_id, product, short_description, required_action, due_date,
            date_added, vendor_project, vulnerability_name, known_ransomware,
            cwes, updated_at
        )
        VALUES (
            :cve_id, :product, :short_description, :required_action, :due_date,
            :date_added, :vendor_project, :vulnerability_name, :known_ransomware,
            :cwes, :updated_at
        )
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
            updated_at = :updated_at
        """,
        {
            "cve_id": entry.get("cveID", ""),
            "product": entry.get("product", ""),
            "short_description": entry.get("shortDescription", ""),
            "required_action": entry.get("requiredAction", ""),
            "due_date": _clean_iso_date(entry.get("dueDate", "")),
            "date_added": _clean_iso_date(entry.get("dateAdded", "")),
            "vendor_project": entry.get("vendorProject", ""),
            "vulnerability_name": entry.get("vulnerabilityName", ""),
            "known_ransomware": entry.get("knownRansomwareCampaignUse", ""),
            "cwes": json.dumps(cwes),
            "updated_at": utcnow_str(),
        },
    )

async def filter_cves_matching_stack(
    db: aiosqlite.Connection, cve_ids: list[str], stack: str
) -> list[dict]:
    """Return CVE rows from cve_ids that match the comma-separated stack terms."""
    from routers.cves import _stack_match_clause

    normalized = [c.upper() for c in cve_ids if c]
    if not normalized or not stack.strip():
        return []
    clause, params, _terms = _stack_match_clause(stack)
    if not clause:
        return []
    placeholders = ",".join("?" * len(normalized))
    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.severity, c.summary,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = c.cve_id) AS kev_due_date
        FROM cves c
        WHERE c.cve_id IN ({placeholders}) AND {clause}
        """,
        normalized + params,
    )
    return [dict(row) for row in rows]

async def insert_epss_history_rows(
    db: aiosqlite.Connection,
    rows: list[dict],
) -> int:
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
    cursor = await db.executemany(
        "INSERT OR IGNORE INTO epss_history (cve_id, score, recorded_date) VALUES (?, ?, ?)",
        tuples,
    )
    return cursor.rowcount
