"""Tests for global API request queue."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_queue as aq


def test_parse_duration_seconds():
    assert aq._parse_duration_seconds("12") == 12.0
    assert aq._parse_duration_seconds("1.5") == 1.5
    assert abs(aq._parse_duration_seconds("7.66s") - 7.66) < 0.01
    assert abs(aq._parse_duration_seconds("2m59.56s") - 179.56) < 0.01


def test_queue_status_tracks_waiting(monkeypatch):
    aq.reset_api_queue()
    pacing_calls = {"n": 0}

    async def fake_sleep(seconds):
        pacing_calls["n"] += 1

    monkeypatch.setattr(aq.asyncio, "sleep", fake_sleep)

    async def run():
        aq.schedule_source_pause("demo", 5.0, reason="test")
        task = asyncio.create_task(aq.await_api_slot("demo"))
        await asyncio.sleep(0)  # let task start
        status = aq.get_api_queue_status()
        await task
        return status

    status = asyncio.run(run())
    assert status["total_queued"] >= 1 or status["sources"].get("demo")
    aq.reset_api_queue()


def test_github_headers_schedule_pause():
    import httpx

    aq.reset_api_queue()
    headers = httpx.Headers(
        {
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(__import__("time").time()) + 30),
        }
    )
    aq.apply_rate_limit_headers("github", headers)
    status = aq.get_api_queue_status()
    assert status["has_pending"] or status["sources"].get("github")
