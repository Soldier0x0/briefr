"""In-memory token-bucket rate limiting (V1.2 §5.5).

Protects the abuse-prone endpoints — `POST /api/ioc/lookup` (burns external
API quota per miss) and `POST /api/refresh*` (kicks off heavy ingest jobs).
Buckets are process-local: the deployment deliberately runs a single uvicorn
worker (`--workers 1` in `deploy/briefr-backend.service`) so one process
holds all buckets; adding workers would silently multiply every limit by the
worker count. Revisit with a shared store before scaling workers.

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

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
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

        from rate_limit_store import shared_acquire, shared_store_enabled

        if shared_store_enabled():
            return shared_acquire(
                self.name or "default",
                key,
                rate_per_minute=self.rate_per_minute,
                now=now,
            )

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
admin_read_bucket = TokenBucket(
    settings.rate_limit_admin_read_per_minute, name="admin_read"
)
wallboard_bucket = TokenBucket(settings.rate_limit_wallboard_per_minute, name="wallboard")
login_bucket = TokenBucket(settings.rate_limit_login_per_minute, name="login")
# Keyed by submitted username (not client IP) — catches credential-stuffing
# against one account spread across many source IPs.
login_username_bucket = TokenBucket(settings.rate_limit_login_per_minute, name="login_username")
auth_refresh_bucket = TokenBucket(
    settings.rate_limit_auth_refresh_per_minute, name="auth_refresh"
)
db_explorer_bucket = TokenBucket(30, name="db_explorer")
search_token_bucket = TokenBucket(
    settings.rate_limit_search_token_per_minute, name="search_token"
)


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


def rate_limit_admin(request: Request) -> None:
    """Route dependency: read-only admin GETs use a generous bucket; POSTs share refresh."""
    if request.method == "GET":
        _enforce(admin_read_bucket, request)
    else:
        _enforce(refresh_bucket, request)


def rate_limit_wallboard(request: Request) -> None:
    """Route dependency: token bucket for GET /api/wallboard."""
    _enforce(wallboard_bucket, request)


def rate_limit_login(request: Request) -> None:
    """Route dependency: per-IP token bucket for POST /api/auth/login."""
    _enforce(login_bucket, request)


def rate_limit_auth_refresh(request: Request) -> None:
    """Route dependency: token bucket for POST /api/auth/refresh."""
    _enforce(auth_refresh_bucket, request)


def rate_limit_db_explorer(request: Request) -> None:
    """Stricter bucket for read-only DB explorer (30/min)."""
    _enforce(db_explorer_bucket, request)


def rate_limit_search_token(request: Request) -> None:
    """Dedicated bucket for Bearer search API tokens (Embeddings E5)."""
    _enforce(search_token_bucket, request)


def check_login_username_rate_limit(username: str) -> None:
    """Per-username companion to rate_limit_login — called directly from the
    login handler (the username lives in the request body, not the dependency-
    injectable part of the request) once the body has been parsed."""
    if not settings.rate_limit_enabled:
        return
    retry_after = login_username_bucket.acquire(username.strip().lower())
    if retry_after > 0:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts for this account. Retry later.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


def get_bucket_stats() -> list[dict]:
    """Return per-bucket stats for the rate limit dashboard.

    Includes every live TokenBucket enforced on a route — not a subset.
    """
    buckets = [
        ioc_bucket,
        refresh_bucket,
        admin_read_bucket,
        wallboard_bucket,
        login_bucket,
        login_username_bucket,
        auth_refresh_bucket,
        db_explorer_bucket,
        search_token_bucket,
    ]
    result = []
    for b in buckets:
        top = sorted(b._hits.items(), key=lambda x: x[1], reverse=True)[:10]
        result.append({
            "name": b.name,
            "rate_per_minute": b.rate_per_minute,
            "total_hits": b.hit_count,
            "active_keys": len(b._buckets),
            "top_consumers": [{"key": k, "hits": v} for k, v in top],
        })
    return result


def get_top_consumers(n: int = 5) -> list[dict]:
    """Per-client hit counts per rate-limit bucket (since process start)."""
    merged: list[dict] = []
    for bucket_name, bucket in (
        ("ioc", ioc_bucket),
        ("refresh", refresh_bucket),
        ("admin_read", admin_read_bucket),
        ("wallboard", wallboard_bucket),
        ("login", login_bucket),
        ("login_username", login_username_bucket),
        ("auth_refresh", auth_refresh_bucket),
        ("db_explorer", db_explorer_bucket),
        ("search_token", search_token_bucket),
    ):
        for key, hits in getattr(bucket, "_hits", {}).items():
            merged.append({"key": key, "hits": hits, "bucket": bucket_name})
    merged.sort(key=lambda row: row["hits"], reverse=True)
    return merged[:n]
