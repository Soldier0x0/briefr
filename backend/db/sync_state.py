"""Generic sync-state key/value store plus NVD watermark helpers. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import os

from db.config import is_postgres
from db.dialect import utcnow_str
from db.metadata import get_cve_count
from db.types import DbConnection

NVD_SYNC_WATERMARK_KEY = "nvd_last_mod_end"

EPSS_BACKFILL_DONE_KEY = "epss_backfill_done"

ATLAS_UPSTREAM_VERSION_KEY = "atlas_upstream_version"

_SELECT_VALUE_SQLITE = "SELECT value FROM sync_state WHERE key = ?"
_SELECT_VALUE_PG = "SELECT value FROM sync_state WHERE key = $1"

_UPSERT_SQLITE = """
INSERT INTO sync_state (key, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""

_UPSERT_PG = """
INSERT INTO sync_state (key, value, updated_at)
VALUES ($1, $2, $3)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""

_SELECT_MAX_MODIFIED_SQLITE = """
SELECT MAX(modified) AS latest
FROM cves
WHERE modified IS NOT NULL AND modified != ''
"""

_SELECT_MAX_MODIFIED_PG = """
SELECT MAX(modified) AS latest
FROM cves
WHERE modified IS NOT NULL AND modified != ''
"""


def _select_value_sql() -> str:
    return _SELECT_VALUE_PG if is_postgres() else _SELECT_VALUE_SQLITE


def _upsert_sql() -> str:
    return _UPSERT_PG if is_postgres() else _UPSERT_SQLITE


def _select_max_modified_sql() -> str:
    return _SELECT_MAX_MODIFIED_PG if is_postgres() else _SELECT_MAX_MODIFIED_SQLITE


def get_stack_terms() -> str:
    """Operator stack profile for server-side matching (BRIEFR_STACK_TERMS)."""
    return os.environ.get("BRIEFR_STACK_TERMS", "").strip()


async def get_sync_state_value(db: DbConnection, key: str) -> str | None:
    """Read any sync_state key; returns None when absent."""
    rows = await db.execute_fetchall(_select_value_sql(), (key,))
    return rows[0]["value"] if rows else None


async def set_sync_state_value(db: DbConnection, key: str, value: str) -> None:
    """Upsert any sync_state key (caller commits)."""
    await db.execute(_upsert_sql(), (key, value, utcnow_str()))


async def get_nvd_sync_watermark(db: DbConnection) -> str | None:
    rows = await db.execute_fetchall(_select_value_sql(), (NVD_SYNC_WATERMARK_KEY,))
    return rows[0]["value"] if rows else None


async def set_nvd_sync_watermark(db: DbConnection, value: str) -> None:
    await db.execute(_upsert_sql(), (NVD_SYNC_WATERMARK_KEY, value, utcnow_str()))


async def seed_nvd_watermark_from_cves(db: DbConnection) -> str | None:
    rows = await db.execute_fetchall(_select_max_modified_sql())
    latest = rows[0]["latest"] if rows else None
    if not latest:
        return None
    await set_nvd_sync_watermark(db, latest)
    return latest


async def resolve_nvd_watermark(db: DbConnection, *, min_cves: int = 10) -> str | None:
    watermark = await get_nvd_sync_watermark(db)
    if watermark:
        return watermark
    count = await get_cve_count(db)
    if count < min_cves:
        return None
    return await seed_nvd_watermark_from_cves(db)
