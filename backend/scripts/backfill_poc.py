#!/usr/bin/env python3
"""One-shot backfill of has_poc from stored source_urls. Safe to run while backend is up."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _reexec_with_venv_python() -> None:
    """Use the same venv as briefr-backend.service when system python lacks deps."""
    try:
        import aiosqlite  # noqa: F401
        return
    except ImportError:
        pass

    candidates: list[Path] = []
    env_venv = os.environ.get("BRIEFR_VENV")
    if env_venv:
        candidates.append(Path(env_venv) / "bin" / "python3")

    backend_dir = Path(__file__).resolve().parents[1]
    install_root = backend_dir.parent
    candidates.extend(
        [
            install_root / "venv" / "bin" / "python3",
            Path("/opt/briefr/venv/bin/python3"),
        ]
    )

    for py in candidates:
        if py.is_file():
            os.execv(str(py), [str(py), *sys.argv])

    print(
        "Could not import aiosqlite. Run with the app venv, for example:\n"
        "  /opt/briefr/venv/bin/python3 /opt/briefr/backend/scripts/backfill_poc.py\n"
        "  /opt/briefr/venv/bin/python3 /opt/briefr/backend/scripts/backfill_poc.py",
        file=sys.stderr,
    )
    sys.exit(1)


_reexec_with_venv_python()

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")

import asyncio

from database import backfill_has_poc, get_db, init_db


async def main() -> None:
    db_path = os.environ.get("DB_PATH", "briefr.db")
    print(f"Using database: {db_path}")

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
