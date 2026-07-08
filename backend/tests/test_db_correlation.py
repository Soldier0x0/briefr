"""Postgres-native correlation module (Post-B Phase 1)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.correlation as correlation_mod
from db.config import is_postgres
from db.correlation import (
    delete_correlation_suppression,
    get_recent_cve_ids_for_otx,
    insert_correlation_suppression,
    list_correlation_suppressions,
    read_otx_cve_pulses,
    read_otx_pulse_iocs,
    replace_otx_cve_pulses,
    replace_otx_pulse_iocs,
)
from database import get_db, init_db
from tests.conftest import run_db_test

CVE_A = "CVE-2024-4001"
CVE_B = "CVE-2024-4002"
PULSE_ID = "pulse-test-001"


def test_correlation_sql_uses_native_placeholders():
    assert "$1" in correlation_mod._READ_OTX_CVE_PULSES_PG
    assert "$2" in correlation_mod._READ_OTX_CVE_PULSES_PG
    assert "?" in correlation_mod._READ_OTX_CVE_PULSES_SQLITE
    assert "ON CONFLICT(pulse_id, ioc_type, ioc_value)" in correlation_mod._UPSERT_OTX_PULSE_IOCS_PG
    assert "$6" in correlation_mod._UPSERT_CORRELATION_SUPPRESSION_PG
    assert "ON CONFLICT(cve_id, scope, scope_key)" in correlation_mod._UPSERT_CORRELATION_SUPPRESSION_PG


def test_otx_cve_pulses_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "correlation_otx_pulses.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            pulses = [
                {
                    "pulse_id": PULSE_ID,
                    "pulse_name": "Test Pulse",
                    "author": "author",
                    "created_date": "2024-06-01",
                    "adversary": "actor",
                    "malware_families": ["mal"],
                    "tags": ["tag1"],
                    "targeted_countries": ["US"],
                    "ioc_count": 2,
                }
            ]
            await replace_otx_cve_pulses(db, CVE_A, pulses)
            await db.commit()

            rows = await read_otx_cve_pulses(db, CVE_A, max_age_hours=6)
            assert rows is not None
            assert len(rows) == 1
            assert rows[0]["pulse_id"] == PULSE_ID
            assert rows[0]["tags"] == ["tag1"]
        finally:
            await db.close()

    run_db_test(_run())


def test_otx_pulse_iocs_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "correlation_otx_iocs.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            iocs = [
                {"ioc_type": "domain", "ioc_value": "evil.example", "description": "bad domain"},
                {"ioc_type": "IPv4", "ioc_value": "1.2.3.4", "description": "bad ip"},
            ]
            await replace_otx_pulse_iocs(db, PULSE_ID, iocs)
            await db.commit()

            rows = await read_otx_pulse_iocs(db, PULSE_ID, max_age_hours=6)
            assert rows is not None
            values = {(r["ioc_type"], r["ioc_value"]) for r in rows}
            assert ("DOMAIN", "evil.example") in values
            assert ("IP", "1.2.3.4") in values

            await replace_otx_pulse_iocs(
                db,
                PULSE_ID,
                [{"ioc_type": "domain", "ioc_value": "evil.example", "description": ""}],
            )
            await db.commit()
            rows2 = await read_otx_pulse_iocs(db, PULSE_ID, max_age_hours=6)
            assert rows2 is not None
            assert len(rows2) == 1
        finally:
            await db.close()

    run_db_test(_run())


def test_correlation_suppression_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "correlation_suppress.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            row = await insert_correlation_suppression(
                db,
                CVE_A,
                scope="campaign",
                scope_key="camp-1",
                reason="false positive",
                dismissed_by="analyst",
            )
            await db.commit()
            assert row["cve_id"] == CVE_A
            assert row["scope"] == "campaign"

            listed = await list_correlation_suppressions(db, CVE_A)
            assert len(listed) == 1
            assert listed[0]["scope_key"] == "camp-1"

            deleted = await delete_correlation_suppression(
                db, CVE_A, "campaign", "camp-1"
            )
            await db.commit()
            assert deleted is True
            assert await list_correlation_suppressions(db, CVE_A) == []
        finally:
            await db.close()

    run_db_test(_run())


def test_get_recent_cve_ids_for_otx(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "correlation_recent.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            recent = (date.today() - timedelta(days=2)).isoformat()
            old = (date.today() - timedelta(days=30)).isoformat()
            cve_ph = "$1, $2, $3" if is_postgres() else "?, ?, ?"
            await db.execute(
                f"INSERT INTO cves (cve_id, description, published) VALUES ({cve_ph})",
                (CVE_A, "recent", recent),
            )
            await db.execute(
                f"INSERT INTO cves (cve_id, description, published) VALUES ({cve_ph})",
                (CVE_B, "old", old),
            )
            await db.commit()

            ids = await get_recent_cve_ids_for_otx(db, days=7)
            assert CVE_A in ids
            assert CVE_B not in ids
        finally:
            await db.close()

    run_db_test(_run())
