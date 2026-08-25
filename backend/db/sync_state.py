"""Generic sync-state key/value store plus NVD watermark helpers. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.

After Alembic ``036_intel_app_schema_split`` (Postgres only), ingest watermarks live in
``intel.sync_state`` and operator keys in ``app.sync_state``. SQLite keeps a single table.
"""

from __future__ import annotations

import os

from db.schema_split import schemas_are_split, sync_state_table
from db.timeutil import utcnow_str
from db.metadata import get_cve_count
from db.types import DbConnection

NVD_SYNC_WATERMARK_KEY = "nvd_last_mod_end"

EPSS_BACKFILL_DONE_KEY = "epss_backfill_done"

ATLAS_UPSTREAM_VERSION_KEY = "atlas_upstream_version"

_SELECT_VALUE_SQLITE = "SELECT value FROM sync_state WHERE key = ?"

_UPSERT_SQLITE = """
INSERT INTO sync_state (key, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""

_SELECT_MAX_MODIFIED_SQL = """
SELECT MAX(modified) AS latest
FROM cves
WHERE modified IS NOT NULL AND modified != ''
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _select_sql(table: str) -> str:
    return f"SELECT value FROM {table} WHERE key = $1"


def _upsert_sql(table: str) -> str:
    return f"""
INSERT INTO {table} (key, value, updated_at)
VALUES ($1, $2, $3)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""


async def _resolve_split(db: DbConnection) -> bool:
    if not _is_postgres_connection(db):
        return False
    return await schemas_are_split(db)


async def get_sync_state_value(db: DbConnection, key: str) -> str | None:
    """Read any sync_state key; returns None when absent."""
    if _is_postgres_connection(db):
        split = await _resolve_split(db)
        sql = _select_sql(sync_state_table(key, split=split))
    else:
        sql = _SELECT_VALUE_SQLITE
    rows = await db.execute_fetchall(sql, (key,))
    return rows[0]["value"] if rows else None


async def set_sync_state_value(db: DbConnection, key: str, value: str) -> None:
    """Upsert any sync_state key (caller commits)."""
    if _is_postgres_connection(db):
        split = await _resolve_split(db)
        sql = _upsert_sql(sync_state_table(key, split=split))
    else:
        sql = _UPSERT_SQLITE
    await db.execute(sql, (key, value, utcnow_str()))


async def get_nvd_sync_watermark(db: DbConnection) -> str | None:
    return await get_sync_state_value(db, NVD_SYNC_WATERMARK_KEY)


async def set_nvd_sync_watermark(db: DbConnection, value: str) -> None:
    await set_sync_state_value(db, NVD_SYNC_WATERMARK_KEY, value)


async def seed_nvd_watermark_from_cves(db: DbConnection) -> str | None:
    rows = await db.execute_fetchall(_SELECT_MAX_MODIFIED_SQL)
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


def get_stack_terms() -> str:
    """Wallboard tiles plus detection-backlog fallback when My Stack is empty. Not used for KEV alerts."""
    return os.environ.get("BRIEFR_STACK_TERMS", "").strip()
