"""V1.2 §5.5 — token-bucket rate limiting on POST /api/ioc/lookup and
POST /api/refresh*. Bursting past the limit must return 429 with a
Retry-After header; other endpoints stay unlimited."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import rate_limit
from main import app
from rate_limit import TokenBucket
from settings import settings

# TestClient connections report this client host; it is the bucket key.
TESTCLIENT_KEY = "testclient"


def _drain(bucket: TokenBucket, key: str = TESTCLIENT_KEY) -> None:
    bucket._buckets[key] = (0.0, time.monotonic())


def _reset(bucket: TokenBucket, key: str = TESTCLIENT_KEY) -> None:
    bucket._buckets.pop(key, None)


# ---------------------------------------------------------------- unit tests


def test_bucket_allows_burst_up_to_capacity_then_denies():
    bucket = TokenBucket(6)
    now = 1000.0
    for _ in range(6):
        assert bucket.acquire("k", now=now) == 0.0
    retry_after = bucket.acquire("k", now=now)
    assert retry_after > 0


def test_bucket_retry_after_matches_refill_rate():
    bucket = TokenBucket(6)  # 0.1 tokens/sec
    now = 1000.0
    for _ in range(6):
        bucket.acquire("k", now=now)
    retry_after = bucket.acquire("k", now=now)
    assert abs(retry_after - 10.0) < 1e-6


def test_bucket_refills_over_time():
    bucket = TokenBucket(6)
    now = 1000.0
    for _ in range(6):
        bucket.acquire("k", now=now)
    assert bucket.acquire("k", now=now) > 0
    assert bucket.acquire("k", now=now + 10.0) == 0.0


def test_bucket_keys_are_isolated():
    bucket = TokenBucket(2)
    now = 1000.0
    assert bucket.acquire("a", now=now) == 0.0
    assert bucket.acquire("a", now=now) == 0.0
    assert bucket.acquire("a", now=now) > 0
    assert bucket.acquire("b", now=now) == 0.0


def test_bucket_never_exceeds_capacity_after_long_idle():
    bucket = TokenBucket(3)
    now = 1000.0
    bucket.acquire("k", now=now)
    # Hours idle: still only `capacity` tokens available.
    later = now + 10_000.0
    for _ in range(3):
        assert bucket.acquire("k", now=later) == 0.0
    assert bucket.acquire("k", now=later) > 0


def test_bucket_hard_cap_bounds_memory_under_key_floods():
    """Distinct spoofed keys inside one refill window must not grow the
    dict without bound (review finding: remotely triggerable OOM)."""
    bucket = TokenBucket(60)
    now = 1000.0
    # All keys active within the window — the idle prune frees nothing.
    for i in range(rate_limit._MAX_BUCKETS + 100):
        bucket.acquire(f"10.0.{i // 256}.{i % 256}", now=now + i * 0.001)
    assert len(bucket._buckets) <= rate_limit._MAX_BUCKETS


def _fake_request(peer: str, headers: dict[str, str] | None = None):
    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        def __init__(self):
            self.headers = headers or {}
            self.client = FakeClient(peer)

    return FakeRequest()


def test_client_key_ignores_forwarded_headers_from_untrusted_peers():
    """A direct connection cannot mint fresh buckets via spoofed headers."""
    request = _fake_request(
        "192.168.1.99",
        {
            "x-forwarded-for": "203.0.113.7",
            "cf-connecting-ip": "203.0.113.8",
            "x-real-ip": "203.0.113.9",
        },
    )
    assert rate_limit.client_key(request) == "192.168.1.99"


def test_client_key_prefers_cf_connecting_ip_behind_loopback_proxy():
    request = _fake_request(
        "127.0.0.1",
        {
            "cf-connecting-ip": "203.0.113.8",
            "x-forwarded-for": "198.51.100.1, 203.0.113.8, 127.0.0.1",
        },
    )
    assert rate_limit.client_key(request) == "203.0.113.8"


def test_client_key_uses_rightmost_untrusted_xff_hop():
    """The leftmost XFF hops are client-controlled; nginx appends the real
    peer on the right, so the rightmost non-loopback hop is proxy-attested."""
    request = _fake_request(
        "127.0.0.1",
        {"x-forwarded-for": "6.6.6.6, 203.0.113.7, 127.0.0.1"},
    )
    assert rate_limit.client_key(request) == "203.0.113.7"


def test_client_key_falls_back_to_x_real_ip_then_peer():
    request = _fake_request("127.0.0.1", {"x-real-ip": "203.0.113.9"})
    assert rate_limit.client_key(request) == "203.0.113.9"
    assert rate_limit.client_key(_fake_request("127.0.0.1")) == "127.0.0.1"


def test_spoofed_xff_does_not_bypass_endpoint_rate_limit():
    """TestClient's peer is not a loopback proxy, so the spoofed header is
    ignored and the drained bucket still answers 429."""
    with TestClient(app) as client:
        _drain(rate_limit.ioc_bucket)
        try:
            resp = client.post(
                "/api/ioc/lookup",
                json={"value": "1.2.3.4", "type": "ip"},
                headers={"X-Forwarded-For": "203.0.113.77"},
            )
            assert resp.status_code == 429
        finally:
            _reset(rate_limit.ioc_bucket)


# ------------------------------------------------------------ endpoint tests


def test_ioc_lookup_returns_429_with_retry_after_when_drained():
    with TestClient(app) as client:
        _drain(rate_limit.ioc_bucket)
        try:
            resp = client.post(
                "/api/ioc/lookup", json={"value": "1.2.3.4", "type": "ip"}
            )
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
            assert int(resp.headers["Retry-After"]) >= 1
            assert "detail" in resp.json()
        finally:
            _reset(rate_limit.ioc_bucket)


def test_ioc_lookup_not_rate_limited_under_the_limit():
    """Under the limit the handler runs (proven by its own 400 validation)."""
    with TestClient(app) as client:
        _reset(rate_limit.ioc_bucket)
        resp = client.post("/api/ioc/lookup", json={"value": "x", "type": "bogus"})
        assert resp.status_code == 400
        _reset(rate_limit.ioc_bucket)


def test_all_refresh_routes_return_429_when_drained():
    with TestClient(app) as client:
        for path in (
            "/api/refresh",
            "/api/refresh/nvd",
            "/api/refresh/kev",
            "/api/refresh/epss",
            "/api/refresh/mitre",
        ):
            _drain(rate_limit.refresh_bucket)
            resp = client.post(path)
            assert resp.status_code == 429, path
            assert int(resp.headers["Retry-After"]) >= 1
        _reset(rate_limit.refresh_bucket)


def test_refresh_passes_through_under_the_limit(monkeypatch, auth_token):
    from routers import refresh as refresh_router

    async def noop_audit(request, action, target=""):
        return None

    monkeypatch.setattr(refresh_router, "refresh_in_progress", lambda: False)
    monkeypatch.setattr(refresh_router, "_spawn", lambda coro: coro.close())
    monkeypatch.setattr(refresh_router, "audit", noop_audit)

    with TestClient(app) as client:
        client.cookies.set("briefr_at", auth_token())
        _reset(rate_limit.refresh_bucket)
        resp = client.post("/api/refresh/kev")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        _reset(rate_limit.refresh_bucket)


def test_rate_limit_consumed_before_auth_check():
    """Unauthenticated bursts must not bypass the bucket."""
    with TestClient(app) as client:
        _drain(rate_limit.refresh_bucket)
        resp = client.post("/api/refresh")
        assert resp.status_code == 429
        _reset(rate_limit.refresh_bucket)


def test_rate_limit_disabled_flag_bypasses_bucket(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    with TestClient(app) as client:
        _drain(rate_limit.ioc_bucket)
        resp = client.post("/api/ioc/lookup", json={"value": "x", "type": "bogus"})
        # 400 (handler validation) proves the request was not rejected with 429.
        assert resp.status_code == 400
        _reset(rate_limit.ioc_bucket)


def test_other_endpoints_are_not_rate_limited():
    with TestClient(app) as client:
        _drain(rate_limit.ioc_bucket)
        _drain(rate_limit.refresh_bucket)
        resp = client.get("/api/config/risk")
        assert resp.status_code == 200
        _reset(rate_limit.ioc_bucket)
        _reset(rate_limit.refresh_bucket)


def test_get_top_consumers_includes_auth_buckets():
    rate_limit.login_bucket._hits["203.0.113.1"] = 3
    rate_limit.auth_refresh_bucket._hits["203.0.113.1"] = 2
    try:
        rows = rate_limit.get_top_consumers(10)
        buckets = {row["bucket"] for row in rows}
        assert "login" in buckets
        assert "auth_refresh" in buckets
    finally:
        rate_limit.login_bucket._hits.clear()
        rate_limit.auth_refresh_bucket._hits.clear()


def test_get_bucket_stats_lists_every_live_bucket():
    """Inbound limits dashboard must not omit buckets that are still enforced."""
    by_name = {row["name"]: row for row in rate_limit.get_bucket_stats()}
    expected = {
        "ioc": settings.rate_limit_ioc_per_minute,
        "refresh": settings.rate_limit_refresh_per_minute,
        "admin_read": settings.rate_limit_admin_read_per_minute,
        "wallboard": settings.rate_limit_wallboard_per_minute,
        "login": settings.rate_limit_login_per_minute,
        "login_username": settings.rate_limit_login_per_minute,
        "auth_refresh": settings.rate_limit_auth_refresh_per_minute,
        "db_explorer": 30,
        "search_token": settings.rate_limit_search_token_per_minute,
    }
    assert set(by_name) == set(expected)
    for name, rate in expected.items():
        assert by_name[name]["rate_per_minute"] == rate
