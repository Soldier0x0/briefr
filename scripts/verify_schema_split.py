#!/usr/bin/env python3
"""Verify intel/app schema split and row-count parity after Alembic 036.

Run once immediately after ``alembic upgrade head`` on production:

  python scripts/verify_schema_split.py --manifest pre-036.json

Exits non-zero when tables are mis-placed or row counts differ from the
pre-migration manifest captured by ``schema_row_counts.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from db.config import postgres_dsn  # noqa: E402
from db.schema_inventory import (  # noqa: E402
    APP_TABLES,
    INTEL_TABLES,
    PUBLIC_INFRA_TABLES,
)

_ALL_CLASSIFIED = (*INTEL_TABLES, *APP_TABLES)


async def _verify(database_url: str, manifest: dict) -> list[str]:
    import asyncpg

    errors: list[str] = []
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
        if not split:
            errors.append("intel.cves not found — schema split migration 036 not applied")
            return errors

        for table in INTEL_TABLES:
            in_intel = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'intel' AND table_name = $1
                )
                """,
                table,
            )
            in_public = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                )
                """,
                table,
            )
            if not in_intel:
                errors.append(f"intel table missing: intel.{table}")
            if in_public:
                errors.append(f"intel table still in public: {table}")

        for table in APP_TABLES:
            in_app = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'app' AND table_name = $1
                )
                """,
                table,
            )
            in_public = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                )
                """,
                table,
            )
            if not in_app:
                errors.append(f"app table missing: app.{table}")
            if in_public and table not in PUBLIC_INFRA_TABLES:
                errors.append(f"app table still in public: {table}")

        public_tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        allowed_public = PUBLIC_INFRA_TABLES
        for row in public_tables:
            name = row["table_name"]
            if name.startswith("procrastinate_"):
                continue
            if name not in allowed_public and name not in {t for t in _ALL_CLASSIFIED}:
                # extensions / unknown — only flag classified tables left behind
                if name in INTEL_TABLES or name in APP_TABLES:
                    errors.append(f"classified table still in public: {name}")

        expected = manifest.get("tables") or {}
        for table, expected_count in expected.items():
            if expected_count < 0:
                continue
            if table in INTEL_TABLES:
                qualified = f"intel.{table}"
            elif table in APP_TABLES:
                qualified = f"app.{table}"
            elif table == "alembic_version":
                qualified = "public.alembic_version"
            else:
                continue
            try:
                actual = int(await conn.fetchval(f"SELECT COUNT(*) FROM {qualified}"))
            except asyncpg.UndefinedTableError:
                errors.append(f"count check: table missing {qualified}")
                continue
            if actual != expected_count:
                errors.append(
                    f"row count mismatch for {table}: expected {expected_count}, got {actual}"
                )
    finally:
        await conn.close()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify intel/app schema split")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL DSN (default: DATABASE_URL)",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Pre-migration manifest from schema_row_counts.py",
    )
    args = parser.parse_args()
    if not args.database_url.strip():
        print("ERROR: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1
    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = asyncio.run(_verify(args.database_url, manifest))
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("OK: schema split verified — table placement and row counts match manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
