"""Tests for the first-run setup flow: GET/POST /api/auth/setup-required, /setup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db
from tests.conftest import run_db_test


def _disable_rate_limiting(monkeypatch):
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    monkeypatch.setattr(_settings, "jwt_secret", "test-secret-for-unit-tests")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)
    _rl.login_bucket._buckets.clear()
    _rl.login_username_bucket._buckets.clear()
    _rl.auth_refresh_bucket._buckets.clear()


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    """Same as test_auth_router.py's `client` fixture, but with zero users seeded."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    _disable_rate_limiting(monkeypatch)

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_setup_required_true_when_no_users(empty_client):
    resp = empty_client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json() == {"required": True}


def test_setup_required_false_once_user_exists(tmp_path, monkeypatch):
    # Self-contained (not `empty_client`): seeds a user before the TestClient
    # opens, since a direct asyncio.run() DB call can't share a pool that's
    # already bound to the TestClient's own event loop (Postgres).
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _disable_rate_limiting(monkeypatch)

    run_db_test(init_db())

    async def _seed():
        db = await get_db()
        try:
            await create_user(db, "ops", "correct-horse-battery", role="admin")
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json() == {"required": False}


def test_setup_creates_account_and_signs_in(empty_client):
    resp = empty_client.post(
        "/api/auth/setup",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"username": "ops", "role": "admin"}
    assert "briefr_at" in resp.cookies
    assert "briefr_rt" in resp.cookies

    me = empty_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "ops"


def test_setup_rejected_once_a_user_already_exists(empty_client):
    first = empty_client.post(
        "/api/auth/setup",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert first.status_code == 200

    second = empty_client.post(
        "/api/auth/setup",
        json={"username": "someone", "password": "another-pass"},
    )
    assert second.status_code == 409


def test_setup_rejects_short_password(empty_client):
    resp = empty_client.post(
        "/api/auth/setup",
        json={"username": "ops", "password": "short"},
    )
    assert resp.status_code == 422
