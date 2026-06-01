#!/usr/bin/env python3
"""One-shot backfill of has_poc from stored source_urls. Safe to run while backend is up."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import backfill_has_poc, get_db, init_db


async def main() -> None:
    await init_db()
    db = await get_db()
    try:
        count = await backfill_has_poc(db)
        await db.commit()
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS total, SUM(has_poc) AS with_poc FROM cves"
        )
        total = rows[0]["total"]
        with_poc = rows[0]["with_poc"] or 0
        print(f"Marked {count} new PoC rows. Total with PoC: {with_poc}/{total}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
