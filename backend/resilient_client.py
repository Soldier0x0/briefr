"""Shared resilient HTTP client for all outbound intel sources.

One pooled httpx.AsyncClient + per-source retries, circuit breakers, a global
API queue (rate-limit pacing — requests wait, never drop), and a health registry
surfaced on /api/health.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from api_queue import (
    apply_rate_limit_headers,
    await_api_slot,
    get_api_queue_status,
    release_api_slot,
    reset_api_queue,
    schedule_source_pause,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5
RETRYABLE_STATUS = {500, 502, 503, 504}

CIRCUIT_FAILURE_THRESHOLD = int(os.environ.get("CIRCUIT_FAILURE_THRESHOLD", "3"))
CIRCUIT_COOLDOWN_SECONDS = float(os.environ.get("CIRCUIT_COOLDOWN_SECONDS", "60"))

_client: httpx.AsyncClient | None = None

# source -> health state (single event loop; plain dict ops are atomic enough)
_health: dict[str, dict[str, Any]] = {}


class CircuitOpenError(Exception):
    """Raised when a source's circuit is open — callers may wait and retry."""

    def __init__(self, source: str, retry_at: float):
        self.source = source
        self.retry_at = retry_at
        super().__init__(f"Circuit open for {source}; retry after {retry_at:.0f}")


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"User-Agent": "BRIEFR/1.0 (+https://github.com/Soldier0x0/briefr)"},
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _state(source: str) -> dict[str, Any]:
    return _health.setdefault(
        source,
        {
            "last_success": None,
            "last_failure": None,
            "last_error": None,
            "consecutive_failures": 0,
            "circuit_open_until": 0.0,
        },
    )


def _record_success(source: str) -> None:
    state = _state(source)
    state["last_success"] = time.time()
    state["consecutive_failures"] = 0
    state["circuit_open_until"] = 0.0
    state["last_error"] = None


def _record_failure(
    source: str, error: str, *, cooldown_seconds: float | None = None
) -> None:
    state = _state(source)
    state["last_failure"] = time.time()
    state["last_error"] = error[:300]
    state["consecutive_failures"] += 1
    if state["consecutive_failures"] >= CIRCUIT_FAILURE_THRESHOLD:
        cooldown = (
            cooldown_seconds
            if cooldown_seconds is not None
            else CIRCUIT_COOLDOWN_SECONDS
        )
        state["circuit_open_until"] = time.time() + cooldown
        logger.warning(
            "Circuit opened for %s after %d consecutive failures (cooldown %ss): %s",
            source,
            state["consecutive_failures"],
            cooldown,
            error,
        )


def _circuit_open_until(source: str) -> float:
    return float(_state(source).get("circuit_open_until") or 0.0)


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    for header in ("Retry-After", "retry-after"):
        retry_after = (response.headers.get(header) or "").strip()
        if not retry_after:
            continue
        try:
            return min(float(retry_after), 120.0)
        except ValueError:
            pass
        match = re.match(
            r"^(?:(?P<mins>\d+)m)?(?:(?P<secs>\d+(?:\.\d+)?)s)?$", retry_after
        )
        if match:
            mins = int(match.group("mins") or 0)
            secs = float(match.group("secs") or 0)
            return min(mins * 60.0 + secs, 120.0)
    return RETRY_BACKOFF_SECONDS * (2**attempt)


async def _execute_request_attempt(
    source: str,
    method: str,
    url: str,
    *,
    headers: dict | None,
    params: dict | None,
    json: Any,
    data: Any,
    timeout: float,
    retries: int,
    record_client_error: bool,
) -> httpx.Response:
    """Single logical request with bounded retries for transport/5xx errors."""
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            _record_failure(source, f"{type(exc).__name__}: {exc}")
            raise

        if response.status_code in RETRYABLE_STATUS:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt < retries:
                await asyncio.sleep(_retry_after_seconds(response, attempt))
                continue
            cooldown = max(
                _retry_after_seconds(response, attempt), CIRCUIT_COOLDOWN_SECONDS
            )
            _record_failure(
                source, f"HTTP {response.status_code}", cooldown_seconds=cooldown
            )
            response.raise_for_status()

        if response.status_code == 429:
            apply_rate_limit_headers(source, response.headers)
            last_exc = httpx.HTTPStatusError(
                "HTTP 429",
                request=response.request,
                response=response,
            )
            if attempt < retries:
                await asyncio.sleep(_retry_after_seconds(response, attempt))
                continue
            raise last_exc

        if response.status_code == 403:
            apply_rate_limit_headers(source, response.headers)
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                try:
                    if int(remaining) <= 0:
                        last_exc = httpx.HTTPStatusError(
                            "HTTP 403 rate limit",
                            request=response.request,
                            response=response,
                        )
                        if attempt < retries:
                            await asyncio.sleep(_retry_after_seconds(response, attempt))
                            continue
                        raise last_exc
                except ValueError:
                    pass

        if response.is_server_error:
            _record_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        if response.is_client_error:
            if record_client_error:
                _state(source)["last_error"] = f"HTTP {response.status_code}"
            response.raise_for_status()

        _record_success(source)
        apply_rate_limit_headers(source, response.headers)
        return response

    raise last_exc if last_exc else RuntimeError(f"request failed for {source}")


