"""In-memory token-bucket rate limiting (V1.2 §5.5).

Protects the abuse-prone endpoints — `POST /api/ioc/lookup` (burns external
API quota per miss) and `POST /api/refresh*` (kicks off heavy ingest jobs).
SQLite pins the deployment to a single uvicorn worker, so process-local
buckets are sufficient; no shared store needed.

Buckets are keyed per client IP. Forwarded headers are honoured **only when
the socket peer is a loopback proxy** (nginx/cloudflared run on the same
box — `deploy/nginx-briefr*.conf` proxy_pass to 127.0.0.1:8000); any direct
connection is keyed by its socket address, so spoofed headers cannot mint
fresh buckets. Behind the tunnel, `CF-Connecting-IP` wins (Cloudflare
overwrites it at the edge), then the rightmost non-loopback
`X-Forwarded-For` hop (the entry appended by our own nginx/Cloudflare —
the leftmost hops are client-controlled), then `X-Real-IP`. Residual risk:
a host on the LAN talking to nginx directly can still forge these headers —
acceptable for the Access-gated private beta; revisit with built-in login.

Limits exceeded → HTTP 429 with a `Retry-After` header (whole seconds).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import math
import time

from fastapi import HTTPException, Request

from settings import settings

# Idle buckets are pruned once the dict grows past this many client keys.
_PRUNE_THRESHOLD = 1024
# Hard cap: a flood of distinct keys inside one refill window defeats the
# idle prune, so least-recently-seen buckets are evicted past this size.
_MAX_BUCKETS = 2 * _PRUNE_THRESHOLD

# Loopback peers are our own reverse proxies (nginx/cloudflared on the same
# box); only they may speak for the client via forwarded headers.
_TRUSTED_PROXY_PEERS = frozenset({"127.0.0.1", "::1", "localhost"})


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
        self.hit_count: int = 0
        # key -> (tokens_remaining, last_update_monotonic)
        self._buckets: dict[str, tuple[float, float]] = {}
        # key -> cumulative acquire() call count for that key
        self._hits: dict[str, int] = {}

    def acquire(self, key: str, now: float | None = None) -> float:
        """Try to take one token for `key`.

        Returns 0.0 when granted, otherwise the number of seconds until the
        next token becomes available (the Retry-After hint).
        """
        self.hit_count += 1
        self._hits[key] = self._hits.get(key, 0) + 1
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
        active_keys = set(self._buckets)
        self._hits = {k: v for k, v in self._hits.items() if k in active_keys}
        if len(self._buckets) <= _MAX_BUCKETS:
            return
        # Flood of distinct keys inside one refill window: nothing is idle,
        # so bound memory by evicting the least-recently-seen buckets. An
        # evicted bucket restarts full — a flooder can reset limits this
        # way, but bounded memory beats a remotely triggerable OOM.
        by_recency = sorted(
            self._buckets.items(), key=lambda item: item[1][1], reverse=True
        )
        self._buckets = dict(by_recency[:_PRUNE_THRESHOLD])
        active_keys = set(self._buckets)
        self._hits = {k: v for k, v in self._hits.items() if k in active_keys}


ioc_bucket = TokenBucket(settings.rate_limit_ioc_per_minute, name="ioc")
refresh_bucket = TokenBucket(settings.rate_limit_refresh_per_minute, name="refresh")
wallboard_bucket = TokenBucket(settings.rate_limit_wallboard_per_minute, name="wallboard")


def client_key(request: Request) -> str:
    peer = request.client.host if request.client else ""
    if peer not in _TRUSTED_PROXY_PEERS:
        # Direct connection (LAN dev, or someone bypassing nginx): the
        # socket address is the only trustworthy identity — forwarded
        # headers here would be attacker-controlled bucket keys.
        return peer or "unknown"

    # Set by the Cloudflare edge and overwritten there, so it cannot be
    # forged by clients coming through the tunnel.
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip

    # nginx appends $remote_addr as the rightmost X-Forwarded-For hop; the
    # rightmost non-loopback hop is therefore proxy-attested, while the
    # leftmost hops are whatever the client sent.
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(hops):
        if hop not in _TRUSTED_PROXY_PEERS:
            return hop

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip and real_ip not in _TRUSTED_PROXY_PEERS:
        return real_ip

    return peer


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


def rate_limit_wallboard(request: Request) -> None:
    """Route dependency: token bucket for GET /api/wallboard."""
    _enforce(wallboard_bucket, request)


def get_top_consumers(n: int = 5) -> list[dict]:
    """Aggregate per-key hit counts across ioc_bucket and refresh_bucket, return top-n."""
    counts: dict[str, int] = {}
    for bucket in (ioc_bucket, refresh_bucket, wallboard_bucket):
        for key, hits in getattr(bucket, "_hits", {}).items():
            counts[key] = counts.get(key, 0) + hits
    return [
        {"key": k, "hits": v}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
    ]
