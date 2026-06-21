"""Tests for /api/admin/config endpoints."""

import asyncio
import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    db_path = tmp_path / "config.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_ADMIN_API_KEY", "")
    monkeypatch.setenv("NVD_API_KEY", "supersecretkey1234")
    monkeypatch.setenv("VIRUSTOTAL_API_KEY", "")

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    # apply-all/restart schedule trigger_graceful_restart as a background task,
    # which TestClient runs synchronously within the request — a real
    # os.kill(SIGTERM) here would kill the test process itself. Neutralize it.
    import routers.admin as _admin_mod
    monkeypatch.setattr(_admin_mod, "trigger_graceful_restart", _noop_async)

    asyncio.run(init_db())

    # Disable rate limiting so tests don't hit 429
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    return TestClient(app, raise_server_exceptions=False)


def test_config_api_keys_are_masked(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data["api_keys"]

    # Each key must be masked or 'not configured'
    masked_pattern = re.compile(r"^…\w{6}$")
    for key, val in api_keys.items():
        assert val == "not configured" or masked_pattern.match(val), (
            f"Key {key!r} not properly masked: {val!r}"
        )


def test_config_no_full_key_values(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data["api_keys"]

    # The NVD_API_KEY was set to "supersecretkey1234" — should only show last 6 chars
    nvd_val = api_keys.get("NVD_API_KEY", "")
    assert "supersecretkey" not in nvd_val
    # Should be masked
    assert nvd_val == "…ey1234"


def test_admin_key_not_in_response(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()

    def _flatten(d, path=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield from _flatten(v, f"{path}.{k}" if path else k)
        elif isinstance(d, list):
            for item in d:
                yield from _flatten(item, path)
        else:
            yield path, d

    for path, val in _flatten(data):
        assert "BRIEFR_ADMIN_API_KEY" not in path, f"Admin key path found: {path}"


def test_config_set_allowlisted_key(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config",
            json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "2"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["key"] == "NVD_SYNC_INTERVAL_HOURS"


def test_config_set_non_integer_for_integer_key(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "not_a_number"},
    )
    assert resp.status_code == 400


def test_config_set_non_allowlisted_key(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "SECRET_KEY", "value": "anything"},
    )
    assert resp.status_code == 400


def test_config_set_admin_key_rejected(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "BRIEFR_ADMIN_API_KEY", "value": "hacked"},
    )
    assert resp.status_code == 400


def test_apply_all_non_allowlisted_key_returns_400(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config/apply-all",
            json=[{"key": "SECRET_UNALLOWED_KEY", "value": "anything"}],
        )
    assert resp.status_code == 400


def test_apply_all_writes_allowed_key(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key") as mock_set_key:
        # We expect a restart to be triggered too, but background_tasks won't actually run in test
        resp = admin_client.post(
            "/api/admin/config/apply-all",
            json=[{"key": "NVD_SYNC_INTERVAL_HOURS", "value": "3"}],
        )
    # Should return 202 (accepted, restart queued) or 200
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert data["ok"] is True
    assert "NVD_SYNC_INTERVAL_HOURS" in data["changed_keys"]


def test_apply_all_empty_body_returns_no_changes(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    resp = admin_client.post("/api/admin/config/apply-all", json=[])
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["changed_keys"] == []


def test_api_keys_never_returned_full_value(admin_client):
    """No API key should be returned in cleartext — only masked or not configured."""
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data.get("api_keys", {})

    for key, val in api_keys.items():
        # Must be masked format or "not configured"
        assert val in ("not configured",) or val.startswith("…"), (
            f"Key {key!r} looks like it may be unmasked: {val!r}"
        )
