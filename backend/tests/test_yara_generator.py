"""Tests for YARA template generation from OTX hashes."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import get_db, init_db, store_otx_pulse_iocs
from detection.yara_generator import build_yara_rules_from_hashes, find_yara_rules_for_cve


def test_build_yara_sha256():
    h = "a" * 64
    rules = build_yara_rules_from_hashes("CVE-2024-1234", [h], pulse_name="Test Pulse")
    assert len(rules) == 1
    assert rules[0]["hash_type"] == "sha256"
    assert h in rules[0]["yara"]
    assert 'import "hash"' in rules[0]["yara"]
    assert "CVE-2024-1234" in rules[0]["yara"]


def test_build_yara_skips_invalid():
    rules = build_yara_rules_from_hashes("CVE-2024-1", ["not-a-hash", ""])
    assert rules == []


def test_find_yara_rules_for_cve_query_runs(tmp_path, monkeypatch):
    """DISTINCT + ORDER BY must stay Postgres-safe (asyncpg rejects an ORDER BY
    column absent from the DISTINCT select list; SQLite silently allows it)."""

    async def run() -> list[dict]:
        db_path = str(tmp_path / "yara.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await get_db()
        try:
            cve_id = "CVE-2024-5001"
            pulse_id = "pulse-yara-test"
            await db.execute(
                "INSERT INTO otx_cve_pulses (cve_id, pulse_id, pulse_name, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (cve_id, pulse_id, "Test Pulse", "2024-01-01 00:00:00"),
            )
            await store_otx_pulse_iocs(
                db,
                pulse_id,
                [{"ioc_type": "sha256", "ioc_value": "a" * 64, "description": ""}],
            )
            await db.commit()
        finally:
            await db.close()

        db = await get_db()
        try:
            return await find_yara_rules_for_cve(db, cve_id)
        finally:
            await db.close()

    rules = asyncio.run(run())
    assert len(rules) == 1
    assert rules[0]["hash"] == "a" * 64
