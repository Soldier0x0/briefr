"""Admin instance UI variant default."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db
from preferences.display_validate import INSTANCE_UI_VARIANT_SETTING_KEY
from tests.conftest import run_db_test

@pytest.fixture
def client(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "ui_variant_default.db"
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))

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

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

def _login(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert res.status_code == 200

def test_instance_ui_variant_default_round_trip(client):
    _login(client)
    put = client.put(
        "/api/admin/display/ui-variant-default",
        json={"ui_variant": "pitch"},
    )
    assert put.status_code == 200
    assert put.json()["ui_variant"] == "pitch"

    get = client.get("/api/admin/display/ui-variant-default")
    assert get.status_code == 200
    assert get.json()["ui_variant"] == "pitch"

    prefs = client.get("/api/me/preferences")
    assert prefs.status_code == 200
    assert prefs.json()["ui_variant"] == "pitch"
    assert prefs.json()["instance_ui_variant_default"] == "pitch"

def test_user_explicit_ui_variant_overrides_instance_default(client):
    _login(client)
    client.put("/api/admin/display/ui-variant-default", json={"ui_variant": "pitch"})
    patch = client.patch("/api/me/preferences", json={"ui_variant": "default"})
    assert patch.status_code == 200
    assert patch.json()["ui_variant"] == "default"
