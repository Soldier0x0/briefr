"""Post-B Phase 2: unified database exceptions."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import SqliteConnection
from db.errors import (
    DatabaseError,
    DatabaseLockedError,
    format_db_exception_message,
    normalize_db_exception,
    reraise_db_exception,
)


def test_normalize_sqlite_locked():
    exc = sqlite3.OperationalError("database is locked")
    out = normalize_db_exception(exc)
    assert isinstance(out, DatabaseLockedError)
    assert "locked" in str(out).lower()


def test_normalize_sqlite_other_operational():
    exc = sqlite3.OperationalError("no such table: missing")
    out = normalize_db_exception(exc)
    assert type(out) is DatabaseError
    assert not isinstance(out, DatabaseLockedError)


def test_normalize_asyncpg_deadlock():
    asyncpg = pytest.importorskip("asyncpg")
    exc = asyncpg.exceptions.DeadlockDetectedError("deadlock")
    out = normalize_db_exception(exc)
    assert isinstance(out, DatabaseLockedError)


def test_normalize_timeout_error():
    out = normalize_db_exception(TimeoutError())
    assert type(out) is DatabaseError
    assert "timeout" in str(out).lower()


def test_format_db_exception_message_timeout():
    wrapped = normalize_db_exception(TimeoutError())
    assert format_db_exception_message(wrapped) == "DatabaseError: Database command timeout"
    assert format_db_exception_message(TimeoutError()) == "TimeoutError: Database command timeout"


def test_reraise_db_exception_preserves_subclass():
    with pytest.raises(DatabaseLockedError, match="busy"):
        reraise_db_exception(sqlite3.OperationalError("database is busy"))


def test_sqlite_connection_translates_locked():
    raw = MagicMock()
    raw.execute = AsyncMock(side_effect=sqlite3.OperationalError("database is locked"))

    async def _run():
        conn = SqliteConnection(raw)
        with pytest.raises(DatabaseLockedError):
            await conn.execute("SELECT 1")

    import asyncio

    asyncio.run(_run())
