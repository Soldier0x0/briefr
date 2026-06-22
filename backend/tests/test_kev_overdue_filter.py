"""KEV overdue quick filter on CVE list."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db


def test_kev_overdue_only_filter(tmp_path, monkeypatch):
    db_path = tmp_path / "kev_overdue.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, is_kev, published)
                VALUES ('CVE-2024-9101', 'Overdue KEV', 'HIGH', 1, '2024-01-01T00:00:00')
                """
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, is_kev, published)
                VALUES ('CVE-2024-9102', 'Future due KEV', 'HIGH', 1, '2024-01-01T00:00:00')
                """
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, is_kev, published)
                VALUES ('CVE-2024-9103', 'Not KEV', 'LOW', 0, '2024-01-01T00:00:00')
                """
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (
                    cve_id, product, short_description, required_action, due_date
                ) VALUES (
                    'CVE-2024-9101', 'Prod', 'Short', 'Patch', '2020-01-01'
                )
                """
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (
                    cve_id, product, short_description, required_action, due_date
                ) VALUES (
                    'CVE-2024-9102', 'Prod', 'Short', 'Patch', '2099-06-15'
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
        body = client.get("/api/cves?kev_overdue_only=true&limit=50").json()
        ids = {row["cve_id"] for row in body["data"]}
        assert ids == {"CVE-2024-9101"}
