#!/usr/bin/env python3
"""Export an allowlisted BRIEFR intel Postgres snapshot (Wave 3 PR 9).

See docs/DATA_SNAPSHOT.md for table/key boundaries.

Usage (from repo root):
  DATABASE_URL=postgresql://briefr:pass@127.0.0.1:5432/briefr \\
    python scripts/export_intel_snapshot.py --output /tmp/briefr-intel.pgdump.gz

Exits non-zero when operator guard tables contain rows or forbidden sync_state
keys are present.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from backup.postgres_util import (  # noqa: E402
    _build_pg_cmd,
    _pg_tool,
    _subprocess_env,
    parse_postgres_url,
    verify_pg_dump,
)
from db.config import postgres_dsn  # noqa: E402
from db.schema_inventory import (  # noqa: E402
    FORBIDDEN_EXPORT_TABLES,
    INTEL_TABLES,
    OPERATOR_GUARD_TABLES,
    SYNC_STATE_INGEST_KEYS,
    feed_cache_key_publishable,
    table_schema,
)
from snapshot_version import BUNDLE_KIND, SNAPSHOT_FORMAT_VERSION  # noqa: E402

# Backward-compatible re-exports for tests and importers.
SYNC_STATE_ALLOWLIST = SYNC_STATE_INGEST_KEYS
FORBIDDEN_TABLES = FORBIDDEN_EXPORT_TABLES


def _alembic_head_revision() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config(str(_REPO / "backend" / "alembic.ini"))
    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
    return head or "unknown"


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


def _qualified_table(table: str, *, split: bool) -> str:
    if not split:
        return table
    return f"{table_schema(table)}.{table}"


async def _preflight(database_url: str, *, allow_operator_seed: bool) -> dict:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        split = await _schemas_split(conn)
        for table in OPERATOR_GUARD_TABLES:
            qualified = _qualified_table(table, split=split)
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}")
            if count:
                raise RuntimeError(
                    f"operator guard table {qualified} has {count} rows — "
                    "refusing intel export (use --allow-operator-seed for dev fixtures only)"
                )

        sync_table = "intel.sync_state" if split else "sync_state"
        rows = await conn.fetch(f"SELECT key FROM {sync_table}")
        keys = [row["key"] for row in rows]
        forbidden_keys = [key for key in keys if key not in SYNC_STATE_INGEST_KEYS]
        if forbidden_keys:
            raise RuntimeError(
                "forbidden sync_state keys present: "
                + ", ".join(sorted(forbidden_keys))
            )

        feed_qualified = _qualified_table("feed_cache", split=split)
        feed_rows = await conn.fetch(f"SELECT cache_key FROM {feed_qualified}")
        bad_feed_keys = [
            row["cache_key"]
            for row in feed_rows
            if not feed_cache_key_publishable(row["cache_key"])
        ]
        if bad_feed_keys:
            raise RuntimeError(
                "non-publishable feed_cache keys present: "
                + ", ".join(sorted(bad_feed_keys)[:20])
                + (" …" if len(bad_feed_keys) > 20 else "")
            )

        if split:
            stray = await conn.fetch(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name = ANY($1::text[])
                """,
                list(INTEL_TABLES) + list(FORBIDDEN_EXPORT_TABLES),
            )
            if stray:
                names = ", ".join(f"{r['table_schema']}.{r['table_name']}" for r in stray)
                raise RuntimeError(
                    f"classified tables still in public schema (run alembic 036 first): {names}"
                )

        counts: dict[str, int] = {}
        for table in INTEL_TABLES:
            qualified = _qualified_table(table, split=split)
            counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}"))

        schema_revision = None
        try:
            schema_revision = await conn.fetchval(
                "SELECT version_num FROM public.alembic_version LIMIT 1"
            )
        except asyncpg.UndefinedTableError:
            schema_revision = None

        alembic_head = _alembic_head_revision()
        build_info: dict = {}
        build_path = _REPO / "backend" / ".build-info.json"
        if build_path.is_file():
            try:
                build_info = json.loads(build_path.read_text(encoding="utf-8"))
            except Exception:
                build_info = {}

        manifest_version = SNAPSHOT_FORMAT_VERSION if split else 1
        payload = {
            "format_version": manifest_version,
            "bundle_kind": BUNDLE_KIND,
            "schema_revision": schema_revision,
            "alembic_head_at_export": alembic_head,
            "schema_split": split,
            "merge_compatible": split,
            "briefr_commit": build_info.get("commit") or build_info.get("git_commit"),
            "tables": list(INTEL_TABLES),
            "row_counts": counts,
            "sync_state_keys": sorted(keys),
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if split:
            payload["schema_names"] = ["intel"]
        return payload
    finally:
        await conn.close()


def _run_pg_dump(database_url: str, destination: Path, *, split: bool) -> None:
    params = parse_postgres_url(database_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if split:
        extra_args = [
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--schema=intel",
            "-f",
            str(destination),
        ]
    else:
        table_args: list[str] = []
        for table in INTEL_TABLES:
            table_args.extend(["--table", table])
        extra_args = [
            "--format=custom",
            "--no-owner",
            "--no-acl",
            *table_args,
            "-f",
            str(destination),
        ]
    cmd = _build_pg_cmd("pg_dump", params, extra_args=extra_args)
    proc = subprocess.run(
        cmd,
        env=_subprocess_env(params),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {detail}")


_RESTORE_LIST_TABLE_RE = re.compile(
    r"^\d+;\s+\d+\s+\d+\s+TABLE(?: DATA)?\s+(?:(?P<schema>intel|app|public)\s+)?(?P<name>\S+)"
)


def _verify_dump_tables(dump_path: Path, *, schema_split: bool) -> None:
    """List tables in the archive; fail if a forbidden name or wrong schema appears."""
    cmd = [_pg_tool("pg_restore"), "--list", str(dump_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore --list failed: {detail}")
    for line in proc.stdout.splitlines():
        match = _RESTORE_LIST_TABLE_RE.match(line)
        if not match:
            continue
        table_name = match.group("name")
        schema = match.group("schema") or "public"
        if table_name in FORBIDDEN_EXPORT_TABLES:
            raise RuntimeError(f"forbidden table {table_name} found in dump catalog")
        if schema_split and schema not in {"intel"}:
            if table_name in INTEL_TABLES or table_name in FORBIDDEN_EXPORT_TABLES:
                raise RuntimeError(
                    f"expected intel schema for {table_name}, found {schema} in dump catalog"
                )


def export_snapshot(
    database_url: str,
    output_path: Path,
    *,
    allow_operator_seed: bool = False,
) -> dict:
    manifest = asyncio.run(_preflight(database_url, allow_operator_seed=allow_operator_seed))
    split = bool(manifest.get("schema_split"))
    staging = output_path.with_suffix(".pgdump")
    if staging == output_path:
        staging = output_path.parent / (output_path.name + ".staging.pgdump")
    try:
        _run_pg_dump(database_url, staging, split=split)
        ok, msg = verify_pg_dump(staging)
        if not ok:
            raise RuntimeError(f"dump verification failed: {msg}")
        _verify_dump_tables(staging, schema_split=split)
        with staging.open("rb") as src, gzip.open(output_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        manifest_path = output_path.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest
    finally:
        if staging.is_file():
            staging.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export allowlisted BRIEFR intel snapshot")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL DSN (default: DATABASE_URL)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for .pgdump.gz bundle",
    )
    parser.add_argument(
        "--allow-operator-seed",
        action="store_true",
        help="Skip operator guard table checks (dev/CI fixtures only)",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    try:
        manifest = export_snapshot(
            args.database_url,
            args.output,
            allow_operator_seed=args.allow_operator_seed,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
