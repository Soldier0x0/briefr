"""IOC cache, feed cache, exploit storage. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from db.cve import _SQLITE_IN_CHUNK
from db.dialect import utcnow_str
from db.enrichment import _insert_cve_changes_batch
from db.types import DbConnection

_IOC_TTL_HOURS = 6
_CIRCL_CACHE_TTL_HOURS = 168

_GET_IOC_CACHE_SQLITE = """
SELECT result FROM ioc_cache
WHERE value = ? AND cached_at > ?
"""

_GET_IOC_CACHE_PG = """
SELECT result FROM ioc_cache
WHERE value = $1 AND cached_at > $2
"""

_UPSERT_IOC_CACHE_SQLITE = """
INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(value) DO UPDATE SET
    result = excluded.result,
    cached_at = excluded.cached_at
"""

_UPSERT_IOC_CACHE_PG = """
INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT(value) DO UPDATE SET
    result = excluded.result,
    cached_at = excluded.cached_at
"""

_DELETE_FEED_CACHE_PREFIX_SQLITE = "DELETE FROM feed_cache WHERE cache_key LIKE ?"
_DELETE_FEED_CACHE_PREFIX_PG = "DELETE FROM feed_cache WHERE cache_key LIKE $1"

_GET_FEED_CACHE_SQLITE = """
SELECT result FROM feed_cache
WHERE cache_key = ?
  AND cached_at > ?
"""

_GET_FEED_CACHE_PG = """
SELECT result FROM feed_cache
WHERE cache_key = $1
  AND cached_at > $2
"""

_UPSERT_FEED_CACHE_SQLITE = """
INSERT INTO feed_cache (cache_key, result, cached_at)
VALUES (?, ?, ?)
ON CONFLICT(cache_key) DO UPDATE SET
    result = excluded.result,
    cached_at = excluded.cached_at
"""

_UPSERT_FEED_CACHE_PG = """
INSERT INTO feed_cache (cache_key, result, cached_at)
VALUES ($1, $2, $3)
ON CONFLICT(cache_key) DO UPDATE SET
    result = excluded.result,
    cached_at = excluded.cached_at
"""

_READ_CVE_EXPLOITS_SQLITE = """
SELECT title, type, source, url, published_date
FROM cve_exploits
WHERE cve_id = ?
  AND fetched_at > ?
ORDER BY published_date DESC
"""

_READ_CVE_EXPLOITS_PG = """
SELECT title, type, source, url, published_date
FROM cve_exploits
WHERE cve_id = $1
  AND fetched_at > $2
ORDER BY published_date DESC
"""

_UPDATE_CVE_SOURCE_URLS_SQLITE = """
UPDATE cves
SET source_urls = ?, updated_at = ?
WHERE cve_id = ?
"""

_UPDATE_CVE_SOURCE_URLS_PG = """
UPDATE cves
SET source_urls = $1, updated_at = $2
WHERE cve_id = $3
"""

_GET_CVE_IDS_MISSING_CIRCL_SQLITE = """
SELECT c.cve_id
FROM cves c
LEFT JOIN feed_cache fc
  ON fc.cache_key = 'circl:' || c.cve_id
 AND fc.cached_at > ?
WHERE fc.cache_key IS NULL
ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
LIMIT ?
"""

_GET_CVE_IDS_MISSING_CIRCL_PG = """
SELECT c.cve_id
FROM cves c
LEFT JOIN feed_cache fc
  ON fc.cache_key = 'circl:' || c.cve_id
 AND fc.cached_at > $1
