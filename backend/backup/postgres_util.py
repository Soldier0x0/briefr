"""PostgreSQL backup helpers (pg_dump / pg_restore) for backup.manager."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from db.config import postgres_dsn

logger = logging.getLogger(__name__)

PG_DUMP_ARCHIVE_NAME = "briefr.pgdump"
PGDUMP_MAGIC = b"PGDMP"
_REDACT_USERINFO = re.compile(r"(postgresql://)([^:@/]+):([^@/]+)@")


def redact_database_url(url: str) -> str:
    return _REDACT_USERINFO.sub(r"\1\2:***@", url)


def parse_postgres_url(url: str) -> dict[str, str | int]:
    """Parse a postgresql:// DSN into pg_dump/pg_restore connection fields."""
    dsn = postgres_dsn(url)
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"Not a PostgreSQL URL: {url!r}")
    dbname = (parsed.path or "").lstrip("/")
    if not dbname:
        raise ValueError(f"PostgreSQL URL missing database name: {url!r}")
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "dbname": dbname,
    }


def _pg_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(
            f"{name} not found on PATH — install postgresql-client "
            "(e.g. apt install postgresql-client)"
        )
    return path


def _subprocess_env(password: str) -> dict[str, str]:
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    else:
        env.pop("PGPASSWORD", None)
    return env


def run_pg_dump(database_url: str, destination: Path) -> None:
    """Create a custom-format pg_dump at destination."""
    params = parse_postgres_url(database_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _pg_tool("pg_dump"),
        "-h",
        str(params["host"]),
        "-p",
        str(params["port"]),
        "-U",
        str(params["user"]),
        "-d",
        str(params["dbname"]),
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "-f",
        str(destination),
    ]
    proc = subprocess.run(
        cmd,
        env=_subprocess_env(str(params["password"])),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {detail}")


def run_pg_restore(database_url: str, dump_path: Path) -> None:
    """Restore a custom-format dump into the target database (--clean --if-exists)."""
    params = parse_postgres_url(database_url)
    if not dump_path.is_file():
        raise FileNotFoundError(f"pg_dump archive not found: {dump_path}")
    cmd = [
        _pg_tool("pg_restore"),
        "-h",
        str(params["host"]),
        "-p",
        str(params["port"]),
        "-U",
        str(params["user"]),
        "-d",
        str(params["dbname"]),
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        str(dump_path),
    ]
    proc = subprocess.run(
        cmd,
        env=_subprocess_env(str(params["password"])),
        capture_output=True,
        text=True,
        check=False,
    )
    # pg_restore may exit 1 when dropping objects that do not exist — treat stderr-only warnings as ok.
    if proc.returncode not in {0, 1}:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"pg_restore failed (exit {proc.returncode}): {detail}")
    if proc.returncode == 1 and proc.stderr:
        logger.warning("pg_restore completed with warnings: %s", proc.stderr.strip()[:500])


def verify_pg_dump(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "pgdump file does not exist"
    if path.stat().st_size < len(PGDUMP_MAGIC):
        return False, "pgdump file is empty or truncated"
    if path.read_bytes()[: len(PGDUMP_MAGIC)] != PGDUMP_MAGIC:
        return False, "not a PostgreSQL custom-format dump"
    return True, "ok"


def check_postgres_health(database_url: str) -> tuple[bool, str]:
    """Lightweight liveness check before refusing a destructive restore."""
    try:
        import psycopg
    except ImportError as exc:
        return False, f"psycopg not available: {exc}"
    try:
        with psycopg.connect(postgres_dsn(database_url), connect_timeout=10) as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def write_audit_postgres(database_url: str, actor: str, action: str, target: str) -> None:
    """Best-effort audit row for Postgres backup operations."""
    try:
        import psycopg
    except ImportError:
        logger.warning("Audit log write skipped (%s): psycopg not installed", action)
        return
    try:
        with psycopg.connect(postgres_dsn(database_url), connect_timeout=10) as conn:
            conn.execute(
                "INSERT INTO audit_log (actor, action, target) VALUES (%s, %s, %s)",
                (actor, action, target),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Audit log write failed (%s %s): %s", action, target, exc)
