"""Tests for efficiency_audit.build_efficiency_report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from efficiency_audit import _table_bytes
from tests.conftest import run_db_test


def test_table_bytes_matches_by_table_name_with_schema():
    sizes = [
        {"schema": "app", "table": "api_call_events", "size_bytes": 4096},
        {"schema": "intel", "table": "cves", "size_bytes": 8192},
        {"schema": "public", "table": "api_call_events", "size_bytes": 99},
    ]
    assert _table_bytes(sizes, "api_call_events") == 4096
    assert _table_bytes(sizes, "cves") == 8192
    assert _table_bytes(sizes, "missing") == 0
    assert _table_bytes(sizes, "api_call_events", schema="public") == 99


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
            for rec in report["recommendations"]:
                assert "basis" in rec
                assert rec["confidence"] in ("low", "medium", "high")
                assert "impact_risk" in rec
                assert "reversible" in rec
                assert rec["auto_scalable"] is False
        finally:
            await db.close()

    run_db_test(_run())


def test_efficiency_report_does_not_acquire_nested_db(tmp_path, monkeypatch):
    db_path = tmp_path / "efficiency-nested.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    async def empty_sizes(db):
        return []

    async def boom():
        raise AssertionError("nested get_db")

    monkeypatch.setattr("efficiency_audit.fetch_table_sizes", empty_sizes)
    monkeypatch.setattr("efficiency_audit.get_db", boom, raising=False)

    async def _run():
        from efficiency_audit import build_efficiency_report
        from database import get_db, init_db

        await init_db()
        db = await get_db()
        try:
            report = await build_efficiency_report(db, db_path=str(db_path))
            assert "subsystems" in report
        finally:
            await db.close()

    run_db_test(_run())
