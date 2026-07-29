"""One-shot SQLite -> PostgreSQL data migration, driven from the admin panel.

Reuses Alembic for DDL on the target and copies rows from the on-disk SQLite
file. Setting DATABASE_URL (via Admin -> Database) switches the running app to
PostgreSQL; this module never writes to briefr.db after that point.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import aiosqlite

from db.config import postgres_dsn

logger = logging.getLogger(__name__)

# PR-R4 (REST-010/REST-012): the in-memory _state dies with the process, so a
# restart mid-migration used to leave the admin panel reporting "idle" with no
# trace. Every status transition is snapshotted to sync_state under this key;
# get_status() falls back to the persisted record, reporting a persisted
# "running" from a dead process as "interrupted".
MIGRATION_STATUS_KEY = "migration.last_status"

# Dependency-safe copy order (parents before children).
TABLE_ORDER: list[str] = [
    "cves", "ioc_cache", "kev_deadlines", "api_usage", "sync_state", "app_settings",
    "mitre_techniques", "cve_technique_map", "atlas_techniques",
    "atlas_case_studies", "cve_atlas_map", "epss_history", "cve_exploits",
    "feed_cache", "cve_change_history", "otx_cve_pulses", "otx_pulse_iocs", "otx_pulses",
    "correlation_actor", "correlation_temporal",
    "correlation_campaigns", "correlation_campaign_members", "correlation_suppressions",
    "mitre_groups", "group_technique_map", "cve_embeddings", "hunt_packs",
    "audit_log", "watchlist", "webhook_alert_log",
    "webhook_destinations", "webhook_delivery_log",
    "users", "sessions", "user_preferences",
]

SERIAL_ID_TABLES: list[str] = [
    "cve_exploits", "cve_change_history", "hunt_packs", "audit_log",
    "correlation_suppressions", "webhook_delivery_log", "users", "sessions",
]

_BATCH_SIZE = 2000
_BACKEND_DIR = Path(__file__).resolve().parents[1]

_state: dict[str, Any] = {
    "status": "idle",  # idle | running | done | error
    "current_table": None,
    "tables_done": 0,
    "tables_total": len(TABLE_ORDER),
    "rows_copied": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "verification": None,
}
_lock = asyncio.Lock()


def get_status() -> dict[str, Any]:
    return dict(_state)


async def _persist_status() -> None:
    """Snapshot the in-memory state to sync_state (best-effort)."""
    from database import get_db, set_sync_state_value

    try:
        db = await get_db()
        try:
            await set_sync_state_value(db, MIGRATION_STATUS_KEY, json.dumps(_state))
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:  # noqa: BLE001 - persistence must never break the migration
        logger.warning("Could not persist migration status: %s", exc)


async def get_status_with_fallback() -> dict[str, Any]:
    """In-memory state when a migration ran in this process; otherwise the
    persisted snapshot. A persisted "running" with no live in-memory run means
    the process died mid-migration — reported as "interrupted"."""
    if _state["status"] != "idle":
        return dict(_state)

    from database import get_db, get_sync_state_value

    try:
        db = await get_db()
        try:
            raw = await get_sync_state_value(db, MIGRATION_STATUS_KEY)
        finally:
            await db.close()
    except Exception:
        raw = None

    if not raw:
        return dict(_state)

    try:
        persisted = json.loads(raw)
    except (ValueError, TypeError):
        return dict(_state)

    if persisted.get("status") == "running":
        persisted["status"] = "interrupted"
        persisted["error"] = (
            "The backend restarted while this migration was running. "
            "Verify the target database and re-run the migration."
        )
    persisted["persisted"] = True
    return persisted


async def test_connection(database_url: str) -> dict[str, Any]:
    """Open and immediately close a connection to validate the target DSN."""
    import asyncpg

    try:
        dsn = postgres_dsn(database_url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=10)
        try:
            version = await conn.fetchval("SELECT version()")
        finally:
            await conn.close()
        return {"ok": True, "server_version": version}
    except Exception:  # noqa: BLE001 - operator-facing connection probe
        logger.exception("Database connection test failed")
        return {"ok": False, "error": "Could not connect to the database. Check DATABASE_URL and server logs."}


async def _apply_schema(database_url: str) -> None:
    """Run ``alembic upgrade head`` against the target DB."""
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    proc = await asyncio.create_subprocess_exec(
        "alembic", "upgrade", "head",
        cwd=str(_BACKEND_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed (exit {proc.returncode}): "
            f"{stderr.decode(errors='replace')[-2000:]}"
        )
    logger.info("Target schema migrated: %s", stdout.decode(errors="replace")[-500:])


async def _sqlite_table_exists(src: aiosqlite.Connection, table: str) -> bool:
    cursor = await src.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return bool(await cursor.fetchone())


async def _sqlite_columns(src: aiosqlite.Connection, table: str) -> list[str]:
    cursor = await src.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in await cursor.fetchall()]


def _intersect_columns(
    sqlite_cols: list[str], pg_cols: list[str],
) -> tuple[list[str], list[str]]:
    """Return (sqlite_select_cols, pg_insert_cols) with case-insensitive match."""
    pg_lower = {c.lower(): c for c in pg_cols}
    sqlite_select: list[str] = []
    pg_insert: list[str] = []
    for col in sqlite_cols:
        pg_col = pg_lower.get(col.lower())
        if pg_col:
            sqlite_select.append(col)
            pg_insert.append(pg_col)
    return sqlite_select, pg_insert


async def _pg_columns(pg: Any, table: str) -> list[str]:
    rows = await pg.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return [row["column_name"] for row in rows]


async def _count_sqlite_rows(src: aiosqlite.Connection, table: str) -> int:
    if not await _sqlite_table_exists(src, table):
        return 0
    cursor = await src.execute(f"SELECT COUNT(*) FROM {table}")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _count_pg_rows(pg: Any, table: str) -> int:
    try:
        return int(await pg.fetchval(f"SELECT COUNT(*) FROM {table}"))
    except Exception:
        return -1


async def reserve_migration_slot() -> None:
    """Atomically claim the running slot, or raise if one is already in flight."""
    async with _lock:
        if _state["status"] == "running":
            raise RuntimeError("A migration is already running")
        _state.update(
            status="running", current_table=None, tables_done=0,
            rows_copied=0, started_at=time.time(), finished_at=None,
            error=None, verification=None,
        )
    await _persist_status()


async def run_migration(database_url: str, sqlite_path: str, _reserved: bool = False) -> None:
    """Copy rows from SQLite into PostgreSQL (truncates target tables first)."""
    import asyncpg

    if not _reserved:
        await reserve_migration_slot()

    async with _lock:
        try:
            await _apply_schema(database_url)

            dsn = postgres_dsn(database_url)
            pg = await asyncpg.connect(dsn=dsn, timeout=30)
            verification: dict[str, Any] = {"tables": {}, "mismatches": []}
            tables_copied = 0
            try:
                async with pg.transaction():
                    existing_pg = []
                    for table in TABLE_ORDER:
                        cols = await _pg_columns(pg, table)
                        if cols:
                            existing_pg.append(table)
                    if existing_pg:
                        table_list = ", ".join(existing_pg)
                        await pg.execute(
                            f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"
                        )

                    async with aiosqlite.connect(sqlite_path) as src:
                        src.row_factory = aiosqlite.Row
                        for table in TABLE_ORDER:
                            _state["current_table"] = table
                            if not await _sqlite_table_exists(src, table):
                                logger.info("Skipping %s — not present in SQLite", table)
                                _state["tables_done"] += 1
                                continue

                            sqlite_cols = await _sqlite_columns(src, table)
                            pg_cols = await _pg_columns(pg, table)
                            if not pg_cols:
                                raise RuntimeError(
                                    f"Table {table} missing on PostgreSQL after Alembic"
                                )

                            sqlite_columns, pg_columns = _intersect_columns(
                                sqlite_cols, pg_cols,
                            )
                            if not sqlite_columns:
                                logger.warning("No shared columns for %s — skipping", table)
                                _state["tables_done"] += 1
                                continue

                            col_list = ", ".join(sqlite_columns)
                            cursor = await src.execute(
                                f"SELECT {col_list} FROM {table}"
                            )
                            while True:
                                batch = await cursor.fetchmany(_BATCH_SIZE)
                                if not batch:
                                    break
                                records = [
                                    tuple(row[c] for c in sqlite_columns) for row in batch
                                ]
                                await pg.copy_records_to_table(
                                    table, records=records, columns=pg_columns,
                                )
                                _state["rows_copied"] += len(records)
                            tables_copied += 1
                            _state["tables_done"] += 1

                            sqlite_count = await _count_sqlite_rows(src, table)
                            pg_count = await _count_pg_rows(pg, table)
                            verification["tables"][table] = {
                                "sqlite_rows": sqlite_count,
                                "postgres_rows": pg_count,
                            }
                            if sqlite_count != pg_count:
                                verification["mismatches"].append(table)

                        for table in SERIAL_ID_TABLES:
                            await pg.execute(
                                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                            )
            finally:
                await pg.close()

            _state["status"] = "done"
            _state["current_table"] = None
            _state["finished_at"] = time.time()
            _state["verification"] = verification
            if verification["mismatches"]:
                logger.warning(
                    "Migration finished with row-count mismatches: %s",
                    verification["mismatches"],
                )
            await _persist_status()
        except Exception as exc:  # noqa: BLE001 - reported to the admin panel
            logger.exception("SQLite to Postgres migration failed")
            _state["status"] = "error"
            _state["error"] = str(exc)
            _state["finished_at"] = time.time()
            await _persist_status()
