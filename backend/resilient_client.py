"""Shared resilient HTTP client for all outbound intel sources.

One pooled httpx.AsyncClient + per-source retries, circuit breakers, and a
health registry surfaced on /api/health. Designed for ~15 external APIs so
an outage fails fast and recovers without hand-rolled error handling in
every feed module.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

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
    """Raised when a source's circuit is open — fail fast, no network call."""

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


def _record_failure(source: str, error: str) -> None:
    state = _state(source)
    state["last_failure"] = time.time()
    state["last_error"] = error[:300]
    state["consecutive_failures"] += 1
    if state["consecutive_failures"] >= CIRCUIT_FAILURE_THRESHOLD:
        state["circuit_open_until"] = time.time() + CIRCUIT_COOLDOWN_SECONDS
        logger.warning(
            "Circuit opened for %s after %d consecutive failures (cooldown %ss): %s",
            source,
            state["consecutive_failures"],
            CIRCUIT_COOLDOWN_SECONDS,
            error,
        )


def _check_circuit(source: str) -> None:
    state = _state(source)
    open_until = state["circuit_open_until"]
    if open_until and time.time() < open_until:
        raise CircuitOpenError(source, open_until)


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return min(float(retry_after), 30.0)
    return RETRY_BACKOFF_SECONDS * (2**attempt)


async def resilient_request(
    source: str,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> httpx.Response:
    """Perform an HTTP request with retries and a per-source circuit breaker.

    Raises CircuitOpenError immediately while the source's circuit is open.
    Retries transport errors and retryable status codes (5xx, 429) with
    backoff; non-retryable HTTP errors are raised after recording health.
    """
    _check_circuit(source)
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
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            _record_failure(source, f"{type(exc).__name__}: {exc}")
            raise

        if response.status_code in RETRYABLE_STATUS or response.status_code == 429:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt < retries:
                await asyncio.sleep(_retry_after_seconds(response, attempt))
                continue
            _record_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        if response.is_server_error:
            _record_failure(source, f"HTTP {response.status_code}")
            response.raise_for_status()

        if response.is_client_error:
            # Non-retryable HTTP error (4xx other than 429): the source is
            # reachable, so do not trip the circuit — record and raise.
            _state(source)["last_error"] = f"HTTP {response.status_code}"
            response.raise_for_status()

        _record_success(source)
        return response

    # Unreachable, but keeps type-checkers honest.
    raise last_exc if last_exc else RuntimeError(f"request failed for {source}")


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


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
