"""ATLAS upstream release-feed version check (auto-refresh trigger)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from feeds import atlas

ATOM_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>v2026.05</title>
    <updated>2026-05-27T20:06:34Z</updated>
  </entry>
  <entry>
    <title>v2026.02</title>
    <updated>2026-02-01T00:00:00Z</updated>
  </entry>
</feed>
"""


def test_get_latest_atlas_release_parses_first_entry_title(monkeypatch):
    class FakeResponse:
        content = ATOM_FIXTURE

    monkeypatch.setattr(atlas, "resilient_get", AsyncMock(return_value=FakeResponse()))

    latest = run_db_test(atlas.get_latest_atlas_release())
    assert latest == "v2026.05"


def test_get_latest_atlas_release_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(atlas, "resilient_get", AsyncMock(side_effect=RuntimeError("boom")))

    latest = run_db_test(atlas.get_latest_atlas_release())
    assert latest is None


def test_run_atlas_version_check_skips_refresh_when_unchanged(monkeypatch, tmp_path):
    import scheduler
    from database import init_db

    db_path = tmp_path / "atlas_check.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())

    monkeypatch.setattr(scheduler, "get_latest_atlas_release", AsyncMock(return_value="v2026.05"))
    refresh_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(scheduler, "run_weekly_mitre_refresh", refresh_mock)

    async def seed_and_run():
        from database import ATLAS_UPSTREAM_VERSION_KEY, get_db, set_sync_state_value

        db = await get_db()
        try:
            await set_sync_state_value(db, ATLAS_UPSTREAM_VERSION_KEY, "v2026.05")
            await db.commit()
        finally:
            await db.close()
        return await scheduler.run_atlas_version_check()

    result = run_db_test(seed_and_run())
    assert result is False
    refresh_mock.assert_not_awaited()


def test_run_atlas_version_check_refreshes_when_version_changes(monkeypatch, tmp_path):
    import scheduler
    from database import init_db

    db_path = tmp_path / "atlas_check2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())

    monkeypatch.setattr(scheduler, "get_latest_atlas_release", AsyncMock(return_value="v2026.05"))
    refresh_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(scheduler, "run_weekly_mitre_refresh", refresh_mock)

    async def seed_and_run():
        from database import ATLAS_UPSTREAM_VERSION_KEY, get_db, set_sync_state_value

        db = await get_db()
        try:
            await set_sync_state_value(db, ATLAS_UPSTREAM_VERSION_KEY, "v2026.02")
            await db.commit()
        finally:
            await db.close()
        return await scheduler.run_atlas_version_check()

    result = run_db_test(seed_and_run())
    assert result is True
    refresh_mock.assert_awaited_once()

    async def read_stored():
        from database import ATLAS_UPSTREAM_VERSION_KEY, get_db, get_sync_state_value

        db = await get_db()
        try:
            return await get_sync_state_value(db, ATLAS_UPSTREAM_VERSION_KEY)
        finally:
            await db.close()

    assert run_db_test(read_stored()) == "v2026.05"
