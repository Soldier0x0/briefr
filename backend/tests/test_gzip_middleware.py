"""I2: GZipMiddleware compresses large JSON API responses."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db


def _force_sqlite(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "gzip.db"
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


def test_api_cves_supports_gzip_encoding(tmp_path, monkeypatch):
    db_path = _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            for i in range(20):
                cve_id = f"CVE-2026-GZIP-{i:04d}"
                await db.execute(
                    """
                    INSERT INTO cves (
                        cve_id, description, severity, published, modified, is_kev, has_poc
                    ) VALUES (
                        ?, ?, 'HIGH', datetime('now'), datetime('now'), 0, 0
                    )
                    """,
                    (
                        cve_id,
                        "Long enough description payload to ensure the JSON list response "
                        "exceeds the GZipMiddleware minimum size threshold for compression.",
                    ),
                )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves?limit=20", headers={"Accept-Encoding": "gzip"})

    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
    body = res.json()
    assert len(body.get("data", [])) == 20