WHERE fc.cache_key IS NULL
ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
LIMIT $2
"""

_DELETE_CVE_EXPLOITS_SQLITE = "DELETE FROM cve_exploits WHERE cve_id = ?"
_DELETE_CVE_EXPLOITS_PG = "DELETE FROM cve_exploits WHERE cve_id = $1"

_DELETE_CVE_EXPLOITS_BY_SOURCE_SQLITE = "DELETE FROM cve_exploits WHERE source = ?"
_DELETE_CVE_EXPLOITS_BY_SOURCE_PG = "DELETE FROM cve_exploits WHERE source = $1"

_INSERT_EXPLOIT_SQLITE = """
INSERT OR IGNORE INTO cve_exploits (
    cve_id, title, type, source, url, published_date, fetched_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_EXPLOIT_PG = """
INSERT INTO cve_exploits (
    cve_id, title, type, source, url, published_date, fetched_at
) VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (cve_id, url) DO NOTHING
"""

_UPDATE_HAS_POC_SQLITE = """
UPDATE cves SET has_poc = 1
WHERE cve_id = ? AND COALESCE(has_poc, 0) = 0
"""

_UPDATE_HAS_POC_PG = """
UPDATE cves SET has_poc = 1
WHERE cve_id = $1 AND COALESCE(has_poc, 0) = 0
"""

_CHANGES_SQLITE = "SELECT changes() AS n"


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _in_placeholders(count: int, *, pg: bool, start: int = 1) -> str:
    if pg:
        return ", ".join(f"${i}" for i in range(start, start + count))
    return ", ".join("?" for _ in range(count))


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


def _cutoff_datetime_hours_ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%d %H:%M:%S")


async def _rows_changed(db: DbConnection) -> int:
    """Rows changed by the last statement — SQLite changes(); Postgres rowcount."""
    if _is_postgres_connection(db):
        return 0
    row = await db.execute_fetchall(_CHANGES_SQLITE)
    return int(row[0]["n"] or 0)


async def get_ioc_cache(db: DbConnection, value: str) -> dict | None:
    cutoff = _cutoff_datetime_hours_ago(_IOC_TTL_HOURS)
    sql = _GET_IOC_CACHE_PG if _is_postgres_connection(db) else _GET_IOC_CACHE_SQLITE
    row = await db.execute_fetchall(sql, (value, cutoff))
    if row:
        return json.loads(row[0]["result"])
    return None


async def get_ioc_cache_batch(db: DbConnection, values: list[str]) -> dict[str, dict]:
    """Batch lookup of cached IOC enrichment results, keyed by value."""
    if not values:
        return {}
    distinct = sorted(set(values))
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(distinct), pg=pg, start=1)
    cutoff_ph = _placeholder(pg, len(distinct) + 1)
    cutoff = _cutoff_datetime_hours_ago(_IOC_TTL_HOURS)
    rows = await db.execute_fetchall(
        f"""
        SELECT value, result FROM ioc_cache
        WHERE value IN ({placeholders}) AND cached_at > {cutoff_ph}
        """,
        tuple(distinct) + (cutoff,),
    )
    return {row["value"]: json.loads(row["result"]) for row in rows}


async def set_ioc_cache(
    db: DbConnection, value: str, ioc_type: str, result: dict
) -> None:
    sql = _UPSERT_IOC_CACHE_PG if _is_postgres_connection(db) else _UPSERT_IOC_CACHE_SQLITE
    await db.execute(sql, (value, ioc_type, json.dumps(result), utcnow_str()))


async def delete_feed_cache_prefix(db: DbConnection, prefix: str) -> int:
    """Delete feed_cache rows whose key starts with prefix."""
    sql = (
        _DELETE_FEED_CACHE_PREFIX_PG
        if _is_postgres_connection(db)
        else _DELETE_FEED_CACHE_PREFIX_SQLITE
    )
    cursor = await db.execute(sql, (f"{prefix}%",))
    return cursor.rowcount or 0


async def get_feed_cache(
    db: DbConnection, cache_key: str, max_age_hours: float
) -> dict | None:
    cutoff = _cutoff_datetime_hours_ago(max_age_hours)
    sql = _GET_FEED_CACHE_PG if _is_postgres_connection(db) else _GET_FEED_CACHE_SQLITE
    row = await db.execute_fetchall(sql, (cache_key, cutoff))
    if row:
        return json.loads(row[0]["result"])
    return None


async def set_feed_cache(db: DbConnection, cache_key: str, result: dict) -> None:
    sql = _UPSERT_FEED_CACHE_PG if _is_postgres_connection(db) else _UPSERT_FEED_CACHE_SQLITE
    await db.execute(sql, (cache_key, json.dumps(result), utcnow_str()))


