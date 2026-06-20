"""One-shot SQLite -> PostgreSQL data migration, driven from the admin panel.

Reuses the existing Alembic schema (backend/alembic/versions/001_initial_schema.py)
for DDL and the Postgres URL helpers in db/config.py. This module only moves rows;
it never decides which engine BRIEFR runs on — that switch happens by setting
DATABASE_URL via the existing /api/admin/config/apply-all + graceful-restart flow.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

import aiosqlite

from db.config import postgres_dsn

logger = logging.getLogger(__name__)

# Mirrors the CREATE TABLE order in alembic/versions/001_initial_schema.py
# (already dependency-safe — cves before *_map tables, etc.)
TABLE_ORDER: list[str] = [
    "cves", "ioc_cache", "kev_deadlines", "api_usage", "sync_state",
    "mitre_techniques", "cve_technique_map", "atlas_techniques",
    "atlas_case_studies", "cve_atlas_map", "epss_history", "cve_exploits",
    "feed_cache", "cve_change_history", "otx_cve_pulses", "otx_pulse_iocs",
    "correlation_infrastructure", "correlation_actor", "correlation_temporal",
    "mitre_groups", "group_technique_map", "cve_embeddings", "hunt_packs",
    "audit_log", "watchlist", "webhook_alert_log",
]

# Tables with a SERIAL id column — sequence must be re-synced after a row-level copy.
SERIAL_ID_TABLES: list[str] = ["cve_exploits", "cve_change_history", "hunt_packs", "audit_log"]

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
}
_lock = asyncio.Lock()


def get_status() -> dict[str, Any]:
    return dict(_state)


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
    except Exception as exc:  # noqa: BLE001 - surfacing the driver error to the operator
        return {"ok": False, "error": str(exc)}


async def _apply_schema(database_url: str) -> None:
    """Run `alembic upgrade head` against the target DB (idempotent — CREATE TABLE IF NOT EXISTS)."""
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


async def run_migration(database_url: str, sqlite_path: str) -> None:
    """Copy every row from the SQLite file at sqlite_path into the target Postgres DB.

    Truncates target tables first, so this is safely re-runnable if it fails partway.
    Designed to be scheduled as a background task; progress is polled via get_status().
    """
    if _state["status"] == "running":
        raise RuntimeError("A migration is already running")

    import asyncpg

    async with _lock:
        _state.update(
            status="running", current_table=None, tables_done=0,
            rows_copied=0, started_at=time.time(), finished_at=None, error=None,
        )
        try:
            await _apply_schema(database_url)

            dsn = postgres_dsn(database_url)
            pg = await asyncpg.connect(dsn=dsn, timeout=30)
            try:
                # Truncate in one statement so FK cascades don't fight table order.
                table_list = ", ".join(TABLE_ORDER)
                await pg.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")

                async with aiosqlite.connect(sqlite_path) as src:
                    src.row_factory = aiosqlite.Row
                    for table in TABLE_ORDER:
                        _state["current_table"] = table
                        cols_cursor = await src.execute(f"PRAGMA table_info({table})")
                        columns = [row[1] for row in await cols_cursor.fetchall()]

                        cursor = await src.execute(f"SELECT {', '.join(columns)} FROM {table}")
                        while True:
                            batch = await cursor.fetchmany(_BATCH_SIZE)
                            if not batch:
                                break
                            records = [tuple(row) for row in batch]
                            await pg.copy_records_to_table(table, records=records, columns=columns)
                            _state["rows_copied"] += len(records)
                        _state["tables_done"] += 1

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
        except Exception as exc:  # noqa: BLE001 - reported to the admin panel, not swallowed
            logger.exception("SQLite to Postgres migration failed")
            _state["status"] = "error"
            _state["error"] = str(exc)
            _state["finished_at"] = time.time()
