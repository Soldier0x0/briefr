"""Momentum batch query optimization."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from database import init_db
import database
from scoring.risk import calculate_momentum, calculate_momentum_batch


def test_calculate_momentum_batch_matches_single(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "momentum-batch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published, is_kev)
                VALUES ('CVE-2024-1001', 'Test', '2024-01-01', 0),
                       ('CVE-2024-1002', 'Test 2', '2024-01-02', 0)
                """
            )
            await db.execute(
                """
                INSERT INTO epss_history (cve_id, score, recorded_date)
                VALUES ('CVE-2024-1001', 0.10, '2024-01-01'),
                       ('CVE-2024-1001', 0.25, '2024-01-14')
                """
            )
            await db.commit()

            single = await calculate_momentum("CVE-2024-1001", db)
            batch = await calculate_momentum_batch(
                ["CVE-2024-1001", "CVE-2024-1002"], db
            )
            assert batch["CVE-2024-1001"]["momentum_score"] == single["momentum_score"]
            assert batch["CVE-2024-1001"]["momentum_signals"] == single["momentum_signals"]
            assert "CVE-2024-1002" in batch
        finally:
            await db.close()

    run_db_test(run())


def test_calculate_momentum_batch_empty():
    async def run():
        from unittest.mock import AsyncMock

        db = AsyncMock()
        result = await calculate_momentum_batch([], db)
        assert result == {}
        db.execute_fetchall.assert_not_called()

    run_db_test(run())
