"""Admin instance typography default."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db
from preferences.display_validate import INSTANCE_TYPOGRAPHY_SETTING_KEY
from tests.conftest import run_db_test


@pytest.fixture
def client(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "typography_default.db"
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

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _login(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert res.status_code == 200


def test_instance_typography_default_round_trip(client):
    _login(client)
    put = client.put(
        "/api/admin/display/typography-default",
        json={"typography_px": {"body": 15, "title": 18}},
    )
    assert put.status_code == 200
    assert put.json()["typography_px"]["body"] == 15

    get = client.get("/api/admin/display/typography-default")
    assert get.status_code == 200
    assert get.json()["typography_px"]["body"] == 15

    prefs = client.get("/api/me/preferences")
    assert prefs.status_code == 200
    assert prefs.json()["instance_typography_default"]["body"] == 15

    async def _read_setting():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT value FROM app_settings WHERE key = ?",
                (INSTANCE_TYPOGRAPHY_SETTING_KEY,),
            )
            return json.loads(rows[0]["value"]) if rows else None
        finally:
            await db.close()

    stored = run_db_test(_read_setting())
    assert stored["title"] == 18
