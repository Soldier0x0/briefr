"""Phase A — four-level IOC preservation on otx_pulse_iocs.

raw_ioc/host_ioc storage (write path), db/init.py DDL parity, and the
migration 037 up/down + host_ioc backfill for legacy rows.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DB_INIT = _BACKEND_DIR / "db" / "init.py"
_VERSIONS_DIR = _BACKEND_DIR / "alembic" / "versions"


def _load_migration(name: str):
    path = _VERSIONS_DIR / f"{name}.py"
    assert path.is_file(), f"missing migration file {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_db_init_sqlite_ddl_has_raw_and_host_columns():
    """The SQLite executescript CREATE TABLE for otx_pulse_iocs must carry
    raw_ioc/host_ioc so fresh SQLite dev/CI DBs match migration 037."""
    source = _DB_INIT.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS otx_pulse_iocs" in source
    assert "raw_ioc TEXT DEFAULT ''" in source
    assert "host_ioc TEXT DEFAULT ''" in source


def test_db_init_pg_bootstrap_has_raw_and_host_alter():
    """The Postgres bootstrap path must add the same columns as migration 037.

    PG schema is applied via Alembic (run_postgres_migrations), with init_db
    dispatching to _init_postgres_schema() when PostgreSQL is active. This
    test targets that dispatch and the migration it runs — a bare text search
    across all of db/init.py would otherwise be satisfied by the SQLite
    migration list alone (CodeRabbit review).
    """
    source = _DB_INIT.read_text(encoding="utf-8")
    pg_bootstrap = source[source.index("async def _init_postgres_schema") :]
    assert "async def _init_postgres_schema" in pg_bootstrap
    assert "_normalize_epss_scores(db)" in pg_bootstrap

    migration = _load_migration("037_otx_pulse_iocs_raw_host")
    import inspect

    upgrade_source = inspect.getsource(migration.upgrade)
    assert "ALTER TABLE intel.otx_pulse_iocs ADD COLUMN IF NOT EXISTS raw_ioc" in (
        upgrade_source
    )
    assert "ALTER TABLE intel.otx_pulse_iocs ADD COLUMN IF NOT EXISTS host_ioc" in (
        upgrade_source
    )


def test_037_migration_revision_and_chain():
    path = _VERSIONS_DIR / "037_otx_pulse_iocs_raw_host.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision = "037_otx_pulse_iocs_raw_host"' in source
    assert 'down_revision = "036_intel_app_schema_split"' in source
    assert "ALTER TABLE intel.otx_pulse_iocs" in source
    assert "raw_ioc" in source
    assert "host_ioc" in source
    assert "DROP COLUMN IF EXISTS host_ioc" in source
    assert "DROP COLUMN IF EXISTS raw_ioc" in source


def test_037_migration_qualifies_intel_schema():
    """036 moved otx_pulse_iocs into the intel schema, and alembic/env.py runs
    without the app pool's search_path — 037 must qualify every reference as
    intel.otx_pulse_iocs or production upgrades from 036 fail with
    'relation \"otx_pulse_iocs\" does not exist' (Codex P1 review)."""
    path = _VERSIONS_DIR / "037_otx_pulse_iocs_raw_host.py"
    source = path.read_text(encoding="utf-8")
    for statement in (
        "ALTER TABLE intel.otx_pulse_iocs ADD COLUMN IF NOT EXISTS raw_ioc",
        "ALTER TABLE intel.otx_pulse_iocs ADD COLUMN IF NOT EXISTS host_ioc",
        "FROM intel.otx_pulse_iocs",
        "UPDATE intel.otx_pulse_iocs SET host_ioc",
        "ALTER TABLE intel.otx_pulse_iocs DROP COLUMN IF EXISTS host_ioc",
        "ALTER TABLE intel.otx_pulse_iocs DROP COLUMN IF EXISTS raw_ioc",
    ):
        assert statement in source, f"missing qualified statement: {statement}"
    unqualified = source.replace("intel.otx_pulse_iocs", "")
    assert "ALTER TABLE otx_pulse_iocs" not in unqualified


def test_037_backfill_helper_derives_host():
    """The migration's frozen host-derivation must mirror read-time URL→domain
    joins (threatfox_corroboration) so legacy rows backfill identically."""
    migration = _load_migration("037_otx_pulse_iocs_raw_host")
    derive = migration._legacy_host
    assert derive("DOMAIN", "EVIL.EXAMPLE.COM") == "evil.example.com"
    assert derive("domain", "sub.example.com.") == "sub.example.com"
    assert derive("URL", "https://drive.google.com/uc?id=abc123") == "drive.google.com"
    assert derive("URL", "https://t.me/still_stellc") == "t.me"
    assert derive("URL", "https://steamcommunity.com/profiles/7656119") == (
        "steamcommunity.com"
    )
    assert derive("IP", "1.2.3.4") == ""
    assert derive("HASH", "a" * 64) == ""


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)
@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)
def test_postgres_schema_and_round_trip_carry_new_columns(tmp_path, monkeypatch):
    """PG-gated: after Alembic head, intel.otx_pulse_iocs has raw_ioc/host_ioc
    and replace_otx_pulse_iocs persists them — the snapshot export (pg_dump of
    the whole intel schema) then carries them automatically."""
    from tests.conftest import run_db_test

    from database import get_db, init_db, replace_otx_pulse_iocs

    async def _run():
        await init_db()
        db = await get_db()
        try:
            cols = await db.execute_fetchall(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'intel' AND table_name = 'otx_pulse_iocs'
                """
            )
            names = {row["column_name"] for row in cols}
            assert "raw_ioc" in names
            assert "host_ioc" in names

            await replace_otx_pulse_iocs(
                db,
                "pulse-a",
                [
                    {
                        "ioc_type": "URL",
                        "ioc_value": "https://t.me/still_stellc",
                        "description": "",
                    },
                    {"ioc_type": "domain", "ioc_value": "EVIL.EXAMPLE.COM", "description": ""},
                ],
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT ioc_type, ioc_value, raw_ioc, host_ioc "
                "FROM otx_pulse_iocs WHERE pulse_id = $1",
                ("pulse-a",),
            )
            by_value = {r["ioc_value"]: r for r in rows}
            assert by_value["https://t.me/still_stellc"]["host_ioc"] == "t.me"
            assert by_value["https://t.me/still_stellc"]["raw_ioc"] == (
                "https://t.me/still_stellc"
            )
            assert by_value["evil.example.com"]["host_ioc"] == "evil.example.com"
        finally:
            await db.close()

    run_db_test(_run())


