"""OTX pulses/IOCs, correlation suppressions, prioritization, asset matching. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from db.cache import set_feed_cache
from db.cve import _SQLITE_IN_CHUNK
from db.timeutil import utcnow_str
from db.metadata import _parse_json_list
from db.types import DbConnection

_UPSERT_OTX_PULSES_SQLITE = """
INSERT INTO otx_pulses (
    pulse_id, pulse_name, author, created_date, adversary,
    malware_families, tags, targeted_countries, ioc_count, fetched_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(pulse_id) DO UPDATE SET
    pulse_name = excluded.pulse_name,
    author = excluded.author,
    created_date = excluded.created_date,
    adversary = excluded.adversary,
    malware_families = excluded.malware_families,
    tags = excluded.tags,
    targeted_countries = excluded.targeted_countries,
    ioc_count = excluded.ioc_count,
    fetched_at = excluded.fetched_at
"""

_UPSERT_OTX_PULSES_PG = """
INSERT INTO otx_pulses (
    pulse_id, pulse_name, author, created_date, adversary,
    malware_families, tags, targeted_countries, ioc_count, fetched_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT(pulse_id) DO UPDATE SET
    pulse_name = excluded.pulse_name,
    author = excluded.author,
    created_date = excluded.created_date,
    adversary = excluded.adversary,
    malware_families = excluded.malware_families,
    tags = excluded.tags,
    targeted_countries = excluded.targeted_countries,
    ioc_count = excluded.ioc_count,
    fetched_at = excluded.fetched_at
"""

_DELETE_OTX_CVE_PULSES_SQLITE = "DELETE FROM otx_cve_pulses WHERE cve_id = ?"
_DELETE_OTX_CVE_PULSES_PG = "DELETE FROM otx_cve_pulses WHERE cve_id = $1"

_INSERT_OTX_CVE_PULSES_SQLITE = """
INSERT INTO otx_cve_pulses (
    cve_id, pulse_id, pulse_name, author, created_date,
    adversary, malware_families, ioc_count, tags, targeted_countries,
    fetched_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_OTX_CVE_PULSES_PG = """
INSERT INTO otx_cve_pulses (
    cve_id, pulse_id, pulse_name, author, created_date,
    adversary, malware_families, ioc_count, tags, targeted_countries,
    fetched_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

_READ_OTX_CVE_PULSES_SQLITE = """
SELECT pulse_id, pulse_name, author, created_date, adversary,
       malware_families, ioc_count, tags, targeted_countries
FROM otx_cve_pulses
WHERE cve_id = ?
  AND fetched_at > ?
ORDER BY created_date DESC
"""

_READ_OTX_CVE_PULSES_PG = """
SELECT pulse_id, pulse_name, author, created_date, adversary,
       malware_families, ioc_count, tags, targeted_countries
FROM otx_cve_pulses
WHERE cve_id = $1
  AND fetched_at > $2
ORDER BY created_date DESC
"""

_DELETE_OTX_PULSE_IOCS_SQLITE = "DELETE FROM otx_pulse_iocs WHERE pulse_id = ?"
_DELETE_OTX_PULSE_IOCS_PG = "DELETE FROM otx_pulse_iocs WHERE pulse_id = $1"

_UPSERT_OTX_PULSE_IOCS_SQLITE = """
INSERT INTO otx_pulse_iocs (
    pulse_id, ioc_type, ioc_value, description, fetched_at, observed_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(pulse_id, ioc_type, ioc_value) DO UPDATE SET
    description = excluded.description,
    fetched_at = excluded.fetched_at,
    observed_at = excluded.observed_at
"""

_UPSERT_OTX_PULSE_IOCS_PG = """
INSERT INTO otx_pulse_iocs (
    pulse_id, ioc_type, ioc_value, description, fetched_at, observed_at
) VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT(pulse_id, ioc_type, ioc_value) DO UPDATE SET
    description = excluded.description,
    fetched_at = excluded.fetched_at,
    observed_at = excluded.observed_at
"""

_SELECT_OTX_PULSE_IOCS_SQLITE = """
SELECT ioc_type, ioc_value
FROM otx_pulse_iocs
WHERE pulse_id = ?
"""

_SELECT_OTX_PULSE_IOCS_PG = """
SELECT ioc_type, ioc_value
FROM otx_pulse_iocs
WHERE pulse_id = $1
"""

_DELETE_STALE_OTX_PULSE_IOC_SQLITE = """
DELETE FROM otx_pulse_iocs
WHERE pulse_id = ? AND ioc_type = ? AND ioc_value = ?
"""

_DELETE_STALE_OTX_PULSE_IOC_PG = """
DELETE FROM otx_pulse_iocs
WHERE pulse_id = $1 AND ioc_type = $2 AND ioc_value = $3
"""

_READ_OTX_PULSE_IOCS_FRESH_SQLITE = """
SELECT ioc_type, ioc_value, description, observed_at
FROM otx_pulse_iocs
WHERE pulse_id = ?
  AND fetched_at > ?
"""

_READ_OTX_PULSE_IOCS_FRESH_PG = """
SELECT ioc_type, ioc_value, description, observed_at
FROM otx_pulse_iocs
WHERE pulse_id = $1
  AND fetched_at > $2
"""

_LIST_CORRELATION_SUPPRESSIONS_SQLITE = """
SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
FROM correlation_suppressions
WHERE cve_id = ?
ORDER BY created_at DESC
"""

_LIST_CORRELATION_SUPPRESSIONS_PG = """
SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
FROM correlation_suppressions
WHERE cve_id = $1
ORDER BY created_at DESC
"""

_UPSERT_CORRELATION_SUPPRESSION_SQLITE = """
INSERT INTO correlation_suppressions (cve_id, scope, scope_key, reason, dismissed_by, created_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(cve_id, scope, scope_key) DO UPDATE SET
    reason = excluded.reason,
    dismissed_by = excluded.dismissed_by,
    created_at = excluded.created_at
"""

_UPSERT_CORRELATION_SUPPRESSION_PG = """
INSERT INTO correlation_suppressions (cve_id, scope, scope_key, reason, dismissed_by, created_at)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT(cve_id, scope, scope_key) DO UPDATE SET
    reason = excluded.reason,
    dismissed_by = excluded.dismissed_by,
    created_at = excluded.created_at
"""

_SELECT_CORRELATION_SUPPRESSION_SQLITE = """
SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
FROM correlation_suppressions
WHERE cve_id = ? AND scope = ? AND scope_key = ?
"""

_SELECT_CORRELATION_SUPPRESSION_PG = """
SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
FROM correlation_suppressions
WHERE cve_id = $1 AND scope = $2 AND scope_key = $3
"""

_DELETE_CORRELATION_SUPPRESSION_SQLITE = """
DELETE FROM correlation_suppressions
WHERE cve_id = ? AND scope = ? AND scope_key = ?
"""

_DELETE_CORRELATION_SUPPRESSION_PG = """
DELETE FROM correlation_suppressions
WHERE cve_id = $1 AND scope = $2 AND scope_key = $3
"""

_GET_RECENT_CVE_IDS_OTX_SQLITE = """
SELECT cve_id FROM cves
WHERE published IS NOT NULL
  AND published != ''
  AND published >= ?
ORDER BY published DESC
"""

_GET_RECENT_CVE_IDS_OTX_PG = """
SELECT cve_id FROM cves
WHERE published IS NOT NULL
  AND published != ''
  AND published >= $1
ORDER BY published DESC
"""

_OTX_EMBEDDING_ANCHORS_SQL = """
SELECT c.cve_id
FROM cves c
LEFT JOIN watchlist w ON w.cve_id = c.cve_id AND w.state = 'pin'
WHERE COALESCE(c.is_kev, 0) = 1 OR w.cve_id IS NOT NULL
ORDER BY COALESCE(c.epss_score, 0) DESC
LIMIT 15
"""

_PRIO_P0_SQL = """
SELECT c.cve_id
FROM cves c
LEFT JOIN watchlist w ON w.cve_id = c.cve_id AND w.state = 'pin'
WHERE COALESCE(c.is_kev, 0) = 1 OR w.cve_id IS NOT NULL
ORDER BY c.published DESC
"""

_PRIO_P1_SQLITE = """
SELECT c.cve_id
FROM cves c
WHERE (
    COALESCE(c.epss_score, 0) >= 0.5
    OR COALESCE(c.has_poc, 0) = 1
    OR c.modified >= ?
)
ORDER BY COALESCE(c.epss_score, 0) DESC, c.published DESC
LIMIT 500
"""

_PRIO_P1_PG = """
SELECT c.cve_id
FROM cves c
WHERE (
    COALESCE(c.epss_score, 0) >= 0.5
    OR COALESCE(c.has_poc, 0) = 1
    OR c.modified >= $1
)
ORDER BY COALESCE(c.epss_score, 0) DESC, c.published DESC
LIMIT 500
"""

_PRIO_P2_SQLITE = """
SELECT cve_id FROM cves
WHERE published >= ?
ORDER BY published DESC
"""

_PRIO_P2_PG = """
SELECT cve_id FROM cves
WHERE published >= $1
ORDER BY published DESC
"""

_PRIO_P3_SQLITE = """
SELECT cve_id FROM cves
ORDER BY published DESC
LIMIT ?
"""

_PRIO_P3_PG = """
SELECT cve_id FROM cves
ORDER BY published DESC
LIMIT $1
"""

_MATCH_CVES_SQL = "SELECT cve_id, cpe_matches, affected_products FROM cves"

_NUM_IOC_LOCKS = 64

_pulse_ioc_locks = [asyncio.Lock() for _ in range(_NUM_IOC_LOCKS)]


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _in_placeholders(count: int, *, pg: bool, start: int = 1) -> str:
    if pg:
        return ", ".join(f"${i}" for i in range(start, start + count))
    return ", ".join("?" for _ in range(count))


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def _cutoff_datetime_hours_ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%d %H:%M:%S")


def _pulse_ioc_lock(pulse_id: str) -> asyncio.Lock:
    """Fixed-size lock pool — avoids unbounded growth from per-pulse lock dicts."""
    return _pulse_ioc_locks[hash(pulse_id) % _NUM_IOC_LOCKS]


async def upsert_otx_pulses(db: DbConnection, pulses: list[dict]) -> None:
    """Upsert pulse dimension rows (caller commits)."""
    if not pulses:
        return
    sql = _UPSERT_OTX_PULSES_PG if _is_postgres_connection(db) else _UPSERT_OTX_PULSES_SQLITE
    await db.executemany(
        sql,
        [
            (
                p.get("pulse_id") or "",
                p.get("pulse_name") or "",
                p.get("author") or "",
                p.get("created_date") or "",
                p.get("adversary") or "",
                json.dumps(p.get("malware_families") or []),
                json.dumps(p.get("tags") or []),
                json.dumps(p.get("targeted_countries") or []),
                int(p.get("ioc_count") or 0),
                utcnow_str(),
            )
            for p in pulses
            if p.get("pulse_id")
        ],
    )


async def replace_otx_cve_pulses(
    db: DbConnection, cve_id: str, pulses: list[dict]
) -> None:
    pg = _is_postgres_connection(db)
    key = cve_id.upper()
    delete_sql = _DELETE_OTX_CVE_PULSES_PG if pg else _DELETE_OTX_CVE_PULSES_SQLITE
    insert_sql = _INSERT_OTX_CVE_PULSES_PG if pg else _INSERT_OTX_CVE_PULSES_SQLITE
    await db.execute(delete_sql, (key,))
    if pulses:
        await upsert_otx_pulses(db, pulses)
        await db.executemany(
            insert_sql,
            [
                (
                    key,
                    p.get("pulse_id") or "",
                    p.get("pulse_name") or "",
                    p.get("author") or "",
                    p.get("created_date") or "",
                    p.get("adversary") or "",
                    json.dumps(p.get("malware_families") or []),
                    int(p.get("ioc_count") or 0),
                    json.dumps(p.get("tags") or []),
                    json.dumps(p.get("targeted_countries") or []),
                    utcnow_str(),
                )
                for p in pulses
                if p.get("pulse_id")
            ],
        )


async def store_otx_cve_pulses(
    db: DbConnection, cve_id: str, pulses: list[dict]
) -> None:
    key = cve_id.upper()
    await replace_otx_cve_pulses(db, key, pulses)
    await set_feed_cache(db, f"otx:cve:{key}", {"pulses": pulses})


async def read_otx_cve_pulses(
    db: DbConnection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cutoff = _cutoff_datetime_hours_ago(max_age_hours)
    sql = _READ_OTX_CVE_PULSES_PG if _is_postgres_connection(db) else _READ_OTX_CVE_PULSES_SQLITE
    rows = await db.execute_fetchall(sql, (cve_id.upper(), cutoff))
    if not rows:
        return None
    return [
        {
            "pulse_id": row["pulse_id"],
            "pulse_name": row["pulse_name"],
            "author": row["author"],
            "created_date": row["created_date"],
            "adversary": row["adversary"],
            "malware_families": json.loads(row["malware_families"] or "[]"),
            "ioc_count": row["ioc_count"],
            "tags": json.loads(row["tags"] or "[]"),
            "targeted_countries": json.loads(row["targeted_countries"] or "[]"),
        }
        for row in rows
    ]


async def replace_otx_pulse_iocs(
    db: DbConnection, pulse_id: str, iocs: list[dict]
) -> None:
    from correlation.ioc_normalize import normalize_ioc_row

    pg = _is_postgres_connection(db)
    delete_sql = _DELETE_OTX_PULSE_IOCS_PG if pg else _DELETE_OTX_PULSE_IOCS_SQLITE
    upsert_sql = _UPSERT_OTX_PULSE_IOCS_PG if pg else _UPSERT_OTX_PULSE_IOCS_SQLITE
    select_sql = _SELECT_OTX_PULSE_IOCS_PG if pg else _SELECT_OTX_PULSE_IOCS_SQLITE
    stale_delete_sql = (
        _DELETE_STALE_OTX_PULSE_IOC_PG if pg else _DELETE_STALE_OTX_PULSE_IOC_SQLITE
    )

    normalized_rows: list[tuple] = []
    for row in iocs:
        norm = normalize_ioc_row(row)
        if norm is None:
            continue
        normalized_rows.append(
            (
                pulse_id,
                norm.get("ioc_type") or "",
                norm.get("ioc_value") or "",
                norm.get("description") or "",
                utcnow_str(),
                str(norm.get("observed_at") or "").strip() or None,
            )
        )
    if not normalized_rows:
        await db.execute(delete_sql, (pulse_id,))
        return
    new_keys = {(row[1], row[2]) for row in normalized_rows}
    await db.executemany(upsert_sql, normalized_rows)
    existing = await db.execute_fetchall(select_sql, (pulse_id,))
    stale = [
        (pulse_id, row["ioc_type"], row["ioc_value"])
        for row in existing
        if (row["ioc_type"], row["ioc_value"]) not in new_keys
    ]
    if stale:
        await db.executemany(stale_delete_sql, stale)


async def store_otx_pulse_iocs(
    db: DbConnection, pulse_id: str, iocs: list[dict]
) -> None:
    async with _pulse_ioc_lock(pulse_id):
        await replace_otx_pulse_iocs(db, pulse_id, iocs)
        await set_feed_cache(db, f"otx:pulse:{pulse_id}", {"iocs": iocs})


async def read_otx_pulse_iocs(
    db: DbConnection, pulse_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cutoff = _cutoff_datetime_hours_ago(max_age_hours)
    sql = (
        _READ_OTX_PULSE_IOCS_FRESH_PG
        if _is_postgres_connection(db)
        else _READ_OTX_PULSE_IOCS_FRESH_SQLITE
    )
    rows = await db.execute_fetchall(sql, (pulse_id, cutoff))
    if not rows:
        return None
    return [
        {
            "ioc_type": row["ioc_type"],
            "ioc_value": row["ioc_value"],
            "description": row["description"],
            "observed_at": row["observed_at"],
        }
        for row in rows
    ]


async def list_correlation_suppressions(db: DbConnection, cve_id: str) -> list[dict]:
    sql = (
        _LIST_CORRELATION_SUPPRESSIONS_PG
        if _is_postgres_connection(db)
        else _LIST_CORRELATION_SUPPRESSIONS_SQLITE
    )
    rows = await db.execute_fetchall(sql, (cve_id.upper(),))
    return [dict(row) for row in rows]


async def insert_correlation_suppression(
    db: DbConnection,
    cve_id: str,
    scope: str,
    scope_key: str,
    reason: str = "",
    dismissed_by: str = "",
) -> dict:
    pg = _is_postgres_connection(db)
    upsert_sql = (
        _UPSERT_CORRELATION_SUPPRESSION_PG if pg else _UPSERT_CORRELATION_SUPPRESSION_SQLITE
    )
    select_sql = (
        _SELECT_CORRELATION_SUPPRESSION_PG if pg else _SELECT_CORRELATION_SUPPRESSION_SQLITE
    )
    key = cve_id.upper()
    await db.execute(
        upsert_sql,
        (key, scope, scope_key, reason, dismissed_by, utcnow_str()),
    )
    rows = await db.execute_fetchall(select_sql, (key, scope, scope_key))
    return dict(rows[0]) if rows else {
        "cve_id": key,
        "scope": scope,
        "scope_key": scope_key,
        "reason": reason,
        "dismissed_by": dismissed_by,
    }


async def delete_correlation_suppression(
    db: DbConnection, cve_id: str, scope: str, scope_key: str
) -> bool:
    sql = (
        _DELETE_CORRELATION_SUPPRESSION_PG
        if _is_postgres_connection(db)
        else _DELETE_CORRELATION_SUPPRESSION_SQLITE
    )
    cursor = await db.execute(sql, (cve_id.upper(), scope, scope_key))
    return (cursor.rowcount or 0) > 0


async def get_recent_cve_ids_for_otx(db: DbConnection, days: int = 7) -> list[str]:
    cutoff = _cutoff_date_days_ago(days)
    sql = _GET_RECENT_CVE_IDS_OTX_PG if _is_postgres_connection(db) else _GET_RECENT_CVE_IDS_OTX_SQLITE
    rows = await db.execute_fetchall(sql, (cutoff,))
    return [row["cve_id"] for row in rows]


async def get_cves_missing_otx_pulses(db: DbConnection, limit: int = 200) -> list[str]:
    """CVEs with no OTX pulse rows yet, tier-prioritized for continuous sync."""
    prioritized = await get_prioritized_cve_ids_for_otx(db, backlog_cap=limit * 2)
    if not prioritized:
        return []

    pg = _is_postgres_connection(db)
    missing: list[str] = []
    for i in range(0, len(prioritized), _SQLITE_IN_CHUNK):
        batch = prioritized[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(batch), pg=pg, start=1)
        rows = await db.execute_fetchall(
            f"""
            SELECT c.cve_id
            FROM cves c
            WHERE c.cve_id IN ({placeholders})
              AND NOT EXISTS (
                SELECT 1 FROM otx_cve_pulses o WHERE o.cve_id = c.cve_id
              )
            """,
            tuple(batch),
        )
        have = {row["cve_id"] for row in rows}
        for cid in batch:
            if cid in have:
                missing.append(cid)
            if len(missing) >= limit:
                return missing
    return missing


async def get_embedding_boosted_cve_ids_for_otx(
    db: DbConnection, limit: int = 150
) -> list[dict]:
    """
    CVEs semantically similar to KEV/watchlist anchors that lack OTX pulses.
    Used as P1b tier when EMBEDDINGS_ENABLED=1.
    """
    from ml.embeddings import embeddings_enabled, find_similar_cves

    if not embeddings_enabled() or limit <= 0:
        return []

    anchors = await db.execute_fetchall(_OTX_EMBEDDING_ANCHORS_SQL)
    if not anchors:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    for row in anchors:
        anchor_id = row["cve_id"]
        similar = await find_similar_cves(db, anchor_id, limit=20)
        if not similar:
            continue
        for item in similar:
            cid = item.get("cve_id")
            if cid and cid not in seen:
                seen.add(cid)
                candidates.append(cid)

    if not candidates:
        return []

    pg = _is_postgres_connection(db)
    missing_set: set[str] = set()
    for i in range(0, len(candidates), _SQLITE_IN_CHUNK):
        chunk = candidates[i : i + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        rows = await db.execute_fetchall(
            f"""
            SELECT c.cve_id
            FROM cves c
            WHERE c.cve_id IN ({placeholders})
              AND NOT EXISTS (
                SELECT 1 FROM otx_cve_pulses o WHERE o.cve_id = c.cve_id
              )
            """,
            tuple(chunk),
        )
        missing_set.update(row["cve_id"] for row in rows)

    ordered = [cid for cid in candidates if cid in missing_set]
    return [{"cve_id": c} for c in ordered[:limit]]


async def get_prioritized_cve_ids_for_otx(
    db: DbConnection,
    days: int | None = None,
    backlog_cap: int = 200,
) -> list[str]:
    """
    Tiered CVE set for OTX pulse refresh (P0 → P3).
    P0: KEV or watchlisted. P1: high EPSS, PoC, or changed in 7d.
    P2: published within sync window. P3: backlog cap by recency.
    """
    from correlation.config import get_otx_cve_sync_days

    pg = _is_postgres_connection(db)
    window_days = days if days is not None else get_otx_cve_sync_days()
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(rows: list) -> None:
        for row in rows:
            cid = row["cve_id"]
            if cid not in seen:
                seen.add(cid)
                ordered.append(cid)

    p0 = await db.execute_fetchall(_PRIO_P0_SQL)
    _add(p0)

    modified_cutoff = _cutoff_datetime_hours_ago(7 * 24)
    p1_sql = _PRIO_P1_PG if pg else _PRIO_P1_SQLITE
    p1 = await db.execute_fetchall(p1_sql, (modified_cutoff,))
    _add(p1)

    try:
        from ml.embeddings import embeddings_enabled

        if embeddings_enabled():
            p1b = await get_embedding_boosted_cve_ids_for_otx(db, limit=150)
            _add(p1b)
    except Exception:
        pass

    published_cutoff = _cutoff_date_days_ago(window_days)
    p2_sql = _PRIO_P2_PG if pg else _PRIO_P2_SQLITE
    p2 = await db.execute_fetchall(p2_sql, (published_cutoff,))
    _add(p2)

    if len(ordered) < backlog_cap:
        p3_sql = _PRIO_P3_PG if pg else _PRIO_P3_SQLITE
        p3 = await db.execute_fetchall(p3_sql, (backlog_cap,))
        _add(p3)

    return ordered[:backlog_cap] if backlog_cap > 0 else ordered


async def match_cves_for_assets(
    db: DbConnection, assets: list[dict]
) -> dict[str, int]:
    """Score every CVE in the database against analyst assets (in-memory request only)."""
    from matching.cpe import score_cve_for_assets

    rows = await db.execute_fetchall(_MATCH_CVES_SQL)
    scores: dict[str, int] = {}
    for row in rows:
        cpe_matches = _parse_json_list(row["cpe_matches"])
        if not cpe_matches:
            for entry in _parse_json_list(row["affected_products"]):
                if isinstance(entry, str) and ":" in entry:
                    vendor, product = entry.split(":", 1)
                    cpe_matches.append({"vendor": vendor, "product": product})

        score = score_cve_for_assets(cpe_matches, assets)
        if score > 0:
            scores[row["cve_id"]] = score
    return scores


_REBUILD_IOC_DEGREE_SQLITE = """
INSERT INTO ioc_degree (ioc_type, ioc_value, cve_count, pulse_count, computed_at)
SELECT oi.ioc_type,
       oi.ioc_value,
       COUNT(DISTINCT ocp.cve_id) AS cve_count,
       COUNT(DISTINCT oi.pulse_id) AS pulse_count,
       ?
FROM otx_pulse_iocs oi
JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id
GROUP BY oi.ioc_type, oi.ioc_value
"""

_REBUILD_IOC_DEGREE_PG = """
INSERT INTO ioc_degree (ioc_type, ioc_value, cve_count, pulse_count, computed_at)
SELECT oi.ioc_type,
       oi.ioc_value,
       COUNT(DISTINCT ocp.cve_id) AS cve_count,
       COUNT(DISTINCT oi.pulse_id) AS pulse_count,
       $1
FROM otx_pulse_iocs oi
JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id
GROUP BY oi.ioc_type, oi.ioc_value
"""


async def rebuild_ioc_degree(db: DbConnection) -> int:
    """Truncate-and-rebuild ioc_degree (CORR-PR-3 / spec §14): how many
    distinct CVEs and pulses reference each (ioc_type, ioc_value). Single
    INSERT...SELECT per the spec's idempotency invariant — a popular IOC
    (public resolver, CDN edge, common hash) gets a high cve_count, which
    confidence.py uses to penalize its edge confidence. Plain DELETE+INSERT,
    not a materialized view (spec §19 — SQLite-testable, refresh-lock-free).
    Returns the row count written."""
    await db.execute("DELETE FROM ioc_degree")
    computed_at = utcnow_str()
    sql = _REBUILD_IOC_DEGREE_PG if _is_postgres_connection(db) else _REBUILD_IOC_DEGREE_SQLITE
    await db.execute(sql, (computed_at,))
    await db.commit()
    rows = await db.execute_fetchall("SELECT COUNT(*) AS n FROM ioc_degree")
    return rows[0]["n"] if rows else 0
