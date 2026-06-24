"""Tests for Groq quota-aware client."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import groq_client as gc
from ai.groq_config import groq_limits
from resilient_client import CircuitOpenError


def test_parse_duration_seconds():
    assert gc._parse_duration_seconds("12") == 12.0
    assert gc._parse_duration_seconds("1.5") == 1.5
    assert gc._parse_duration_seconds("7.66s") == pytest.approx(7.66)
    assert gc._parse_duration_seconds("2m59.56s") == pytest.approx(179.56)


def test_groq_limits_default_interval_respects_tpm():
    limits = groq_limits()
    assert limits.rpm == 30
    assert limits.tpm == 6000
    assert limits.min_interval_seconds >= 15.0


def test_apply_rate_limit_headers_pauses_on_low_remaining_tokens():
    gc.reset_groq_limiter_state()
    headers = httpx.Headers(
        {
            "x-ratelimit-remaining-tokens": "100",
            "x-ratelimit-reset-tokens": "5s",
        }
    )
    gc._apply_rate_limit_headers(headers, estimated_tokens=1500)
    assert gc._pause_until > 0


def test_message_content_handles_malformed_json():
    response = httpx.Response(200, json={"not": "choices"})
    assert gc.message_content(response) == ""


def test_chat_completion_retries_on_429_then_succeeds(monkeypatch):
    gc.reset_groq_limiter_state()
    calls = {"n": 0}

    class Fake429Response:
        status_code = 429
        headers = httpx.Headers({"retry-after": "0"})
        request = httpx.Request("POST", "https://api.groq.com")

    class Fake200Response:
        status_code = 200
        headers = httpx.Headers({})
        request = httpx.Request("POST", "https://api.groq.com")

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    async def fake_resilient(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            resp = Fake429Response()
            raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
        return Fake200Response()

    async def noop():
        return None

    monkeypatch.setattr(gc, "resilient_request", fake_resilient)
    monkeypatch.setattr(gc, "await_groq_slot", noop)
    monkeypatch.setattr(gc, "GROQ_RATE_LIMIT_MAX_RETRIES", 3)

    async def run():
        response = await gc.chat_completion(
            "gsk_test",
            messages=[{"role": "user", "content": "hi"}],
        )
        return response

    response = asyncio.run(run())
    assert response.status_code == 200
    assert calls["n"] == 2


def test_chat_completion_waits_for_open_circuit(monkeypatch):
    gc.reset_groq_limiter_state()
    calls = {"n": 0}

    class Fake200Response:
        status_code = 200
        headers = httpx.Headers({})
        request = httpx.Request("POST", "https://api.groq.com")

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    async def fake_resilient(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise CircuitOpenError("groq", 0.0)
        return Fake200Response()

    async def noop():
        return None

    monkeypatch.setattr(gc, "resilient_request", fake_resilient)
    monkeypatch.setattr(gc, "await_groq_slot", noop)

    async def run():
        return await gc.chat_completion(
            "gsk_test",
            messages=[{"role": "user", "content": "hi"}],
        )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert calls["n"] == 2


def test_chat_completion_raises_after_exhausted_429_retries(monkeypatch):
    gc.reset_groq_limiter_state()

    class FakeResponse:
        status_code = 429
        headers = httpx.Headers({"retry-after": "0"})
        request = httpx.Request("POST", "https://api.groq.com")

    async def fake_resilient(*_args, **_kwargs):
        resp = FakeResponse()
        raise httpx.HTTPStatusError("429", request=resp.request, response=resp)

    async def noop():
        return None

    monkeypatch.setattr(gc, "resilient_request", fake_resilient)
    monkeypatch.setattr(gc, "await_groq_slot", noop)
    monkeypatch.setattr(gc, "GROQ_RATE_LIMIT_MAX_RETRIES", 1)

    async def run():
        with pytest.raises(gc.GroqRateLimitError):
            await gc.chat_completion(
                "gsk_test",
                messages=[{"role": "user", "content": "hi"}],
            )

    asyncio.run(run())
