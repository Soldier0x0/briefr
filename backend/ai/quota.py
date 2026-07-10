"""Advisory LLM provider quota snapshots from rate-limit response headers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_LLM_PROVIDERS = frozenset({"groq", "gemini", "cerebras", "openrouter"})
_snapshots: dict[str, dict[str, Any]] = {}


def _normalize_provider(source: str) -> str | None:
    key = (source or "").strip().lower()
    if key in _LLM_PROVIDERS:
        return key
    return None


def record_quota_snapshot(source: str, headers: Any) -> None:
    provider = _normalize_provider(source)
    if not provider:
        return
    get = getattr(headers, "get", None)
    if not callable(get):
        return
    _snapshots[provider] = {
        "remaining_requests": get("x-ratelimit-remaining-requests") or get("X-RateLimit-Remaining-Requests"),
        "reset_requests": get("x-ratelimit-reset-requests") or get("X-RateLimit-Reset-Requests"),
        "remaining_tokens": get("x-ratelimit-remaining-tokens") or get("X-RateLimit-Remaining-Tokens"),
        "reset_tokens": get("x-ratelimit-reset-tokens") or get("X-RateLimit-Reset-Tokens"),
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def get_quota_snapshot(provider: str) -> dict[str, Any] | None:
    return _snapshots.get(provider)


def quota_warnings() -> list[str]:
    warnings: list[str] = []
    for provider, snap in _snapshots.items():
        remaining = snap.get("remaining_requests")
        if remaining is None:
            continue
        try:
            if int(remaining) <= 5:
                warnings.append(f"{provider}: low request quota ({remaining} remaining)")
        except (TypeError, ValueError):
            continue
    return warnings
