"""Tests for /api/admin/scheduler/* endpoints."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db, get_db, get_sync_state_value
from tests.conftest import run_db_test


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "scheduler.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    # Disable rate limiting so tests don't hit 429
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def _make_mock_job(job_id, name="Test Job", next_run_time=None, paused=False):
    job = MagicMock()
    job.id = job_id
    job.name = name
    job.next_run_time = None if paused else (next_run_time or MagicMock())
    if not paused and next_run_time is None:
        from datetime import datetime, timezone
        job.next_run_time.astimezone.return_value.isoformat.return_value = "2026-06-20T00:00:00+00:00"
    return job


def test_scheduler_returns_jobs_with_lock_held(admin_client, monkeypatch):
    mock_job = _make_mock_job("nvd_incremental_sync", "NVD Sync")
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [mock_job]

    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.get("/api/admin/scheduler")
        assert resp.status_code == 200
        jobs = resp.json()
        assert isinstance(jobs, list)
        # Each job should have lock_held field
        for job in jobs:
            assert "lock_held" in job
    finally:
        sched_module._scheduler = original


def test_pause_job_persists_to_sync_state(admin_client, monkeypatch, tmp_path):
    db_path = tmp_path / "scheduler.db"

    mock_job = _make_mock_job("nvd_incremental_sync")
    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = mock_job

    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/pause", json={"job_id": "nvd_incremental_sync"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify persisted in sync_state. Run on the TestClient's own portal
        # loop/thread (not a fresh asyncio.run()) — the fixture's pool is
        # already bound there, and a separate event loop can't use it
        # (Postgres).
        async def check():
            db = await get_db()
            try:
                val = await get_sync_state_value(db, "scheduler.paused.nvd_incremental_sync")
                return val
            finally:
                await db.close()

        val = admin_client.portal.call(check)
        assert val == "1"
    finally:
        sched_module._scheduler = original


def test_resume_job_sets_key_to_zero(admin_client, monkeypatch, tmp_path):
    mock_job = _make_mock_job("kev_metadata_sync")
    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = mock_job

    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/resume", json={"job_id": "kev_metadata_sync"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        async def check():
            db = await get_db()
            try:
                val = await get_sync_state_value(db, "scheduler.paused.kev_metadata_sync")
                return val
            finally:
                await db.close()

        val = admin_client.portal.call(check)
        assert val == "0"
    finally:
        sched_module._scheduler = original


def test_pause_all_requires_confirm(admin_client, monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [_make_mock_job("a"), _make_mock_job("b")]
    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/pause-all", json={})
        assert resp.status_code == 400
    finally:
        sched_module._scheduler = original


def test_pause_all_pauses_only_active_jobs(admin_client, monkeypatch):
    active = _make_mock_job("a")
    already_paused = _make_mock_job("b", paused=True)
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [active, already_paused]
    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/pause-all", json={"confirm_text": "pause"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["paused"] == ["a"]
        active.pause.assert_called_once()
        already_paused.pause.assert_not_called()
    finally:
        sched_module._scheduler = original


def test_resume_all_requires_confirm(admin_client, monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [_make_mock_job("a", paused=True)]
    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/resume-all", json={"confirm_text": "wrong"})
        assert resp.status_code == 400
    finally:
        sched_module._scheduler = original


def test_resume_all_resumes_only_paused_jobs(admin_client, monkeypatch):
    paused = _make_mock_job("a", paused=True)
    already_active = _make_mock_job("b")
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [paused, already_active]
    import scheduler as sched_module
    original = sched_module._scheduler
    sched_module._scheduler = mock_scheduler
    try:
        resp = admin_client.post("/api/admin/scheduler/resume-all", json={"confirm_text": "resume"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["resumed"] == ["a"]
        paused.resume.assert_called_once()
        already_active.resume.assert_not_called()
    finally:
        sched_module._scheduler = original


def test_run_unknown_job_returns_400(admin_client):
    resp = admin_client.post("/api/admin/scheduler/run", json={"job_id": "nonexistent_job_xyz"})
    assert resp.status_code == 400


def test_run_locked_job_returns_409(admin_client, monkeypatch):
    import scheduler_locks

    # Simulate the NVD lock being held
    lock = scheduler_locks.get_lock("nvd_incremental_sync")
    original_locked = lock.locked
    lock.locked = lambda: True
    try:
        resp = admin_client.post("/api/admin/scheduler/run", json={"job_id": "nvd_incremental_sync"})
        assert resp.status_code == 409
    finally:
        lock.locked = original_locked


def test_run_disabled_job_returns_400(admin_client, monkeypatch):
    import routers.admin as admin_router

    monkeypatch.setattr(admin_router, "_job_is_disabled", lambda job_id: job_id == "detection_context_sync")
    resp = admin_client.post("/api/admin/scheduler/run", json={"job_id": "detection_context_sync"})
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


def test_run_valid_job_returns_ok(admin_client, monkeypatch):
    import scheduler as sched_module
    import scheduler_locks

    called = []

    async def _mock_run():
        called.append(True)

    monkeypatch.setattr(sched_module, "run_nvd_incremental_sync", _mock_run)
    # Ensure lock is not held
    scheduler_locks.get_lock("nvd_incremental_sync").locked = lambda: False

    resp = admin_client.post("/api/admin/scheduler/run", json={"job_id": "nvd_incremental_sync"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["job_id"] == "nvd_incremental_sync"


def test_last_five_run_history_written_and_trimmed(monkeypatch, tmp_path):
    """_write_job_last_run should store max 5 entries, newest first."""
    import json
    from datetime import datetime, timezone

    db_path = tmp_path / "hist.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    run_db_test(init_db())

    import scheduler as sched_module

    async def _do():
        from database import get_db, get_sync_state_value

        start = datetime.now(timezone.utc)
        for i in range(7):
            await sched_module._write_job_last_run(
                "nvd_incremental_sync",
                start,
                records=i,
                had_error=False,
                error_message="",
            )

        db = await get_db()
        try:
            raw = await get_sync_state_value(db, "scheduler.last_run.nvd_incremental_sync")
        finally:
            await db.close()

        history = json.loads(raw)
        assert isinstance(history, list)
        assert len(history) == 5, f"Expected 5 entries, got {len(history)}"
        # Most recent (records=6) should be first
        assert history[0]["records_upserted"] == 6

    run_db_test(_do())


def test_last_run_history_includes_error_message(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timezone

    db_path = tmp_path / "errhist.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    run_db_test(init_db())

    import scheduler as sched_module

    async def _do():
        from database import get_db, get_sync_state_value

        start = datetime.now(timezone.utc)
        await sched_module._write_job_last_run(
            "kev_metadata_sync",
            start,
            had_error=True,
            error_message="Connection timeout",
        )
        db = await get_db()
        try:
            raw = await get_sync_state_value(db, "scheduler.last_run.kev_metadata_sync")
        finally:
            await db.close()

        history = json.loads(raw)
        assert isinstance(history, list)
        entry = history[0]
        assert entry["had_error"] is True
        assert entry["error_message"] == "Connection timeout"

    run_db_test(_do())
