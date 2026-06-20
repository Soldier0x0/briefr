"""Tests for the parallel RSS fetch used by the snapshot scheduler job."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_feed_cache, init_db
from feeds import incident_news

RSS_TEMPLATE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>{label}</title>
    <item>
      <title>{title}</title>
      <link>https://example.com/{slug}</link>
      <description>Exploitation observed in the wild.</description>
      <pubDate>Mon, 02 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parallel_fetch_collects_items_and_isolates_failures(tmp_path, monkeypatch):
    db_path = tmp_path / "news.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    sources = [
        {"id": "alpha", "label": "Alpha News", "url": "https://alpha.example/rss"},
        {"id": "beta", "label": "Beta News", "url": "https://beta.example/rss"},
        {"id": "broken", "label": "Broken News", "url": "https://broken.example/rss"},
    ]
    monkeypatch.setattr(incident_news, "INCIDENT_RSS_SOURCES", sources)

    async def fake_fetch(url: str, source_id: str = "rss") -> bytes:
        if "broken" in url:
            raise RuntimeError("connection refused")
        slug = "alpha" if "alpha" in url else "beta"
        return RSS_TEMPLATE.format(
            label=slug.title(), title=f"{slug} headline", slug=slug
        ).encode()

    monkeypatch.setattr(incident_news, "_fetch_rss_bytes", fake_fetch)

    async def run() -> None:
        await init_db()
        from database import get_db

        db = await get_db()
        try:
            cards, errors = await incident_news.fetch_all_incident_news_parallel(db)
            await db.commit()

            titles = {c["title"] for c in cards}
            assert titles == {"alpha headline", "beta headline"}
            assert len(errors) == 1
            assert errors[0]["source"] == "Broken News"

            # Successful sources were written to the per-source cache.
            cached = await get_feed_cache(
                db, "incident_rss:alpha", max_age_hours=1
            )
            assert cached is not None
            assert cached["items"][0]["title"] == "alpha headline"

            # Second call serves from cache without network.
            async def must_not_fetch(url: str, source_id: str = "rss") -> bytes:
                raise AssertionError("network fetch on warm cache")

            monkeypatch.setattr(incident_news, "_fetch_rss_bytes", must_not_fetch)
            cards2, errors2 = await incident_news.fetch_all_incident_news_parallel(db)
            cached_titles = {c["title"] for c in cards2}
            assert {"alpha headline", "beta headline"} <= cached_titles
            # Broken source is retried (still uncached) and fails again.
            assert len(errors2) == 1
        finally:
            await db.close()

    asyncio.run(run())
