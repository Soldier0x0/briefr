"""Merge intel snapshot staging data into ``intel`` without touching ``app``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import asyncpg

from db.config import postgres_dsn
from db.schema_inventory import APP_TABLES, INTEL_TABLES
from intel_snapshot.merge_rules import MERGE_STRATEGIES, MERGE_TABLE_ORDER
from intel_snapshot.restore import restore_dump_to_staging, source_schema_from_manifest

logger = logging.getLogger(__name__)

_STAGING_SCHEMA = "intel_staging"


async def _table_exists(conn: asyncpg.Connection, schema: str, table: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
            """,
            schema,
            table,
        )
    )


async def _column_names(conn: asyncpg.Connection, schema: str, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """,
        schema,
        table,
    )
    return [row["column_name"] for row in rows]


async def _primary_key_columns(conn: asyncpg.Connection, schema: str, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = $1
          AND tc.table_name = $2
        ORDER BY kcu.ordinal_position
        """,
        schema,
        table,
    )
    return [row["column_name"] for row in rows]


async def _merge_table(conn: asyncpg.Connection, table: str) -> int:
    if not await _table_exists(conn, _STAGING_SCHEMA, table):
        logger.info("merge skip %s (not in staging)", table)
        return 0
    if not await _table_exists(conn, "intel", table):
        raise RuntimeError(f"target intel.{table} does not exist — run alembic upgrade head")

    columns = await _column_names(conn, _STAGING_SCHEMA, table)
    if not columns:
        return 0
    pk_cols = await _primary_key_columns(conn, _STAGING_SCHEMA, table)
    if not pk_cols:
        raise RuntimeError(f"cannot merge {table}: no primary key in staging")

    col_list = ", ".join(f'"{c}"' for c in columns)
    conflict = ", ".join(f'"{c}"' for c in pk_cols)
    strategy = MERGE_STRATEGIES.get(table, "update")

    if strategy == "nothing":
        sql = f"""
            INSERT INTO intel."{table}" ({col_list})
            SELECT {col_list} FROM {_STAGING_SCHEMA}."{table}"
            ON CONFLICT ({conflict}) DO NOTHING
        """
    else:
        non_pk = [c for c in columns if c not in pk_cols]
        if non_pk:
            set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in non_pk)
            sql = f"""
                INSERT INTO intel."{table}" ({col_list})
                SELECT {col_list} FROM {_STAGING_SCHEMA}."{table}"
                ON CONFLICT ({conflict}) DO UPDATE SET {set_clause}
            """
        else:
            sql = f"""
                INSERT INTO intel."{table}" ({col_list})
                SELECT {col_list} FROM {_STAGING_SCHEMA}."{table}"
                ON CONFLICT ({conflict}) DO NOTHING
            """

    status = await conn.execute(sql)
    parts = status.split()
    if parts and parts[-1].isdigit():
        return int(parts[-1])
    return 0


async def _app_row_counts(conn: asyncpg.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in APP_TABLES:
        try:
            counts[table] = int(await conn.fetchval(f'SELECT COUNT(*) FROM app."{table}"'))
        except asyncpg.UndefinedTableError:
            counts[table] = -1
    return counts


async def merge_intel_snapshot(
    database_url: str,
    dump_path: Path,
    manifest: dict,
) -> dict[str, Any]:
    """Merge bundle into existing ``intel`` schema; ``app`` rows must be unchanged."""
    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=120)
    try:
        before_app = await _app_row_counts(conn)
        source_schema = source_schema_from_manifest(manifest)
        restore_dump_to_staging(
            database_url,
            dump_path,
            source_schema=source_schema,
            staging_schema=_STAGING_SCHEMA,
        )

        merged: dict[str, int] = {}
        try:
            for table in MERGE_TABLE_ORDER:
                if table not in INTEL_TABLES:
                    continue
                merged[table] = await _merge_table(conn, table)
        finally:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{_STAGING_SCHEMA}" CASCADE')

        after_app = await _app_row_counts(conn)
        for table, before in before_app.items():
            after = after_app.get(table, -1)
            if before >= 0 and after >= 0 and before != after:
                raise RuntimeError(
                    f"app.{table} row count changed during merge ({before} -> {after})"
                )

        return {"merged_rows": merged, "app_row_counts_unchanged": True}
    finally:
        await conn.close()
