"""Tests for env-configured Telegram/Discord webhook sender."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

import resilient_client
from resilient_client import reset_feed_health
from webhooks.sender import configured_channels, send_alert, webhooks_enabled


def _install_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_feed_health()
    for key in (
        "DISCORD_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    yield
    reset_feed_health()


def test_webhooks_disabled_without_env(monkeypatch):
    assert webhooks_enabled() is False
    assert configured_channels() == []
    result = asyncio.run(send_alert("hello"))
    assert result["status"] == "skipped"


def test_discord_only(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url), request.content))
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    assert configured_channels() == ["discord"]

    result = asyncio.run(send_alert("KEV alert"))
    assert result["status"] == "ok"
    assert result["sent"] == ["discord"]
    assert calls[0][0] == "POST"
    assert b"KEV alert" in calls[0][2]


def test_telegram_only(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)
    assert configured_channels() == ["telegram"]

    result = asyncio.run(send_alert("stack hit"))
    assert result["status"] == "ok"
    assert result["sent"] == ["telegram"]
    assert calls[0].url.path.endswith("/sendMessage")
    assert b"stack hit" in calls[0].content


def test_both_channels(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(204 if "discord" in str(request.url) else 200)

    _install_transport(monkeypatch, handler)
    result = asyncio.run(send_alert("both"))
    assert set(result["sent"]) == {"discord", "telegram"}
    assert calls["n"] == 2


def test_uses_retries(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    result = asyncio.run(send_alert("retry me"))
    assert result["status"] == "ok"
    assert calls["n"] == 2
