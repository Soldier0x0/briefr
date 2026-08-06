"""Postgres-native init module (Post-B Phase 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.init as init_mod
from db.config import is_postgres
from database import get_db, init_db
from tests.conftest import run_db_test


def test_init_exports_dialect_neutral_fixup_sql():
    assert "epss_score = NULL" in init_mod._NORMALIZE_EPSS_SCORES_SQL
    assert "?" not in init_mod._NORMALIZE_EPSS_SCORES_SQL
    assert "$1" not in init_mod._NORMALIZE_EPSS_SCORES_SQL
    assert "idx_cves_has_poc" in init_mod._CREATE_IDX_CVES_HAS_POC_SQL
    assert "idx_cves_modified" in init_mod._CREATE_IDX_CVES_MODIFIED_SQL
    assert "alembic_version" in init_mod._ALEMBIC_VERSION_SQL


def test_init_db_creates_core_tables(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "init_bootstrap.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            tables = await db.execute_fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                if not is_postgres()
                else """
                SELECT tablename AS name
                FROM pg_tables
                WHERE schemaname IN ('intel', 'app')
                ORDER BY tablename
                """
            )
            names = {row["name"] for row in tables}
            for required in (
                "cves",
                "sync_state",
                "watchlist",
                "cve_embeddings",
                "correlation_suppressions",
            ):
                assert required in names
        finally:
            await db.close()

    run_db_test(_run())


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "init_idempotent.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        await init_db()
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT COUNT(*) AS n FROM cves"
                if not is_postgres()
                else "SELECT COUNT(*)::int AS n FROM cves"
            )
            assert rows[0]["n"] == 0
        finally:
            await db.close()

    run_db_test(_run())


def test_init_db_creates_threatfox_compat_view(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "init_threatfox_view.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        await init_db()
        db = await get_db()
        try:
            if not is_postgres():
                kinds = await db.execute_fetchall(
                    "SELECT name, type FROM sqlite_master WHERE name = 'threatfox_iocs'"
                )
                assert kinds and kinds[0]["type"] == "view"
            else:
                kinds = await db.execute_fetchall(
                    "SELECT viewname AS name FROM pg_views "
                    "WHERE schemaname = 'app' AND viewname = 'threatfox_iocs'"
                )
                assert kinds
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, malware,
                    threat_type, confidence_level, first_seen
                ) VALUES ('threatfox', 'view-1', 'domain', 'evil.example',
                          'evil.example', 'vidar', 'botnet_cc', 90, '2024-06-01')
                """
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT ioc_id, ioc_type, ioc_value FROM threatfox_iocs"
                if not is_postgres()
                else "SELECT ioc_id, ioc_type, ioc_value FROM app.threatfox_iocs"
            )
            assert [r["ioc_id"] for r in rows] == ["view-1"]
        finally:
            await db.close()

    run_db_test(_run())


def test_normalize_epss_scores_zeros_to_null(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "init_epss.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            insert_sql = (
                "INSERT INTO cves (cve_id, description, epss_score) VALUES ($1, $2, $3)"
                if is_postgres()
                else "INSERT INTO cves (cve_id, description, epss_score) VALUES (?, ?, ?)"
            )
            await db.execute(insert_sql, ("CVE-2024-INIT", "test", 0.0))
            await db.commit()
            await init_mod._normalize_epss_scores(db)
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT epss_score FROM cves WHERE cve_id = ?"
                if not is_postgres()
                else "SELECT epss_score FROM cves WHERE cve_id = $1",
                ("CVE-2024-INIT",),
            )
            assert rows[0]["epss_score"] is None
        finally:
            await db.close()

    run_db_test(_run())
