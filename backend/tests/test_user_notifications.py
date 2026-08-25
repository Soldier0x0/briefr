"""Tests for /api/me/notifications inbox (analyst + operator scopes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from auth.repo import create_user
from database import get_db, init_db
from db.user_notifications import insert_notification
from tests.conftest import run_db_test

pytestmark = pytest.mark.no_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "user_notifications.db"
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

    async def _seed_users():
        db = await get_db()
        try:
            await create_user(db, "admin1", "correct-horse-battery", role="admin")
            await create_user(db, "analyst1", "correct-horse-battery", role="analyst")
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed_users())

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


def _login(client, username="admin1"):
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "correct-horse-battery"},
    )
    assert res.status_code == 200


def _user_id(username: str) -> int:
    async def _lookup():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            )
            return int(rows[0]["id"])
        finally:
            await db.close()

    return run_db_test(_lookup())


def _insert(user_id: int, scope: str, *, severity: str = "high", dedupe: str):
    async def _do():
        db = await get_db()
        try:
            await insert_notification(
                db,
                user_id=user_id,
                scope=scope,
                category="test",
                severity=severity,
                title=f"Alert {dedupe}",
                body="detail",
                dedupe_key=dedupe,
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_do())


def test_notifications_require_auth(client):
    res = client.get("/api/me/notifications")
    assert res.status_code == 401


def test_analyst_scope_lists_and_counts_unread(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="a1")
    _insert(uid, "analyst", severity="low", dedupe="a2")

    _login(client, "analyst1")
    res = client.get("/api/me/notifications?scope=analyst")
    assert res.status_code == 200
    body = res.json()
    assert len(body["notifications"]) == 2
    assert body["unread_count"] == 2

    seen = client.post("/api/me/notifications/seen", json={"scope": "analyst"})
    assert seen.status_code == 200
    seen_body = seen.json()
    assert seen_body["marked_seen"] == 2
    assert seen_body["unread_count"] == 0

    after = client.get("/api/me/notifications?scope=analyst")
    assert after.json()["unread_count"] == 0
    assert len(after.json()["notifications"]) == 2


def test_list_view_done_excludes_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="d1")
    _login(client, "analyst1")
    listed = client.get("/api/me/notifications?scope=analyst").json()
    nid = listed["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")
    inbox = client.get("/api/me/notifications?scope=analyst&view=inbox").json()
    done = client.get("/api/me/notifications?scope=analyst&view=done").json()
    assert inbox["notifications"] == []
    assert len(done["notifications"]) == 1
    assert done["unread_count"] == 0


def test_list_view_aliases_active_cleared(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="alias1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications?scope=analyst").json()["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")

    active = client.get("/api/me/notifications?scope=analyst&view=active").json()
    inbox = client.get("/api/me/notifications?scope=analyst&view=inbox").json()
    cleared = client.get("/api/me/notifications?scope=analyst&view=cleared").json()
    done = client.get("/api/me/notifications?scope=analyst&view=done").json()

    assert active["notifications"] == []
    assert inbox["notifications"] == []
    assert len(cleared["notifications"]) == 1
    assert len(done["notifications"]) == 1
    assert cleared["unread_count"] == 0


def test_list_view_rejects_unknown(client):
    _login(client, "analyst1")
    res = client.get("/api/me/notifications?scope=analyst&view=archive")
    assert res.status_code == 422


def test_dismiss_one_and_dismiss_all(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="d1")
    _insert(uid, "analyst", dedupe="d2")

    _login(client, "analyst1")
    listed = client.get("/api/me/notifications?scope=analyst").json()
    first_id = listed["notifications"][0]["id"]

    dismiss = client.post(f"/api/me/notifications/{first_id}/dismiss")
    assert dismiss.status_code == 200

    remaining = client.get("/api/me/notifications?scope=analyst").json()
    assert len(remaining["notifications"]) == 1

    dismiss_all = client.post("/api/me/notifications/dismiss-all", json={"scope": "analyst"})
    assert dismiss_all.status_code == 200
    assert dismiss_all.json()["dismissed"] == 1

    empty = client.get("/api/me/notifications?scope=analyst").json()
    assert empty["notifications"] == []


def test_operator_scope_admin_only(client):
    admin_id = _user_id("admin1")
    _insert(admin_id, "operator", dedupe="op1")

    _login(client, "analyst1")
    forbidden = client.get("/api/me/notifications?scope=operator")
    assert forbidden.status_code == 403

    _login(client, "admin1")
    ok = client.get("/api/me/notifications?scope=operator")
    assert ok.status_code == 200
    assert len(ok.json()["notifications"]) == 1


def test_read_does_not_remove_from_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="r1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications").json()["notifications"][0]["id"]
    res = client.post(f"/api/me/notifications/{nid}/read")
    assert res.status_code == 200
    body = client.get("/api/me/notifications").json()
    assert len(body["notifications"]) == 1
    assert body["unread_count"] == 0
    assert body["notifications"][0]["read_at"]


def test_restore_returns_to_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="u1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications").json()["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")
    assert client.post(f"/api/me/notifications/{nid}/restore").status_code == 200
    inbox = client.get("/api/me/notifications?view=inbox").json()
    assert len(inbox["notifications"]) == 1


def test_dismiss_all_scope_all(client):
    admin_id = _user_id("admin1")
    _insert(admin_id, "analyst", dedupe="da-a")
    _insert(admin_id, "operator", dedupe="da-o")

    _login(client, "admin1")
    dismiss_all = client.post(
        "/api/me/notifications/dismiss-all", json={"scope": "all"}
    )
    assert dismiss_all.status_code == 200
    assert dismiss_all.json()["dismissed"] == 2

    empty = client.get("/api/me/notifications?scope=all").json()
    assert empty["notifications"] == []


def test_scope_all_admin_only(client):
    admin_id = _user_id("admin1")
    analyst_id = _user_id("analyst1")
    _insert(admin_id, "analyst", dedupe="aa")
    _insert(admin_id, "operator", dedupe="oo")
    _insert(analyst_id, "analyst", dedupe="xx")
    _login(client, "analyst1")
    assert client.get("/api/me/notifications?scope=all").status_code == 403
    _login(client, "admin1")
    body = client.get("/api/me/notifications?scope=all").json()
    scopes = {n["scope"] for n in body["notifications"]}
    assert scopes == {"analyst", "operator"}
    assert len(body["notifications"]) == 2


def test_patch_preferences_notification_sound(client):
    _login(client, "admin1")
    patch = client.patch("/api/me/preferences", json={"notification_sound": False})
    assert patch.status_code == 200
    assert patch.json()["notification_sound"] is False


def test_patch_notification_mutes(client):
    _login(client, "admin1")
    patch = client.patch(
        "/api/me/preferences",
        json={"notification_mutes": {"watchlist": True}},
    )
    assert patch.status_code == 200
    assert patch.json()["notification_mutes"]["watchlist"] is True
    assert patch.json()["notification_mutes"]["job_error"] is False


def test_patch_notification_mutes_rejects_unknown_key(client):
    _login(client, "admin1")
    res = client.patch(
        "/api/me/preferences",
        json={"notification_mutes": {"not_a_category": True}},
    )
    assert res.status_code == 422


def test_muted_category_does_not_insert(client):
    from notifications.emit import emit_watchlist_notification

    _login(client, "analyst1")
    client.patch("/api/me/preferences", json={"notification_mutes": {"watchlist": True}})

    async def _only_analyst_active():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET is_active = 0 WHERE username = ?",
                ("admin1",),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_only_analyst_active())

    async def _emit():
        db = await get_db()
        try:
            n = await emit_watchlist_notification(
                db,
                cve_id="CVE-2024-1",
                reason="Entered KEV",
                detail="x",
                dedupe_key="watch:CVE-2024-1:kev",
            )
            await db.commit()
            return n
        finally:
            await db.close()

    created = run_db_test(_emit())
    assert created == 0
    listed = client.get("/api/me/notifications?scope=analyst").json()
    assert listed["notifications"] == []
