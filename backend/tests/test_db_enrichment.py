"""Postgres-native enrichment module (Post-B Phase 1)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.enrichment as enrichment_mod
from db.config import is_postgres
from db.enrichment import (
    get_epss_history,
    insert_epss_history_rows,
    mark_cves_as_kev,
    update_epss_scores,
    write_audit_log,
)
from database import get_db, init_db
from tests.conftest import run_db_test

CVE_A = "CVE-2024-2001"
CVE_B = "CVE-2024-2002"


def test_enrichment_sql_uses_native_placeholders():
    assert "$1" in enrichment_mod._WRITE_AUDIT_LOG_PG
    assert "$11" in enrichment_mod._UPSERT_KEV_PG
    assert "ON CONFLICT (cve_id, recorded_date)" in enrichment_mod._SNAPSHOT_EPSS_PG
    assert "?" in enrichment_mod._WRITE_AUDIT_LOG_SQLITE
    assert "INSERT OR IGNORE" in enrichment_mod._INSERT_EPSS_HISTORY_SQLITE


def test_write_audit_log_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "enrichment_audit.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await write_audit_log(db, "admin", "test.action", "target-1")
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT actor, action, target FROM audit_log"
            )
            assert len(rows) == 1
            assert rows[0]["actor"] == "admin"
            assert rows[0]["action"] == "test.action"
        finally:
            await db.close()

    run_db_test(_run())


def test_mark_cves_as_kev_transitions(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "enrichment_kev.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            cve_ph = (
                "$1, $2, $3"
                if is_postgres()
                else "?, ?, ?"
            )
            await db.execute(
                f"INSERT INTO cves (cve_id, description, is_kev) VALUES ({cve_ph})",
                (CVE_A, "a", 0),
            )
            await db.execute(
                f"INSERT INTO cves (cve_id, description, is_kev) VALUES ({cve_ph})",
                (CVE_B, "b", 1),
            )
            await db.commit()

            newly = await mark_cves_as_kev(db, [CVE_A, CVE_B])
            await db.commit()
            assert newly == [CVE_A]

            rows = await db.execute_fetchall(
                "SELECT cve_id, is_kev FROM cves ORDER BY cve_id"
            )
            assert rows[0]["is_kev"] == 1
            assert rows[1]["is_kev"] == 1
        finally:
            await db.close()

    run_db_test(_run())


def test_get_epss_history_uses_cutoff(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "enrichment_epss_hist.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            old = (date.today() - timedelta(days=40)).isoformat()
            recent = (date.today() - timedelta(days=2)).isoformat()
            hist_ph = (
                "$1, $2, $3), ($4, $5, $6"
                if is_postgres()
                else "?, ?, ?), (?, ?, ?"
            )
            await db.execute(
                f"INSERT INTO epss_history (cve_id, score, recorded_date) VALUES ({hist_ph})",
                (CVE_A, 0.1, old, CVE_A, 0.2, recent),
            )
            await db.commit()

            history = await get_epss_history(db, CVE_A, days=30)
            assert len(history) == 1
            assert history[0]["score"] == 0.2
        finally:
            await db.close()

    run_db_test(_run())


def test_insert_epss_history_rows_dedupes(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "enrichment_epss_insert.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            row = {"cve_id": CVE_A, "score": 0.42, "date": "2024-06-01"}
            assert await insert_epss_history_rows(db, [row]) >= 1
            await db.commit()
            assert await insert_epss_history_rows(db, [row]) == 0
            await db.commit()
        finally:
            await db.close()

    run_db_test(_run())


def test_update_epss_scores_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "enrichment_epss_update.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            cve_ph = "$1, 'x', 0.01" if is_postgres() else "?, 'x', 0.01"
            await db.execute(
                f"INSERT INTO cves (cve_id, description, epss_score) VALUES ({cve_ph})",
                (CVE_A,),
            )
            await db.commit()

            await update_epss_scores(
                db, {CVE_A: {"score": 0.5, "percentile": 0.9}}
            )
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT epss_score, epss_percentile FROM cves WHERE cve_id = ?"
                if not is_postgres()
                else "SELECT epss_score, epss_percentile FROM cves WHERE cve_id = $1",
                (CVE_A,),
            )
            assert float(rows[0]["epss_score"]) == 0.5
            assert float(rows[0]["epss_percentile"]) == 0.9
        finally:
            await db.close()

    run_db_test(_run())
