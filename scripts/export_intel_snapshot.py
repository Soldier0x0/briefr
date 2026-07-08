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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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

INTEL_TABLES: tuple[str, ...] = (
    "cves",
    "kev_deadlines",
    "epss_history",
    "cve_change_history",
    "mitre_techniques",
    "cve_technique_map",
    "atlas_techniques",
    "atlas_case_studies",
    "cve_atlas_map",
    "cve_exploits",
    "feed_cache",
    "otx_cve_pulses",
    "otx_pulse_iocs",
    "otx_pulses",
    "correlation_actor",
    "correlation_temporal",
    "correlation_campaigns",
    "correlation_campaign_members",
    "correlation_infrastructure",
    "cve_embeddings",
    "mitre_groups",
    "group_technique_map",
    "sync_state",
)

OPERATOR_GUARD_TABLES: tuple[str, ...] = (
    "users",
    "sessions",
    "user_preferences",
)

FORBIDDEN_TABLES: frozenset[str] = frozenset({
    "users",
    "sessions",
    "user_preferences",
    "watchlist",
    "audit_log",
    "ioc_cache",
    "api_usage",
    "webhook_destinations",
    "webhook_delivery_log",
    "webhook_alert_log",
    "correlation_suppressions",
    "hunt_packs",
    "alembic_version",
})

SYNC_STATE_ALLOWLIST: frozenset[str] = frozenset({
    "nvd_last_mod_end",
    "epss_backfill_done",
    "atlas_upstream_version",
    "cvelistv5_head_sha",
    "poc_github_commit",
    "correlation_build_watermark",
    "correlation_last_run",
})


async def _preflight(database_url: str, *, allow_operator_seed: bool) -> dict:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        if not allow_operator_seed:
            for table in OPERATOR_GUARD_TABLES:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                if count:
                    raise RuntimeError(
                        f"operator guard table {table} has {count} rows — "
                        "refusing intel export (use --allow-operator-seed for dev fixtures only)"
                    )

        rows = await conn.fetch("SELECT key FROM sync_state")
        keys = [row["key"] for row in rows]
        forbidden_keys = [key for key in keys if key not in SYNC_STATE_ALLOWLIST]
        if forbidden_keys:
            raise RuntimeError(
                "forbidden sync_state keys present: "
                + ", ".join(sorted(forbidden_keys))
            )

        counts: dict[str, int] = {}
        for table in INTEL_TABLES:
            counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))

        return {
            "tables": list(INTEL_TABLES),
            "row_counts": counts,
            "sync_state_keys": sorted(keys),
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
    finally:
        await conn.close()


def _run_pg_dump(database_url: str, destination: Path) -> None:
    params = parse_postgres_url(database_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    table_args: list[str] = []
    for table in INTEL_TABLES:
        table_args.extend(["--table", table])
    cmd = _build_pg_cmd(
        "pg_dump",
        params,
        extra_args=[
            "--format=custom",
            "--no-owner",
            "--no-acl",
            *table_args,
            "-f",
            str(destination),
        ],
    )
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


def _verify_dump_tables(dump_path: Path) -> None:
    """List tables in the archive; fail if a forbidden name appears."""
    cmd = [_pg_tool("pg_restore"), "--list", str(dump_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore --list failed: {detail}")
    for line in proc.stdout.splitlines():
        for forbidden in FORBIDDEN_TABLES:
            if f"TABLE public {forbidden}" in line or f"TABLE {forbidden}" in line:
                raise RuntimeError(f"forbidden table {forbidden} found in dump catalog")


def export_snapshot(
    database_url: str,
    output_path: Path,
    *,
    allow_operator_seed: bool = False,
) -> dict:
    manifest = asyncio.run(_preflight(database_url, allow_operator_seed=allow_operator_seed))
    staging = output_path.with_suffix(".pgdump")
    if staging == output_path:
        staging = output_path.parent / (output_path.name + ".staging.pgdump")
    try:
        _run_pg_dump(database_url, staging)
        ok, msg = verify_pg_dump(staging)
        if not ok:
            raise RuntimeError(f"dump verification failed: {msg}")
        _verify_dump_tables(staging)
        with staging.open("rb") as src, gzip.open(output_path, "wb") as dst:
            dst.writelines(src)
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
