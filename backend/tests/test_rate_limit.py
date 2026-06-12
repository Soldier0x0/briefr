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


def test_client_key_prefers_first_xff_hop():
    class FakeClient:
        host = "127.0.0.1"

    class FakeRequest:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        client = FakeClient()

    assert rate_limit.client_key(FakeRequest()) == "203.0.113.7"

    class NoXff:
        headers = {}
        client = FakeClient()

    assert rate_limit.client_key(NoXff()) == "127.0.0.1"


# ------------------------------------------------------------ endpoint tests


def test_ioc_lookup_returns_429_with_retry_after_when_drained():
    client = TestClient(app)
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
    client = TestClient(app)
    _reset(rate_limit.ioc_bucket)
    resp = client.post("/api/ioc/lookup", json={"value": "x", "type": "bogus"})
    assert resp.status_code == 400
    _reset(rate_limit.ioc_bucket)


def test_all_refresh_routes_return_429_when_drained():
    client = TestClient(app)
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


def test_refresh_passes_through_under_the_limit(monkeypatch):
    from routers import refresh as refresh_router

    async def noop_audit(request, action, target=""):
        return None

    monkeypatch.setattr(refresh_router, "refresh_in_progress", lambda: False)
    monkeypatch.setattr(refresh_router, "_spawn", lambda coro: coro.close())
    monkeypatch.setattr(refresh_router, "audit", noop_audit)
    monkeypatch.setattr(settings, "briefr_admin_api_key", "")

    client = TestClient(app)
    _reset(rate_limit.refresh_bucket)
    resp = client.post("/api/refresh/kev")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    _reset(rate_limit.refresh_bucket)


def test_rate_limit_consumed_before_admin_key_check(monkeypatch):
    """Unauthenticated bursts must not bypass the bucket."""
    monkeypatch.setattr(settings, "briefr_admin_api_key", "secret")
    client = TestClient(app)
    _drain(rate_limit.refresh_bucket)
    resp = client.post("/api/refresh")
    assert resp.status_code == 429
    _reset(rate_limit.refresh_bucket)


def test_rate_limit_disabled_flag_bypasses_bucket(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    client = TestClient(app)
    _drain(rate_limit.ioc_bucket)
    resp = client.post("/api/ioc/lookup", json={"value": "x", "type": "bogus"})
    # 400 (handler validation) proves the request was not rejected with 429.
    assert resp.status_code == 400
    _reset(rate_limit.ioc_bucket)


def test_other_endpoints_are_not_rate_limited():
    client = TestClient(app)
    _drain(rate_limit.ioc_bucket)
    _drain(rate_limit.refresh_bucket)
    resp = client.get("/api/config/risk")
    assert resp.status_code == 200
    _reset(rate_limit.ioc_bucket)
    _reset(rate_limit.refresh_bucket)
