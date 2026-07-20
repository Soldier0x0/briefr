"""Global outbound API request queue — wait for slots, never drop on rate limits."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from api_queue_operations import (
    RATE_LIMIT_REASONS,
    public_request_state,
    resolve_queue_task,
    wait_reason_label,
)
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


@dataclass
class _ApiRequest:
    request_id: str
    source: str
    pacing_key: str
    operation: str
    display_label: str
    context_type: str | None
    context_id: str | None
    state: str  # queued | waiting | rate_limited | active
    queued_at_mono: float
    queued_at: str
    started_at: str | None = None
    started_at_mono: float | None = None
    wait_reason: str | None = None


_states: dict[str, _SourceQueueState] = {}
_requests: dict[str, _ApiRequest] = {}
# LIFO stack of active request_ids per pacing key (legacy release_api_slot(source))
_active_stacks: dict[str, list[str]] = {}


def _state(source: str) -> _SourceQueueState:
    key = resolve_pacing_key(source)
    return _states.setdefault(key, _SourceQueueState())


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Cap provider pause so a misparsed absolute timestamp cannot stall the queue for years.
_MAX_SOURCE_PAUSE_SECONDS = 3600.0
# Bare numbers at/above this are treated as Unix epoch seconds (not relative duration).
_UNIX_SECONDS_FLOOR = 1_000_000_000.0  # ~2001-09-09
# Bare numbers at/above this are treated as Unix epoch milliseconds.
_UNIX_MS_FLOOR = 1_000_000_000_000.0


def _parse_duration_seconds(value: str) -> float:
    """Parse Retry-After / X-RateLimit-Reset-* into a relative wait in seconds.

    Accepts:
    - relative seconds (``12``, ``1.5``)
    - unit durations (``12ms``, ``7.66s``, ``2m59s``, ``1h``, ``6m0s``)
    - HTTP-date absolute times
    - Unix epoch seconds or milliseconds (converted to delta from now)

    Misparsed absolute timestamps must never be treated as multi-year relative waits.
    """
    text = (value or "").strip()
    if not text:
        return 0.0

    # Prefer unit durations before bare float so "12ms" is not rejected later.
    match = re.match(
        r"^(?:(?P<hours>\d+)h)?(?:(?P<mins>\d+)m(?!s))?(?:(?P<secs>\d+(?:\.\d+)?)(?P<sunit>ms|s))?$",
        text,
        flags=re.IGNORECASE,
    )
    if match and any(match.group(g) for g in ("hours", "mins", "secs")):
        hours = int(match.group("hours") or 0)
        mins = int(match.group("mins") or 0)
        secs_raw = match.group("secs")
        sunit = (match.group("sunit") or "s").lower()
        secs = float(secs_raw) if secs_raw is not None else 0.0
        if sunit == "ms":
            secs = secs / 1000.0
        return hours * 3600.0 + mins * 60.0 + secs

    try:
        num = float(text)
    except ValueError:
        num = None

    if num is not None and num == num:  # finite (reject NaN)
        now = time.time()
        if num >= _UNIX_MS_FLOOR:
            return max(0.0, (num / 1000.0) - now)
        if num >= _UNIX_SECONDS_FLOOR:
            return max(0.0, num - now)
        # Relative seconds (including negative / clock-skew junk → 0).
        return max(0.0, num)

    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError, IndexError):
        logger.warning(
            "Failed to parse Retry-After date value (len=%d)",
            len(text),
            exc_info=True,
        )
    return 0.0


def schedule_source_pause(source: str, seconds: float, *, reason: str = "rate_limit") -> None:
    if seconds <= 0:
        return
    if seconds > _MAX_SOURCE_PAUSE_SECONDS:
        logger.warning(
            "Clamping source pause for %s from %.1fs to %.1fs (reason=%s)",
            resolve_pacing_key(source),
            seconds,
            _MAX_SOURCE_PAUSE_SECONDS,
            reason,
        )
        seconds = _MAX_SOURCE_PAUSE_SECONDS
    state = _state(source)
    state.pause_until = max(state.pause_until, time.monotonic() + seconds)
    state.wait_reason = reason
    _sync_request_wait_states(source)


def _sync_request_wait_states(source: str) -> None:
    """Propagate source-level wait_reason to in-flight requests."""
    pacing_key = resolve_pacing_key(source)
    state = _state(source)
    now = time.monotonic()
    for req in _requests.values():
        if req.pacing_key != pacing_key or req.state == "active":
            continue
        reason = state.wait_reason or None
        paused = max(0.0, state.pause_until - now) if state.pause_until > now else 0.0
        if paused > 0 or (reason and reason in RATE_LIMIT_REASONS):
            req.state = "rate_limited"
        else:
            req.state = "waiting" if reason else "queued"
        req.wait_reason = reason


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

    try:
        from ai.quota import record_quota_snapshot

        record_quota_snapshot(source, headers)
    except Exception:
        logger.warning(
            "Quota snapshot record failed for source=%s",
            source,
            exc_info=True,
        )


async def await_api_slot(
    source: str,
    *,
    operation: str | None = None,
    context_type: str | None = None,
    context_id: str | None = None,
) -> str:
    """Block until this source's pacing window allows another request.

    Returns a request_id token for release_api_slot().
    """
    pacing = get_source_pacing(source)
    pacing_key = resolve_pacing_key(source)
    state = _state(source)
    if state.lock is None:
        state.lock = asyncio.Lock()

    task = resolve_queue_task(
        source,
        operation=operation,
        context_type=context_type,
        context_id=context_id,
    )
    request_id = uuid.uuid4().hex[:12]
    now_mono = time.monotonic()
    req = _ApiRequest(
        request_id=request_id,
        source=source,
        pacing_key=pacing_key,
        operation=task["operation"],
        display_label=task["display_label"],
        context_type=task["context_type"],
        context_id=task["context_id"],
        state="queued",
        queued_at_mono=now_mono,
        queued_at=_utc_now(),
    )
    _requests[request_id] = req

    state.queued += 1
    try:
        while True:
            async with state.lock:
                now = time.monotonic()
                if state.active >= pacing.max_concurrent:
                    state.wait_reason = "concurrency"
                    req.state = "waiting"
                    req.wait_reason = "concurrency"
                    wait = 0.25
                else:
                    earliest = max(
                        state.pause_until,
                        state.last_request_at + pacing.min_interval_seconds,
                    )
                    if earliest > now:
                        reason = state.wait_reason or "pacing"
                        paused = state.pause_until > now
                        if paused and reason in RATE_LIMIT_REASONS:
                            req.state = "rate_limited"
                        else:
                            req.state = "waiting"
                        req.wait_reason = reason
                        state.wait_reason = reason
                        wait = earliest - now
                    else:
                        state.active += 1
                        state.last_request_at = time.monotonic()
                        state.wait_reason = ""
                        req.state = "active"
                        req.wait_reason = None
                        req.started_at_mono = time.monotonic()
                        req.started_at = _utc_now()
                        stack = _active_stacks.setdefault(pacing_key, [])
                        stack.append(request_id)
                        return request_id
            await asyncio.sleep(min(wait, 1.0))
    finally:
        state.queued = max(0, state.queued - 1)
        if req.state != "active":
            _requests.pop(request_id, None)


def release_api_slot(source: str, request_id: str | None = None) -> None:
    """Release a slot. Pass request_id from await_api_slot when available."""
    pacing_key = resolve_pacing_key(source)
    state = _state(source)
    stack = _active_stacks.setdefault(pacing_key, [])

    if request_id is not None:
        if request_id in _requests:
            _requests.pop(request_id, None)
            if request_id in stack:
                stack.remove(request_id)
            state.active = max(0, state.active - 1)
        return

    if stack:
        rid = stack.pop()
        _requests.pop(rid, None)
    state.active = max(0, state.active - 1)


def get_api_queue_status() -> dict[str, Any]:
    """Snapshot for /api/health and admin UI."""
    now = time.monotonic()
    sources: dict[str, dict[str, Any]] = {}
    total_queued = 0
    total_active = 0
    requests_out: list[dict[str, Any]] = []

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

    for req in sorted(_requests.values(), key=lambda r: (r.queued_at_mono, r.request_id)):
        src_state = _states.get(req.pacing_key)
        paused_for = 0.0
        if src_state and src_state.pause_until > now:
            paused_for = src_state.pause_until - now
        elapsed = 0.0
        if req.started_at_mono is not None:
            elapsed = now - req.started_at_mono
        elif req.state != "active":
            elapsed = now - req.queued_at_mono

        pub_state = public_request_state(
            req.state,
            req.wait_reason or (src_state.wait_reason if src_state else None),
            paused_for_seconds=paused_for,
        )
        analyst_reason = wait_reason_label(req.wait_reason or (src_state.wait_reason if src_state else None))

        requests_out.append({
            "request_id": req.request_id,
            "source": req.pacing_key,
            "operation": req.operation,
            "display_label": req.display_label,
            "context_type": req.context_type,
            "context_id": req.context_id,
            "state": pub_state,
            "queued_at": req.queued_at,
            "started_at": req.started_at,
            "elapsed_seconds": round(elapsed, 1),
            "wait_reason": analyst_reason,
            "retry_in_seconds": round(paused_for, 1) if pub_state == "rate_limited" and paused_for > 0 else None,
        })

    return {
        "total_queued": total_queued,
        "total_active": total_active,
        "has_pending": total_queued > 0 or total_active > 0 or any(
            s.get("paused_for_seconds", 0) > 0 for s in sources.values()
        ),
        "sources": sources,
        "requests": requests_out,
    }


def reset_api_queue() -> None:
    """Test helper — clear queue state."""
    _states.clear()
    _requests.clear()
    _active_stacks.clear()
