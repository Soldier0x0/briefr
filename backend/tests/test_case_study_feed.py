"""Tests for combined case study feed loading."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db
from feeds import case_study_feed


def test_fetch_combined_feed_uses_single_db_connection(tmp_path, monkeypatch):
    db_path = tmp_path / "feed.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

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
            "fetch_all_incident_news",
            AsyncMock(
                return_value=(
                    [{"id": "n1", "kind": "news", "publishedAt": "2026-01-02"}],
                    [],
                )
            ),
        )

        cards, errors = await case_study_feed.fetch_combined_case_study_feed(atlas_limit=5)

        assert len(connections) == 1
        assert errors == []
        assert any(card.get("kind") == "news" for card in cards)

    asyncio.run(run())
