"""Postgres-native cache module (Post-B Phase 1)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.cache as cache_mod
from db.cache import (
    get_feed_cache,
    get_ioc_cache,
    get_ioc_cache_batch,
    merge_cve_exploits,
    set_feed_cache,
    set_ioc_cache,
)
from db.config import is_postgres
from database import get_db, init_db
from tests.conftest import run_db_test


def _utc(hours_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_cache_sql_uses_native_placeholders():
    assert "$1" in cache_mod._GET_IOC_CACHE_PG
    assert "$2" in cache_mod._GET_IOC_CACHE_PG
    assert "$4" in cache_mod._UPSERT_IOC_CACHE_PG
    assert "ON CONFLICT (cve_id, url)" in cache_mod._INSERT_EXPLOIT_PG
    assert "?" in cache_mod._GET_IOC_CACHE_SQLITE
    assert "INSERT OR IGNORE" in cache_mod._INSERT_EXPLOIT_SQLITE


def test_ioc_cache_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_ioc.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await get_ioc_cache(db, "8.8.8.8") is None
            await set_ioc_cache(db, "8.8.8.8", "ip", {"score": 1})
            await db.commit()
            hit = await get_ioc_cache(db, "8.8.8.8")
            assert hit == {"score": 1}

            batch = await get_ioc_cache_batch(db, ["8.8.8.8", "1.1.1.1"])
            assert batch == {"8.8.8.8": {"score": 1}}
        finally:
            await db.close()

    run_db_test(_run())


def test_feed_cache_respects_max_age(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_feed.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            key = "test:feed-key"
            await set_feed_cache(db, key, {"ok": True})
            await db.commit()
            assert await get_feed_cache(db, key, max_age_hours=6) == {"ok": True}

            stale_sql = (
                "UPDATE feed_cache SET cached_at = $1 WHERE cache_key = $2"
                if is_postgres()
                else "UPDATE feed_cache SET cached_at = ? WHERE cache_key = ?"
            )
            await db.execute(stale_sql, (_utc(12), key))
            await db.commit()
            assert await get_feed_cache(db, key, max_age_hours=6) is None
        finally:
            await db.close()

    run_db_test(_run())


def test_merge_cve_exploits_dedupes(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cache_exploit.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            cve_placeholders = (
                "$1, $2, $3"
                if is_postgres()
                else "?, ?, ?"
            )
            await db.execute(
                f"INSERT INTO cves (cve_id, description, has_poc) VALUES ({cve_placeholders})",
                ("CVE-2024-9001", "test", 0),
            )
            await db.commit()

            exploit = {
                "title": "PoC",
                "type": "poc",
                "source": "test",
                "url": "https://example.com/poc",
                "published_date": "2024-01-01",
            }
            assert await merge_cve_exploits(db, "CVE-2024-9001", [exploit]) == 1
            assert await merge_cve_exploits(db, "CVE-2024-9001", [exploit]) == 0
            await db.commit()
        finally:
            await db.close()

    run_db_test(_run())
