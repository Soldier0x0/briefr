"""Tests for API queue operation labels and safe context sanitization."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_queue_operations import (
    LLM_TASK_OPERATIONS,
    OPERATION_LABELS,
    operation_label,
    public_request_state,
    resolve_queue_task,
    sanitize_context,
    wait_reason_label,
)


def test_operation_label_known_operations():
    assert operation_label("exploit_search") == "Searching public exploit references"
    assert operation_label("cve_ingest") == "Syncing NVD vulnerability feed"
    assert operation_label("news_feed_sync") == "Syncing incident news feed"
    assert operation_label("threat_intel_sync") == "Syncing ThreatFox indicators"
    assert operation_label("unknown_op") == OPERATION_LABELS["outbound_request"]


def test_wait_reason_label_maps_internal_keys():
    assert wait_reason_label("github_quota") == "GitHub rate limit"
    assert wait_reason_label("pacing") == "Provider pacing"
    assert wait_reason_label("concurrency") == "Waiting for active request"
    assert wait_reason_label("mystery") == "Waiting for provider slot"
    assert wait_reason_label(None) is None


def test_sanitize_context_cve():
    assert sanitize_context("cve", "cve-2024-12345") == ("cve", "CVE-2024-12345")
    assert sanitize_context("cve", "not-a-cve") == (None, None)


def test_sanitize_context_ip_hash_domain_url():
    assert sanitize_context("ip", "192.168.1.1") == ("ip", "192.168.1.1")
    assert sanitize_context("ip", "999.999.999.999") == (None, None)
    assert sanitize_context(
        "hash",
        "a" * 64,
    ) == ("hash", "a" * 64)
    assert sanitize_context("domain", "evil.example.com") == ("domain", "evil.example.com")
    assert sanitize_context(
        "url",
        "https://example.com/path?token=secret",
    ) == ("url", "https://example.com/path")


def test_sanitize_context_strips_secrets_from_url():
    ctype, cid = sanitize_context("url", "https://hooks.example.com/notify?sig=abc123")
    assert ctype == "url"
    assert "?" not in cid
    assert "sig" not in cid


def test_sanitize_context_masks_webhook_path_tail():
    ctype, cid = sanitize_context(
        "url",
        "https://discord.com/api/webhooks/1234567890/abcdefghijklmnop",
    )
    assert ctype == "url"
    assert cid.endswith("/…")
    assert "abcdefghijklmnop" not in cid


def test_resolve_queue_task_rejects_unknown_operation():
    task = resolve_queue_task(
        "github",
        operation="not_registered_anywhere",
        context_type="cve",
        context_id="CVE-2024-0001",
    )
    assert task["operation"] == "outbound_request"
    assert task["context_type"] == "cve"
    assert task["context_id"] == "CVE-2024-0001"


def test_public_request_state_mapping():
    assert public_request_state("active", None) == "active"
    assert public_request_state("queued", None) == "queued"
    assert public_request_state("waiting", "pacing") == "waiting"
    assert public_request_state("rate_limited", "github_quota", paused_for_seconds=10) == "rate_limited"
    assert public_request_state("waiting", "github_quota", paused_for_seconds=5) == "rate_limited"


def test_llm_task_operations_cover_router_tasks():
    assert LLM_TASK_OPERATIONS["product_extraction"] == "product_extraction"
    assert LLM_TASK_OPERATIONS["pdf_summary"] == "report_summary"
    assert LLM_TASK_OPERATIONS["detection_context"] == "detection_context"
