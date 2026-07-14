"""Tests for SQLite -> PostgreSQL migration helpers."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import migration.sqlite_to_postgres as mig_mod
from db.config import is_postgres
from migration.sqlite_to_postgres import (
    MIGRATION_STATUS_KEY,
    SERIAL_ID_TABLES,
    TABLE_ORDER,
    _intersect_columns,
    get_status_with_fallback,
)
from tests.conftest import run_db_test


def test_table_order_includes_auth_and_webhooks():
    assert "users" in TABLE_ORDER
    assert "sessions" in TABLE_ORDER
    assert TABLE_ORDER.index("users") < TABLE_ORDER.index("sessions")
    assert "webhook_destinations" in TABLE_ORDER
    assert "webhook_delivery_log" in TABLE_ORDER
    assert "otx_pulses" in TABLE_ORDER
    assert "correlation_suppressions" in TABLE_ORDER


def test_serial_id_tables_cover_auth_and_webhooks():
    for table in ("users", "sessions", "webhook_delivery_log", "correlation_suppressions"):
        assert table in SERIAL_ID_TABLES


def test_intersect_columns_case_insensitive():
    sqlite_cols = ["cve_id", "CVSS_Score", "description"]
    pg_cols = ["cve_id", "cvss_score", "description", "extra"]
    sqlite_select, pg_insert = _intersect_columns(sqlite_cols, pg_cols)
    assert sqlite_select == ["cve_id", "CVSS_Score", "description"]
    assert pg_insert == ["cve_id", "cvss_score", "description"]


def test_status_fallback_reads_persisted_record(tmp_path, monkeypatch):
    """PR-R4: idle in-memory state falls back to the sync_state snapshot; a
    persisted 'running' from a dead process reads as 'interrupted'."""
    if is_postgres():
        return
    db_path = tmp_path / "migration_status.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        from database import get_db, init_db, set_sync_state_value

        await init_db()

        # No persisted record → in-memory idle state returned as-is.
        assert mig_mod._state["status"] == "idle"
        status = await get_status_with_fallback()
        assert status["status"] == "idle"
        assert "persisted" not in status

        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                MIGRATION_STATUS_KEY,
                json.dumps({"status": "running", "tables_done": 5, "rows_copied": 1000}),
            )
            await db.commit()
        finally:
            await db.close()

        status = await get_status_with_fallback()
        assert status["status"] == "interrupted"
        assert status["persisted"] is True
        assert "restarted" in status["error"]

        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                MIGRATION_STATUS_KEY,
                json.dumps({"status": "done", "tables_done": 34, "rows_copied": 5000}),
            )
            await db.commit()
        finally:
            await db.close()

        status = await get_status_with_fallback()
        assert status["status"] == "done"
        assert status["persisted"] is True

    run_db_test(_run())


def test_status_fallback_ignored_when_in_memory_active(monkeypatch):
    monkeypatch.setitem(mig_mod._state, "status", "running")
    import asyncio

    status = asyncio.run(get_status_with_fallback())
    assert status["status"] == "running"
    assert "persisted" not in status
