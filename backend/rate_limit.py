"""In-memory token-bucket rate limiting (V1.2 §5.5).

Protects the abuse-prone endpoints — `POST /api/ioc/lookup` (burns external
API quota per miss) and `POST /api/refresh*` (kicks off heavy ingest jobs).
SQLite pins the deployment to a single uvicorn worker, so process-local
buckets are sufficient; no shared store needed.

Buckets are keyed per client IP. Behind nginx/cloudflared every connection
arrives from 127.0.0.1, so the first `X-Forwarded-For` hop is preferred when
present (spoofable only with direct network access — acceptable for the
Cloudflare-Access-gated private beta; revisit with built-in app login).

Limits exceeded → HTTP 429 with a `Retry-After` header (whole seconds).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import math
import time

from fastapi import HTTPException, Request

from settings import settings

# Idle buckets are pruned once the dict grows past this many client keys.
_PRUNE_THRESHOLD = 1024


class TokenBucket:
    """Classic token bucket, one bucket per key.

    Capacity equals the per-minute rate (a full minute's allowance may be
    spent as a burst); tokens refill continuously at rate/60 per second.
    Single-threaded asyncio access — no locking needed (no await between
    the read and the write of a bucket's state).
    """

    def __init__(self, rate_per_minute: int, name: str = ""):
        self.rate_per_minute = max(1, int(rate_per_minute))
        self.capacity = float(self.rate_per_minute)
        self.refill_per_second = self.rate_per_minute / 60.0
        self.name = name
        # key -> (tokens_remaining, last_update_monotonic)
        self._buckets: dict[str, tuple[float, float]] = {}

    def acquire(self, key: str, now: float | None = None) -> float:
        """Try to take one token for `key`.

        Returns 0.0 when granted, otherwise the number of seconds until the
        next token becomes available (the Retry-After hint).
        """
        if now is None:
            now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            self._maybe_prune(now)
            return 0.0
        self._buckets[key] = (tokens, now)
        return (1.0 - tokens) / self.refill_per_second

    def _maybe_prune(self, now: float) -> None:
        if len(self._buckets) < _PRUNE_THRESHOLD:
            return
        # A bucket idle long enough to be full again carries no state worth
        # keeping; dropping it is equivalent to recreating it on next use.
        full_after = self.capacity / self.refill_per_second
        self._buckets = {
            key: state
            for key, state in self._buckets.items()
            if now - state[1] < full_after
        }


ioc_bucket = TokenBucket(settings.rate_limit_ioc_per_minute, name="ioc")
refresh_bucket = TokenBucket(settings.rate_limit_refresh_per_minute, name="refresh")


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else "unknown"


def _enforce(bucket: TokenBucket, request: Request) -> None:
    if not settings.rate_limit_enabled:
        return
    retry_after = bucket.acquire(client_key(request))
    if retry_after > 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded for {bucket.name or 'this'} endpoints "
                f"({bucket.rate_per_minute}/min). Retry later."
            ),
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


def rate_limit_ioc(request: Request) -> None:
    """Route dependency: token bucket for POST /api/ioc/lookup."""
    _enforce(ioc_bucket, request)


def rate_limit_refresh(request: Request) -> None:
    """Route dependency: token bucket for all POST /api/refresh* routes."""
    _enforce(refresh_bucket, request)
