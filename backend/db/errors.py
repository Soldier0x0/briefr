"""App-level database exceptions — dialect-neutral replacements for sqlite3/asyncpg types.

Post-B Phase 2: callers outside ``db/`` must catch ``DatabaseError`` /
``DatabaseLockedError``, not ``sqlite3.*`` or ``asyncpg.*``.
"""

from __future__ import annotations

import sqlite3
from typing import TypeVar

_T = TypeVar("_T", bound=BaseException)


class DatabaseError(Exception):
    """Unified failure from either SQLite (aiosqlite) or PostgreSQL (asyncpg)."""


class DatabaseLockedError(DatabaseError):
    """Retryable lock / contention (SQLite ``database is locked``, Postgres deadlocks)."""


def _sqlite_locked_message(exc: sqlite3.Error) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def _asyncpg_locked(exc: BaseException) -> bool:
    try:
        import asyncpg
    except ImportError:
        return False
    locked_types = (
        asyncpg.exceptions.DeadlockDetectedError,
        asyncpg.exceptions.LockNotAvailableError,
    )
    return isinstance(exc, locked_types)


def format_db_exception_message(exc: BaseException) -> str:
    """Operator-safe one-line message for logs and notifications."""
    if isinstance(exc, DatabaseError) and str(exc):
        return f"{type(exc).__name__}: {exc}"
    if isinstance(exc, DatabaseError):
        cause = exc.__cause__
        if isinstance(cause, TimeoutError):
            return "DatabaseError: Database command timeout"
        return type(exc).__name__
    if isinstance(exc, TimeoutError):
        return "TimeoutError: Database command timeout"
    if str(exc):
        return f"{type(exc).__name__}: {exc}"
    return type(exc).__name__


def normalize_db_exception(exc: BaseException) -> DatabaseError:
    """Map sqlite3/asyncpg failures to app-level types; pass through existing."""
    if isinstance(exc, DatabaseError):
        return exc
    if isinstance(exc, TimeoutError):
        return DatabaseError("Database command timeout")
    if isinstance(exc, sqlite3.OperationalError):
        if _sqlite_locked_message(exc):
            return DatabaseLockedError(str(exc))
        return DatabaseError(str(exc))
    if isinstance(exc, sqlite3.Error):
        return DatabaseError(str(exc))
    if _asyncpg_locked(exc):
        return DatabaseLockedError(str(exc))
    try:
        import asyncpg
    except ImportError:
        asyncpg = None  # type: ignore[assignment,misc]
    if asyncpg is not None and isinstance(exc, asyncpg.PostgresError):
        return DatabaseError(str(exc))
    return DatabaseError(str(exc))


def reraise_db_exception(exc: BaseException) -> None:
    """Re-raise *exc* as a ``DatabaseError`` subclass when applicable."""
    if isinstance(exc, DatabaseError):
        raise exc
    raise normalize_db_exception(exc) from exc