async def get_cached_cve_exploits(
    db: DbConnection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cached = await get_feed_cache(db, f"sploitus:{cve_id.upper()}", max_age_hours)
    if cached is None:
        return None
    return cached.get("exploits", [])


async def store_cve_exploits(
    db: DbConnection, cve_id: str, exploits: list[dict]
) -> None:
    await merge_cve_exploits(db, cve_id, exploits)
    merged = await read_cve_exploits_from_db(db, cve_id, max_age_hours=24 * 365)
    await set_feed_cache(
        db,
        f"sploitus:{cve_id.upper()}",
        {"exploits": merged or exploits},
    )


async def read_cve_exploits_from_db(
    db: DbConnection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cutoff = _cutoff_datetime_hours_ago(max_age_hours)
    sql = _READ_CVE_EXPLOITS_PG if _is_postgres_connection(db) else _READ_CVE_EXPLOITS_SQLITE
    rows = await db.execute_fetchall(sql, (cve_id.upper(), cutoff))
    if not rows:
        return None
    return [
        {
            "title": row["title"],
            "type": row["type"],
            "source": row["source"],
            "url": row["url"],
            "published_date": row["published_date"],
        }
        for row in rows
    ]


async def update_cve_source_urls(
    db: DbConnection, cve_id: str, source_urls: list[str]
) -> None:
    sql = (
        _UPDATE_CVE_SOURCE_URLS_PG
        if _is_postgres_connection(db)
        else _UPDATE_CVE_SOURCE_URLS_SQLITE
    )
    await db.execute(sql, (json.dumps(source_urls), utcnow_str(), cve_id.upper()))


async def get_cve_ids_missing_circl_capec(db: DbConnection, limit: int = 100) -> list[str]:
    cutoff = _cutoff_datetime_hours_ago(_CIRCL_CACHE_TTL_HOURS)
    sql = (
        _GET_CVE_IDS_MISSING_CIRCL_PG
        if _is_postgres_connection(db)
        else _GET_CVE_IDS_MISSING_CIRCL_SQLITE
    )
    rows = await db.execute_fetchall(sql, (cutoff, limit))
    return [row["cve_id"] for row in rows]


async def replace_cve_exploits(
    db: DbConnection, cve_id: str, exploits: list[dict]
) -> None:
    key = cve_id.upper()
    delete_sql = _DELETE_CVE_EXPLOITS_PG if _is_postgres_connection(db) else _DELETE_CVE_EXPLOITS_SQLITE
    insert_sql = _INSERT_EXPLOIT_PG if _is_postgres_connection(db) else _INSERT_EXPLOIT_SQLITE
    await db.execute(delete_sql, (key,))
    if exploits:
        await db.executemany(
            insert_sql,
            [
                (
                    key,
                    exp.get("title") or "",
                    exp.get("type") or "poc",
                    exp.get("source") or "",
                    exp.get("url") or "",
                    exp.get("published_date") or "",
                    utcnow_str(),
                )
                for exp in exploits
            ],
        )


async def merge_cve_exploits(db: DbConnection, cve_id: str, exploits: list[dict]) -> int:
    """Insert exploit rows for a CVE; skip duplicates by (cve_id, url)."""
    key = cve_id.upper()
    insert_sql = _INSERT_EXPLOIT_PG if _is_postgres_connection(db) else _INSERT_EXPLOIT_SQLITE
    inserted = 0
    for exp in exploits:
        url = (exp.get("url") or "").strip()
        if not url:
            continue
        cursor = await db.execute(
            insert_sql,
            (
                key,
                exp.get("title") or "",
                exp.get("type") or "poc",
                exp.get("source") or "",
                url,
                exp.get("published_date") or "",
                utcnow_str(),
            ),
        )
        rc = cursor.rowcount
        if rc is None or rc < 0:
            inserted += await _rows_changed(db)
        elif rc > 0:
            inserted += rc
    return inserted


async def replace_cve_exploits_by_source(
    db: DbConnection, source: str, cve_exploits: dict[str, list[dict]]
) -> tuple[int, int]:
    """Replace all rows for a feed source; returns (rows_inserted, cves_touched)."""
    delete_sql = (
        _DELETE_CVE_EXPLOITS_BY_SOURCE_PG
        if _is_postgres_connection(db)
        else _DELETE_CVE_EXPLOITS_BY_SOURCE_SQLITE
    )
    insert_sql = _INSERT_EXPLOIT_PG if _is_postgres_connection(db) else _INSERT_EXPLOIT_SQLITE
    await db.execute(delete_sql, (source,))
    rows: list[tuple] = []
    seen: set[tuple[str, str]] = set()
    for cve_id, exploits in cve_exploits.items():
        key = cve_id.upper()
        for exp in exploits:
            url = (exp.get("url") or "").strip()
            if not url:
                continue
            dedupe_key = (key, url)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                (
                    key,
                    exp.get("title") or "",
                    exp.get("type") or "poc",
                    source,
                    url,
                    exp.get("published_date") or "",
                    utcnow_str(),
                )
            )
    if rows:
        await db.executemany(insert_sql, rows)
    return len(rows), len(cve_exploits)


async def mark_has_poc_additive(db: DbConnection, cve_ids: list[str] | set[str]) -> int:
    """Set has_poc=1 for the given CVE IDs; never downgrade from 1."""
    ids = sorted({str(c).upper() for c in cve_ids if c})
    if not ids:
        return 0
    pg = _is_postgres_connection(db)
    update_sql = _UPDATE_HAS_POC_PG if pg else _UPDATE_HAS_POC_SQLITE
    rows: list = []
    for offset in range(0, len(ids), _SQLITE_IN_CHUNK):
        chunk = ids[offset : offset + _SQLITE_IN_CHUNK]
        placeholders = _in_placeholders(len(chunk), pg=pg, start=1)
        chunk_rows = await db.execute_fetchall(
            f"""
            SELECT cve_id FROM cves
            WHERE cve_id IN ({placeholders}) AND COALESCE(has_poc, 0) = 0
            """,
            tuple(chunk),
        )
        rows.extend(chunk_rows)
    if not rows:
        return 0
    history = [(row["cve_id"], "has_poc", "0", "1") for row in rows]
    await _insert_cve_changes_batch(db, history)
    updated = 0
    for row in rows:
        cve_key = row["cve_id"]
        cursor = await db.execute(update_sql, (cve_key,))
        rc = cursor.rowcount
        if rc is None or rc < 0:
            updated += await _rows_changed(db)
        elif rc > 0:
            updated += rc
    return updated
