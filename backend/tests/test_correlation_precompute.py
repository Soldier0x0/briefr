"""ADR-004 correlation precompute — snapshot store and request-path reads."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation.engine import _compute_correlation_for_cve, get_correlation_for_cve, run_nightly_correlation
from correlation.ioc_graph import count_hub_suppressed_ioc_peers
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
from db.correlation import (
    get_correlation_cve_snapshot,
    list_cve_ids_for_precompute,
    rebuild_ioc_degree,
    upsert_correlation_cve_snapshot,
)
import database
from tests.conftest import run_db_test


async def _seed_precompute_db(db_path: str):
    database.DB_PATH = db_path
    await init_db()
    db = await database.get_db()
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
        VALUES
            ('CVE-2024-1001', 'Alpha', '2024-01-01', 1, 0, 0.8),
            ('CVE-2024-1002', 'Beta', '2024-01-02', 0, 0, 0.2),
            ('CVE-2024-1003', 'Gamma', '2024-01-03', 0, 0, 0.3)
        """
    )
    pulses = [
        {
            "pulse_id": "pulse-shared",
            "pulse_name": "Shared infra",
            "author": "analyst",
            "created_date": "2024-01-10",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses)
    await replace_otx_cve_pulses(db, "CVE-2024-1002", pulses)
    await replace_otx_pulse_iocs(
        db,
        "pulse-shared",
        [{"ioc_type": "domain", "ioc_value": "shared.evil.example", "description": ""}],
    )
    await db.commit()
    return db


def test_correlation_snapshot_round_trip(tmp_path, monkeypatch):
    db_path = str(tmp_path / "corr_precompute.db")
    monkeypatch.setenv("DB_PATH", db_path)

    async def _run():
        db = await _seed_precompute_db(db_path)
        try:
            result = await _compute_correlation_for_cve(db, "CVE-2024-1001")
            await upsert_correlation_cve_snapshot(
                db,
                "CVE-2024-1001",
                result,
                hub_edges_suppressed=2,
            )
            await db.commit()
            row = await get_correlation_cve_snapshot(db, "CVE-2024-1001")
            assert row is not None
            assert row["payload"]["cve_id"] == "CVE-2024-1001"
            assert row["hub_edges_suppressed"] == 2
        finally:
            await db.close()

    run_db_test(_run())


def test_get_correlation_reads_snapshot_when_flag_enabled(tmp_path, monkeypatch):
    db_path = str(tmp_path / "corr_precompute_flag.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("CORRELATION_PRECOMPUTE_ENABLED", "1")

    async def _run():
        db = await _seed_precompute_db(db_path)
        try:
            payload = {
                "cve_id": "CVE-2024-1001",
                "campaigns": [{"campaign_id": "c-test", "members": ["CVE-2024-1001"]}],
                "infrastructure": [],
                "actor": [],
                "temporal": [],
                "boosters": {"kev": [], "exploit": []},
                "computed_at": "2026-01-01T00:00:00+00:00",
                "otx_status": "ok",
                "priority": {"score": 1, "components": []},
                "meta": {"engine_version": "2.0"},
            }
            await upsert_correlation_cve_snapshot(db, "CVE-2024-1001", payload)
            await db.commit()

            result = await get_correlation_for_cve(db, "CVE-2024-1001")
            assert result["meta"]["precompute"] is True
            assert result["campaigns"][0]["campaign_id"] == "c-test"
            assert result.get("error") is None
        finally:
            await db.close()

    run_db_test(_run())


def test_hub_degree_cap_excludes_mega_ioc_edges(tmp_path, monkeypatch):
    db_path = str(tmp_path / "corr_hub_cap.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("CORRELATION_HUB_CVE_PULSE_CAP", "2")

    async def _run():
        db = await _seed_precompute_db(db_path)
        try:
            await db.execute(
                """
                INSERT INTO ioc_degree (ioc_type, ioc_value, cve_count, pulse_count, computed_at)
                VALUES ('DOMAIN', 'shared.evil.example', 99, 99, datetime('now'))
                """
            )
            await db.commit()
            suppressed = await count_hub_suppressed_ioc_peers(db, "CVE-2024-1001")
            assert suppressed >= 1
            result = await _compute_correlation_for_cve(db, "CVE-2024-1001")
            assert result["infrastructure"] == []
            assert result["meta"]["hub_edges_suppressed"] >= 1
        finally:
            await db.close()

    run_db_test(_run())


def test_nightly_precompute_writes_snapshots(tmp_path, monkeypatch):
    db_path = str(tmp_path / "corr_nightly_precompute.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("CORRELATION_PRECOMPUTE_ENABLED", "1")
    monkeypatch.setenv("CORRELATION_PRECOMPUTE_MAX_PER_RUN", "5")

    async def _run():
        db = await _seed_precompute_db(db_path)
        try:
            stats = await run_nightly_correlation(db)
            assert stats.get("precompute_snapshots", 0) >= 1
            snap = await get_correlation_cve_snapshot(db, "CVE-2024-1001")
            assert snap is not None
            assert snap["payload"]["cve_id"] == "CVE-2024-1001"
            ids = await list_cve_ids_for_precompute(db, limit=3)
            assert "CVE-2024-1001" in ids
        finally:
            await db.close()

    run_db_test(_run())


def test_rebuild_ioc_degree_still_works_after_snapshot_table(tmp_path, monkeypatch):
    db_path = str(tmp_path / "corr_ioc_degree.db")
    monkeypatch.setenv("DB_PATH", db_path)

    async def _run():
        db = await _seed_precompute_db(db_path)
        try:
            count = await rebuild_ioc_degree(db)
            assert count >= 1
        finally:
            await db.close()

    run_db_test(_run())
