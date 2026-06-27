#!/usr/bin/env python3
"""Compare row counts between SQLite briefr.db and PostgreSQL (DATABASE_URL).

Usage (from repo root):
  python scripts/verify_db_parity.py --sqlite backend/briefr.db
  DATABASE_URL=postgresql://... python scripts/verify_db_parity.py --sqlite backend/briefr.db

Exit 0 when all shared tables match; exit 1 on mismatches or connection errors.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from migration.sqlite_to_postgres import TABLE_ORDER  # noqa: E402


async def _sqlite_counts(path: str) -> dict[str, int]:
    import aiosqlite

    counts: dict[str, int] = {}
    async with aiosqlite.connect(path) as db:
        for table in TABLE_ORDER:
            cursor = await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if not await cursor.fetchone():
                counts[table] = 0
                continue
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            counts[table] = int(row[0]) if row else 0
    return counts


async def _postgres_counts(database_url: str) -> dict[str, int]:
    import asyncpg

    from db.config import postgres_dsn

    counts: dict[str, int] = {}
    conn = await asyncpg.connect(dsn=postgres_dsn(database_url), timeout=30)
    try:
        for table in TABLE_ORDER:
            try:
                counts[table] = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))
            except Exception:
                counts[table] = -1
    finally:
        await conn.close()
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQLite → PostgreSQL row parity")
    parser.add_argument(
        "--sqlite",
        default=str(_REPO / "backend" / "briefr.db"),
        help="Path to source SQLite file",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL DSN (default: DATABASE_URL env)",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        print(f"ERROR: SQLite file not found: {sqlite_path}", file=sys.stderr)
        return 1
    if not args.database_url.strip():
        print("ERROR: Set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 1

    sqlite_counts = await _sqlite_counts(str(sqlite_path))
    pg_counts = await _postgres_counts(args.database_url.strip())

    mismatches: list[str] = []
    print(f"{'Table':<32} {'SQLite':>10} {'Postgres':>10}  Status")
    print("-" * 62)
    for table in TABLE_ORDER:
        s = sqlite_counts.get(table, 0)
        p = pg_counts.get(table, -1)
        if p < 0:
            status = "MISSING ON PG"
            mismatches.append(table)
        elif s != p:
            status = "MISMATCH"
            mismatches.append(table)
        else:
            status = "ok"
        print(f"{table:<32} {s:>10} {p:>10}  {status}")

    total_sqlite = sum(sqlite_counts.values())
    total_pg = sum(v for v in pg_counts.values() if v >= 0)
    print("-" * 62)
    print(f"{'TOTAL (all tables)':<32} {total_sqlite:>10} {total_pg:>10}")

    if mismatches:
        print(f"\nFAILED: {len(mismatches)} table(s) differ: {', '.join(mismatches)}", file=sys.stderr)
        return 1

    print("\nOK: PostgreSQL has matching row counts for all migrated tables.")
    if total_pg > total_sqlite:
        print(f"Note: Postgres has {total_pg - total_sqlite} more rows (expected after ongoing ingest).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
