#!/usr/bin/env python3
"""Erase a built-in app login account and all data tied to it (sessions,
preferences, IOC watchlist, notifications). Never exposed over HTTP — user
lifecycle management is CLI-only by design (see scripts/create_user.py).

This is the operational counterpart to a data-subject erasure request: an
operator can run this to honor a "delete my account" request without a
manual SQL query.

Usage:
    python3 scripts/delete_user.py --username ops
    python3 scripts/delete_user.py --username ops --yes
"""
from __future__ import annotations

import argparse
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
        "Could not import aiosqlite. Run with the app venv:\n"
        "  /opt/briefr/venv/bin/python3 /opt/briefr/backend/scripts/delete_user.py",
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

from auth.repo import count_users, delete_user, get_user_by_username
from database import get_db, init_db


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Login username to erase")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt",
    )
    args = parser.parse_args()

    await init_db()
    db = await get_db()
    try:
        user = await get_user_by_username(db, args.username)
        if user is None:
            print(f"No such user '{args.username}'.", file=sys.stderr)
            sys.exit(1)

        if not args.yes:
            confirm = input(
                f"Erase user '{user['username']}' (id={user['id']}) and all "
                "sessions/preferences/watchlist/notifications tied to it? "
                "This cannot be undone. Type 'yes' to continue: "
            )
            if confirm.strip().lower() != "yes":
                print("Aborted.", file=sys.stderr)
                sys.exit(1)

        if await count_users(db) <= 1:
            print(
                "Refusing to delete the last remaining account — this would "
                "lock the instance out entirely. Create another account first.",
                file=sys.stderr,
            )
            sys.exit(1)

        await delete_user(db, user["id"])
        await db.commit()
        print(f"Erased user '{user['username']}' (id={user['id']}).")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
