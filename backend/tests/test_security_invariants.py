"""Sprint A0 security invariants.

Every admin-gated route — the /api/admin router (router-level dependency)
AND the five /api/refresh* routes (inline require_admin calls) — must
reject unauthenticated callers with 401 and non-admin roles with 403.
Routes are enumerated from the routers themselves so new admin endpoints
are covered automatically; never hand-list them here.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


def _protected_routes():
    """(method, concrete_path) for every route behind require_admin."""
    from routers.admin import router as admin_router
    from routers.refresh import router as refresh_router

    routes = []
    for router in (admin_router, refresh_router):
        for route in router.routes:
            path = re.sub(r"\{[^}]+\}", "1", route.path)
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                routes.append((method, path))
    return routes


PROTECTED_ROUTES = _protected_routes()


def test_route_enumeration_finds_admin_and_refresh_routes():
    """Guard the guard: enumeration must cover both protected surfaces."""
    paths = {p for _, p in PROTECTED_ROUTES}
    assert any(p.startswith("/api/admin") for p in paths)
    assert "/api/refresh" in paths
    assert len(PROTECTED_ROUTES) > 40


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "security_invariants.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    from database import get_db, init_db
    from tests.conftest import run_db_test

    run_db_test(init_db())

    async def seed_user() -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (1, 'pytest-admin', 'hash', 'admin', 1)
                """
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed_user())

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(autouse=True)
def _reset_user_role(client):
    from database import get_db
    from tests.conftest import run_db_test

    async def reset() -> None:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET role = 'admin', is_active = 1 WHERE id = 1"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(reset())


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_admin_routes_reject_unauthenticated(client, method, path):
    resp = client.request(method, path, json={})
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, want 401"


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_admin_routes_reject_non_admin_role(client, auth_token, method, path):
    from database import get_db
    from tests.conftest import run_db_test

    async def demote() -> None:
        db = await get_db()
        try:
            await db.execute("UPDATE users SET role = 'analyst' WHERE id = 1")
            await db.commit()
        finally:
            await db.close()

    run_db_test(demote())
    client.cookies.set("briefr_at", auth_token(role="analyst"))
    resp = client.request(method, path, json={})
    assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}, want 403"


def test_admin_routes_reject_demoted_admin_jwt(client, auth_token):
    """JWT may still claim admin after DB role demotion — must 403 immediately."""
    from database import get_db
    from tests.conftest import run_db_test

    async def demote() -> None:
        db = await get_db()
        try:
            await db.execute("UPDATE users SET role = 'analyst' WHERE id = 1")
            await db.commit()
        finally:
            await db.close()

    run_db_test(demote())
    client.cookies.set("briefr_at", auth_token(role="admin"))
    resp = client.get("/api/admin/system")
    assert resp.status_code == 403


def test_login_failure_body_stays_generic(client):
    """Exact-message check for the login endpoint only — admin routes return
    'Not authenticated' / 'Admin access required' instead."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "definitely-wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid username or password"}
