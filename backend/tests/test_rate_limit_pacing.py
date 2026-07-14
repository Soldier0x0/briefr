"""Rate-limit pacing profiles and quota enforcement."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from source_rate_limits import get_openrouter_daily_limit, get_source_pacing
import tracking
from tests.conftest import run_db_test
from database import get_db, init_db


@pytest.fixture(autouse=True)
def reset_tracking_buffers():
    tracking._API_USAGE_LOCK = asyncio.Lock()
    tracking._API_USAGE_WRITE_LOCK = asyncio.Lock()
    tracking._api_usage_pending.clear()
    if tracking._api_usage_flush_task and not tracking._api_usage_flush_task.done():
        tracking._api_usage_flush_task.cancel()
    tracking._api_usage_flush_task = None
    yield
    tracking._API_USAGE_LOCK = asyncio.Lock()
    tracking._API_USAGE_WRITE_LOCK = asyncio.Lock()
    tracking._api_usage_pending.clear()
    if tracking._api_usage_flush_task and not tracking._api_usage_flush_task.done():
        tracking._api_usage_flush_task.cancel()
    tracking._api_usage_flush_task = None


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "rate_limits.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setattr("database.DB_PATH", str(path))
    run_db_test(init_db())
    return path


def test_github_unauthenticated_interval(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    pacing = get_source_pacing("github")
    assert pacing.min_interval_seconds == 60.0


def test_vulncheck_and_threatfox_profiles():
    vulncheck = get_source_pacing("vulncheck")
    threatfox = get_source_pacing("threatfox")
    assert vulncheck.min_interval_seconds == pytest.approx(0.06, abs=0.01)
    assert threatfox.min_interval_seconds == 2.0


def test_openrouter_daily_limit_default():
    assert get_openrouter_daily_limit() == 50


def test_has_quota_enforces_weekly_greynoise(db_path):
    async def _run():
        week_start = tracking._week_start_utc()
        db = await get_db()
        try:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            await db.execute(
                tracking._API_USAGE_UPSERT_SQL,
                ("greynoise", week_start, month, 50),
            )
            await db.commit()
        finally:
            await db.close()
        assert await tracking.has_quota("greynoise") is False

    run_db_test(_run())


def test_has_quota_enforces_monthly_virustotal(db_path):
    async def _run():
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        past_day = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        db = await get_db()
        try:
            await db.execute(
                tracking._API_USAGE_UPSERT_SQL,
                ("virustotal", past_day, month, 15500),
            )
            await db.commit()
        finally:
            await db.close()
        assert await tracking.get_today_usage("virustotal") == 0
        assert await tracking.has_quota("virustotal") is False

    run_db_test(_run())


def test_greynoise_health_accepts_404(monkeypatch):
    from monitoring import api_key_health

    class _Resp:
        status_code = 404
        request = httpx.Request("GET", "https://example.test")

    async def _fake_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError("404", request=_Resp.request, response=_Resp())

    monkeypatch.setattr(api_key_health, "resilient_request", _fake_request)

    async def _run():
        result = await api_key_health._check_greynoise("test-key")
        assert result["healthy"] is True
        assert result["status_code"] == 404

    run_db_test(_run())
