"""Global outbound API request queue — wait for slots, never drop on rate limits."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from source_rate_limits import get_source_pacing, resolve_pacing_key

logger = logging.getLogger(__name__)


@dataclass
class _SourceQueueState:
    queued: int = 0
    active: int = 0
    pause_until: float = 0.0
    last_request_at: float = 0.0
    wait_reason: str = ""
    lock: asyncio.Lock | None = None


_states: dict[str, _SourceQueueState] = {}


def _state(source: str) -> _SourceQueueState:
    key = resolve_pacing_key(source)
    return _states.setdefault(key, _SourceQueueState())


def _parse_duration_seconds(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    match = re.match(r"^(?:(?P<mins>\d+)m)?(?:(?P<secs>\d+(?:\.\d+)?)s)?$", text)
    if not match:
        return 0.0
    mins = int(match.group("mins") or 0)
    secs = float(match.group("secs") or 0)
    return mins * 60.0 + secs


def schedule_source_pause(source: str, seconds: float, *, reason: str = "rate_limit") -> None:
    if seconds <= 0:
        return
    state = _state(source)
    state.pause_until = max(state.pause_until, time.monotonic() + seconds)
    state.wait_reason = reason


def apply_rate_limit_headers(
    source: str,
    headers: httpx.Headers,
    *,
    estimated_tokens: int | None = None,
) -> None:
    """Update pacing from provider rate-limit response headers."""
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after:
        schedule_source_pause(
            source, _parse_duration_seconds(retry_after), reason="retry-after"
        )

    remaining_tokens = headers.get("x-ratelimit-remaining-tokens")
    reset_tokens = headers.get("x-ratelimit-reset-tokens")
    if remaining_tokens is not None and reset_tokens and estimated_tokens is not None:
        try:
            if int(remaining_tokens) < estimated_tokens:
                schedule_source_pause(
                    source,
                    _parse_duration_seconds(reset_tokens),
                    reason="token_quota",
                )
        except ValueError:
            pass

    remaining_requests = headers.get("x-ratelimit-remaining-requests")
    reset_requests = headers.get("x-ratelimit-reset-requests")
    if remaining_requests is not None and reset_requests:
        try:
            if int(remaining_requests) <= 0:
                schedule_source_pause(
                    source,
                    _parse_duration_seconds(reset_requests),
                    reason="request_quota",
                )
        except ValueError:
            pass

    # GitHub REST: x-ratelimit-remaining / x-ratelimit-reset (unix epoch)
    gh_remaining = headers.get("x-ratelimit-remaining")
    gh_reset = headers.get("x-ratelimit-reset")
    if gh_remaining is not None and gh_reset:
        try:
            if int(gh_remaining) <= 0:
                reset_at = float(gh_reset)
                schedule_source_pause(
                    source,
                    max(0.5, reset_at - time.time()),
                    reason="github_quota",
                )
        except ValueError:
            pass


async def await_api_slot(source: str) -> None:
    """Block until this source's pacing window allows another request."""
    pacing = get_source_pacing(source)
    state = _state(source)
    if state.lock is None:
        state.lock = asyncio.Lock()

    state.queued += 1
    try:
        while True:
            async with state.lock:
                now = time.monotonic()
                if state.active >= pacing.max_concurrent:
                    state.wait_reason = "concurrency"
                    wait = 0.25
                else:
                    earliest = max(
                        state.pause_until,
                        state.last_request_at + pacing.min_interval_seconds,
                    )
                    if earliest > now:
                        state.wait_reason = "pacing"
                        wait = earliest - now
                    else:
                        state.active += 1
                        state.last_request_at = time.monotonic()
                        state.wait_reason = ""
                        return
            await asyncio.sleep(min(wait, 1.0))
    except BaseException:
        state.queued = max(0, state.queued - 1)
        raise
    else:
        state.queued = max(0, state.queued - 1)


def release_api_slot(source: str) -> None:
    state = _state(source)
    state.active = max(0, state.active - 1)


def get_api_queue_status() -> dict[str, Any]:
    """Snapshot for /api/health and admin UI."""
    now = time.monotonic()
    sources: dict[str, dict[str, Any]] = {}
    total_queued = 0
    total_active = 0

    for key, state in sorted(_states.items()):
        if state.queued == 0 and state.active == 0 and state.pause_until <= now:
            continue
        pacing = get_source_pacing(key)
        paused_for = max(0.0, state.pause_until - now) if state.pause_until > now else 0.0
        entry = {
            "queued": state.queued,
            "active": state.active,
            "paused_for_seconds": round(paused_for, 1),
            "wait_reason": state.wait_reason or None,
            "min_interval_seconds": pacing.min_interval_seconds,
        }
        sources[key] = entry
        total_queued += state.queued
        total_active += state.active

    return {
        "total_queued": total_queued,
        "total_active": total_active,
        "has_pending": total_queued > 0 or total_active > 0 or any(
            s.get("paused_for_seconds", 0) > 0 for s in sources.values()
        ),
        "sources": sources,
    }


def reset_api_queue() -> None:
    """Test helper — clear queue state."""
    _states.clear()
