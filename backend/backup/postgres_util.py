"""PostgreSQL backup helpers (pg_dump / pg_restore) for backup.manager."""

from __future__ import annotations

import asyncio
import glob
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
    """Parse a postgresql:// DSN into pg_dump/pg_restore connection fields.

    Only keys explicitly present in the DSN are returned so libpq can fall back
    to Unix sockets, peer auth, or ~/.pgpass when host/user/port are omitted.
    """
    dsn = postgres_dsn(url)
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"Not a PostgreSQL URL: {url!r}")
    dbname = (parsed.path or "").lstrip("/")
    if not dbname:
        raise ValueError(f"PostgreSQL URL missing database name: {url!r}")

    params: dict[str, str | int] = {"dbname": dbname}
    if parsed.hostname is not None:
        params["host"] = parsed.hostname
    if parsed.port is not None:
        params["port"] = parsed.port
    if parsed.username is not None:
        params["user"] = unquote(parsed.username)
    if parsed.password is not None:
        params["password"] = unquote(parsed.password)
    return params


def _versioned_pg_tool_paths(name: str) -> list[str]:
    def _version_key(path: str) -> int:
        match = re.search(r"/(\d+)/bin/", path)
        return int(match.group(1)) if match else 0

    paths = glob.glob(f"/usr/lib/postgresql/*/bin/{name}")
    return sorted(paths, key=_version_key, reverse=True)


def postgres_server_live(url: str | None = None) -> bool:
    """True when ``url`` (or ``DATABASE_URL``) points at a reachable Postgres server."""
    raw = url if url is not None else os.environ.get("DATABASE_URL", "")
    if not raw.startswith("postgresql"):
        return False

    async def _ping() -> None:
        import asyncpg

        conn = await asyncpg.connect(postgres_dsn(raw), timeout=5)
        await conn.close()

    try:
        asyncio.run(_ping())
        return True
    except Exception:
        return False


def pg_dump_available() -> bool:
    """True when ``pg_dump`` is on PATH or in a Debian versioned client dir."""
    try:
        _pg_tool("pg_dump")
        return True
    except RuntimeError:
        return False


def postgres_backup_tools_available() -> bool:
    """Live Postgres backup round-trip needs both ``pg_dump`` and ``pg_restore``."""
    try:
        _pg_tool("pg_dump")
        _pg_tool("pg_restore")
        return True
    except RuntimeError:
        return False


def _pg_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    # Debian/Ubuntu postgresql-client-N installs under /usr/lib/postgresql/N/bin
    # without always symlinking into PATH.
    for candidate in _versioned_pg_tool_paths(name):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(
        f"{name} not found on PATH — install postgresql-client "
        "(e.g. apt install postgresql-client or postgresql-client-16)"
    )


def _subprocess_env(params: dict[str, str | int]) -> dict[str, str]:
    env = os.environ.copy()
    password = params.get("password")
    if password:
        env["PGPASSWORD"] = str(password)
    else:
        env.pop("PGPASSWORD", None)
    return env


def _build_pg_cmd(
    tool: str,
    params: dict[str, str | int],
    *,
    extra_args: list[str],
) -> list[str]:
    cmd = [_pg_tool(tool)]
    if "host" in params:
        cmd.extend(["-h", str(params["host"])])
    if "port" in params:
        cmd.extend(["-p", str(params["port"])])
    if "user" in params:
        cmd.extend(["-U", str(params["user"])])
    cmd.extend(["-d", str(params["dbname"])])
    cmd.extend(extra_args)
    return cmd


def run_pg_dump(database_url: str, destination: Path) -> None:
    """Create a custom-format pg_dump at destination."""
    params = parse_postgres_url(database_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = _build_pg_cmd(
        "pg_dump",
        params,
        extra_args=[
            "--format=custom",
            "--no-owner",
            "--no-acl",
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


def run_pg_restore(database_url: str, dump_path: Path) -> None:
    """Restore a custom-format dump into the target database (--clean --if-exists)."""
    params = parse_postgres_url(database_url)
    if not dump_path.is_file():
        raise FileNotFoundError(f"pg_dump archive not found: {dump_path}")
    cmd = _build_pg_cmd(
        "pg_restore",
        params,
        extra_args=[
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            str(dump_path),
        ],
    )
    proc = subprocess.run(
        cmd,
        env=_subprocess_env(params),
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
    try:
        with path.open("rb") as handle:
            header = handle.read(len(PGDUMP_MAGIC))
        if header != PGDUMP_MAGIC:
            return False, "not a PostgreSQL custom-format dump"
    except OSError as exc:
        return False, f"failed to read file: {exc}"
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
