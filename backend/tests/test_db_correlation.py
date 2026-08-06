"""Postgres-native correlation module (Post-B Phase 1)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

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


def test_pulse_ioc_lock_pool_scoped_per_event_loop():
    """Each live loop must consistently get the same lock for a pulse_id.

    Regression: the module-level pool was created once at import, so a call
    from a loop other than the one that first awaited a lock raised "bound to
    a different event loop". The pool must be stable per loop and isolated
    across concurrently-running loops."""

    def grab_locks():
        first = correlation_mod._pulse_ioc_lock("pulse-a")
        second = correlation_mod._pulse_ioc_lock("pulse-a")
        return first, second

    async def loop_body(results, key):
        results[key] = grab_locks()

    async def run_pair():
        results = {}
        await asyncio.gather(loop_body(results, "a"), loop_body(results, "b"))
        return results

    results_a = asyncio.run(run_pair())
    results_b = asyncio.run(run_pair())

    for results in (results_a, results_b):
        assert results["a"][0] is results["a"][1], "same pulse reuses same lock"
        assert results["a"][0] is results["b"][0], "concurrent tasks share the loop pool"

    # results_a and results_b ran in separate event loops, so the "pulse-a"
    # lock from each must be a distinct object (per-loop pool isolation).
    assert results_a["a"][0] is not results_b["a"][0], "loops must not share a pool"


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
                {
                    "ioc_type": "domain",
                    "ioc_value": "evil.example",
                    "description": "bad domain",
                    "observed_at": "2024-06-15T12:00:00Z",
                },
                {"ioc_type": "IPv4", "ioc_value": "1.2.3.4", "description": "bad ip"},
            ]
            await replace_otx_pulse_iocs(db, PULSE_ID, iocs)
            await db.commit()

            rows = await read_otx_pulse_iocs(db, PULSE_ID, max_age_hours=6)
            assert rows is not None
            values = {(r["ioc_type"], r["ioc_value"]) for r in rows}
            assert ("DOMAIN", "evil.example") in values
            assert ("IP", "1.2.3.4") in values
            by_value = {r["ioc_value"]: r for r in rows}
            assert by_value["evil.example"]["observed_at"] == "2024-06-15T12:00:00Z"
            assert by_value["1.2.3.4"]["observed_at"] is None

            await replace_otx_pulse_iocs(
                db,
                PULSE_ID,
                [{"ioc_type": "domain", "ioc_value": "evil.example", "description": ""}],
            )
            await db.commit()
            rows2 = await read_otx_pulse_iocs(db, PULSE_ID, max_age_hours=6)
            assert rows2 is not None
            assert len(rows2) == 1
            assert rows2[0]["observed_at"] is None
        finally:
            await db.close()

    run_db_test(_run())


def test_otx_pulse_iocs_persists_raw_and_host_columns(tmp_path, monkeypatch):
    """Phase A: replace_otx_pulse_iocs must persist raw_ioc (verbatim raw
    value) and host_ioc (normalized host) so four-level IOC preservation is
    durable. Read directly from the table — the read API is write-path-only
    for Phase A."""
    placeholder = "$1" if is_postgres() else "?"
    if not is_postgres():
        db_path = tmp_path / "correlation_otx_iocs_raw.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await replace_otx_pulse_iocs(
                db,
                PULSE_ID,
                [
                    {
                        "ioc_type": "URL",
                        "ioc_value": "https://drive.google.com/uc?id=abc123",
                        "description": "phish",
                    },
                    {"ioc_type": "domain", "ioc_value": "EVIL.EXAMPLE.COM", "description": ""},
                    {"ioc_type": "IPv4", "ioc_value": "1.2.3.4", "description": ""},
                ],
            )
            await db.commit()
            rows = await db.execute_fetchall(
                f"SELECT ioc_type, ioc_value, raw_ioc, host_ioc "
                f"FROM otx_pulse_iocs WHERE pulse_id = {placeholder}",
                (PULSE_ID,),
            )
            by_value = {r["ioc_value"]: r for r in rows}
            assert by_value["https://drive.google.com/uc?id=abc123"]["raw_ioc"] == (
                "https://drive.google.com/uc?id=abc123"
            )
            assert by_value["https://drive.google.com/uc?id=abc123"]["host_ioc"] == (
                "drive.google.com"
            )
            assert by_value["evil.example.com"]["raw_ioc"] == "EVIL.EXAMPLE.COM"
            assert by_value["evil.example.com"]["host_ioc"] == "evil.example.com"
            assert by_value["1.2.3.4"]["raw_ioc"] == "1.2.3.4"
            assert by_value["1.2.3.4"]["host_ioc"] == ""

            await replace_otx_pulse_iocs(
                db,
                PULSE_ID,
                [{"ioc_type": "domain", "ioc_value": "EVIL.EXAMPLE.COM", "description": "x"}],
            )
            await db.commit()
            rows2 = await db.execute_fetchall(
                f"SELECT ioc_type, ioc_value, raw_ioc, host_ioc "
                f"FROM otx_pulse_iocs WHERE pulse_id = {placeholder}",
                (PULSE_ID,),
            )
            assert len(rows2) == 1
            assert rows2[0]["host_ioc"] == "evil.example.com"
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
