from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_queue
import catchup_mode as cm
import database
import rate_limit as _rl
from main import app
from settings import settings as _settings


@pytest.fixture(autouse=True)
def reset_catchup_mode():
    cm.reset_catchup_for_tests()
    api_queue.reset_api_queue()
    yield
    cm.reset_catchup_for_tests()
    api_queue.reset_api_queue()


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "catchup.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


@pytest.fixture
def anon_client(tmp_path, monkeypatch):
    db_path = tmp_path / "catchup_anon.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


async def _read_last_blob() -> dict:
    db = await database.get_db()
    try:
        raw = await database.get_sync_state_value(db, cm.CATCHUP_MODE_LAST_KEY)
    finally:
        await db.close()
    assert raw is not None
    return json.loads(raw)


async def _write_last_blob(payload: dict) -> None:
    db = await database.get_db()
    try:
        await database.set_sync_state_value(db, cm.CATCHUP_MODE_LAST_KEY, json.dumps(payload))
        await db.commit()
    finally:
        await db.close()


def test_catchup_get_inactive_includes_queue_summary(admin_client):
    resp = admin_client.get("/api/admin/catchup")

    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False
    assert data["api_queue"] == {
        "total_queued": 0,
        "total_active": 0,
        "has_pending": False,
    }


def test_catchup_start_conflict_stop_roundtrip_persists_state(admin_client):
    start = admin_client.post("/api/admin/catchup/start", json={"duration_hours": 6})

    assert start.status_code == 200
    started = start.json()
    assert started["active"] is True
    assert started["duration_hours"] == 6

    persisted_start = admin_client.portal.call(_read_last_blob)
    assert persisted_start["active"] is True
    assert persisted_start["duration_hours"] == 6

    conflict = admin_client.post("/api/admin/catchup/start", json={"duration_hours": 2})
    assert conflict.status_code == 409

    stop = admin_client.post("/api/admin/catchup/stop", json={})
    assert stop.status_code == 200
    stopped = stop.json()
    assert stopped["active"] is False
    assert stopped["cleared_reason"] == "ended_early"

    persisted_stop = admin_client.portal.call(_read_last_blob)
    assert persisted_stop["active"] is False
    assert persisted_stop["cleared_reason"] == "ended_early"


def test_catchup_start_accepts_ends_at(admin_client):
    ends_at = datetime.now(timezone.utc) + timedelta(hours=2)

    resp = admin_client.post(
        "/api/admin/catchup/start",
        json={"ends_at": ends_at.isoformat().replace("+00:00", "Z")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert 1.9 < data["duration_hours"] < 2.1


def test_clear_after_restart_marks_future_active_blob(admin_client):
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    payload = {
        "active": True,
        "started_at": (future - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "ends_at": future.isoformat().replace("+00:00", "Z"),
        "duration_hours": 6,
        "started_by": "pytest-admin",
        "cleared_reason": None,
        "in_wind_down": False,
        "should_start_new_work": True,
    }
    admin_client.portal.call(_write_last_blob, payload)

    cleared = admin_client.portal.call(cm.clear_catchup_after_restart)

    assert cleared["active"] is False
    assert cleared["cleared_reason"] == "restart"
    assert cm.is_catchup_active() is False
    persisted = admin_client.portal.call(_read_last_blob)
    assert persisted["active"] is False
    assert persisted["cleared_reason"] == "restart"


def test_clear_after_restart_marks_expired_active_blob(admin_client):
    """Active blob whose ends_at is already past must not stay stuck active in DB."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "active": True,
        "started_at": (past - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        "ends_at": past.isoformat().replace("+00:00", "Z"),
        "duration_hours": 6,
        "started_by": "pytest-admin",
        "cleared_reason": None,
        "in_wind_down": False,
        "should_start_new_work": True,
    }
    admin_client.portal.call(_write_last_blob, payload)

    cleared = admin_client.portal.call(cm.clear_catchup_after_restart)

    assert cleared["active"] is False
    assert cleared["cleared_reason"] == "expired"
    persisted = admin_client.portal.call(_read_last_blob)
    assert persisted["active"] is False
    assert persisted["cleared_reason"] == "expired"


def test_get_catchup_persists_expire_once(admin_client, monkeypatch):
    calls = {"n": 0}
    real = cm.persist_catchup_status

    async def counting_persist(status=None):
        calls["n"] += 1
        return await real(status)

    monkeypatch.setattr(cm, "persist_catchup_status", counting_persist)

    cm.start_catchup(duration_hours=1, started_by="pytest")
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) - timedelta(seconds=1))

    first = admin_client.get("/api/admin/catchup")
    assert first.status_code == 200
    assert first.json()["cleared_reason"] == "expired"
    assert "db_persisted" not in first.json()
    assert calls["n"] == 1

    second = admin_client.get("/api/admin/catchup")
    assert second.status_code == 200
    assert calls["n"] == 1  # no redundant write on poll


@pytest.mark.no_auth
def test_catchup_requires_admin(anon_client):
    assert anon_client.get("/api/admin/catchup").status_code in (401, 403)
    assert anon_client.post("/api/admin/catchup/start", json={"duration_hours": 6}).status_code in (
        401,
        403,
    )
    assert anon_client.post("/api/admin/catchup/stop", json={}).status_code in (401, 403)
