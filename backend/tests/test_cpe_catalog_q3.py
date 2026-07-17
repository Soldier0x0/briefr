"""Q3 NVD CPE software catalog + autocomplete."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from db.software_catalog import (
    categorize_cpe as _categorize,
    parse_cpe23,
    suggest_software,
    upsert_catalog_rows,
)
from feeds.cpe_catalog import normalize_cpe_product


def test_parse_and_categorize_cpe():
    parsed = parse_cpe23("cpe:2.3:a:apache:http_server:2.4.49:*:*:*:*:*:*:*")
    assert parsed["vendor"] == "apache"
    assert parsed["product"] == "http_server"
    assert parsed["version"] == "2.4.49"
    assert _categorize(part="a", vendor="apache", product="http_server") == "web_server"
    assert _categorize(part="o", vendor="canonical", product="ubuntu_linux") == "os"
    assert _categorize(part="a", vendor="openssl", product="openssl") == "library"


def test_normalize_cpe_product_from_api_shape():
    row = normalize_cpe_product(
        {
            "cpeName": "cpe:2.3:a:nginx:nginx:1.18.0:*:*:*:*:*:*:*",
            "titles": [{"title": "nginx 1.18.0", "lang": "en"}],
        }
    )
    assert row is not None
    assert row["vendor"] == "nginx"
    assert row["category"] == "web_server"
    assert "nginx" in row["display_name"].lower()


@pytest.mark.asyncio
async def test_suggest_requires_three_chars(tmp_path, monkeypatch):
    db_path = tmp_path / "cpe.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)

    from database import get_db, init_db

    await init_db()
    db = await get_db()
    try:
        await upsert_catalog_rows(
            db,
            [
                {
                    "cpe_uri": "cpe:2.3:a:apache:http_server:2.4.49:*:*:*:*:*:*:*",
                    "vendor": "apache",
                    "product": "http_server",
                    "version": "2.4.49",
                    "display_name": "Apache HTTP Server",
                    "category": "web_server",
                    "title": "Apache HTTP Server",
                    "versions_json": ["2.4.49"],
                }
            ],
        )
        await db.commit()
        assert await suggest_software(db, query="ap") == []
        items = await suggest_software(db, query="apa")
        assert items
        assert items[0]["product"] == "http_server"
        assert "2.4.49" in items[0]["versions"]
    finally:
        await db.close()


def test_catalog_suggest_endpoint(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "cpe_api.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    import asyncio
    from database import get_db, init_db
    from main import app

    async def _seed():
        await init_db()
        db = await get_db()
        try:
            await upsert_catalog_rows(
                db,
                [
                    {
                        "cpe_uri": "cpe:2.3:a:nginx:nginx:1.20.0:*:*:*:*:*:*:*",
                        "vendor": "nginx",
                        "product": "nginx",
                        "version": "1.20.0",
                        "display_name": "nginx",
                        "category": "web_server",
                        "title": "nginx",
                        "versions_json": ["1.20.0"],
                    }
                ],
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(_seed())
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        short = client.get("/api/stack/catalog/suggest?q=ng")
        assert short.status_code == 200
        assert short.json()["items"] == []
        ok = client.get("/api/stack/catalog/suggest?q=ngi")
        assert ok.status_code == 200
        body = ok.json()
        assert body["ok"] is True
        assert any(i["product"] == "nginx" for i in body["items"])


def test_sync_uses_resilient_get(monkeypatch, tmp_path):
    db_path = tmp_path / "cpe_sync.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("CPE_CATALOG_MAX_PAGES", "1")
    monkeypatch.setenv("CPE_CATALOG_PAGE_SIZE", "50")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)

    class _Resp:
        def json(self):
            return {
                "resultsPerPage": 1,
                "startIndex": 0,
                "totalResults": 1,
                "products": [
                    {
                        "cpe": {
                            "cpeName": "cpe:2.3:a:postgresql:postgresql:14.0:*:*:*:*:*:*:*",
                            "titles": [{"title": "PostgreSQL", "lang": "en"}],
                        }
                    }
                ],
            }

    async def _fake_get(source, url, **kwargs):
        assert source == "nvd"
        return _Resp()

    monkeypatch.setattr("feeds.cpe_catalog.resilient_get", _fake_get)

    import asyncio
    from database import get_db, init_db
    from feeds.cpe_catalog import sync_cpe_catalog

    async def _run():
        await init_db()
        db = await get_db()
        try:
            stats = await sync_cpe_catalog(db)
            assert stats["upserted"] == 1
            items = await suggest_software(db, query="post")
            assert items and items[0]["category"] == "database"
        finally:
            await db.close()

    asyncio.run(_run())
