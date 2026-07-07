"""Sprint A6 — production posture self-check.

production_posture_warnings() reports every unsafe flag; main.py logs one
warning per entry at startup in production, and GET /api/admin/security
surfaces the same list in the Security panel readout.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from settings import Settings, production_posture_warnings, settings


def test_all_unsafe_flags_reported():
    unsafe = Settings(
        rate_limit_enabled=False,
        auth_cookie_secure=False,
        wallboard_token="",
    )

    warnings = production_posture_warnings(unsafe)

    flags = [w["flag"] for w in warnings]
    assert flags == [
        "RATE_LIMIT_ENABLED=0",
        "AUTH_COOKIE_SECURE=0",
        "WALLBOARD_TOKEN unset",
    ]
    for w in warnings:
        assert w["message"]


def test_safe_configuration_reports_nothing():
    safe = Settings(
        rate_limit_enabled=True,
        auth_cookie_secure=True,
        wallboard_token="kiosk-token",
    )

    assert production_posture_warnings(safe) == []


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "posture.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_security_readout_includes_posture(client, auth_token, monkeypatch):
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    monkeypatch.setattr(settings, "wallboard_token", "")

    client.cookies.set("briefr_at", auth_token(role="admin"))
    resp = client.get("/api/admin/security")

    assert resp.status_code == 200
    body = resp.json()
    assert body["environment"] == settings.briefr_env
    flags = [w["flag"] for w in body["posture_warnings"]]
    # rate limiting is disabled by the fixture, so all three flags trip
    assert flags == [
        "RATE_LIMIT_ENABLED=0",
        "AUTH_COOKIE_SECURE=0",
        "WALLBOARD_TOKEN unset",
    ]
