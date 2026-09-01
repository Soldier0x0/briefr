"""App-level database exceptions — replacements for asyncpg types.

Callers outside ``db/`` must catch ``DatabaseError`` / ``DatabaseLockedError``,
not ``asyncpg.*``.
"""

from __future__ import annotations

from typing import TypeVar

_T = TypeVar("_T", bound=BaseException)


class DatabaseError(Exception):
    """Unified failure from PostgreSQL (asyncpg)."""


class DatabaseLockedError(DatabaseError):
    """Retryable lock / contention (Postgres deadlocks)."""


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
    """Map asyncpg failures to app-level types; pass through existing."""
    if isinstance(exc, DatabaseError):
        return exc
    if isinstance(exc, TimeoutError):
        return DatabaseError("Database command timeout")
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
