"""Additive kev_due_date on CVE list/export responses."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db

from database import init_db


def test_cve_list_includes_kev_due_date(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "kev_due.db"
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
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, is_kev, published)
                VALUES ('CVE-2024-9001', 'Test KEV', 'HIGH', 1, '2024-01-01T00:00:00')
                """
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, is_kev, published)
                VALUES ('CVE-2024-9002', 'No KEV', 'LOW', 0, '2024-01-01T00:00:00')
                """
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (
                    cve_id, product, short_description, required_action, due_date,
                    known_ransomware
                ) VALUES (
                    'CVE-2024-9001', 'Test Product', 'Short', 'Patch', '2099-06-15',
                    'Known'
                )
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        body = client.get("/api/cves?limit=10").json()
        by_id = {row["cve_id"]: row for row in body["data"]}
        assert by_id["CVE-2024-9001"]["kev_due_date"] == "2099-06-15"
        assert by_id["CVE-2024-9001"]["kev_ransomware_use"] is True
        assert by_id["CVE-2024-9002"]["kev_due_date"] is None
        assert by_id["CVE-2024-9002"]["kev_ransomware_use"] is False

        export = client.get("/api/cves/export?limit=10").json()
        export_by_id = {row["cve_id"]: row for row in export["data"]}
        assert export_by_id["CVE-2024-9001"]["kev_due_date"] == "2099-06-15"
        assert export_by_id["CVE-2024-9001"]["kev_ransomware_use"] is True
