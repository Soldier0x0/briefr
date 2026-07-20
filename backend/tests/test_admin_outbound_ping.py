"""Tests for the admin durable-queue health_ping canary endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from procrastinate.exceptions import AlreadyEnqueued

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _client(tmp_path, monkeypatch):
    db_path = tmp_path / "outbound_ping.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from jobs.app import reset_app_for_tests
    from main import app

    reset_app_for_tests()
    return TestClient(app, raise_server_exceptions=False)


def _install_enabled_ping(monkeypatch, *, already_enqueued: bool = False):
    import routers.admin.jobs as admin_jobs

    configured = []
    deferred = []

    class FakeDeferrer:
        async def defer_async(self, **kwargs):
            deferred.append(kwargs)
            if already_enqueued:
                raise AlreadyEnqueued()
            return 123

    class FakeTask:
        def configure(self, **kwargs):
            configured.append(kwargs)
            return FakeDeferrer()

    async def fake_open_app():
        return object()

    monkeypatch.setattr(admin_jobs, "is_procrastinate_enabled", lambda: True, raising=False)
    monkeypatch.setattr(admin_jobs, "open_app", fake_open_app, raising=False)
    monkeypatch.setattr(admin_jobs, "health_ping", FakeTask(), raising=False)
    return configured, deferred


def test_outbound_ping_requires_auth(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        resp = client.post("/api/admin/jobs/outbound/ping")

    assert resp.status_code == 401


def test_outbound_ping_rejects_non_admin(tmp_path, monkeypatch, auth_token):
    from database import get_db
    from tests.conftest import run_db_test

    with _client(tmp_path, monkeypatch) as client:
        client.cookies.set("briefr_at", auth_token())

        async def demote() -> None:
            db = await get_db()
            try:
                await db.execute("UPDATE users SET role = 'analyst' WHERE id = 1")
                await db.commit()
            finally:
                await db.close()

        run_db_test(demote())
        client.cookies.set("briefr_at", auth_token(role="analyst"))
        resp = client.post("/api/admin/jobs/outbound/ping")

    assert resp.status_code == 403


def test_outbound_ping_defers_health_ping(tmp_path, monkeypatch, auth_token):
    configured, deferred = _install_enabled_ping(monkeypatch)

    with _client(tmp_path, monkeypatch) as client:
        client.cookies.set("briefr_at", auth_token())
        resp = client.post("/api/admin/jobs/outbound/ping")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"] == "jobs:health_ping"
    assert configured == [{"queueing_lock": "health_ping"}]
    assert deferred == [{"note": "admin-canary"}]


def test_outbound_ping_treats_already_enqueued_as_ok(tmp_path, monkeypatch, auth_token):
    configured, deferred = _install_enabled_ping(monkeypatch, already_enqueued=True)

    with _client(tmp_path, monkeypatch) as client:
        client.cookies.set("briefr_at", auth_token())
        resp = client.post("/api/admin/jobs/outbound/ping")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["already_enqueued"] is True
    assert configured == [{"queueing_lock": "health_ping"}]
    assert deferred == [{"note": "admin-canary"}]
