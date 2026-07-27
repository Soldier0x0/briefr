"""Post-B4: production backup path round-trip against live Postgres.

Exercises the same stack as ``deploy/briefr-pg-backup.sh`` /
``deploy/briefr-backup.sh`` (``python -m backup run`` → tarball with
``briefr.pgdump``) and ``restore_backup(..., force=True)`` (same restore
logic as ``deploy/briefr-restore.sh``). Skips when ``DATABASE_URL`` is not
PostgreSQL (default SQLite CI job).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backup.postgres_util import postgres_backup_tools_available, postgres_server_live

_SKIP_REASON: str | None = None
if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
    _SKIP_REASON = "DATABASE_URL not set to PostgreSQL"
elif not postgres_backup_tools_available():
    _SKIP_REASON = "pg_dump/pg_restore not installed"

pytestmark = pytest.mark.skipif(
    _SKIP_REASON is not None,
    reason=_SKIP_REASON or "",
)


@pytest.fixture(autouse=True)
def _ensure_postgres_live():
    """Skip at runtime when DATABASE_URL is set but the server is down."""
    if os.environ.get("DATABASE_URL", "").startswith("postgresql") and not postgres_server_live():
        pytest.skip("PostgreSQL server is not live")


CORE_TABLES = ("cves", "kev_deadlines")

# Match db.connection pool search_path after migration 036 (intel/app schema split).
_PG_SERVER_SETTINGS = {"search_path": "app, intel, public"}


def _backup_config(tmp_path: Path):
    from backup.manager import BackupConfig

    database_url = os.environ["DATABASE_URL"]
    env_path = tmp_path / ".env"
    env_path.write_text(f"DATABASE_URL={database_url}\n", encoding="utf-8")
    return BackupConfig(
        db_path=tmp_path / "briefr.db",
        env_path=env_path,
        backup_dir=tmp_path / "backups",
        retention_count=3,
        log_path=tmp_path / "backups" / "logs" / "backup.log",
        enabled=True,
        age_key_path=None,
        database_url=database_url,
    )


async def _seed_core_rows(conn) -> None:
    await conn.execute(
        """
        INSERT INTO cves (
            cve_id, description, severity, is_kev, cvss_score, published, modified
        ) VALUES
            ('CVE-2024-9001', 'Round-trip KEV row', 'CRITICAL', 1, 9.8,
             '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
            ('CVE-2024-9002', 'Round-trip non-KEV row', 'HIGH', 0, 7.5,
             '2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z')
        """
    )
    await conn.execute(
        """
        INSERT INTO kev_deadlines (
            cve_id, product, short_description, required_action, due_date, date_added
        ) VALUES (
            'CVE-2024-9001', 'TestProduct', 'RCE in the wild', 'Apply vendor patch',
            '2024-06-01', '2024-01-01T00:00:00Z'
        )
        """
    )


async def _table_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in CORE_TABLES:
        counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
    return counts


async def _truncate_app_tables(conn) -> None:
    rows = await conn.fetch(
        "SELECT schemaname, tablename FROM pg_tables"
        " WHERE schemaname IN ('app', 'intel', 'public')"
        " AND tablename != 'alembic_version'"
    )
    names = ", ".join(
        f'"{r["schemaname"]}"."{r["tablename"]}"' for r in rows
    )
    if names:
        await conn.execute(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")


def test_pg_dump_restore_round_trip_core_tables(tmp_path, monkeypatch):
    """pg_dump archive from run_backup restores row counts for core intel tables."""
    from backup.manager import restore_backup, run_backup
    from db.config import postgres_dsn

    database_url = os.environ["DATABASE_URL"]
    dsn = postgres_dsn(database_url)
    cfg = _backup_config(tmp_path)
    monkeypatch.setattr("backup.manager.write_audit_postgres", lambda *a, **k: None)

    async def _prepare() -> dict[str, int]:
        import asyncpg

        conn = await asyncpg.connect(
            dsn=dsn, timeout=30, server_settings=_PG_SERVER_SETTINGS
        )
        try:
            await _seed_core_rows(conn)
            return await _table_counts(conn)
        finally:
            await conn.close()

    before = asyncio.run(_prepare())
    assert before["cves"] == 2
    assert before["kev_deadlines"] == 1

    backup = run_backup(reason="ci-roundtrip", config=cfg)
    assert backup["status"] == "ok"
    archive = Path(backup["archive"])
    assert archive.is_file()

    async def _wipe() -> None:
        import asyncpg

        conn = await asyncpg.connect(
            dsn=dsn, timeout=30, server_settings=_PG_SERVER_SETTINGS
        )
        try:
            await _truncate_app_tables(conn)
            wiped = await _table_counts(conn)
            assert wiped["cves"] == 0
            assert wiped["kev_deadlines"] == 0
        finally:
            await conn.close()

    asyncio.run(_wipe())

    restore = restore_backup(archive, config=cfg, force=True)
    assert restore["status"] == "ok"
    assert restore["backend"] == "postgresql"

    async def _after() -> dict[str, int]:
        import asyncpg

        conn = await asyncpg.connect(
            dsn=dsn, timeout=30, server_settings=_PG_SERVER_SETTINGS
        )
        try:
            return await _table_counts(conn)
        finally:
            await conn.close()

    after = asyncio.run(_after())
    for table in CORE_TABLES:
        assert after[table] == before[table], table
