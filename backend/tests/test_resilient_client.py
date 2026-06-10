"""Tests for the shared resilient HTTP client (retries, circuit breaker, health)."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

import resilient_client
from resilient_client import (
    CircuitOpenError,
    get_feed_health,
    reset_feed_health,
    resilient_get,
)


def _install_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    reset_feed_health()
    # No real sleeping between retries in tests.
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    yield
    reset_feed_health()


def test_success_records_health(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)

    async def run():
        response = await resilient_get("demo", "https://example.com/api")
        assert response.json() == {"ok": True}

    asyncio.run(run())

    health = get_feed_health()["demo"]
    assert health["last_success"] is not None
    assert health["consecutive_failures"] == 0
    assert health["circuit_open"] is False


def test_retries_5xx_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)

    async def run():
        response = await resilient_get("flaky", "https://example.com/api", retries=2)
        assert response.status_code == 200

    asyncio.run(run())
    assert calls["n"] == 3
    assert get_feed_health()["flaky"]["consecutive_failures"] == 0


def test_non_retryable_4xx_raises_without_tripping_circuit(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    _install_transport(monkeypatch, handler)

    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await resilient_get("missing", "https://example.com/api", retries=2)

    asyncio.run(run())
    # No retries for plain 4xx, and the circuit must stay closed.
    assert calls["n"] == 1
    health = get_feed_health()["missing"]
    assert health["circuit_open"] is False
    assert health["last_error"] == "HTTP 404"


def test_circuit_opens_after_threshold_and_fails_fast(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr(resilient_client, "CIRCUIT_FAILURE_THRESHOLD", 3)

    async def run():
        for _ in range(3):
            with pytest.raises(httpx.HTTPStatusError):
                await resilient_get("down", "https://example.com/api", retries=0)

        health = get_feed_health()["down"]
        assert health["circuit_open"] is True
        assert health["consecutive_failures"] == 3

        before = calls["n"]
        with pytest.raises(CircuitOpenError):
            await resilient_get("down", "https://example.com/api")
        # Fail fast: no network call while the circuit is open.
        assert calls["n"] == before

    asyncio.run(run())


def test_circuit_closes_after_cooldown(monkeypatch):
    state = {"healthy": False}

    def handler(request):
        if state["healthy"]:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr(resilient_client, "CIRCUIT_FAILURE_THRESHOLD", 2)

    async def run():
        for _ in range(2):
            with pytest.raises(httpx.HTTPStatusError):
                await resilient_get("recovering", "https://example.com/api", retries=0)

        with pytest.raises(CircuitOpenError):
            await resilient_get("recovering", "https://example.com/api")

        # Simulate cooldown expiry, then the source recovers.
        resilient_client._health["recovering"]["circuit_open_until"] = (
            time.time() - 1
        )
        state["healthy"] = True
        response = await resilient_get("recovering", "https://example.com/api")
        assert response.status_code == 200
        assert get_feed_health()["recovering"]["circuit_open"] is False

    asyncio.run(run())


def test_transport_errors_retry_then_record_failure(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("refused", request=request)

    _install_transport(monkeypatch, handler)

    async def run():
        with pytest.raises(httpx.ConnectError):
            await resilient_get("dead", "https://example.com/api", retries=2)

    asyncio.run(run())
    assert calls["n"] == 3
    health = get_feed_health()["dead"]
    assert health["consecutive_failures"] == 1
    assert "ConnectError" in health["last_error"]