def test_sqlite_schema_has_raw_and_host_columns(tmp_path, monkeypatch):
    """Functional parity: after init_db() on SQLite the new columns exist with
    the default value, and replace_otx_pulse_iocs round-trips them."""
    from tests.conftest import run_db_test, use_sqlite_backend

    from database import get_db, init_db, replace_otx_pulse_iocs

    use_sqlite_backend(monkeypatch, tmp_path / "phase_a.db")

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await replace_otx_pulse_iocs(
                db,
                "pulse-a",
                [
                    {
                        "ioc_type": "URL",
                        "ioc_value": "https://drive.google.com/uc?id=abc123",
                        "description": "",
                    }
                ],
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT raw_ioc, host_ioc FROM otx_pulse_iocs WHERE pulse_id = ?",
                ("pulse-a",),
            )
            assert rows[0]["raw_ioc"] == "https://drive.google.com/uc?id=abc123"
            assert rows[0]["host_ioc"] == "drive.google.com"
        finally:
            await db.close()

    run_db_test(_run())


def test_sqlite_backfill_host_ioc_for_legacy_rows(tmp_path, monkeypatch):
    """CodeRabbit: the SQLite migration path adds host_ioc with an empty
    default but must also backfill existing DOMAIN/HOSTNAME/URL/URI rows so a
    legacy dev/CI DB matches what migration 037 backfills on PostgreSQL."""
    from database import get_db

    from tests.conftest import run_db_test, use_sqlite_backend

    from database import get_db, init_db

    db_path = tmp_path / "phase_a_legacy.db"
    use_sqlite_backend(monkeypatch, db_path)

    async def _seed_legacy_db():
        conn = await get_db()
        try:
            await conn.executescript(
                """
                CREATE TABLE otx_pulse_iocs (
                    pulse_id TEXT NOT NULL,
                    ioc_type TEXT NOT NULL DEFAULT '',
                    ioc_value TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    fetched_at TEXT DEFAULT (datetime('now')),
                    observed_at TEXT,
                    PRIMARY KEY (pulse_id, ioc_type, ioc_value)
                );
                INSERT INTO otx_pulse_iocs (pulse_id, ioc_type, ioc_value) VALUES
                    ('legacy-a', 'DOMAIN', 'EVIL.EXAMPLE.COM'),
                    ('legacy-b', 'HOSTNAME', 'sub.example.com.'),
                    ('legacy-c', 'URL', 'https://drive.google.com/uc?id=abc123'),
                    ('legacy-d', 'URI', 'https://t.me/still_stellc'),
                    ('legacy-e', 'IP', '1.2.3.4'),
                    ('legacy-f', 'HASH', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
                """
            )
            await conn.commit()
        finally:
            await conn.close()

    async def _run():
        await _seed_legacy_db()
        await init_db()
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT pulse_id, ioc_type, ioc_value, raw_ioc, host_ioc "
                "FROM otx_pulse_iocs ORDER BY pulse_id"
            )
            by_pulse = {r["pulse_id"]: r for r in rows}
            assert by_pulse["legacy-a"]["host_ioc"] == "evil.example.com"
            assert by_pulse["legacy-b"]["host_ioc"] == "sub.example.com"
            assert by_pulse["legacy-c"]["host_ioc"] == "drive.google.com"
            assert by_pulse["legacy-d"]["host_ioc"] == "t.me"
            assert by_pulse["legacy-e"]["host_ioc"] == ""
            assert by_pulse["legacy-f"]["host_ioc"] == ""
            assert all(r["raw_ioc"] == "" for r in rows)
        finally:
            await db.close()

    run_db_test(_run())
