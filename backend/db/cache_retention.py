"""Physical retention sweeps for cache and overlay tables (Sprint C3).

Read paths enforce TTL via ``cached_at`` / ``fetched_at`` filters; this module
deletes rows that are past their physical retention window so tables do not
grow without bound.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite

# Physical retention >= read TTL for each key family (hours).
IOC_CACHE_RETENTION_HOURS = 24

FEED_CACHE_PREFIX_RETENTION: tuple[tuple[str, float], ...] = (
    ("ssvc:", 24 * 365),
    ("correlation:v2:", 7 * 24),
    ("correlation:v1:", 7 * 24),
    ("circl:", 168),
    ("circl_miss:", 48),
    ("sploitus:", 168),
    ("llm_products:", 168),
    ("otx:cve:", 48),
    ("otx:pulse:", 48),
    ("otx:ioc:", 48),
    ("malwarebazaar:", 48),
    ("urlhaus:", 48),
    ("greynoise:", 48),
    ("sigma:", 48),
    ("detection_ctx:", 168),
    ("detection_ctx_llm:", 168),
    ("elastic:", 48),
    ("incident_rss:", 48),
    ("incident_feed:snapshot", 7 * 24),
    ("wallboard:snapshot", 24),
    ("admin_db_integrity", 24),
)
DEFAULT_FEED_CACHE_RETENTION_HOURS = 168

OTX_TABLE_RETENTION_HOURS = 7 * 24
EPSS_HISTORY_RETENTION_DAYS = 90
CVE_CHANGE_HISTORY_RETENTION_DAYS = 90


def _cutoff_datetime_hours_ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%d %H:%M:%S")


def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


async def _rows_deleted(db: aiosqlite.Connection, cursor) -> int:
    rc = cursor.rowcount
    if rc is not None and rc >= 0:
        return rc
    row = await db.execute_fetchall("SELECT changes() AS n")
    return int(row[0]["n"] or 0)


async def purge_stale_ioc_cache(
    db: aiosqlite.Connection,
    retention_hours: float = IOC_CACHE_RETENTION_HOURS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_hours)
    cursor = await db.execute(
        """
        DELETE FROM ioc_cache
        WHERE cached_at < ?
        """,
        (cutoff,),
    )
    return await _rows_deleted(db, cursor)


async def purge_stale_feed_cache(db: aiosqlite.Connection) -> int:
    deleted = 0
    now = datetime.now(timezone.utc)
    for prefix, hours in FEED_CACHE_PREFIX_RETENTION:
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            """
            DELETE FROM feed_cache
            WHERE cache_key LIKE ?
              AND cached_at < ?
            """,
            (f"{prefix}%", cutoff),
        )
        deleted += await _rows_deleted(db, cursor)

    long_prefixes = [
        prefix
        for prefix, hours in FEED_CACHE_PREFIX_RETENTION
        if hours > DEFAULT_FEED_CACHE_RETENTION_HOURS
    ]
    default_cutoff = (now - timedelta(hours=DEFAULT_FEED_CACHE_RETENTION_HOURS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    if long_prefixes:
        not_like = " AND ".join(
            f"cache_key NOT LIKE '{prefix}%'" for prefix in long_prefixes
        )
        cursor = await db.execute(
            f"""
            DELETE FROM feed_cache
            WHERE cached_at < ?
              AND {not_like}
            """,
            (default_cutoff,),
        )
    else:
        cursor = await db.execute(
            """
            DELETE FROM feed_cache
            WHERE cached_at < ?
            """,
            (default_cutoff,),
        )
    deleted += await _rows_deleted(db, cursor)
    return deleted


async def purge_old_epss_history(
    db: aiosqlite.Connection,
    retention_days: int = EPSS_HISTORY_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_date_days_ago(retention_days)
    cursor = await db.execute(
        """
        DELETE FROM epss_history
        WHERE recorded_date < ?
        """,
        (cutoff,),
    )
    return await _rows_deleted(db, cursor)


async def purge_old_cve_change_history(
    db: aiosqlite.Connection,
    retention_days: int = CVE_CHANGE_HISTORY_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_days * 24)
    cursor = await db.execute(
        """
        DELETE FROM cve_change_history
        WHERE detected_at < ?
        """,
        (cutoff,),
    )
    return await _rows_deleted(db, cursor)


async def purge_stale_otx_tables(
    db: aiosqlite.Connection,
    retention_hours: float = OTX_TABLE_RETENTION_HOURS,
) -> dict[str, int]:
    cutoff = _cutoff_datetime_hours_ago(retention_hours)
    cve_cursor = await db.execute(
        """
        DELETE FROM otx_cve_pulses
        WHERE fetched_at < ?
        """,
        (cutoff,),
    )
    pulse_cursor = await db.execute(
        """
        DELETE FROM otx_pulse_iocs
        WHERE fetched_at < ?
        """,
        (cutoff,),
    )
    return {
        "otx_cve_pulses": await _rows_deleted(db, cve_cursor),
        "otx_pulse_iocs": await _rows_deleted(db, pulse_cursor),
    }


async def run_retention_cleanup(db: aiosqlite.Connection) -> dict[str, int]:
    """Sweep stale cache/overlay rows. Caller commits."""
    otx = await purge_stale_otx_tables(db)
    return {
        "ioc_cache": await purge_stale_ioc_cache(db),
        "feed_cache": await purge_stale_feed_cache(db),
        "epss_history": await purge_old_epss_history(db),
        "cve_change_history": await purge_old_cve_change_history(db),
        **otx,
    }
