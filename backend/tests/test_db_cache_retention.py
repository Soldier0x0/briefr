"""Postgres-native cache_retention module (Post-B Phase 1)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.cache_retention as cache_retention_mod
from db.cache_retention import (
    purge_old_cve_change_history,
    purge_stale_feed_cache,
    purge_stale_ioc_cache,
    run_retention_cleanup,
)
from db.config import is_postgres
from database import get_db, init_db
from tests.conftest import run_db_test


def _utc(days_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_cache_retention_sql_uses_native_placeholders():
    assert "$1" in cache_retention_mod._PURGE_IOC_CACHE_PG
    assert "$2" in cache_retention_mod._PURGE_FEED_CACHE_PREFIX_PG
    assert "$1" in cache_retention_mod._PURGE_EPSS_HISTORY_PG
    assert "?" in cache_retention_mod._PURGE_IOC_CACHE_SQLITE
    assert "?" in cache_retention_mod._PURGE_FEED_CACHE_PREFIX_SQLITE


def test_purge_stale_ioc_cache_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_retention_ioc.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            placeholders = (
                "$1, $2, $3, $4), ($5, $6, $7, $8"
                if is_postgres()
                else "?, ?, ?, ?), (?, ?, ?, ?"
            )
            await db.execute(
                f"""
                INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
                VALUES ({placeholders})
                """,
                (
                    "8.8.8.8",
                    "ip",
                    "{}",
                    _utc(2),
                    "1.1.1.1",
                    "ip",
                    "{}",
                    _utc(0.01),
                ),
            )
            await db.commit()

            deleted = await purge_stale_ioc_cache(db, retention_hours=24)
            await db.commit()

            rows = await db.execute_fetchall("SELECT value FROM ioc_cache")
            assert deleted == 1
            assert [row["value"] for row in rows] == ["1.1.1.1"]
        finally:
            await db.close()

    run_db_test(_run())


def test_run_retention_cleanup_returns_counts(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_retention_run.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            counts = await run_retention_cleanup(db)
            await db.commit()
            assert set(counts.keys()) == {
                "ioc_cache",
                "feed_cache",
                "epss_history",
                "cve_change_history",
                "otx_cve_pulses",
                "otx_pulse_iocs",
            }
            assert all(isinstance(v, int) for v in counts.values())
        finally:
            await db.close()

    run_db_test(_run())


def test_purge_old_cve_change_history_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_retention_change.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            placeholders = (
                "$1, $2, $3, $4, $5), ($6, $7, $8, $9, $10"
                if is_postgres()
                else "?, ?, ?, ?, ?), (?, ?, ?, ?, ?"
            )
            await db.execute(
                f"""
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES ({placeholders})
                """,
                (
                    "CVE-2024-0001",
                    "severity",
                    "LOW",
                    "HIGH",
                    _utc(120),
                    "CVE-2024-0002",
                    "severity",
                    "LOW",
                    "MEDIUM",
                    _utc(1),
                ),
            )
            await db.commit()

            deleted = await purge_old_cve_change_history(db, retention_days=90)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT cve_id FROM cve_change_history ORDER BY cve_id"
            )
            assert deleted == 1
            assert [row["cve_id"] for row in rows] == ["CVE-2024-0002"]
        finally:
            await db.close()

    run_db_test(_run())
