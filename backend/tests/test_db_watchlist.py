"""Postgres-native watchlist module (Post-B Phase 1)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.watchlist as watchlist_mod
from db.config import is_postgres
from db.watchlist import (
    delete_all_snooze_entries,
    delete_watchlist_entry,
    get_watchlist_entry,
    list_watchlist_entries,
    upsert_watchlist_entry,
)
from database import get_db, init_db
from tests.conftest import run_db_test

CVE_PIN = "CVE-2024-1001"
CVE_SNOOZE = "CVE-2024-1002"


def test_watchlist_sql_uses_native_placeholders():
    if is_postgres():
        assert "$1" in watchlist_mod._UPSERT_PG
        assert "$4" in watchlist_mod._UPSERT_PG
        assert "snooze_until::timestamp" in watchlist_mod._WATCHLIST_ACTIVE_PG
    else:
        assert "?" in watchlist_mod._UPSERT_SQLITE
        assert "datetime(snooze_until)" in watchlist_mod._WATCHLIST_ACTIVE_SQLITE


def test_watchlist_crud_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "watchlist_native.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await list_watchlist_entries(db) == []
            assert await get_watchlist_entry(db, CVE_PIN) is None

            pin = await upsert_watchlist_entry(db, CVE_PIN, "pin")
            await db.commit()
            assert pin["cve_id"] == CVE_PIN
            assert pin["state"] == "pin"

            future = (datetime.now(timezone.utc) + timedelta(days=3)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            snooze = await upsert_watchlist_entry(db, CVE_SNOOZE, "snooze", future)
            await db.commit()
            assert snooze["state"] == "snooze"

            entries = await list_watchlist_entries(db)
            assert {e["cve_id"] for e in entries} == {CVE_PIN, CVE_SNOOZE}

            entry = await get_watchlist_entry(db, CVE_PIN)
            assert entry is not None
            assert entry["state"] == "pin"

            assert await delete_watchlist_entry(db, CVE_PIN) is True
            await db.commit()
            assert await get_watchlist_entry(db, CVE_PIN) is None
            assert await delete_watchlist_entry(db, CVE_PIN) is False

            deleted = await delete_all_snooze_entries(db)
            await db.commit()
            assert deleted == 1
            assert await list_watchlist_entries(db) == []
        finally:
            await db.close()

    run_db_test(_run())


def test_expired_snooze_excluded_from_active(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "watchlist_expired.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            await upsert_watchlist_entry(db, CVE_SNOOZE, "snooze", past)
            await db.commit()
            assert await list_watchlist_entries(db) == []
            assert await get_watchlist_entry(db, CVE_SNOOZE) is None
        finally:
            await db.close()

    run_db_test(_run())
