"""Postgres-native metadata module (Post-B Phase 1)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.metadata as metadata_mod
from db.config import is_postgres
from db.metadata import (
    _parse_json_list,
    get_mitre_technique_count,
    get_techniques_for_cve,
    get_timeline_activity_summary,
    replace_mitre_groups,
    replace_mitre_techniques,
    upsert_cve_technique_pairs,
    upsert_group_technique_pairs,
)
from database import get_db, init_db
from tests.conftest import run_db_test

CVE_A = "CVE-2024-3001"
CVE_B = "CVE-2024-3002"


def test_metadata_sql_uses_native_placeholders():
    assert "$1" in metadata_mod._TIMELINE_ACTIVITY_PG
    assert "published::date" in metadata_mod._TIMELINE_ACTIVITY_PG
    assert "?" in metadata_mod._TIMELINE_ACTIVITY_SQLITE
    assert "ON CONFLICT (cve_id, technique_id) DO NOTHING" in metadata_mod._INSERT_CVE_TECHNIQUE_PAIR_PG
    assert "INSERT OR IGNORE" in metadata_mod._INSERT_CVE_TECHNIQUE_PAIR_SQLITE
    assert "$6" in metadata_mod._REPLACE_MITRE_GROUPS_PG
    assert "ON CONFLICT (group_id, technique_id) DO NOTHING" in metadata_mod._INSERT_GROUP_TECHNIQUE_PAIR_PG


def test_parse_json_list():
    assert _parse_json_list(None) == []
    assert _parse_json_list("") == []
    assert _parse_json_list('["a", "b"]') == ["a", "b"]
    assert _parse_json_list("not-json") == []
    assert _parse_json_list('{"x": 1}') == []


def test_replace_mitre_techniques_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "metadata_mitre.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await replace_mitre_techniques(
                db,
                [
                    {
                        "technique_id": "T1059",
                        "name": "Command and Scripting Interpreter",
                        "description": "desc",
                        "tactic": "Execution",
                        "url": "https://attack.mitre.org/techniques/T1059/",
                        "platforms": ["Linux"],
                        "detection": "monitor scripts",
                    }
                ],
            )
            await upsert_cve_technique_pairs(db, [(CVE_A, "T1059")])
            await db.commit()

            assert await get_mitre_technique_count(db) == 1
            techs = await get_techniques_for_cve(db, CVE_A)
            assert len(techs) == 1
            assert techs[0]["id"] == "T1059"
            assert techs[0]["name"] == "Command and Scripting Interpreter"
        finally:
            await db.close()

    run_db_test(_run())


def test_get_timeline_activity_summary(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "metadata_timeline.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            recent = (date.today() - timedelta(days=2)).isoformat()
            old = (date.today() - timedelta(days=120)).isoformat()
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

            summary = await get_timeline_activity_summary(db, days=90)
            assert summary["window_days"] == 90
            assert summary["total_cves"] >= 1
            assert summary["days_with_data"] >= 1
        finally:
            await db.close()

    run_db_test(_run())


def test_replace_mitre_groups_and_pairs(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "metadata_groups.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            count = await replace_mitre_groups(
                db,
                [
                    {
                        "group_id": "G0001",
                        "name": "Test Group",
                        "aliases": ["alias-a"],
                        "description": "group desc",
                        "sectors": ["finance"],
                        "url": "https://example.test/g0001",
                    }
                ],
            )
            assert count == 1
            assert await upsert_group_technique_pairs(db, [("G0001", "T1059")]) == 1
            assert await upsert_group_technique_pairs(db, [("G0001", "T1059")]) == 1
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT group_id, technique_id FROM group_technique_map"
            )
            assert len(rows) == 1
            assert rows[0]["group_id"] == "G0001"
        finally:
            await db.close()

    run_db_test(_run())
