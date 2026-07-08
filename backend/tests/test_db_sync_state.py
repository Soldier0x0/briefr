"""Postgres-native sync_state module (Post-B Phase 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.sync_state as sync_state_mod
from db.config import is_postgres
from db.sync_state import EPSS_BACKFILL_DONE_KEY, get_sync_state_value, set_sync_state_value
from database import get_db, init_db
from tests.conftest import run_db_test


def test_sync_state_sql_uses_native_placeholders():
    if is_postgres():
        assert "$1" in sync_state_mod._SELECT_VALUE_PG
        assert "$3" in sync_state_mod._UPSERT_PG
    else:
        assert "?" in sync_state_mod._SELECT_VALUE_SQLITE


def test_get_set_sync_state_value_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "sync_state_native.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await get_sync_state_value(db, "phase1_key") is None
            await set_sync_state_value(db, "phase1_key", "alpha")
            await db.commit()
            assert await get_sync_state_value(db, "phase1_key") == "alpha"
            await set_sync_state_value(db, EPSS_BACKFILL_DONE_KEY, "1")
            await db.commit()
            assert await get_sync_state_value(db, EPSS_BACKFILL_DONE_KEY) == "1"
        finally:
            await db.close()

    run_db_test(_run())
