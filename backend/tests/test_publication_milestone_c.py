"""Milestone C: actors and headline dedup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from publications.actors import make_actor_id, actor_slug


def test_actor_slug_normalizes():
    assert actor_slug("Bruce Schneier") == "bruce-schneier"


def test_make_actor_id_source_qualified():
    aid = make_actor_id("cisa-news", "CISA")
    assert aid == "cisa-news:author:cisa"


@pytest.mark.asyncio
async def test_headline_url_set_empty_without_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "headlines.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from database import get_db, init_db
    from db.publications import get_headline_url_set

    await init_db()
    db = await get_db()
    try:
        urls = await get_headline_url_set(db)
        assert urls == set()
    finally:
        await db.close()
