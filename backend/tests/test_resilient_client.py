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
    resilient_request,
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


def test_non_retryable_5xx_records_failure_and_trips_circuit(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(501)

    _install_transport(monkeypatch, handler)

    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await resilient_get("broken", "https://example.com/api", retries=0)

    asyncio.run(run())
    assert calls["n"] == 1
    health = get_feed_health()["broken"]
    assert health["consecutive_failures"] == 1
    assert health["last_error"] == "HTTP 501"
    assert health["last_failure"] is not None


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


def test_optional_client_error_does_not_record_health(monkeypatch):
    def handler(request):
        return httpx.Response(404)

    _install_transport(monkeypatch, handler)

    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await resilient_get(
                "osv",
                "https://example.com/vuln",
                retries=0,
                record_client_error=False,
            )

    asyncio.run(run())

    health = get_feed_health().get("osv")
    assert health is None or health.get("last_error") is None


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


def test_rate_limit_waits_and_retries(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"ok": True})

    _install_transport(monkeypatch, handler)

    async def run():
        response = await resilient_get("limited", "https://example.com/api", retries=0)
        assert response.status_code == 200

    asyncio.run(run())
    assert calls["n"] == 2
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


def test_retry_after_parses_unix_ms_not_as_relative_years():
    """Same class as api_queue: OpenRouter-style absolute ms must not become years."""
    future_ms = int((time.time() + 45.0) * 1000.0)
    response = httpx.Response(429, headers={"retry-after": str(future_ms)})
    wait = resilient_client._retry_after_seconds(response, attempt=0)
    assert 30 < wait <= 120.0


def test_retry_after_caps_unit_durations():
    response = httpx.Response(429, headers={"retry-after": "5m"})
    wait = resilient_client._retry_after_seconds(response, attempt=0)
    assert wait == 120.0  # 5m parsed, then transport-retry cap


def test_record_circuit_false_does_not_open_feed_health(monkeypatch):
    """Probes must not poison the shared circuit used by real traffic."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError(
            "[Errno -3] Temporary failure in name resolution",
            request=request,
        )

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr(resilient_client, "CIRCUIT_FAILURE_THRESHOLD", 1)

    async def run():
        for _ in range(3):
            with pytest.raises(httpx.ConnectError):
                await resilient_request(
                    "gemini",
                    "GET",
                    "https://example.com/models",
                    retries=0,
                    record_circuit=False,
                    ignore_circuit=True,
                )

    asyncio.run(run())
    assert calls["n"] == 3
    health = get_feed_health().get("gemini")
    assert health is None or (
        health["circuit_open"] is False
        and health["consecutive_failures"] == 0
        and health["last_error"] is None
    )


def test_ignore_circuit_allows_probe_while_open(monkeypatch):
    def handler(request):
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr(resilient_client, "CIRCUIT_FAILURE_THRESHOLD", 1)

    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await resilient_get("cerebras", "https://example.com/models", retries=0)
        assert get_feed_health()["cerebras"]["circuit_open"] is True

        with pytest.raises(CircuitOpenError):
            await resilient_get("cerebras", "https://example.com/models", retries=0)

        # Probe can still dial while the circuit is open.
        with pytest.raises(httpx.HTTPStatusError):
            await resilient_request(
                "cerebras",
                "GET",
                "https://example.com/models",
                retries=0,
                record_circuit=False,
                ignore_circuit=True,
            )

    asyncio.run(run())
