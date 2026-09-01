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
    client.cookies.clear()
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

def test_put_stack_preserves_profile_when_omitted(client):
    _login(client)
    profile = {
        "version": 1,
        "operatingSystems": [{"product": "Ubuntu", "version": "22.04", "vendor": "Canonical"}],
        "applications": [],
        "environment": {"internetFacing": "Some", "industry": "Technology", "criticality": "Medium"},
        "aiSystems": [],
    }
    client.put(
        "/api/me/stack",
        json={"stack_terms": "nginx", "profile": profile},
    )
    updated = client.put("/api/me/stack", json={"stack_terms": "apache"})
    assert updated.status_code == 200
    body = updated.json()
    assert body["stack_terms"] == "apache"
    assert body["profile"]["operatingSystems"][0]["product"] == "Ubuntu"

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

def test_put_stack_rejects_oversized_profile(client):
    _login(client)
    huge = {"version": 1, "aiSystems": ["x" * 70000]}
    res = client.put("/api/me/stack", json={"stack_terms": "nginx", "profile": huge})
    assert res.status_code == 422

def test_effective_stack_terms_prefers_env(client, monkeypatch):
    from preferences.repo import get_effective_stack_terms
    from database import get_db
    from tests.conftest import run_db_test

    monkeypatch.setenv("BRIEFR_STACK_TERMS", "env-term")

    async def run():
        db = await get_db()
        try:
            return await get_effective_stack_terms(db)
        finally:
            await db.close()

    assert run_db_test(run()) == "env-term"

def test_effective_stack_terms_does_not_use_user_prefs(tmp_path, monkeypatch, client):
    from preferences.repo import get_effective_stack_terms
    from database import get_db
    from tests.conftest import run_db_test

    monkeypatch.delenv("BRIEFR_STACK_TERMS", raising=False)
    _login(client)
    client.put("/api/me/stack", json={"stack_terms": "saved-stack", "profile": None})

    async def run():
        db = await get_db()
        try:
            return await get_effective_stack_terms(db)
        finally:
            await db.close()

    assert run_db_test(run()) == ""

def test_alert_stack_assets_from_admin_terms(client, monkeypatch):
    from preferences.repo import get_alert_stack_assets
    from database import get_db
    from tests.conftest import run_db_test

    monkeypatch.delenv("BRIEFR_STACK_TERMS", raising=False)
    _login(client)
    client.put("/api/me/stack", json={"stack_terms": "nginx", "profile": None})

    async def run():
        db = await get_db()
        try:
            return await get_alert_stack_assets(db)
        finally:
            await db.close()

    assert run_db_test(run()) == [{"product": "nginx", "vendor": "", "version": ""}]