async def resilient_request(
    source: str,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json: Any = None,
    data: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    wait_on_rate_limit: bool = True,
    wait_on_circuit: bool = False,
    record_client_error: bool = True,
    queue_operation: str | None = None,
    queue_context_type: str | None = None,
    queue_context_id: str | None = None,
) -> httpx.Response:
    """Perform an HTTP request with queue pacing, retries, and circuit recovery.

    Rate limits (HTTP 429) never drop the request when ``wait_on_rate_limit``
    is True — the call waits in the API queue and retries. Circuit-open behavior
    is controlled by ``wait_on_circuit`` (False = fail fast for optional feeds).
    """
    while True:
        open_until = _circuit_open_until(source)
        if open_until and time.time() < open_until:
            if wait_on_circuit:
                wait = open_until - time.time() + 0.1
                schedule_source_pause(source, wait, reason="circuit_open")
                logger.info(
                    "Waiting %.1fs for %s circuit to close before retrying",
                    wait,
                    source,
                )
                await asyncio.sleep(wait)
                continue
            raise CircuitOpenError(source, open_until)

        slot_id = await await_api_slot(
            source,
            operation=queue_operation,
            context_type=queue_context_type,
            context_id=queue_context_id,
        )
        try:
            return await _execute_request_attempt(
                source,
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
                retries=retries,
                record_client_error=record_client_error,
            )
        except httpx.HTTPStatusError as exc:
            is_rate_limited = exc.response.status_code == 429 or (
                exc.response.status_code == 403
                and exc.response.headers.get("x-ratelimit-remaining") == "0"
            )
            if wait_on_rate_limit and is_rate_limited:
                logger.warning(
                    "Rate limited on %s — queued retry after pacing", source
                )
                continue
            raise
        finally:
            release_api_slot(source, slot_id)


async def resilient_get(source: str, url: str, **kwargs: Any) -> httpx.Response:
    return await resilient_request(source, "GET", url, **kwargs)


def get_pooled_client() -> httpx.AsyncClient:
    """Shared pooled client for modules with bespoke retry logic (e.g. NVD)."""
    return _get_client()


def record_source_success(source: str) -> None:
    """Health hook for modules that manage their own request logic."""
    _record_success(source)


def record_source_failure(source: str, error: str) -> None:
    """Health hook for modules that manage their own request logic."""
    _record_failure(source, error)


def get_feed_health() -> dict[str, dict[str, Any]]:
    """Per-source health snapshot for /api/health."""
    now = time.time()
    result: dict[str, dict[str, Any]] = {}
    for source, state in sorted(_health.items()):
        open_until = state["circuit_open_until"]
        result[source] = {
            "last_success": _iso(state["last_success"]),
            "last_failure": _iso(state["last_failure"]),
            "last_error": state["last_error"],
            "consecutive_failures": state["consecutive_failures"],
            "circuit_open": bool(open_until and now < open_until),
        }
    return result


def reset_feed_health() -> None:
    """Test helper — clear all recorded health state."""
    _health.clear()
    reset_api_queue()


def reset_circuit(source_id: str) -> None:
    """Admin action: immediately close an open circuit for a named source.
    Raises KeyError if source_id is not in the health registry.
    """
    if source_id not in _health:
        raise KeyError(source_id)
    state = _health[source_id]
    state["circuit_open_until"] = 0.0
    state["consecutive_failures"] = 0
    state["last_error"] = None
    logger.info("Circuit reset by admin for source: %s", source_id)


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


__all__ = [
    "CircuitOpenError",
    "await_api_slot",
    "get_api_queue_status",
    "get_feed_health",
    "get_pooled_client",
    "record_source_failure",
    "record_source_success",
    "release_api_slot",
    "reset_circuit",
    "reset_feed_health",
    "resilient_get",
    "resilient_request",
    "schedule_source_pause",
]
