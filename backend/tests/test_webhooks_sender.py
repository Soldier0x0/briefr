"""Tests for env-configured Telegram/Discord webhook sender."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import httpx
import pytest

import resilient_client
from database import init_db
from resilient_client import reset_feed_health
from webhooks.destinations import sync_env_destinations_to_db
from webhooks.sender import configured_channels, send_alert, webhooks_enabled


def _setup_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "sender.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())
    run_db_test(sync_env_destinations_to_db())


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
    ):
        monkeypatch.delenv(key, raising=False)

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    import api_queue as _aq

    monkeypatch.setattr(_aq.asyncio, "sleep", no_sleep)
    yield
    reset_feed_health()


def test_webhooks_disabled_without_env(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    assert webhooks_enabled() is False
    assert configured_channels() == []
    result = run_db_test(send_alert("hello"))
    assert result["status"] == "skipped"


def test_discord_only(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url), request.content))
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    assert configured_channels() == ["discord"]

    result = run_db_test(send_alert("KEV alert"))
    assert result["status"] == "ok"
    assert result["sent"] == ["discord"]
    assert calls[0][0] == "POST"
    assert b"KEV alert" in calls[0][2]


def test_telegram_only(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    run_db_test(sync_env_destinations_to_db())
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)
    assert configured_channels() == ["telegram"]

    result = run_db_test(send_alert("stack hit"))
    assert result["status"] == "ok"
    assert result["sent"] == ["telegram"]
    assert calls[0].url.path.endswith("/sendMessage")
    assert b"stack hit" in calls[0].content


def test_both_channels(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    run_db_test(sync_env_destinations_to_db())
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(204 if request.headers.get("Host") == "discord.com" else 200)

    _install_transport(monkeypatch, handler)
    result = run_db_test(send_alert("both"))
    assert set(result["sent"]) == {"discord", "telegram"}
    assert calls["n"] == 2


def test_uses_retries(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    result = run_db_test(send_alert("retry me"))
    assert result["status"] == "ok"
    assert calls["n"] == 2
