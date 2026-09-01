"""Integration tests for wallboard token issuance API (issue #843)."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def _patch_app_lifecycle(monkeypatch) -> None:
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

def _disable_rate_limit(monkeypatch) -> None:
    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.wallboard_bucket._buckets.pop("testclient", None)

@pytest.mark.no_auth
def test_wallboard_auto_token_flow_uses_enabled_default(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "wb-auto.db"
    monkeypatch.setenv("WALLBOARD_TOKEN", "kiosk-secret-token")
    _patch_app_lifecycle(monkeypatch)
    _disable_rate_limit(monkeypatch)

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "wallboard_token", "kiosk-secret-token")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)
    monkeypatch.setattr(_settings, "jwt_secret", "test-jwt-secret")

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        config = client.get("/api/wallboard/config")
        assert config.status_code == 200
        assert config.json()["auto_token_enabled"] is True

        denied = client.get("/api/wallboard")
        assert denied.status_code == 401

        client.cookies.set("briefr_at", auth_token("admin"))
        issued = client.post("/api/wallboard/token")
        assert issued.status_code == 200
        body = issued.json()
        assert body.get("ok") is True
        assert body.get("token", "").startswith("wbiss.")

        ok = client.get("/api/wallboard")
        assert ok.status_code == 200

@pytest.mark.no_auth
def test_wallboard_auto_token_disabled_returns_404(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "wb-auto-off.db"
    _patch_app_lifecycle(monkeypatch)
    _disable_rate_limit(monkeypatch)

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "wallboard_auto_token", False)
    monkeypatch.setattr(_settings, "wallboard_token", "kiosk-secret-token")

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token("admin"))
        issued = client.post("/api/wallboard/token")
        assert issued.status_code == 404
