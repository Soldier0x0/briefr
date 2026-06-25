"""Tests for Groq quota-aware client."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import groq_client as gc


def test_message_content_handles_malformed_json():
    response = httpx.Response(200, json={"not": "choices"})
    assert gc.message_content(response) == ""


def test_message_content_handles_null_choice():
    response = httpx.Response(200, json={"choices": [None]})
    assert gc.message_content(response) == ""


def test_chat_completion_retries_on_429_then_succeeds(monkeypatch):
    gc.reset_groq_limiter_state()

    class Fake200Response:
        status_code = 200
        headers = httpx.Headers({})

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    async def fake_resilient(*_args, **_kwargs):
        return Fake200Response()

    monkeypatch.setattr(gc, "resilient_request", fake_resilient)

    async def run():
        response = await gc.chat_completion(
            "gsk_test",
            messages=[{"role": "user", "content": "hi"}],
        )
        return response

    response = asyncio.run(run())
    assert response.status_code == 200
    assert gc.message_content(response) == "ok"
