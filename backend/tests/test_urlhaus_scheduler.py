"""Phase 2: run_catalog_sync wiring for the URLhaus catalog source."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database
from database import init_db
from scheduler import _catalog_window_days, run_catalog_sync
import sources.registry as registry


def _urlhaus_desc():
    return next(s for s in registry.CATALOG_SOURCES if s.source_key == "urlhaus")


def test_urlhaus_sync_honors_enabled_env(tmp_path, monkeypatch):
    """URLHAUS_SYNC_ENABLED=0 must short-circuit run_catalog_sync before any
    fetch/upsert, even when the Auth-Key is present."""
    async def run():
        db_path = str(tmp_path / "uh-sched-disabled.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("ABUSECH_AUTH_KEY", "test-key")
        monkeypatch.setenv("URLHAUS_SYNC_ENABLED", "0")

        def fail_if_called(*args, **kwargs):
            raise AssertionError("disabled sync must not fetch upstream")

        monkeypatch.setattr(registry, "CATALOG_SOURCES", (replace(_urlhaus_desc(), fetch=fail_if_called),))
        monkeypatch.setattr(
            registry,
            "SOURCES_BY_KEY",
            registry.MappingProxyType({"urlhaus": replace(_urlhaus_desc(), fetch=fail_if_called)}),
        )
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc,
                    malware, threat_type, confidence_level, first_seen
                ) VALUES (
                    'urlhaus', 'uh-sched-1', 'url', 'http://evil.example/x',
                    'http://evil.example/x', 'evil.example', 'emotet',
                    'malware_download', 100, '2024-06-01'
                )
                """
            )
            await db.commit()
            result = await run_catalog_sync("urlhaus")
            assert result is True
            rows = await db.execute_fetchall(
                "SELECT COUNT(*) AS c FROM ti_mirror_iocs WHERE source = 'urlhaus'"
            )
            assert rows[0]["c"] == 1
        finally:
            await db.close()

    run_db_test(run())


def test_urlhaus_sync_upserts_rows(tmp_path, monkeypatch):
    """Enabled sync (key present) fetches and upserts mirror rows via the
    generic ti_mirror upsert."""
    async def fake_fetch(auth_key: str, *, days: int = 7) -> list[dict]:
        assert auth_key == "test-key"
        return [
            {
                "ioc_id": "sched-1",
                "ioc_type": "url",
                "ioc_value": "http://evil.example/a.bin",
                "raw_ioc": "http://evil.example/a.bin",
                "host_ioc": "evil.example",
                "malware": "emotet",
                "threat_type": "malware_download",
                "confidence_level": "100",
                "first_seen": "2024-06-01",
            }
        ]

    async def run():
        db_path = str(tmp_path / "uh-sched-enabled.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("ABUSECH_AUTH_KEY", "test-key")
        monkeypatch.setenv("URLHAUS_SYNC_ENABLED", "1")
        monkeypatch.setattr(
            registry,
            "CATALOG_SOURCES",
            (replace(_urlhaus_desc(), fetch=fake_fetch),),
        )
        monkeypatch.setattr(
            registry,
            "SOURCES_BY_KEY",
            registry.MappingProxyType({s.source_key: s for s in registry.CATALOG_SOURCES}),
        )
        await init_db()
        db = await database.get_db()
        try:
            result = await run_catalog_sync("urlhaus")
            assert result is True
            rows = await db.execute_fetchall(
                "SELECT ref_id, ioc_value FROM ti_mirror_iocs WHERE source = 'urlhaus'"
            )
            assert len(rows) == 1
            assert rows[0]["ref_id"] == "sched-1"
        finally:
            await db.close()

    run_db_test(run())


def test_catalog_window_days_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv("URLHAUS_SYNC_DAYS", raising=False)
    assert _catalog_window_days(_urlhaus_desc()) == 7
    monkeypatch.setenv("URLHAUS_SYNC_DAYS", "0")
    assert _catalog_window_days(_urlhaus_desc()) == 1
    monkeypatch.setenv("URLHAUS_SYNC_DAYS", "not-a-number")
    assert _catalog_window_days(_urlhaus_desc()) == 7
    monkeypatch.setenv("URLHAUS_SYNC_DAYS", "3650")
    assert _catalog_window_days(_urlhaus_desc()) == 7