"""Admin daily-brief preview and test-send routes (Task 5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from tests.conftest import run_db_test


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "daily_brief_admin.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    # Preview/test must work while cron slot flags are off.
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "0")
    monkeypatch.setenv("DAILY_BRIEF_STANDUP_ENABLED", "0")
    monkeypatch.setenv("DAILY_BRIEF_LLM_ENABLED", "0")

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    import routers.admin as _admin_mod

    monkeypatch.setattr(_admin_mod, "trigger_graceful_restart", _noop_async)

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


async def _delivery_log_count() -> int:
    from database import get_db

    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM webhook_delivery_log")
        row = rows[0]
        return int(row["cnt"] if isinstance(row, dict) else row[0])
    finally:
        await db.close()


def test_daily_brief_preview_returns_text_without_delivery(admin_client):
    before = run_db_test(_delivery_log_count())

    resp = admin_client.get("/api/admin/webhooks/daily-brief/preview", params={"slot": "eod"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "text" in body
    assert "// COUNTS" not in body["text"]
    assert "At a glance" in body["text"]
    assert body.get("discord_embeds")
    assert body.get("brief") is not None
    assert body["brief"]["slot"] == "eod"

    after = run_db_test(_delivery_log_count())
    assert after == before


def test_daily_brief_preview_invalid_slot_422(admin_client):
    resp = admin_client.get(
        "/api/admin/webhooks/daily-brief/preview",
        params={"slot": "midnight"},
    )
    assert resp.status_code == 422


def test_daily_brief_test_send_skip_dedupe(admin_client, monkeypatch):
    calls: list[dict] = []

    async def fake_dispatch(event_type, message, **kwargs):
        calls.append({"event_type": event_type, "message": message, **kwargs})
        return {
            "status": "ok",
            "sent": ["discord"],
            "errors": {},
            "event_type": event_type,
        }

    monkeypatch.setattr("routers.admin.webhooks.dispatch_event", fake_dispatch)

    resp = admin_client.post(
        "/api/admin/webhooks/daily-brief/test",
        json={"slot": "standup"},
    )
    assert resp.status_code == 200, resp.text
    assert calls, "expected dispatch_event to be called"
    assert calls[0]["event_type"] == "daily_brief"
    assert calls[0].get("skip_dedupe") is True
    assert calls[0].get("telegram_parse_mode") == "HTML"
    assert calls[0].get("discord_embeds")
    assert "At a glance" in (calls[0].get("discord_fallback") or calls[0]["message"])


def test_daily_brief_test_invalid_slot_422(admin_client):
    resp = admin_client.post(
        "/api/admin/webhooks/daily-brief/test",
        json={"slot": "noon"},
    )
    assert resp.status_code == 422
