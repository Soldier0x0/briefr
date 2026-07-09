#!/usr/bin/env python3
"""Import a versioned BRIEFR intel snapshot into PostgreSQL (Wave 4).

Greenfield bootstrap or intel-only refresh — never overwrites operator tables
on a production instance with users/sessions. See docs/OPERATIONS.md § Intel
snapshot import and upgrade.

Usage:
  python scripts/import_intel_snapshot.py \\
    --input briefr-intel-2026-07.pgdump.gz \\
    --database-url postgresql://briefr:pass@127.0.0.1:5432/briefr_intel

  # Refresh intel tables on an empty seed database (dev/CI):
  python scripts/import_intel_snapshot.py --input ... --database-url ... --replace-intel
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))
sys.path.insert(0, str(_REPO / "scripts"))

from backup.postgres_util import parse_postgres_url, run_pg_restore  # noqa: E402
from db.config import postgres_dsn  # noqa: E402
from export_intel_snapshot import INTEL_TABLES, OPERATOR_GUARD_TABLES  # noqa: E402
from verify_intel_snapshot import verify_snapshot  # noqa: E402


async def _assert_safe_target(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        for table in OPERATOR_GUARD_TABLES:
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
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            if count:
                raise RuntimeError(
                    f"refusing import: operator table {table} has {count} rows — "
                    "use a dedicated intel database or empty seed instance"
                )
    finally:
        await conn.close()


async def _truncate_intel_tables(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=60)
    try:
        tables = list(INTEL_TABLES)
        quoted = ", ".join(f'"{t}"' for t in tables)
        await conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
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
    proc = subprocess.run(
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


async def _row_counts(database_url: str) -> dict[str, int]:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        counts: dict[str, int] = {}
        for table in INTEL_TABLES:
            counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
        return counts
    finally:
        await conn.close()


def import_snapshot(
    input_path: Path,
    database_url: str,
    *,
    replace_intel: bool = False,
    skip_migrations: bool = False,
) -> dict:
    manifest = verify_snapshot(input_path)
    asyncio.run(_assert_safe_target(database_url))

    staging_path: Path | None = None
    dump_path = input_path
    if input_path.name.endswith(".gz"):
        staging = tempfile.NamedTemporaryFile(suffix=".pgdump", delete=False)
        staging_path = Path(staging.name)
        staging.close()
        with gzip.open(input_path, "rb") as src, staging_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        dump_path = staging_path

    try:
        if replace_intel:
            asyncio.run(_truncate_intel_tables(database_url))
        run_pg_restore(database_url, dump_path)
        if not skip_migrations:
            _run_alembic_upgrade(database_url)
        restored = asyncio.run(_row_counts(database_url))
        for table in INTEL_TABLES:
            expected = manifest["row_counts"].get(table)
            if expected is not None and restored[table] != expected:
                raise RuntimeError(
                    f"row count mismatch for {table}: expected {expected}, got {restored[table]}"
                )
        return {
            "manifest": manifest,
            "row_counts": restored,
            "database_host": parse_postgres_url(database_url).get("host"),
        }
    finally:
        if staging_path and staging_path.is_file():
            staging_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import BRIEFR intel snapshot")
    parser.add_argument("--input", required=True, type=Path, help="Path to .pgdump.gz")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL DSN",
    )
    parser.add_argument(
        "--replace-intel",
        action="store_true",
        help="TRUNCATE intel allowlist tables before restore (dev/seed only)",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip alembic upgrade head after restore",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    try:
        result = import_snapshot(
            args.input,
            args.database_url,
            replace_intel=args.replace_intel,
            skip_migrations=args.skip_migrations,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    print(f"Imported {args.input} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
