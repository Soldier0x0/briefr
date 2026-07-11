"""Tests for /api/auth/login, /logout, /refresh, /me."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.no_auth

from auth.repo import create_user
from database import get_db, init_db
from tests.conftest import run_db_test


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    # Seeding happens before the TestClient/lifespan below creates the
    # schema, so create it explicitly first (no-op on Postgres — already
    # migrated by the session fixture; creates tables on a fresh SQLite file).
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
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    monkeypatch.setattr(_settings, "jwt_secret", "test-secret-for-unit-tests")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)
    _rl.login_bucket._buckets.clear()
    _rl.login_username_bucket._buckets.clear()
    _rl.auth_refresh_bucket._buckets.clear()

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_login_succeeds_with_correct_credentials(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"username": "ops", "role": "admin"}
    assert "briefr_at" in resp.cookies
    assert "briefr_rt" in resp.cookies


def test_login_fails_with_wrong_password(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_rejects_malformed_username_with_generic_error(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "bad name!", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_login_fails_for_unknown_username(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever12"},
    )
    assert resp.status_code == 401


def test_login_rate_limited_per_ip(client, monkeypatch):
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", True)
    monkeypatch.setattr(_settings, "rate_limit_login_per_minute", 2)

    import rate_limit as _rl
    _rl.login_bucket.rate_per_minute = 2
    _rl.login_bucket.capacity = 2.0
    _rl.login_bucket.refill_per_second = 2 / 60.0
    _rl.login_bucket._buckets.clear()

    for _ in range(2):
        client.post(
            "/api/auth/login",
            json={"username": "ops", "password": "wrong-password"},
        )
    resp = client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "wrong-password"},
    )
    assert resp.status_code == 429


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_rejects_legacy_jwt_missing_username(client, monkeypatch):
    import jwt

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "jwt_secret", "test-secret-for-unit-tests")
    legacy_token = jwt.encode(
        {"sub": "1", "email": "ops@example.com", "role": "admin"},
        _settings.jwt_secret,
        algorithm="HS256",
    )
    client.cookies.set("briefr_at", legacy_token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_user_after_login(client):
    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "ops"
    assert body["role"] == "admin"


def test_refresh_rotates_token_and_keeps_session_valid(client):
    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    old_refresh_cookie = client.cookies.get("briefr_rt")

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200
    new_refresh_cookie = client.cookies.get("briefr_rt")
    assert new_refresh_cookie != old_refresh_cookie

    me = client.get("/api/auth/me")
    assert me.status_code == 200


def test_refresh_reuse_of_rotated_token_revokes_all_sessions(client):
    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    old_refresh_cookie = client.cookies.get("briefr_rt")

    client.post("/api/auth/refresh")
    rotated_refresh_cookie = client.cookies.get("briefr_rt")

    # Replay the stale (pre-rotation) refresh token — a theft signal.
    client.cookies.set("briefr_rt", old_refresh_cookie)
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401

    # The rotated session must now be revoked too (all sessions killed).
    client.cookies.set("briefr_rt", rotated_refresh_cookie)
    resp2 = client.post("/api/auth/refresh")
    assert resp2.status_code == 401


def test_logout_clears_cookies_and_revokes_session(client):
    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 401


def test_refresh_rejects_expired_session(client):
    from datetime import datetime, timedelta, timezone

    from auth.tokens import hash_refresh_token

    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    refresh_cookie = client.cookies.get("briefr_rt")

    async def _expire():
        db = await get_db()
        try:
            expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            await db.execute(
                "UPDATE sessions SET expires_at = ? WHERE refresh_token_hash = ?",
                (expired, hash_refresh_token(refresh_cookie)),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_expire())
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_rejects_malformed_expires_at(client):
    from auth.tokens import hash_refresh_token

    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    refresh_cookie = client.cookies.get("briefr_rt")

    async def _corrupt():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE sessions SET expires_at = ? WHERE refresh_token_hash = ?",
                ("not-a-timestamp", hash_refresh_token(refresh_cookie)),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_corrupt())
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_rejects_empty_expires_at(client):
    from auth.tokens import hash_refresh_token

    client.post(
        "/api/auth/login",
        json={"username": "ops", "password": "correct-horse-battery"},
    )
    refresh_cookie = client.cookies.get("briefr_rt")

    async def _clear():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE sessions SET expires_at = ? WHERE refresh_token_hash = ?",
                ("", hash_refresh_token(refresh_cookie)),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_clear())
    assert client.post("/api/auth/refresh").status_code == 401
