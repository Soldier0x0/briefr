"""Tests for GET/PUT /api/me/stack (Wave 2 PR 3)."""

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

    db_path = tmp_path / "me_stack.db"
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


def test_get_stack_empty_by_default(client):
    _login(client)
    res = client.get("/api/me/stack")
    assert res.status_code == 200
    body = res.json()
    assert body["stack_terms"] == ""
    assert body["profile"] is None
    assert body["updated_at"] is None


def test_get_stack_requires_auth(client):
    res = client.get("/api/me/stack")
    assert res.status_code == 401


def test_put_stack_persists_terms_and_profile(client):
    _login(client)
    profile = {
        "version": 1,
        "operatingSystems": [{"product": "Windows Server", "version": "2022", "vendor": "Microsoft"}],
        "applications": [],
        "environment": {"internetFacing": "Some", "industry": "Technology", "criticality": "Medium"},
        "aiSystems": ["TensorFlow"],
    }
    put = client.put(
        "/api/me/stack",
        json={"stack_terms": " nginx , log4j , ", "profile": profile},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["stack_terms"] == "nginx,log4j"
    assert body["profile"]["aiSystems"] == ["TensorFlow"]
    assert body["updated_at"]

    get = client.get("/api/me/stack")
    assert get.status_code == 200
    saved = get.json()
    assert saved["stack_terms"] == "nginx,log4j"
    assert saved["profile"]["operatingSystems"][0]["product"] == "Windows Server"


def test_put_stack_clear_profile(client):
    _login(client)
    client.put(
        "/api/me/stack",
        json={"stack_terms": "nginx", "profile": {"version": 1, "aiSystems": ["llama"]}},
    )
    cleared = client.put("/api/me/stack", json={"stack_terms": "nginx", "profile": None})
    assert cleared.status_code == 200
    assert cleared.json()["profile"] is None


def test_put_stack_rejects_invalid_profile(client):
    _login(client)
    res = client.put("/api/me/stack", json={"stack_terms": "nginx", "profile": "not-an-object"})
    assert res.status_code == 422
