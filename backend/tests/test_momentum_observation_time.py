"""CORR-PR-7: momentum OTX signal uses pulse observation time, not fetched_at."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from scoring.risk import calculate_momentum
from tests.conftest import run_db_test


def test_momentum_ignores_recent_fetch_on_old_pulse_created_date(tmp_path, monkeypatch):
    db_path = str(tmp_path / "momentum_obs.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)

    cve_id = "CVE-2026-MOM-001"
    now = datetime.now(timezone.utc)
    old_created = (now - timedelta(days=120)).strftime("%Y-%m-%d")
    recent_fetch = now.strftime("%Y-%m-%d %H:%M:%S")

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                (cve_id, "test", "2024-01-01"),
            )
            await db.execute(
                """
                INSERT INTO otx_cve_pulses (
                    cve_id, pulse_id, pulse_name, author, created_date, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cve_id, "pulse-old", "Old campaign", "author", old_created, recent_fetch),
            )
            await db.commit()

            result = await calculate_momentum(cve_id, db)
            otx_signals = [s for s in result["momentum_signals"] if s["type"] == "otx_pulse"]
            assert otx_signals == []
        finally:
            await db.close()

    run_db_test(_run())


def test_momentum_detects_recent_pulse_created_date(tmp_path, monkeypatch):
    db_path = str(tmp_path / "momentum_recent.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)

    cve_id = "CVE-2026-MOM-002"
    now = datetime.now(timezone.utc)
    recent_created = (now - timedelta(hours=6)).isoformat()
    recent_fetch = now.strftime("%Y-%m-%d %H:%M:%S")

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                (cve_id, "test", "2024-01-01"),
            )
            await db.execute(
                """
                INSERT INTO otx_cve_pulses (
                    cve_id, pulse_id, pulse_name, author, created_date, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cve_id, "pulse-new", "New campaign", "author", recent_created, recent_fetch),
            )
            await db.commit()

            result = await calculate_momentum(cve_id, db)
            otx_signals = [s for s in result["momentum_signals"] if s["type"] == "otx_pulse"]
            assert len(otx_signals) == 1
            assert otx_signals[0]["contribution"] == 0.50
        finally:
            await db.close()

    run_db_test(_run())
