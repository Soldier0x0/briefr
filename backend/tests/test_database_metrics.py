"""Tests for db.database_metrics projection and fetch."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database_metrics import fetch_database_metrics, project_disk_usage
from database import get_db, init_db
from tests.conftest import run_db_test


def test_project_disk_usage_linear_growth():
    samples = [
        {"ts": "2026-07-01T00:00:00+00:00", "db_bytes": 1_000_000_000},
        {"ts": "2026-07-11T00:00:00+00:00", "db_bytes": 1_100_000_000},
    ]
    result = project_disk_usage(samples, horizon_days=30, partition_total_bytes=10_000_000_000)
    assert result["daily_growth_bytes"] == 10_000_000
    assert result["projected_bytes"] == 1_100_000_000 + 10_000_000 * 30
    assert result["severity"] == "ok"
    assert result["pct_of_partition"] is not None


def test_project_disk_usage_warns_near_partition_ceiling():
    samples = [
        {"ts": "2026-07-01T00:00:00+00:00", "db_bytes": 6_000_000_000},
        {"ts": "2026-07-11T00:00:00+00:00", "db_bytes": 7_000_000_000},
    ]
    result = project_disk_usage(samples, horizon_days=30, partition_total_bytes=10_000_000_000)
    assert result["severity"] in ("warn", "critical")


def test_fetch_database_metrics_includes_integrity(tmp_path, monkeypatch):
    db_path = tmp_path / "db_metrics.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            metrics = await fetch_database_metrics(db, db_path=str(db_path))
            assert "db_size_bytes" in metrics
            assert "integrity_ok" in metrics
            assert "integrity_checked_at" in metrics
            assert "disk_projection" in metrics
            assert metrics["table_count"] >= 1
        finally:
            await db.close()

    run_db_test(_run())
