#!/usr/bin/env python3
"""Export, verify, and stage a BRIEFR intel snapshot for publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

from export_intel_snapshot import export_snapshot  # noqa: E402
from verify_intel_snapshot import verify_snapshot  # noqa: E402


def publish_snapshot(
    database_url: str,
    output_dir: Path,
    *,
    allow_operator_seed: bool = False,
    publisher_instance: bool = False,
) -> dict:
    if not publisher_instance:
        import asyncio

        from export_intel_snapshot import OPERATOR_GUARD_TABLES, _qualified_table, _schemas_split
        from db.config import postgres_dsn

        async def _guard() -> None:
            import asyncpg

            conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
            try:
                split = await _schemas_split(conn)
                for table in OPERATOR_GUARD_TABLES:
                    qualified = _qualified_table(table, split=split)
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}")
                    if count:
                        raise RuntimeError(
                            f"publisher guard: {qualified} has rows — "
                            "use --publisher-instance only on dedicated publisher DBs"
                        )
            finally:
                await conn.close()

        asyncio.run(_guard())

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bundle_path = output_dir / f"briefr-intel-{stamp}.pgdump.gz"
    manifest = export_snapshot(
        database_url,
        bundle_path,
        allow_operator_seed=allow_operator_seed,
    )
    verify_snapshot(bundle_path)

    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    pointer = {
        "url": str(bundle_path),
        "sha256": digest,
        "exported_at": manifest.get("exported_at"),
        "format_version": manifest.get("format_version"),
        "alembic_head_at_export": manifest.get("alembic_head_at_export"),
        "bundle_kind": manifest.get("bundle_kind"),
    }
    latest_path = output_dir / "latest.json"
    latest_path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    return {"bundle": str(bundle_path), "latest": str(latest_path), "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish BRIEFR intel snapshot to a directory")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("INTEL_PUBLISH_DIR", "/var/lib/briefr/intel-publish"),
        type=Path,
    )
    parser.add_argument("--allow-operator-seed", action="store_true")
    parser.add_argument(
        "--publisher-instance",
        action="store_true",
        help="Skip publisher guard (dedicated intel-only DB)",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    try:
        result = publish_snapshot(
            args.database_url,
            args.output_dir,
            allow_operator_seed=args.allow_operator_seed,
            publisher_instance=args.publisher_instance,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
