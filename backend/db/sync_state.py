"""Generic sync-state key/value store plus NVD watermark helpers. Split from database.py (Phase 3)."""

import os

import aiosqlite
from db.dialect import utcnow_str

from db.metadata import get_cve_count


NVD_SYNC_WATERMARK_KEY = "nvd_last_mod_end"

EPSS_BACKFILL_DONE_KEY = "epss_backfill_done"

ATLAS_UPSTREAM_VERSION_KEY = "atlas_upstream_version"

async def get_sync_state_value(db: aiosqlite.Connection, key: str) -> str | None:
    """Read any sync_state key; returns None when absent."""
    rows = await db.execute_fetchall(
        "SELECT value FROM sync_state WHERE key = ?",
        (key,),
    )
    return rows[0]["value"] if rows else None

async def set_sync_state_value(db: aiosqlite.Connection, key: str, value: str) -> None:
    """Upsert any sync_state key (caller commits)."""
    await db.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, utcnow_str()),
    )

def get_stack_terms() -> str:
    """Operator stack profile for server-side matching (BRIEFR_STACK_TERMS)."""
    return os.environ.get("BRIEFR_STACK_TERMS", "").strip()

async def get_nvd_sync_watermark(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        "SELECT value FROM sync_state WHERE key = ?",
        (NVD_SYNC_WATERMARK_KEY,),
    )
    return rows[0]["value"] if rows else None

async def set_nvd_sync_watermark(db: aiosqlite.Connection, value: str) -> None:
    await db.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (NVD_SYNC_WATERMARK_KEY, value, utcnow_str()),
    )

async def seed_nvd_watermark_from_cves(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        """
        SELECT MAX(modified) AS latest
        FROM cves
        WHERE modified IS NOT NULL AND modified != ''
        """
    )
    latest = rows[0]["latest"] if rows else None
    if not latest:
        return None
    await set_nvd_sync_watermark(db, latest)
    return latest

async def resolve_nvd_watermark(db: aiosqlite.Connection, *, min_cves: int = 10) -> str | None:
    watermark = await get_nvd_sync_watermark(db)
    if watermark:
        return watermark
    count = await get_cve_count(db)
    if count < min_cves:
        return None
    return await seed_nvd_watermark_from_cves(db)
