"""Controlled operation labels and safe context for API queue task metadata."""

from __future__ import annotations

import re
from typing import Any

CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)
IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)
HASH_RE = re.compile(r"^[a-f0-9]{32,128}$", re.I)
DOMAIN_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.I,
)

# Internal wait_reason -> analyst-facing (never expose raw quota keys in UI copy)
WAIT_REASON_LABELS: dict[str, str] = {
    "concurrency": "Waiting for active request",
    "pacing": "Provider pacing",
    "circuit_open": "Provider circuit recovery",
    "retry-after": "Provider rate limit",
    "token_quota": "Provider token limit",
    "request_quota": "Provider request limit",
    "github_quota": "GitHub rate limit",
    "rate_limit": "Provider rate limit",
}

RATE_LIMIT_REASONS = frozenset(
    {"retry-after", "token_quota", "request_quota", "github_quota", "rate_limit"}
)

# operation -> display_label (source-independent semantics)
OPERATION_LABELS: dict[str, str] = {
    "exploit_search": "Searching public exploit references",
    "advisory_lookup": "Checking GitHub security advisories",
    "repository_lookup": "Inspecting referenced repository",
    "detection_rule_search": "Searching detection rule sources",
    "pulse_lookup": "Checking OTX threat pulses",
    "indicator_lookup": "Enriching threat observable",
    "ip_lookup": "Checking IP reputation",
    "observable_lookup": "Enriching observable",
    "hash_lookup": "Checking malware sample",
    "url_lookup": "Checking malicious URL intelligence",
    "cve_lookup": "Fetching vulnerability intelligence",
    "product_extraction": "Extracting affected product metadata",
    "report_summary": "Generating report summary",
    "detection_context": "Extracting detection context",
    "pdf_summary": "Generating report summary",
    "cve_ingest": "Syncing NVD vulnerability feed",
    "exploit_feed_sync": "Syncing public exploit index",
    "news_feed_sync": "Syncing incident news feed",
    "threat_intel_sync": "Syncing ThreatFox indicators",
    "osv_lookup": "Fetching OSV vulnerability record",
    "outbound_request": "Outbound API request",
    "webhook_delivery": "Delivering webhook notification",
}

# LLM router task names map to queue operations
LLM_TASK_OPERATIONS: dict[str, str] = {
    "product_extraction": "product_extraction",
    "pdf_summary": "report_summary",
    "detection_context": "detection_context",
}

DEFAULT_OPERATION = "outbound_request"


def operation_label(operation: str | None) -> str:
    key = (operation or DEFAULT_OPERATION).strip().lower()
    return OPERATION_LABELS.get(key, OPERATION_LABELS[DEFAULT_OPERATION])


def wait_reason_label(reason: str | None) -> str | None:
    if not reason:
        return None
    return WAIT_REASON_LABELS.get(reason.strip().lower(), "Waiting for provider slot")


def sanitize_context(context_type: str | None, context_id: str | None) -> tuple[str | None, str | None]:
    """Return safe (context_type, context_id) for queue status — no secrets."""
    if not context_id:
        return None, None
    raw = str(context_id).strip()
    if not raw or len(raw) > 128:
        return None, None

    ctype = (context_type or "").strip().lower()
    if ctype == "cve":
        cve = raw.upper()
        return ("cve", cve) if CVE_RE.match(cve) else (None, None)
    if ctype == "ip":
        return ("ip", raw) if IPV4_RE.match(raw) else (None, None)
    if ctype == "hash":
        return ("hash", raw.lower()) if HASH_RE.match(raw) else (None, None)
    if ctype == "domain":
        host = raw.lower().split("/")[0].split("?")[0]
        return ("domain", host) if DOMAIN_RE.match(host) else (None, None)
    if ctype == "url":
        # Strip query strings — may contain tokens
        base = raw.split("?")[0].split("#")[0]
        if len(base) > 96:
            base = base[:96] + "…"
        return ("url", base) if base.startswith(("http://", "https://")) else (None, None)
    if ctype == "observable":
        if len(raw) > 64:
            raw = raw[:64] + "…"
        return ("observable", raw)
    if ctype == "task":
        safe = re.sub(r"[^a-z0-9_-]", "", raw.lower())[:48]
        return ("task", safe) if safe else (None, None)
    return (None, None)


def resolve_queue_task(
    source: str,
    *,
    operation: str | None = None,
    context_type: str | None = None,
    context_id: str | None = None,
) -> dict[str, Any]:
    """Build a safe task descriptor for queue registration."""
    op = (operation or DEFAULT_OPERATION).strip().lower()
    if op not in OPERATION_LABELS:
        op = DEFAULT_OPERATION
    ctype, cid = sanitize_context(context_type, context_id)
    return {
        "source": source,
        "operation": op,
        "display_label": operation_label(op),
        "context_type": ctype,
        "context_id": cid,
    }


def public_request_state(
    internal_state: str,
    wait_reason: str | None,
    *,
    paused_for_seconds: float = 0.0,
) -> str:
    """Map internal tracking to analyst-facing state token."""
    if internal_state == "active":
        return "active"
    reason = (wait_reason or "").strip().lower()
    if paused_for_seconds > 0 or reason in RATE_LIMIT_REASONS:
        return "rate_limited"
    if internal_state == "queued" and not reason:
        return "queued"
    return "waiting"
