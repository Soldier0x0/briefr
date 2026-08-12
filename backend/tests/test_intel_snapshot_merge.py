"""Intel snapshot merge import tests (Postgres)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


def _pg_tools_present() -> bool:
    try:
        from backup.postgres_util import _pg_tool

        _pg_tool("pg_dump")
        _pg_tool("pg_restore")
        return True
    except RuntimeError:
        return False


if not _pg_tools_present():
    pytestmark = [
        pytestmark,
        pytest.mark.skipif(True, reason="pg_dump/pg_restore not found on PATH"),
    ]


@pytest.fixture(scope="module")
def postgres_schema():
    async def _boot() -> None:
        from database import run_postgres_migrations

        await run_postgres_migrations()

    asyncio.run(_boot())


def test_merge_import_leaves_app_rows_untouched(tmp_path, postgres_schema):
    database_url = os.environ["DATABASE_URL"]
    from export_intel_snapshot import export_snapshot
    from import_intel_snapshot import import_snapshot

    export_path = tmp_path / "publisher.pgdump.gz"
    export_snapshot(database_url, export_path, allow_operator_seed=True)

    import asyncio

    async def _seed_operator() -> int:
        import asyncpg
        from db.config import postgres_dsn

        conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
        try:
            before_users = await conn.fetchval('SELECT COUNT(*) FROM app.users')
            marker = "merge-test-stack-terms"
            await conn.execute(
                """
                INSERT INTO app.user_preferences (user_id, stack_terms, timezone)
                VALUES (1, $1, 'UTC')
                ON CONFLICT (user_id) DO UPDATE SET stack_terms = EXCLUDED.stack_terms
                """,
                marker,
            )
            return int(before_users or 0)
        finally:
            await conn.close()

    try:
        asyncio.run(_seed_operator())
    except Exception:
        pytest.skip("no app.users seed fixture for merge test")

    result = import_snapshot(export_path, database_url, mode="merge")
    assert result["mode"] == "merge"
    assert result.get("merge", {}).get("app_row_counts_unchanged") is True

    async def _check_stack() -> str | None:
        import asyncpg
        from db.config import postgres_dsn

        conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
        try:
            return await conn.fetchval(
                "SELECT stack_terms FROM app.user_preferences WHERE user_id = 1"
            )
        finally:
            await conn.close()

    stack = asyncio.run(_check_stack())
    assert stack == "merge-test-stack-terms"
