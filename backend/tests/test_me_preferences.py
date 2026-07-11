"""Tests for GET/PATCH /api/me/preferences (Wave 2 PR 5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db
from tests.conftest import run_db_test


@pytest.fixture
def client(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "me_prefs.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)

    run_db_test(init_db())

    async def _seed_user():
        db = await get_db()
        try:
            await create_user(db, "ops", "correct-horse-battery", role="admin")
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed_user())

    import rate_limit as _rl
    async def _noop_migrations() -> None:
        return None

    monkeypatch.setattr("main.run_postgres_migrations", _noop_migrations)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    monkeypatch.setattr(_settings, "jwt_secret", "test-secret-for-unit-tests")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)
    _rl.login_bucket._buckets.clear()
    _rl.login_username_bucket._buckets.clear()
    _rl.auth_refresh_bucket._buckets.clear()

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _login(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert res.status_code == 200


def test_get_preferences_defaults(client):
    _login(client)
    res = client.get("/api/me/preferences")
    assert res.status_code == 200
    body = res.json()
    assert body["font_scale"] == "medium"
    assert body["density"] == "comfortable"
    assert body["show_technical_ids"] is False
    assert body["poll_interval_seconds"] == 30
    assert body["utc_time"] is False
    assert body["reduce_motion"] is False
    assert body["notification_sound"] is True
    assert body["timezone"] == "UTC"
    assert body["remember_profile_on_server"] is False
    assert body["updated_at"] is None


def test_get_preferences_requires_auth(client):
    client.cookies.clear()
    res = client.get("/api/me/preferences")
    assert res.status_code == 401


def test_patch_preferences_partial_update(client):
    _login(client)
    patch = client.patch(
        "/api/me/preferences",
        json={"font_scale": "large", "timezone": "Asia/Kolkata", "show_technical_ids": True},
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["font_scale"] == "large"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["show_technical_ids"] is True
    assert body["density"] == "comfortable"
    assert body["updated_at"]

    get = client.get("/api/me/preferences")
    assert get.status_code == 200
    saved = get.json()
    assert saved["font_scale"] == "large"
    assert saved["timezone"] == "Asia/Kolkata"


def test_patch_preferences_rejects_empty_body(client):
    _login(client)
    res = client.patch("/api/me/preferences", json={})
    assert res.status_code == 422


def test_patch_preferences_rejects_invalid_timezone(client):
    _login(client)
    res = client.patch("/api/me/preferences", json={"timezone": "Not/A/Zone"})
    assert res.status_code == 422


def test_patch_preferences_remembers_profile_toggle(client):
    _login(client)
    patch = client.patch(
        "/api/me/preferences",
        json={"remember_profile_on_server": True},
    )
    assert patch.status_code == 200
    assert patch.json()["remember_profile_on_server"] is True

    get = client.get("/api/me/preferences")
    assert get.json()["remember_profile_on_server"] is True


def test_patch_preferences_rejects_invalid_font_scale(client):
    _login(client)
    res = client.patch("/api/me/preferences", json={"font_scale": "huge"})
    assert res.status_code == 422
