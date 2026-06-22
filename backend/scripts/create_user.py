#!/usr/bin/env python3
"""Create or reset a built-in app login account. Never exposed over HTTP —
this is the only way accounts get provisioned (decision 2026-06-11).

Usage:
    python3 scripts/create_user.py --username ops
    python3 scripts/create_user.py --username ops --password 'hunter2' --non-interactive
"""
from __future__ import annotations

import argparse
import getpass
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
        "  /opt/briefr/venv/bin/python3 /opt/briefr/backend/scripts/create_user.py",
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

from auth.passwords import validate_password_strength
from auth.repo import create_user, get_user_by_username
from auth.usernames import validate_username
from database import get_db, init_db


def _read_password(non_interactive_value: str | None) -> str:
    if non_interactive_value is not None:
        try:
            validate_password_strength(non_interactive_value)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        return non_interactive_value
    while True:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match, try again.", file=sys.stderr)
            continue
        try:
            validate_password_strength(password)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            continue
        return password


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument(
        "--password",
        default=None,
        help="Password (omit to be prompted interactively via getpass)",
    )
    parser.add_argument("--role", default="admin", help="Account role (default: admin)")
    args = parser.parse_args()

    try:
        username = validate_username(args.username)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    password = _read_password(args.password)

    await init_db()
    db = await get_db()
    try:
        existing = await get_user_by_username(db, username)
        user = await create_user(db, username, password, role=args.role)
        await db.commit()
        verb = "Reset password for" if existing else "Created"
        print(f"{verb} user '{user['username']}' (id={user['id']}, role={user['role']}).")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
