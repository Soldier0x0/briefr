"""EPSS change history must not record sub-display-threshold noise."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import (
    _epss_scores_differ,
    get_recent_cve_changes,
    init_db,
    update_epss_scores,
)


def test_epss_scores_differ_uses_display_precision():
    assert not _epss_scores_differ(0.0001, 0.0002)
    assert not _epss_scores_differ(None, 0.00004)
    assert not _epss_scores_differ(0.0, None)
    assert _epss_scores_differ(0.001, 0.002)
    assert _epss_scores_differ(None, 0.05)


def test_update_epss_scores_skips_display_identical_changes(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "epss_noise.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)

    asyncio.run(init_db())

    async def run() -> None:
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, epss_score, severity)
                VALUES ('CVE-2026-9732', 'test', 0.0001, 'HIGH')
                """
            )
            await db.commit()
            await update_epss_scores(db, {"CVE-2026-9732": 0.0002})
            await db.commit()
            noise = await get_recent_cve_changes(db, field_name="epss_score", limit=10)
            assert noise == []

            await update_epss_scores(db, {"CVE-2026-9732": 0.002})
            await db.commit()
            real = await get_recent_cve_changes(db, field_name="epss_score", limit=10)
            assert len(real) == 1
            assert real[0]["cve_id"] == "CVE-2026-9732"
            assert real[0]["severity"] == "HIGH"
        finally:
            await db.close()

    asyncio.run(run())
