"""API key health ping monitoring."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_run_api_key_health_checks_skips_placeholders(monkeypatch, tmp_path):
    from database import get_db, init_db
    from monitoring import api_key_health as mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health.db"))
    asyncio.run(init_db())

    monkeypatch.setenv("GROQ_API_KEY", "your_key_here")
    monkeypatch.setenv("NVD_API_KEY", "")

    async def fake_ping(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        return response

    monkeypatch.setattr(mod, "resilient_request", fake_ping)

    async def run() -> dict:
        db = await get_db()
        try:
            return await mod.run_api_key_health_checks(db)
        finally:
            await db.close()

    stats = asyncio.run(run())
    assert stats["checked"] == 0


def test_run_api_key_health_checks_persists_result(monkeypatch, tmp_path):
    from database import get_db, get_sync_state_value, init_db
    from monitoring import api_key_health as mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health2.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkey1234567890abcd")

    async def fake_ping(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        return response

    monkeypatch.setattr(mod, "resilient_request", fake_ping)

    async def run() -> tuple[dict, str | None]:
        db = await get_db()
        try:
            stats = await mod.run_api_key_health_checks(db)
            raw = await get_sync_state_value(db, "api_key_health:groq")
            return stats, raw
        finally:
            await db.close()

    stats, raw = asyncio.run(run())
    assert stats["checked"] == 1
    assert stats["healthy"] == 1
    payload = json.loads(raw)
    assert payload["healthy"] is True
    assert payload["checked_at"]


def test_build_api_key_health_payload_suffix(monkeypatch, tmp_path):
    from database import get_db, init_db, set_sync_state_value
    from monitoring.api_key_health import build_api_key_health_payload

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health3.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey1234567890")

    async def run() -> dict:
        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                "api_key_health:gemini",
                json.dumps(
                    {
                        "provider": "gemini",
                        "healthy": False,
                        "checked_at": "2026-07-10T12:00:00+00:00",
                        "latency_ms": 120,
                        "status_code": 403,
                        "error": "HTTP 403",
                    }
                ),
            )
            await db.commit()
            return await build_api_key_health_payload(db)
        finally:
            await db.close()

    payload = asyncio.run(run())
    gemini = next(row for row in payload["providers"] if row["provider"] == "gemini")
    assert gemini["configured"] is True
    assert gemini["key_suffix"].startswith("AIza")
    assert gemini["healthy"] is False
    assert gemini["error"] == "HTTP 403"


def test_ping_json_actually_reaches_the_http_layer(monkeypatch):
    """Regression test for the source/method argument-order bug.

    Prior tests all mocked resilient_request itself with a catch-all
    `*args, **kwargs` fake, so a call passing arguments in the wrong order
    (or position) was invisible. This test installs a fake transport on the
    real resilient_client._client so resilient_request's own argument
    binding executes for real — it must fail with the TypeError
    ("got multiple values for argument 'source'") on the unfixed code.
    """
    import resilient_client
    from monitoring.api_key_health import _ping_json

    seen_requests = []

    def handler(request):
        seen_requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)

    async def run():
        return await _ping_json(
            source="test-provider",
            method="GET",
            url="https://example.com/health",
        )

    result = asyncio.run(run())

    assert result["healthy"] is True, result
    assert result["status_code"] == 200
    assert len(seen_requests) == 1
    assert seen_requests[0].url.host == "example.com"


def test_ping_json_connect_error_does_not_trip_feed_circuit(monkeypatch):
    """API key health probes must not open Feed Health circuits."""
    import resilient_client
    from monitoring.api_key_health import _ping_json
    from resilient_client import get_feed_health, reset_feed_health

    reset_feed_health()
    monkeypatch.setattr(resilient_client, "CIRCUIT_FAILURE_THRESHOLD", 1)

    def handler(request):
        raise httpx.ConnectError(
            "[Errno -3] Temporary failure in name resolution",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)

    async def run():
        return await _ping_json(
            source="cerebras",
            method="GET",
            url="https://api.cerebras.ai/v1/models",
        )

    result = asyncio.run(run())
    assert result["healthy"] is False
    assert "ConnectError" in (result["error"] or "")
    health = get_feed_health().get("cerebras")
    assert health is None or (
        health["circuit_open"] is False
        and health["consecutive_failures"] == 0
        and health["last_error"] is None
    )
    reset_feed_health()


def test_repeated_identical_failure_notifies_once_not_every_run(monkeypatch, tmp_path):
    """Regression test for the dedupe_key bug: it used to embed checked_at
    (a fresh per-run timestamp), so deduplication never fired and a
    provider stuck on the same failure re-notified every 6h forever. The
    fix keys on (provider, error) instead of (provider, timestamp).

    Captures the actual dedupe_key strings passed to
    emit_api_key_unhealthy_notification across two runs with an identical
    error, rather than asserting on notification row counts through the
    full DB-backed insert/dedupe path (unique-constraint enforcement is
    exercised separately by db/user_notifications.py's own tests) — this
    isolates exactly what changed: the key's stability, not the storage
    layer's dedup mechanics.
    """
    from database import get_db, init_db
    from monitoring import api_key_health as mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health4.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkey1234567890abcd")

    async def fake_401(*args, **kwargs):
        response = MagicMock()
        response.status_code = 401
        return response

    monkeypatch.setattr(mod, "resilient_request", fake_401)

    captured_dedupe_keys: list[str] = []

    async def capture_notification(db, *, provider, error, dedupe_key):
        captured_dedupe_keys.append(dedupe_key)
        return 1

    monkeypatch.setattr(
        "notifications.emit.emit_api_key_unhealthy_notification", capture_notification
    )

    async def run() -> None:
        db = await get_db()
        try:
            await mod.run_api_key_health_checks(db)
            await mod.run_api_key_health_checks(db)  # second identical run
        finally:
            await db.close()

    asyncio.run(run())

    assert len(captured_dedupe_keys) == 2, captured_dedupe_keys
    assert captured_dedupe_keys[0] == captured_dedupe_keys[1], (
        "dedupe_key must be identical across two runs with the same error "
        f"(the bug embedded a fresh per-run timestamp, which would make "
        f"these differ): {captured_dedupe_keys}"
    )
    # "401" is itself digits, collapsed by the dedupe normalizer (see
    # test_dedupe_normalizes_dynamic_content_in_error_text) -- this is
    # still a stable, correct key, just not the literal raw error text.
    assert captured_dedupe_keys[0] == "api_key:groq:HTTP #"


def test_dedupe_normalizes_dynamic_content_in_error_text(monkeypatch, tmp_path):
    """Gemini review on PR #482: some exception messages embed a value that
    changes every occurrence (Unix timestamps, ports, byte counts), which
    would defeat the (provider, error) dedupe key exactly like the original
    (provider, checked_at) bug did. CircuitOpenError is the concrete example
    -- resilient_client.py formats it as 'Circuit open for X; retry after
    <unix-ts>', a fresh integer on every occurrence."""
    from database import get_db, init_db
    from monitoring import api_key_health as mod
    from resilient_client import CircuitOpenError

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health5.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkey1234567890abcd")

    call_count = {"n": 0}

    async def fake_circuit_open(*args, **kwargs):
        call_count["n"] += 1
        # A different retry_at each call -- exactly what made the
        # not-yet-normalized dedupe key unstable.
        raise CircuitOpenError("groq", retry_at=1_700_000_000.0 + call_count["n"])

    monkeypatch.setattr(mod, "resilient_request", fake_circuit_open)

    captured_dedupe_keys: list[str] = []

    async def capture_notification(db, *, provider, error, dedupe_key):
        captured_dedupe_keys.append(dedupe_key)
        return 1

    monkeypatch.setattr(
        "notifications.emit.emit_api_key_unhealthy_notification", capture_notification
    )

    async def run() -> None:
        db = await get_db()
        try:
            await mod.run_api_key_health_checks(db)
            await mod.run_api_key_health_checks(db)
        finally:
            await db.close()

    asyncio.run(run())

    assert len(captured_dedupe_keys) == 2, captured_dedupe_keys
    assert captured_dedupe_keys[0] == captured_dedupe_keys[1], (
        "two CircuitOpenError occurrences with different retry_at timestamps "
        f"must still normalize to the same dedupe key: {captured_dedupe_keys}"
    )
