"""Tests for the Incidents & News snapshot (build, read, staleness)."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import aiosqlite

from database import init_db
from feeds import case_study_feed


def _setup_db(tmp_path, monkeypatch, name: str) -> None:
    db_path = tmp_path / name
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))


def test_build_snapshot_uses_single_db_connection(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "feed.db")

    async def run() -> None:
        await init_db()

        connections: list[aiosqlite.Connection] = []
        original_get_db = case_study_feed.get_db

        async def tracking_get_db():
            db = await original_get_db()
            connections.append(db)
            return db

        monkeypatch.setattr(case_study_feed, "get_db", tracking_get_db)
        monkeypatch.setattr(
            case_study_feed,
            "fetch_all_incident_news_parallel",
            AsyncMock(
                return_value=(
                    [{"id": "n1", "kind": "news", "sourceId": "krebs", "publishedAt": "2026-01-02"}],
                    [],
                )
            ),
        )

        snapshot = await case_study_feed.build_incident_feed_snapshot()

        assert len(connections) == 1
        assert snapshot["errors"] == []
        assert any(card.get("kind") == "news" for card in snapshot["news"])
        assert snapshot["generated_at"]

    run_db_test(run())


def test_get_incident_feed_serves_snapshot_with_meta(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "feed2.db")

    async def run() -> None:
        await init_db()
        monkeypatch.setattr(
            case_study_feed,
            "fetch_all_incident_news_parallel",
            AsyncMock(
                return_value=(
                    [
                        {"id": "n1", "kind": "news", "sourceId": "krebs", "publishedAt": "2026-01-02"},
                        {"id": "n2", "kind": "news", "sourceId": "krebs", "publishedAt": "2026-01-05"},
                    ],
                    [{"source": "News feeds", "message": "boom"}],
                )
            ),
        )

        # Cold miss never blocks: returns warming meta and schedules a
        # background build.
        cards, errors, meta = await case_study_feed.get_incident_feed(atlas_limit=5)
        assert cards == []
        assert errors == []
        assert meta["warming"] is True
        assert meta["stale"] is True

        # Let the scheduled background build run to completion.
        if case_study_feed._background_tasks:
            await asyncio.gather(*case_study_feed._background_tasks)

        cards2, errors2, meta2 = await case_study_feed.get_incident_feed(atlas_limit=5)
        assert [c["id"] for c in cards2 if c["kind"] == "news"] == ["n2", "n1"]
        assert errors2 == [{"source": "News feeds", "message": "boom"}]
        assert meta2["warming"] is False
        assert meta2["stale"] is False
        assert meta2["refreshed_at"]

        # Subsequent reads are pure: rebuild must not be triggered.
        build_mock = AsyncMock(side_effect=AssertionError("must not rebuild"))
        monkeypatch.setattr(
            case_study_feed, "build_incident_feed_snapshot", build_mock
        )
        cards3, _, meta3 = await case_study_feed.get_incident_feed(atlas_limit=5)
        assert [c["id"] for c in cards3 if c["kind"] == "news"] == ["n2", "n1"]
        assert meta3["refreshed_at"] == meta2["refreshed_at"]

    run_db_test(run())


def test_snapshot_staleness_reported(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "feed3.db")

    async def run() -> None:
        await init_db()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=6)
        ).isoformat()
        db = await case_study_feed.get_db()
        try:
            await case_study_feed.set_feed_cache(
                db,
                case_study_feed.SNAPSHOT_CACHE_KEY,
                {
                    "news": [],
                    "atlas": [],
                    "errors": [],
                    "generated_at": old_ts,
                },
            )
            await db.commit()
        finally:
            await db.close()

        _, _, meta = await case_study_feed.get_incident_feed(atlas_limit=5)
        assert meta["stale"] is True

        status = await case_study_feed.get_incident_feed_status()
        assert status["stale"] is True
        assert status["last_refresh"] == old_ts

    run_db_test(run())


def test_status_without_snapshot_is_stale(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "feed4.db")

    async def run() -> None:
        await init_db()
        status = await case_study_feed.get_incident_feed_status()
        assert status["last_refresh"] is None
        assert status["stale"] is True
        assert isinstance(status.get("sources"), list)

    run_db_test(run())
