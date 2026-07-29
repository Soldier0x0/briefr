"""Tests for efficiency_audit.build_efficiency_report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from tests.conftest import run_db_test


def test_efficiency_report_includes_subsystems_and_recommendations(tmp_path, monkeypatch):
    db_path = tmp_path / "efficiency.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    async def _run():
        from efficiency_audit import build_efficiency_report

        await init_db()
        db = await get_db()
        try:
            report = await build_efficiency_report(db, db_path=str(db_path))
            assert "subsystems" in report
            assert any(s["id"] == "api_call_events" for s in report["subsystems"])
            assert isinstance(report["recommendations"], list)
            assert report["host_profile"]["memory_total_bytes"] > 0
        finally:
            await db.close()

    run_db_test(_run())
