"""IOC cache, feed cache, exploit storage. Split from database.py (Phase 3)."""

import json
import aiosqlite
from db.dialect import utcnow_str

from db.cve import _SQLITE_IN_CHUNK
from db.enrichment import _insert_cve_changes_batch


async def get_ioc_cache(db: aiosqlite.Connection, value: str) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM ioc_cache
        WHERE value = ? AND cached_at > datetime('now', '-6 hours')
        """,
        (value,),
    )
    if row:
        return json.loads(row[0]["result"])
    return None

async def get_ioc_cache_batch(
    db: aiosqlite.Connection, values: list[str]
) -> dict[str, dict]:
    """Batch lookup of cached IOC enrichment results, keyed by value."""
    if not values:
        return {}
    distinct = sorted(set(values))
    placeholders = ",".join("?" * len(distinct))
    rows = await db.execute_fetchall(
        f"""
        SELECT value, result FROM ioc_cache
        WHERE value IN ({placeholders}) AND cached_at > datetime('now', '-6 hours')
        """,
        tuple(distinct),
    )
    return {row["value"]: json.loads(row["result"]) for row in rows}

async def set_ioc_cache(db: aiosqlite.Connection, value: str, ioc_type: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(value) DO UPDATE SET
            result = excluded.result,
            cached_at = excluded.cached_at
        """,
        (value, ioc_type, json.dumps(result), utcnow_str()),
    )

async def delete_feed_cache_prefix(db: aiosqlite.Connection, prefix: str) -> int:
    """Delete feed_cache rows whose key starts with prefix."""
    cursor = await db.execute(
        "DELETE FROM feed_cache WHERE cache_key LIKE ?",
        (f"{prefix}%",),
    )
    return cursor.rowcount or 0

async def get_feed_cache(
    db: aiosqlite.Connection, cache_key: str, max_age_hours: float
) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM feed_cache
        WHERE cache_key = ?
          AND cached_at > datetime('now', ?)
        """,
        (cache_key, f"-{max_age_hours} hours"),
    )
    if row:
        return json.loads(row[0]["result"])
    return None

async def set_feed_cache(db: aiosqlite.Connection, cache_key: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO feed_cache (cache_key, result, cached_at)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            result = excluded.result,
            cached_at = excluded.cached_at
        """,
        (cache_key, json.dumps(result), utcnow_str()),
    )

async def get_cached_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cached = await get_feed_cache(db, f"sploitus:{cve_id.upper()}", max_age_hours)
    if cached is None:
        return None
    return cached.get("exploits", [])

async def store_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    await merge_cve_exploits(db, cve_id, exploits)
    merged = await read_cve_exploits_from_db(db, cve_id, max_age_hours=24 * 365)
    await set_feed_cache(
        db,
        f"sploitus:{cve_id.upper()}",
        {"exploits": merged or exploits},
    )

async def read_cve_exploits_from_db(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT title, type, source, url, published_date
        FROM cve_exploits
        WHERE cve_id = ?
          AND fetched_at > datetime('now', ?)
        ORDER BY published_date DESC
        """,
        (cve_id.upper(), f"-{max_age_hours} hours"),
    )
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
    db: aiosqlite.Connection, cve_id: str, source_urls: list[str]
) -> None:
    await db.execute(
        """
        UPDATE cves
        SET source_urls = ?, updated_at = ?
        WHERE cve_id = ?
        """,
        (json.dumps(source_urls), utcnow_str(), cve_id.upper()),
    )

async def get_cve_ids_missing_circl_capec(
    db: aiosqlite.Connection, limit: int = 100
) -> list[str]:
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        LEFT JOIN feed_cache fc
          ON fc.cache_key = 'circl:' || c.cve_id
         AND fc.cached_at > datetime('now', '-168 hours')
        WHERE fc.cache_key IS NULL
        ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [row["cve_id"] for row in rows]

async def replace_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    key = cve_id.upper()
    await db.execute("DELETE FROM cve_exploits WHERE cve_id = ?", (key,))
    if exploits:
        await db.executemany(
            """
            INSERT INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
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

async def _sqlite_changes(db: aiosqlite.Connection) -> int:
    """Rows changed by the last statement — reliable when rowcount is -1/0."""
    row = await db.execute_fetchall("SELECT changes() AS n")
    return int(row[0]["n"] or 0)

async def merge_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> int:
    """Insert exploit rows for a CVE; skip duplicates by (cve_id, url)."""
    key = cve_id.upper()
    inserted = 0
    for exp in exploits:
        url = (exp.get("url") or "").strip()
        if not url:
            continue
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
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
            inserted += await _sqlite_changes(db)
        elif rc > 0:
            inserted += rc
    return inserted

async def replace_cve_exploits_by_source(
    db: aiosqlite.Connection, source: str, cve_exploits: dict[str, list[dict]]
) -> tuple[int, int]:
    """Replace all rows for a feed source; returns (rows_inserted, cves_touched)."""
    await db.execute("DELETE FROM cve_exploits WHERE source = ?", (source,))
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
        await db.executemany(
            """
            INSERT OR IGNORE INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows), len(cve_exploits)

async def mark_has_poc_additive(
    db: aiosqlite.Connection, cve_ids: list[str] | set[str]
) -> int:
    """Set has_poc=1 for the given CVE IDs; never downgrade from 1."""
    ids = sorted({str(c).upper() for c in cve_ids if c})
    if not ids:
        return 0
    rows: list = []
    for offset in range(0, len(ids), _SQLITE_IN_CHUNK):
        chunk = ids[offset : offset + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        chunk_rows = await db.execute_fetchall(
            f"""
            SELECT cve_id FROM cves
            WHERE cve_id IN ({placeholders}) AND COALESCE(has_poc, 0) = 0
            """,
            chunk,
        )
        rows.extend(chunk_rows)
    if not rows:
        return 0
    history = [(row["cve_id"], "has_poc", "0", "1") for row in rows]
    await _insert_cve_changes_batch(db, history)
    updated = 0
    for row in rows:
        cve_key = row["cve_id"]
        cursor = await db.execute(
            """
            UPDATE cves SET has_poc = 1
            WHERE cve_id = ? AND COALESCE(has_poc, 0) = 0
            """,
            (cve_key,),
        )
        rc = cursor.rowcount
        if rc is None or rc < 0:
            updated += await _sqlite_changes(db)
        elif rc > 0:
            updated += rc
    return updated
