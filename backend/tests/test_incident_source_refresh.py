"""Per-source incident feed refresh (RSS + ATLAS partial snapshot merge)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db, set_feed_cache
from feeds import case_study_feed


def _setup_db(tmp_path, monkeypatch, name: str) -> None:
    db_path = tmp_path / name
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "incidents_admin.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("briefr_at", auth_token())
    return client


def test_refresh_unknown_source_returns_400(admin_client):
    resp = admin_client.post(
        "/api/admin/incidents/refresh",
        json={"sources": ["not_a_real_source"]},
    )
    assert resp.status_code == 400
    assert "Unknown source" in resp.json()["detail"]


def test_partial_rss_refresh_replaces_only_that_source(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "partial.db")

    async def run() -> None:
        await init_db()
        db = await case_study_feed.get_db()
        try:
            await set_feed_cache(
                db,
                case_study_feed.SNAPSHOT_CACHE_KEY,
                {
                    "news": [
                        {
                            "id": "old-bleep",
                            "sourceId": "bleeping",
                            "source": "Bleeping Computer",
                            "publishedAt": "2020-01-01",
                            "kind": "news",
                        },
                        {
                            "id": "keep-hn",
                            "sourceId": "hackernews",
                            "source": "The Hacker News",
                            "publishedAt": "2026-01-01",
                            "kind": "news",
                        },
                    ],
                    "atlas": [{"id": "AML.CS0001", "kind": "atlas"}],
                    "errors": [],
                    "generated_at": "2020-01-01T00:00:00+00:00",
                },
            )
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(
            case_study_feed,
            "fetch_rss_source",
            AsyncMock(
                return_value=[
                    {
                        "id": "new-bleep",
                        "sourceId": "bleeping",
                        "source": "Bleeping Computer",
                        "publishedAt": "2026-06-01",
                        "kind": "news",
                    }
                ]
            ),
        )

        snapshot = await case_study_feed.refresh_incident_feed_sources(["bleeping"])
        news_ids = [c["id"] for c in snapshot["news"]]
        assert set(news_ids) == {"keep-hn", "new-bleep"}
        assert snapshot["atlas"] == [{"id": "AML.CS0001", "kind": "atlas"}]
        assert snapshot["generated_at"] != "2020-01-01T00:00:00+00:00"

    asyncio.run(run())


def test_atlas_only_refresh_keeps_rss_cards(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch, "atlas_only.db")

    async def run() -> None:
        await init_db()
        db = await case_study_feed.get_db()
        try:
            await set_feed_cache(
                db,
                case_study_feed.SNAPSHOT_CACHE_KEY,
                {
                    "news": [
                        {
                            "id": "n1",
                            "sourceId": "hackernews",
                            "publishedAt": "2026-01-01",
                            "kind": "news",
                        }
                    ],
                    "atlas": [{"id": "old-atlas", "kind": "atlas"}],
                    "errors": [],
                    "generated_at": "2020-01-01T00:00:00+00:00",
                },
            )
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(
            case_study_feed,
            "_load_atlas_cards",
            AsyncMock(
                return_value=(
                    [{"id": "new-atlas", "kind": "atlas", "publishedAt": "2026-02-01"}],
                    [],
                )
            ),
        )

        snapshot = await case_study_feed.refresh_incident_feed_sources(["atlas"])
        assert [c["id"] for c in snapshot["news"]] == ["n1"]
        assert snapshot["atlas"][0]["id"] == "new-atlas"

    asyncio.run(run())


def test_admin_incidents_refresh_accepts_valid_source(admin_client, monkeypatch):
    async def _noop_refresh(_sources=None):
        return {"news": [], "atlas": [], "errors": [], "generated_at": "now"}

    monkeypatch.setattr(
        "feeds.case_study_feed.refresh_incident_feed_sources",
        _noop_refresh,
    )

    resp = admin_client.post(
        "/api/admin/incidents/refresh",
        json={"sources": ["hackernews"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sources"] == ["hackernews"]
