"""Tests for GET /api/admin/system."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "system.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

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
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("briefr_at", auth_token())
    return client


def test_system_returns_200_with_keys(admin_client):
    resp = admin_client.get("/api/admin/system")
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = [
        "cve_count", "last_nvd_sync_age_seconds", "last_backup_age_seconds",
        "backup_threshold_seconds", "disk_free_bytes", "disk_total_bytes",
        "db_integrity", "scheduler_jobs", "feeds", "open_circuit_count",
        "refresh_in_progress", "epss_backfill_done", "version", "failed_auth_last_24h",
    ]
    for key in expected_keys:
        assert key in data, f"Missing key: {key}"


def test_cve_count_is_int(admin_client):
    resp = admin_client.get("/api/admin/system")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["cve_count"], int)
    assert data["cve_count"] >= 0


def test_db_integrity_is_bool(admin_client):
    resp = admin_client.get("/api/admin/system")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["db_integrity"]["ok"], bool)


def test_refresh_in_progress_is_bool(admin_client):
    resp = admin_client.get("/api/admin/system")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["refresh_in_progress"], bool)


def test_failed_auth_is_int(admin_client):
    resp = admin_client.get("/api/admin/system")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["failed_auth_last_24h"], int)
