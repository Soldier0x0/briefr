#!/usr/bin/env python3
"""Import a versioned BRIEFR intel snapshot into PostgreSQL.

Modes:
  bootstrap — empty operator tables; replace intel data (greenfield seed)
  merge     — upsert intel only; app rows (users, stack, settings) untouched

See docs/OPERATIONS.md and docs/INTEL_PUBLISH.md.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))
sys.path.insert(0, str(_REPO / "scripts"))

from backup.postgres_util import parse_postgres_url, run_pg_restore  # noqa: E402
from db.config import postgres_dsn  # noqa: E402
from db.schema_inventory import INTEL_TABLES, OPERATOR_GUARD_TABLES  # noqa: E402
from export_intel_snapshot import INTEL_TABLES as EXPORT_INTEL_TABLES  # noqa: E402
from intel_snapshot.merge import merge_intel_snapshot  # noqa: E402
from intel_snapshot.restore import restore_dump_to_schema, source_schema_from_manifest  # noqa: E402
from verify_intel_snapshot import verify_snapshot  # noqa: E402

LAST_IMPORT_AT_KEY = "intel_snapshot.last_import_at"
LAST_IMPORT_MODE_KEY = "intel_snapshot.last_import_mode"
LAST_MANIFEST_EXPORTED_AT_KEY = "intel_snapshot.last_manifest_exported_at"


async def _schemas_split(conn) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'intel' AND table_name = 'cves'
            )
            """
        )
    )


def _intel_qualified(table: str, *, split: bool) -> str:
    if split:
        return f'intel."{table}"'
    return f'"{table}"'


async def _assert_bootstrap_target(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        split = await _schemas_split(conn)
        for table in OPERATOR_GUARD_TABLES:
            if split:
                qualified = f'app."{table}"'
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'app' AND table_name = $1
                    )
                    """,
                    table,
                )
            else:
                qualified = f'public."{table}"'
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = $1
                    )
                    """,
                    table,
                )
            if not exists:
                continue
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}")
            if count:
                raise RuntimeError(
                    f"refusing bootstrap import: operator table {qualified} has {count} rows — "
                    "use --mode merge for an existing instance"
                )
    finally:
        await conn.close()


async def _truncate_intel_tables(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=60)
    try:
        split = await _schemas_split(conn)
        qualified = ", ".join(_intel_qualified(t, split=split) for t in INTEL_TABLES)
        await conn.execute(f"TRUNCATE {qualified} RESTART IDENTITY CASCADE")
    finally:
        await conn.close()


async def _intel_row_counts(database_url: str) -> dict[str, int]:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        split = await _schemas_split(conn)
        counts: dict[str, int] = {}
        for table in EXPORT_INTEL_TABLES:
            qualified = _intel_qualified(table, split=split)
            counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}"))
        return counts
    finally:
        await conn.close()


async def _record_import(database_url: str, *, mode: str, manifest: dict) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        exported_at = manifest.get("exported_at") or ""
        for key, value in (
            (LAST_IMPORT_AT_KEY, now),
            (LAST_IMPORT_MODE_KEY, mode),
            (LAST_MANIFEST_EXPORTED_AT_KEY, exported_at),
        ):
            await conn.execute(
                """
                INSERT INTO app.sync_state (key, value, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                key,
                value,
                now,
            )
    except asyncpg.UndefinedTableError:
        # Pre-036 or SQLite — skip metadata
        pass
    finally:
        await conn.close()


def _run_alembic_upgrade(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(_REPO / "backend" / "alembic.ini"),
        "upgrade",
        "head",
    ]
    proc = __import__("subprocess").run(
        cmd,
        cwd=str(_REPO / "backend"),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"alembic upgrade head failed: {detail}")


def _decompress_if_needed(input_path: Path) -> tuple[Path, Path | None]:
    if not input_path.name.endswith(".gz"):
        return input_path, None
    staging = tempfile.NamedTemporaryFile(suffix=".pgdump", delete=False)
    staging_path = Path(staging.name)
    staging.close()
    with gzip.open(input_path, "rb") as src, staging_path.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return staging_path, staging_path


def import_snapshot(
    input_path: Path,
    database_url: str,
    *,
    mode: str = "bootstrap",
    replace_intel: bool = False,
    skip_migrations: bool = False,
) -> dict:
    if mode not in {"bootstrap", "merge"}:
        raise ValueError("mode must be bootstrap or merge")

    manifest = verify_snapshot(input_path)
    dump_path, temp_path = _decompress_if_needed(input_path)

    try:
        if mode == "bootstrap":
            asyncio.run(_assert_bootstrap_target(database_url))
            if not skip_migrations:
                _run_alembic_upgrade(database_url)
            if replace_intel:
                asyncio.run(_truncate_intel_tables(database_url))

            split = asyncio.run(_schemas_split_conn(database_url))
            source_schema = source_schema_from_manifest(manifest)
            if split or manifest.get("format_version", 1) >= 2:
                restore_dump_to_schema(
                    database_url,
                    dump_path,
                    source_schema=source_schema,
                    target_schema="intel" if split else source_schema,
                )
            else:
                run_pg_restore(database_url, dump_path)
                if not skip_migrations:
                    _run_alembic_upgrade(database_url)
        else:
            if not skip_migrations:
                _run_alembic_upgrade(database_url)
            merge_result = asyncio.run(
                merge_intel_snapshot(database_url, dump_path, manifest)
            )
            restored = asyncio.run(_intel_row_counts(database_url))
            asyncio.run(_record_import(database_url, mode=mode, manifest=manifest))
            return {
                "mode": mode,
                "manifest": manifest,
                "merge": merge_result,
                "row_counts": restored,
                "database_host": parse_postgres_url(database_url).get("host"),
            }

        restored = asyncio.run(_intel_row_counts(database_url))
        for table in EXPORT_INTEL_TABLES:
            expected = manifest["row_counts"].get(table)
            if expected is not None and restored[table] != expected:
                raise RuntimeError(
                    f"row count mismatch for {table}: expected {expected}, got {restored[table]}"
                )
        asyncio.run(_record_import(database_url, mode=mode, manifest=manifest))
        return {
            "mode": mode,
            "manifest": manifest,
            "row_counts": restored,
            "database_host": parse_postgres_url(database_url).get("host"),
        }
    finally:
        if temp_path and temp_path.is_file():
            temp_path.unlink()


async def _schemas_split_conn(database_url: str) -> bool:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        return await _schemas_split(conn)
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import BRIEFR intel snapshot")
    parser.add_argument("--input", required=True, type=Path, help="Path to .pgdump.gz")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL DSN",
    )
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "merge"),
        default="bootstrap",
        help="bootstrap = empty operator tables; merge = upsert intel only",
    )
    parser.add_argument(
        "--replace-intel",
        action="store_true",
        help="TRUNCATE intel tables before bootstrap restore",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip alembic upgrade head before/after restore",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    try:
        result = import_snapshot(
            args.input,
            args.database_url,
            mode=args.mode,
            replace_intel=args.replace_intel,
            skip_migrations=args.skip_migrations,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    print(f"Imported {args.input} OK ({result.get('mode', 'bootstrap')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
