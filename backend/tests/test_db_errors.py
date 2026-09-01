"""Post-B Phase 2: unified database exceptions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.errors import (
    DatabaseError,
    DatabaseLockedError,
    format_db_exception_message,
    normalize_db_exception,
    reraise_db_exception,
)


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
    asyncpg = pytest.importorskip("asyncpg")
    with pytest.raises(DatabaseLockedError, match="deadlock"):
        reraise_db_exception(asyncpg.exceptions.DeadlockDetectedError("deadlock"))
