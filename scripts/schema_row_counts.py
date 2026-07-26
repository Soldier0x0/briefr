#!/usr/bin/env python3
"""Capture per-table row counts for schema-split migration verification.

Run **once** before production ``alembic upgrade head`` (revision 036):

  python scripts/schema_row_counts.py --output pre-036.json

After upgrade, compare with:

  python scripts/verify_schema_split.py --manifest pre-036.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from db.config import postgres_dsn  # noqa: E402
from db.schema_inventory import APP_TABLES, INTEL_TABLES  # noqa: E402

_ALL_TABLES = (*INTEL_TABLES, *APP_TABLES, "alembic_version")


async def _collect(database_url: str) -> dict:
    import asyncpg

    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        split = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'intel' AND table_name = 'cves'
            )
            """
        )
        counts: dict[str, int] = {}
        for table in _ALL_TABLES:
            if split:
                schema = "intel" if table in INTEL_TABLES else "app"
                if table == "alembic_version":
                    schema = "public"
                qualified = f"{schema}.{table}"
            else:
                qualified = f"public.{table}"
            try:
                counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}"))
            except asyncpg.UndefinedTableError:
                counts[table] = -1
        return {
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "schema_split": bool(split),
            "tables": counts,
        }
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture BRIEFR table row counts manifest")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL DSN (default: DATABASE_URL)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON manifest path",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    manifest = asyncio.run(_collect(args.database_url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
