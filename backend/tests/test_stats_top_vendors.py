"""Tests for GET /api/stats/top-vendors KEV vendor aggregates."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db


def test_stats_top_vendors_groups_kev_catalog(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "top_vendors.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)
    monkeypatch.setattr(settings, "briefr_require_postgres", False)

    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await db.executemany(
                """
                INSERT INTO kev_deadlines (
                    cve_id, product, short_description, required_action, due_date,
                    vendor_project
                ) VALUES (?, ?, 'desc', 'patch', '2099-01-01', ?)
                """,
                [
                    ("CVE-2024-1001", "Chromium", "Google"),
                    ("CVE-2024-1002", "Chrome", "Google"),
                    ("CVE-2024-1003", "NetScaler", "Citrix"),
                    ("CVE-2024-1004", "Unknown product", ""),
                ],
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        body = client.get("/api/stats/top-vendors?limit=5").json()

    assert body["total_kev"] == 4
    vendors = {row["vendor"]: row["kev_count"] for row in body["data"]}
    assert vendors["Google"] == 2
    assert vendors["Citrix"] == 1
    assert vendors["Unknown product"] == 1
