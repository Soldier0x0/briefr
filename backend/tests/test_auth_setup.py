"""Tests for the first-run setup flow: GET/POST /api/auth/setup-required, /setup."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    """Same as test_auth_router.py's `client` fixture, but with zero users seeded."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_ADMIN_API_KEY", "")

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    monkeypatch.setattr(_settings, "jwt_secret", "test-secret-for-unit-tests")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)
    _rl.login_bucket._buckets.clear()
    _rl.login_email_bucket._buckets.clear()
    _rl.auth_refresh_bucket._buckets.clear()

    from main import app
    return TestClient(app, raise_server_exceptions=False)


def test_setup_required_true_when_no_users(empty_client):
    resp = empty_client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json() == {"required": True}


def test_setup_required_false_once_user_exists(empty_client):
    async def _seed():
        db = await get_db()
        try:
            await create_user(db, "ops@example.com", "correct-horse-battery", role="admin")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(_seed())

    resp = empty_client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json() == {"required": False}


def test_setup_creates_account_and_signs_in(empty_client):
    resp = empty_client.post(
        "/api/auth/setup",
        json={"email": "ops@example.com", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"email": "ops@example.com", "role": "admin"}
    assert "briefr_at" in resp.cookies
    assert "briefr_rt" in resp.cookies

    me = empty_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ops@example.com"


def test_setup_rejected_once_a_user_already_exists(empty_client):
    first = empty_client.post(
        "/api/auth/setup",
        json={"email": "ops@example.com", "password": "correct-horse-battery"},
    )
    assert first.status_code == 200

    second = empty_client.post(
        "/api/auth/setup",
        json={"email": "someone-else@example.com", "password": "another-pass"},
    )
    assert second.status_code == 409


def test_setup_rejects_short_password(empty_client):
    resp = empty_client.post(
        "/api/auth/setup",
        json={"email": "ops@example.com", "password": "short"},
    )
    assert resp.status_code == 400
