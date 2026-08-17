"""Publication store, APIs, and sync behavior."""

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from db.publications import upsert_publication, replace_publication_entity_links
from feeds.publication_rss import parse_publication_rss_items
from publications.registry import SOURCES_BY_KEY

pytestmark = pytest.mark.no_auth


CISA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>CISA Advisory CVE-2026-42424</title>
      <link>https://www.cisa.gov/news-events/alerts/2026/01/01/example-advisory</link>
      <description>Critical flaw CVE-2026-55555 in edge devices.</description>
      <pubDate>Mon, 08 Jun 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "publications.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    from database import get_db, init_db
    from tests.conftest import run_db_test

    run_db_test(init_db())

    from main import app

    return TestClient(app)


def test_parse_publication_rss_items_extracts_metadata():
    desc = SOURCES_BY_KEY["cisa-news"]
    items = parse_publication_rss_items(CISA_XML, desc)
    assert len(items) == 1
    assert items[0]["title"].startswith("CISA Advisory")
    assert items[0]["document_kind"] == "advisory"
    assert "cisa.gov" in items[0]["canonical_url"]


@pytest.mark.asyncio
async def test_upsert_dedupes_by_url(tmp_path, monkeypatch):
    db_path = tmp_path / "pub_dedup.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from database import get_db, init_db
    from tests.conftest import run_db_test

    await run_db_test(init_db())
    db = await get_db()
    try:
        pid1, new1 = await upsert_publication(
            db,
            source_key="cisa-news",
            canonical_url="https://example.com/a",
            content_sha256="abc",
            title="First",
            document_kind="advisory",
            published_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
            retrieved_at="2026-01-02T00:00:00+00:00",
        )
        pid2, new2 = await upsert_publication(
            db,
            source_key="cisa-news",
            canonical_url="https://example.com/a",
            content_sha256="def",
            title="Updated title",
            document_kind="advisory",
            published_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-03T00:00:00+00:00",
            retrieved_at="2026-01-03T00:00:00+00:00",
        )
        assert new1 is True
        assert new2 is False
        assert pid1 == pid2
        links = await replace_publication_entity_links(
            db,
            pid1,
            title="CVE-2026-11111 patched",
            body="Also CVE-2026-22222",
            retrieved_at="2026-01-03T00:00:00+00:00",
        )
        assert links == 2
        await db.commit()
        rows = await db.execute_fetchall(
            "SELECT entity_id FROM publication_entity_links WHERE publication_id = ?",
            (pid1,),
        )
        assert {r["entity_id"] for r in rows} == {"CVE-2026-11111", "CVE-2026-22222"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_publication_sync_does_not_touch_correlation(tmp_path, monkeypatch):
    db_path = tmp_path / "pub_corr.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from database import get_db, init_db
    from tests.conftest import run_db_test

    await run_db_test(init_db())
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO correlation_cve_snapshot (cve_id, payload, computed_at)
            VALUES ('CVE-2026-00001', '{}', '2026-01-01T00:00:00Z')
            """
        )
        await db.commit()
        before = await db.execute_fetchall("SELECT COUNT(*) AS n FROM correlation_cve_snapshot")
        pid, _ = await upsert_publication(
            db,
            source_key="cisa-news",
            canonical_url="https://example.com/corr",
            content_sha256="sha",
            title="CVE-2026-00001 advisory",
            document_kind="advisory",
            published_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
            retrieved_at="2026-01-01T00:00:00+00:00",
        )
        await replace_publication_entity_links(
            db,
            pid,
            title="CVE-2026-00001",
            body="",
            retrieved_at="2026-01-01T00:00:00+00:00",
        )
        await db.commit()
        after = await db.execute_fetchall("SELECT COUNT(*) AS n FROM correlation_cve_snapshot")
        assert before[0]["n"] == after[0]["n"]
    finally:
        await db.close()


def test_publications_api_list_and_detail(client):
  seed = _seed_publication(client)
  listing = client.get("/api/publications")
  assert listing.status_code == 200
  body = listing.json()
  assert any(row["publication_id"] == seed["publication_id"] for row in body["data"])

  detail = client.get(f"/api/publications/{seed['publication_id']}")
  assert detail.status_code == 200
  assert detail.json()["data"]["title"] == seed["title"]

  by_cve = client.get("/api/cves/CVE-2026-77777/publications")
  assert by_cve.status_code == 200
  assert len(by_cve.json()["data"]) == 1


def _seed_publication(client: TestClient) -> dict:
    import asyncio

    from database import get_db, init_db
    from tests.conftest import run_db_test

    async def _seed() -> dict:
        await run_db_test(init_db())
        db = await get_db()
        try:
            pid, _ = await upsert_publication(
                db,
                source_key="cisa-news",
                canonical_url="https://example.com/seed-advisory",
                content_sha256="seedsha",
                title="Seed advisory CVE-2026-77777",
                document_kind="advisory",
                published_at="2026-06-08T11:00:00+00:00",
                updated_at="2026-06-08T11:00:00+00:00",
                retrieved_at="2026-06-08T11:00:00+00:00",
            )
            await replace_publication_entity_links(
                db,
                pid,
                title="Seed advisory CVE-2026-77777",
                body="Details for CVE-2026-77777",
                retrieved_at="2026-06-08T11:00:00+00:00",
            )
            await db.commit()
            return {"publication_id": pid, "title": "Seed advisory CVE-2026-77777"}
        finally:
            await db.close()

    return asyncio.run(_seed())
