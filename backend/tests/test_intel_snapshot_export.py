"""Intel snapshot export round-trip smoke (Wave 3 PR 9 / Track J2)."""

from __future__ import annotations

import asyncio
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


def _pg_tool(name: str) -> str:
    from backup.postgres_util import _pg_tool as tool

    return tool(name)


@pytest.fixture(scope="module")
def postgres_schema():
    async def _boot() -> None:
        from database import run_postgres_migrations

        await run_postgres_migrations()

    asyncio.run(_boot())


def test_export_intel_snapshot_round_trip(tmp_path, postgres_schema):
    database_url = os.environ["DATABASE_URL"]
    from export_intel_snapshot import export_snapshot, INTEL_TABLES, OPERATOR_GUARD_TABLES
    from backup.postgres_util import parse_postgres_url, run_pg_restore

    output = tmp_path / "briefr-intel.pgdump.gz"
    manifest = export_snapshot(database_url, output, allow_operator_seed=True)
    assert output.is_file()
    assert manifest["row_counts"]["cves"] >= 0

    staging = tmp_path / "briefr-intel.pgdump"
    with gzip.open(output, "rb") as src, staging.open("wb") as dst:
        shutil.copyfileobj(src, dst)

    params = parse_postgres_url(database_url)
    restore_db = f"{params['dbname']}_intel_restore"
    admin_url = database_url.rsplit("/", 1)[0] + "/postgres"
    admin_params = parse_postgres_url(admin_url)

    create_cmd = [
        _pg_tool("psql"),
        "-h",
        str(admin_params.get("host", "127.0.0.1")),
        "-p",
        str(admin_params.get("port", 5432)),
        "-U",
        str(admin_params["user"]),
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        f'DROP DATABASE IF EXISTS "{restore_db}";',
        "-c",
        f'CREATE DATABASE "{restore_db}";',
    ]
    env = os.environ.copy()
    if admin_params.get("password"):
        env["PGPASSWORD"] = str(admin_params["password"])
    subprocess.run(create_cmd, env=env, check=True, capture_output=True, text=True)

    restore_url = database_url.rsplit("/", 1)[0] + f"/{restore_db}"
    run_pg_restore(restore_url, staging)

    async def _counts() -> dict[str, int]:
        import asyncpg
        from db.config import postgres_dsn

        conn = await asyncpg.connect(dsn=postgres_dsn(restore_url), timeout=30)
        try:
            counts = {}
            for table in INTEL_TABLES:
                counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
            for table in OPERATOR_GUARD_TABLES:
                counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
            return counts
        finally:
            await conn.close()

    restored = asyncio.run(_counts())
    for table in INTEL_TABLES:
        assert restored[table] == manifest["row_counts"][table], table
    for table in OPERATOR_GUARD_TABLES:
        assert restored[table] == 0, table
