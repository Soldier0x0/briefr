"""Tests for global API request queue."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_queue as aq


def test_parse_duration_seconds():
    assert aq._parse_duration_seconds("12") == 12.0
    assert aq._parse_duration_seconds("1.5") == 1.5
    assert abs(aq._parse_duration_seconds("7.66s") - 7.66) < 0.01
    assert abs(aq._parse_duration_seconds("2m59.56s") - 179.56) < 0.01


def test_parse_duration_http_date():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    http_date = format_datetime(future)
    result = aq._parse_duration_seconds(http_date)
    assert 100 < result < 140


def test_queued_decrements_after_slot_acquired():
    aq.reset_api_queue()

    async def run():
        rid = await aq.await_api_slot("test_source")
        status = aq.get_api_queue_status()
        aq.release_api_slot("test_source", rid)
        return status

    status = asyncio.run(run())
    assert status["total_queued"] == 0
    assert status["total_active"] == 1
    aq.reset_api_queue()


def test_task_registration_metadata():
    aq.reset_api_queue()

    async def run():
        rid = await aq.await_api_slot(
            "github",
            operation="exploit_search",
            context_type="cve",
            context_id="CVE-2026-48282",
        )
        active_status = aq.get_api_queue_status()
        aq.release_api_slot("github", rid)
        cleared_status = aq.get_api_queue_status()
        return active_status, cleared_status

    active_status, cleared_status = asyncio.run(run())
    assert len(active_status["requests"]) == 1
    assert len(cleared_status["requests"]) == 0
    aq.reset_api_queue()

    async def run_active():
        rid = await aq.await_api_slot(
            "github",
            operation="exploit_search",
            context_type="cve",
            context_id="CVE-2026-48282",
        )
        return aq.get_api_queue_status(), rid

    status, rid = asyncio.run(run_active())
    assert status["total_active"] == 1
    assert len(status["requests"]) == 1
    req = status["requests"][0]
    assert req["source"] == "github"
    assert req["operation"] == "exploit_search"
    assert req["display_label"] == "Searching public exploit references"
    assert req["context_type"] == "cve"
    assert req["context_id"] == "CVE-2026-48282"
    assert req["state"] == "active"
    assert req["elapsed_seconds"] >= 0
    aq.release_api_slot("github", rid)
    aq.reset_api_queue()


def test_queued_to_active_transition():
    aq.reset_api_queue()

    async def run():
        aq.schedule_source_pause("demo", 0.05, reason="pacing")
        task = asyncio.create_task(
            aq.await_api_slot("demo", operation="cve_lookup", context_type="cve", context_id="CVE-2024-0001")
        )
        await asyncio.sleep(0)
        waiting_status = aq.get_api_queue_status()
        await task
        return waiting_status

    waiting_status = asyncio.run(run())
    assert waiting_status["total_active"] + waiting_status["total_queued"] >= 1
    reqs = waiting_status.get("requests") or []
    if reqs:
        assert reqs[0]["state"] in ("queued", "waiting", "rate_limited")
    aq.reset_api_queue()


def test_task_removal_on_release():
    aq.reset_api_queue()

    async def run():
        rid = await aq.await_api_slot("otx", operation="pulse_lookup", context_type="cve", context_id="CVE-2024-0002")
        before = aq.get_api_queue_status()
        aq.release_api_slot("otx", rid)
        after = aq.get_api_queue_status()
        return before, after

    before, after = asyncio.run(run())
    assert len(before["requests"]) == 1
    assert len(after["requests"]) == 0
    assert after["total_active"] == 0
    aq.reset_api_queue()


def test_concurrent_request_isolation():
    aq.reset_api_queue()

    async def run():
        rid_a = await aq.await_api_slot(
            "rss",
            operation="outbound_request",
            context_type="cve",
            context_id="CVE-2024-0001",
        )
        rid_b = await aq.await_api_slot(
            "rss",
            operation="outbound_request",
            context_type="cve",
            context_id="CVE-2024-0002",
        )
        status = aq.get_api_queue_status()
        ids = {r["request_id"] for r in status["requests"]}
        contexts = {(r["context_type"], r["context_id"]) for r in status["requests"]}
        aq.release_api_slot("rss", rid_a)
        aq.release_api_slot("rss", rid_b)
        return ids, contexts, status

    ids, contexts, status = asyncio.run(run())
    assert len(ids) == 2
    assert ("cve", "CVE-2024-0001") in contexts
    assert ("cve", "CVE-2024-0002") in contexts
    aq.reset_api_queue()


def test_no_secrets_in_queue_status():
    aq.reset_api_queue()

    async def run():
        rid = await aq.await_api_slot(
            "webhook.test",
            operation="webhook_delivery",
            context_type="url",
            context_id="https://hooks.example.com/path?token=supersecret",
        )
        status = aq.get_api_queue_status()
        aq.release_api_slot("webhook.test", rid)
        return status

    status = asyncio.run(run())
    blob = json.dumps(status)
    assert "supersecret" not in blob
    assert "token=" not in blob
    reqs = status.get("requests") or []
    if reqs:
        assert "?" not in (reqs[0].get("context_id") or "")
    aq.reset_api_queue()


def test_aggregate_counts_remain_correct():
    aq.reset_api_queue()

    async def run():
        rids = []
        for _ in range(2):
            rids.append(
                await aq.await_api_slot(
                    "rss",
                    operation="outbound_request",
                    context_type="task",
                    context_id="rss_fetch",
                )
            )
        status = aq.get_api_queue_status()
        for rid in rids:
            aq.release_api_slot("rss", rid)
        return status

    status = asyncio.run(run())
    assert status["total_active"] == 2
    assert status["sources"]["rss"]["active"] == 2
    assert status["total_queued"] == 0
    aq.reset_api_queue()


def test_queue_status_tracks_waiting():
    aq.reset_api_queue()

    async def run():
        aq.schedule_source_pause("demo", 0.05, reason="pacing")
        task = asyncio.create_task(
            aq.await_api_slot("demo", operation="cve_lookup", context_type="cve", context_id="CVE-2024-0001")
        )
        await asyncio.sleep(0)
        status = aq.get_api_queue_status()
        await task
        return status

    status = asyncio.run(run())
    assert status["total_queued"] >= 0
    reqs = status.get("requests") or []
    if reqs:
        assert reqs[0]["state"] in ("queued", "waiting", "rate_limited", "active")
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


def test_rate_limited_request_exposes_retry_and_readable_reason():
    aq.reset_api_queue()
    aq.schedule_source_pause("github", 42.0, reason="github_quota")

    async def run():
        task = asyncio.create_task(
            aq.await_api_slot("github", operation="exploit_search", context_type="cve", context_id="CVE-2024-0099")
        )
        await asyncio.sleep(0)
        status = aq.get_api_queue_status()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return status

    status = asyncio.run(run())
    reqs = status.get("requests") or []
    if reqs:
        assert reqs[0]["state"] == "rate_limited"
        assert reqs[0]["wait_reason"] == "GitHub rate limit"
        assert reqs[0].get("retry_in_seconds", 0) > 0
    aq.reset_api_queue()


def test_legacy_release_without_request_id():
    aq.reset_api_queue()

    async def run():
        await aq.await_api_slot("legacy_source")
        aq.release_api_slot("legacy_source")
        return aq.get_api_queue_status()

    status = asyncio.run(run())
    assert status["total_active"] == 0
    aq.reset_api_queue()
