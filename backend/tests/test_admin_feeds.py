"""Tests for /api/admin/feeds/* endpoints — circuit breaker reset."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    db_path = tmp_path / "feeds.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_ADMIN_API_KEY", "")

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    return TestClient(app, raise_server_exceptions=False)


def test_reset_circuit_unknown_source_returns_404(admin_client):
    resp = admin_client.post("/api/admin/feeds/nonexistent_source_xyz/reset-circuit", json={})
    assert resp.status_code == 404


def test_reset_circuit_on_open_circuit(admin_client, monkeypatch):
    import resilient_client as rc

    # Use monkeypatch.setitem so the dict entry is automatically restored even
    # if an assertion fails before we reach cleanup.
    monkeypatch.setitem(rc._health, "test_source", {
        "last_success": None,
        "last_failure": 1.0,
        "last_error": "connection refused",
        "consecutive_failures": 5,
        "circuit_open_until": 9999999999.0,
    })

    resp = admin_client.post("/api/admin/feeds/test_source/reset-circuit", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True

    # Verify circuit is reset
    state = rc._health["test_source"]
    assert state["circuit_open_until"] == 0.0
    assert state["consecutive_failures"] == 0


def test_reset_circuit_resets_to_healthy_state(admin_client, monkeypatch):
    import resilient_client as rc
    import time

    monkeypatch.setitem(rc._health, "nvd", {
        "last_success": None,
        "last_failure": time.time(),
        "last_error": "timeout",
        "consecutive_failures": 10,
        "circuit_open_until": time.time() + 60,
    })

    resp = admin_client.post("/api/admin/feeds/nvd/reset-circuit", json={})
    assert resp.status_code == 200

    state = rc._health.get("nvd", {})
    assert state.get("circuit_open_until", 0) == 0.0
    assert state.get("consecutive_failures") == 0


def test_webhooks_log_returns_ok(admin_client):
    resp = admin_client.get("/api/admin/webhooks/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert "total" in data
    assert isinstance(data["rows"], list)
