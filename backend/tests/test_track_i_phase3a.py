"""Track I Phase 3a: keyset feed cursor and drawer aggregate bundle."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db
import pytest
from fastapi.testclient import TestClient

from database import init_db
from routers.cves import _decode_feed_cursor, _encode_feed_cursor


def _force_sqlite(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "phase3a.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)
    monkeypatch.setattr(settings, "briefr_require_postgres", False)

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)
    return db_path


def test_feed_cursor_roundtrip():
    cursor = _encode_feed_cursor("2026-01-15T12:00:00Z", "CVE-2026-0002")
    published, cve_id = _decode_feed_cursor(cursor)
    assert published == "2026-01-15T12:00:00Z"
    assert cve_id == "CVE-2026-0002"


def test_list_cves_keyset_cursor(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:

        db = await get_db()
        try:
            for idx, cve_id in enumerate(("CVE-2026-0003", "CVE-2026-0002", "CVE-2026-0001")):
                await db.execute(
                    """
                    INSERT INTO cves (
                        cve_id, description, severity, published, modified, is_kev, has_poc
                    ) VALUES (?, ?, 'HIGH', ?, ?, 0, 0)
                    """,
                    (
                        cve_id,
                        f"test {cve_id}",
                        f"2026-01-{10 + idx:02d}T12:00:00Z",
                        f"2026-01-{10 + idx:02d}T12:00:00Z",
                    ),
                )
            await db.commit()
        finally:
            await db.close()

    from main import app

    with TestClient(app) as client:
        asyncio.run(seed())
        first = client.get("/api/cves", params={"limit": 1, "pagination": "keyset"})
        assert first.status_code == 200
        body = first.json()
        assert body["pagination"] == "keyset"
        assert len(body["data"]) == 1
        assert body["data"][0]["cve_id"] == "CVE-2026-0001"
        assert body.get("next_cursor")

        second = client.get(
            "/api/cves",
            params={"limit": 1, "pagination": "keyset", "cursor": body["next_cursor"]},
        )
        assert second.status_code == 200
        ids = [row["cve_id"] for row in second.json()["data"]]
        assert ids == ["CVE-2026-0002"]


def test_drawer_bundle_endpoint(tmp_path, monkeypatch):
    db_path = _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (
                    cve_id, description, severity, published, modified, is_kev, has_poc
                ) VALUES ('CVE-2026-DRAW-1', 'drawer bundle test', 'HIGH',
                          '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 0, 0)
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves/CVE-2026-DRAW-1/drawer")
        assert res.status_code == 200
        body = res.json()
        assert body["cve_id"] == "CVE-2026-DRAW-1"
        assert "sentences" in body
        assert "epss_history" in body
        assert "related" in body
        assert "correlation" in body
        assert "momentum" in body


def test_default_response_not_orjson():
    """Guard: ORJSONResponse is deprecated in FastAPI 0.131+; use Pydantic JSON bytes."""
    from fastapi.responses import ORJSONResponse
    from main import app

    assert app.router.default_response_class is not ORJSONResponse
