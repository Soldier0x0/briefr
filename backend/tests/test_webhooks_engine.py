"""Tests for the V1.4 webhook engine."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import httpx
import pytest

import resilient_client
from database import get_db, init_db, was_webhook_alert_sent
from resilient_client import reset_feed_health
from webhooks.destinations import (
    EVENT_BACKUP_FAILURE,
    EVENT_HEALTH,
    EVENT_KEV_ALERT,
    load_destinations,
    sync_env_destinations_to_db,
    webhooks_enabled,
)
from webhooks.engine import dispatch_event, send_test_message
from webhooks.sender import configured_channels, send_alert


def _setup_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "engine.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())
    run_db_test(sync_env_destinations_to_db())
    return db_path


def _install_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_feed_health()
    for key in (
        "DISCORD_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "WEBHOOK_GENERIC_URL",
        "DISCORD_WEBHOOK_ENABLED",
        "TELEGRAM_WEBHOOK_ENABLED",
        "WEBHOOK_GENERIC_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    yield
    reset_feed_health()


def test_webhooks_disabled_without_env(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    assert run_db_test(webhooks_enabled()) is False
    assert run_db_test(configured_channels()) == []
    result = run_db_test(send_alert("hello"))
    assert result["status"] == "skipped"


def test_discord_only(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())
    calls = []

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request):
        calls.append((request.method, str(request.url), request.headers.get("Host"), request.content))
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)
    assert run_db_test(configured_channels()) == ["discord"]

    result = run_db_test(send_alert("KEV alert"))
    assert result["status"] == "ok"
    assert result["sent"] == ["discord"]
    assert calls[0][0] == "POST"
    assert calls[0][2] == "discord.com"
    assert b"KEV alert" in calls[0][3]


def test_telegram_only(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    run_db_test(sync_env_destinations_to_db())
    calls = []

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)
    assert run_db_test(configured_channels()) == ["telegram"]

    result = run_db_test(send_alert("stack hit"))
    assert result["status"] == "ok"
    assert result["sent"] == ["telegram"]
    assert calls[0].headers["Host"] == "api.telegram.org"
    assert b"stack hit" in calls[0].content


def test_generic_destination_json_payload(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("WEBHOOK_GENERIC_URL", "https://hooks.example.com/briefr")
    run_db_test(sync_env_destinations_to_db())
    calls = []

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    result = run_db_test(
        dispatch_event(EVENT_HEALTH, "health ping", dedupe_key="probe", skip_dedupe=True)
    )
    assert result["status"] == "ok"
    assert result["sent"] == ["generic"]
    assert calls[0]["text"] == "health ping"
    assert calls[0]["event_type"] == EVENT_HEALTH


def test_per_destination_enable_disable(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    monkeypatch.setenv("DISCORD_WEBHOOK_ENABLED", "0")
    run_db_test(sync_env_destinations_to_db())

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    def handler(request):
        return httpx.Response(204 if "discord" in request.headers.get("Host", "") else 200)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    result = run_db_test(send_alert("both"))
    assert result["sent"] == ["telegram"]


def test_event_type_subscription_filter(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("DISCORD_WEBHOOK_EVENTS", "backup_failure")
    run_db_test(sync_env_destinations_to_db())

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    skipped = run_db_test(dispatch_event(EVENT_KEV_ALERT, "no subscribers", skip_dedupe=True))
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "no_subscribers"

    delivered = run_db_test(dispatch_event(EVENT_BACKUP_FAILURE, "backup stale", skip_dedupe=True))
    assert delivered["status"] == "ok"
    assert calls["n"] == 1


def test_dedupe_records_once(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    first = run_db_test(dispatch_event(EVENT_KEV_ALERT, "once", dedupe_key="CVE-2024-1"))
    second = run_db_test(dispatch_event(EVENT_KEV_ALERT, "once", dedupe_key="CVE-2024-1"))
    assert first["status"] == "ok"
    assert second["status"] == "skipped"
    assert second["reason"] == "deduped"
    assert calls["n"] == 1

    async def check():
        db = await get_db()
        try:
            return await was_webhook_alert_sent(db, EVENT_KEV_ALERT, "CVE-2024-1")
        finally:
            await db.close()

    assert run_db_test(check()) is True


def test_send_test_message_unknown_destination(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    result = run_db_test(send_test_message("missing", "hello"))
    assert result["ok"] is False
    assert result["error"] == "unknown destination"


def test_webhooks_enabled_uses_db_enabled_state(monkeypatch, tmp_path):
    """Guard helpers must await load_destinations(), not env-only builders."""
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())

    async def disable_in_db():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE webhook_destinations SET enabled = 0 WHERE id = 'discord'"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(disable_in_db())
    assert run_db_test(webhooks_enabled()) is False
    assert run_db_test(configured_channels()) == []
