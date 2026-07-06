"""Tests for the destructive_actions registry and its wiring into admin routes."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db
from destructive_actions import get_action, list_actions, require_confirm


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "destructive.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

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
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("briefr_at", auth_token())
    return client


def test_require_confirm_passes_with_correct_word():
    require_confirm("watchlist.clear_snoozes", "clear")  # should not raise


def test_require_confirm_raises_with_wrong_word():
    with pytest.raises(ValueError, match="clear"):
        require_confirm("watchlist.clear_snoozes", "wrong")


def test_require_confirm_noop_for_no_confirm_word_action():
    require_confirm("storage.purge.epss_backfill_reset", "")  # should not raise


def test_get_action_returns_none_for_unknown_id():
    assert get_action("not.a.real.action") is None


def test_list_actions_shape():
    actions = list_actions()
    assert actions
    ids = {a["id"] for a in actions}
    assert "watchlist.clear_snoozes" in ids
    assert "scheduler.pause_all" in ids
    sample = next(a for a in actions if a["id"] == "watchlist.clear_snoozes")
    assert sample["confirm_word"] == "clear"
    assert "description" in sample


def test_destructive_actions_endpoint_returns_registry(admin_client):
    resp = admin_client.get("/api/admin/destructive-actions")
    assert resp.status_code == 200
    ids = {a["id"] for a in resp.json()}
    assert "scheduler.resume_all" in ids
    assert "system.restart" in ids


def test_clear_snoozes_requires_confirm(admin_client):
    resp = admin_client.post("/api/admin/watchlist/clear-snoozes", json={})
    assert resp.status_code == 400


def test_clear_snoozes_succeeds_with_confirm(admin_client):
    resp = admin_client.post("/api/admin/watchlist/clear-snoozes", json={"confirm_text": "clear"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_restart_requires_confirm(admin_client):
    resp = admin_client.post("/api/admin/restart", json={})
    assert resp.status_code == 400


def test_drain_restart_does_not_require_confirm(admin_client, monkeypatch):
    async def _noop(*args, **kwargs):
        return None
    monkeypatch.setattr("routers.admin.trigger_graceful_restart", _noop)
    resp = admin_client.post("/api/admin/restart", json={"drain": True})
    assert resp.status_code == 202
