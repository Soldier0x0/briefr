"""Tests for /api/admin/scheduler/* endpoints."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db, get_db, get_sync_state_value


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    db_path = tmp_path / "scheduler.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_ADMIN_API_KEY", "")

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    # Disable rate limiting so tests don't hit 429
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    return TestClient(app, raise_server_exceptions=False)


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

        # Verify persisted in sync_state
        async def check():
            db = await get_db()
            try:
                val = await get_sync_state_value(db, "scheduler.paused.nvd_incremental_sync")
                return val
            finally:
                await db.close()

        val = asyncio.run(check())
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

        val = asyncio.run(check())
        assert val == "0"
    finally:
        sched_module._scheduler = original
