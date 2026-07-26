"""schema_inventory and schema split migration tests."""

from __future__ import annotations

import asyncio
import os

import pytest

from db.schema_inventory import (
    APP_TABLES,
    FORBIDDEN_EXPORT_TABLES,
    INTEL_TABLES,
    SYNC_STATE_INGEST_KEYS,
    feed_cache_key_publishable,
)


def test_table_inventory_counts():
    assert len(INTEL_TABLES) == 30
    assert len(APP_TABLES) == 27
    assert len(set(INTEL_TABLES) & set(APP_TABLES)) == 0
    assert "correlation_cve_snapshot" in INTEL_TABLES
    assert "embeddings" in INTEL_TABLES
    assert "software_catalog" in INTEL_TABLES


def test_sync_state_ingest_allowlist_includes_epss_csv_identity():
    assert "epss_csv_file_identity" in SYNC_STATE_INGEST_KEYS


def test_forbidden_export_covers_all_app_tables():
    for table in APP_TABLES:
        assert table in FORBIDDEN_EXPORT_TABLES


def test_feed_cache_publishable_rules():
    assert feed_cache_key_publishable("ssvc:foo")
    assert feed_cache_key_publishable("otx:cve:CVE-2024-1")
    assert not feed_cache_key_publishable("wallboard:snapshot")
    assert not feed_cache_key_publishable("llm_products:CVE-2024-1")
    assert not feed_cache_key_publishable("admin_db_integrity")


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)
def test_schema_split_after_migrations():
    async def _run() -> None:
        from database import get_db, run_postgres_migrations
        from db.schema_split import schemas_are_split
        from db.sync_state import get_sync_state_value, set_sync_state_value

        await run_postgres_migrations()
        db = await get_db()
        try:
            split = await schemas_are_split(db)
            assert split, "expected intel/app schema split after Alembic head"

            rows = await db.execute_fetchall(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema IN ('intel', 'app', 'public')
                ORDER BY table_schema, table_name
                """
            )
            by_schema: dict[str, set[str]] = {"intel": set(), "app": set(), "public": set()}
            for row in rows:
                by_schema[row["table_schema"]].add(row["table_name"])

            for table in INTEL_TABLES:
                assert table in by_schema["intel"], f"missing intel.{table}"
                assert table not in by_schema["public"], f"{table} still in public"

            for table in APP_TABLES:
                assert table in by_schema["app"], f"missing app.{table}"
                assert table not in by_schema["public"], f"{table} still in public"

            assert "alembic_version" in by_schema["public"]

            await set_sync_state_value(db, "nvd_last_mod_end", "test-watermark")
            await set_sync_state_value(db, "scheduler.last_run.nvd_sync", "2026-01-01T00:00:00Z")
            await db.commit()

            intel_rows = await db.execute_fetchall(
                "SELECT key FROM intel.sync_state WHERE key = $1",
                ("nvd_last_mod_end",),
            )
            app_rows = await db.execute_fetchall(
                "SELECT key FROM app.sync_state WHERE key = $1",
                ("scheduler.last_run.nvd_sync",),
            )
            assert intel_rows, "ingest key should land in intel.sync_state"
            assert app_rows, "operator key should land in app.sync_state"

            assert await get_sync_state_value(db, "nvd_last_mod_end") == "test-watermark"
            assert (
                await get_sync_state_value(db, "scheduler.last_run.nvd_sync")
                == "2026-01-01T00:00:00Z"
            )
        finally:
            await db.close()

    asyncio.run(_run())
