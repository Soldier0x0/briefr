"""Postgres-safe SQL shapes for correlation nightly queries."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from correlation.campaigns import build_campaigns_from_pulses
from correlation.engine import prefetch_pulse_iocs_for_nightly
from database import init_db, replace_otx_cve_pulses
import database


def test_prefetch_pulse_iocs_query_runs(tmp_path, monkeypatch):
    """GROUP BY prefetch query must not use DISTINCT + ORDER BY on missing columns."""

    async def run():
        db_path = str(tmp_path / "prefetch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            pulses = [
                {
                    "pulse_id": "pulse-1",
                    "pulse_name": "Test pulse",
                    "author": "tester",
                    "created_date": "2024-01-01",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses)
            await db.commit()
        finally:
            await db.close()

        async def _noop_fetch(_pulse_id: str):
            return []

        monkeypatch.setattr("feeds.otx.fetch_pulse_iocs", _noop_fetch)
        db = await database.get_db()
        try:
            count = await prefetch_pulse_iocs_for_nightly("fake-key", max_pulses=5, db=db)
            assert count == 0
        finally:
            await db.close()

    run_db_test(run())


def test_build_campaign_members_query_runs(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "campaign.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published)
                VALUES ('CVE-2024-1001', 'A', '2024-01-01'), ('CVE-2024-1002', 'B', '2024-01-02')
                """
            )
            pulses = [
                {
                    "pulse_id": "pulse-1",
                    "pulse_name": "Campaign",
                    "author": "tester",
                    "created_date": "2024-01-01",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses)
            await replace_otx_cve_pulses(db, "CVE-2024-1002", pulses)
            await db.commit()
            stats = await build_campaigns_from_pulses(db)
            assert stats["campaigns"] == 1
            assert stats["members"] == 2
        finally:
            await db.close()

    run_db_test(run())


def test_nightly_correlation_recovers_after_temporal_failure(tmp_path, monkeypatch):
    from correlation.engine import run_nightly_correlation

    async def run():
        db_path = str(tmp_path / "nightly-recover.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            calls = {"temporal": 0}

            async def boom_temporal(_db):
                calls["temporal"] += 1
                raise RuntimeError("simulated temporal SQL failure")

            monkeypatch.setattr(
                "correlation.engine.find_temporal_anomalies",
                boom_temporal,
            )
            stats = await run_nightly_correlation(db)
            assert calls["temporal"] == 1
            assert stats["pruned_members"] == 0
            assert stats["campaigns_built"] == 0
        finally:
            await db.close()

    run_db_test(run())
