"""PR-O1 / ERR-001: KEV feed failures propagate to scheduler had_error."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.errors import FeedFetchError
from feeds.kev import fetch_kev
from resilient_client import CircuitOpenError
from tests.conftest import run_db_test


def test_fetch_kev_raises_on_circuit_open(monkeypatch):
    async def _boom(*_a, **_k):
        raise CircuitOpenError("kev", 0.0)

    monkeypatch.setattr("feeds.kev.resilient_get", _boom)

    async def _run():
        with pytest.raises(FeedFetchError, match="circuit open"):
            await fetch_kev()

    run_db_test(_run())


def test_fetch_kev_raises_on_empty_catalog(monkeypatch):
    class _Resp:
        def json(self):
            return {"vulnerabilities": []}

    async def _ok(*_a, **_k):
        return _Resp()

    monkeypatch.setattr("feeds.kev.resilient_get", _ok)
    monkeypatch.setattr("feeds.kev.record_api_call", lambda *_a, **_k: None)

    async def _run():
        with pytest.raises(FeedFetchError, match="parsed empty"):
            await fetch_kev()

    run_db_test(_run())


def test_run_kev_sync_sets_had_error_on_fetch_failure(monkeypatch, tmp_path):
    from db import init as db_init_mod
    from scheduler import run_kev_sync

    db_path = tmp_path / "kev_err.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _fail():
        raise FeedFetchError("KEV circuit open")

    monkeypatch.setattr("scheduler.fetch_kev", _fail)
    monkeypatch.setattr("scheduler.get_lock", lambda _id: _NoopLock())
    monkeypatch.setattr(db_init_mod, "is_postgres", lambda url=None: False)

    written: list[dict] = []

    async def _capture(job_id, started_at, *, had_error=False, error_message=""):
        written.append(
            {
                "job_id": job_id,
                "had_error": had_error,
                "error_message": error_message,
            }
        )

    monkeypatch.setattr("scheduler._write_job_last_run", _capture)

    async def _run():
        with pytest.raises(FeedFetchError):
            await run_kev_sync()

    run_db_test(_run())

    assert written
    assert written[-1]["job_id"] == "kev_metadata_sync"
    assert written[-1]["had_error"] is True
    assert "KEV" in written[-1]["error_message"]


class _NoopLock:
    def locked(self):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False
