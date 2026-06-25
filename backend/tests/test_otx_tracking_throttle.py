"""Tests for OTX hourly tracking and source throttle."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from source_rate_limits import get_min_interval, get_otx_hourly_limit
from source_throttle import reset_throttle_state, throttle_before_request
import tracking


def test_otx_hourly_limit_default():
    assert get_otx_hourly_limit() == 10000


def test_otx_min_interval():
    assert get_min_interval("otx") == 0.5


def test_otx_has_hourly_limit_in_api_limits():
    assert tracking.API_LIMITS["otx"]["hourly_limit"] == 10000
    assert tracking.API_LIMITS["otx"]["monthly_limit"] is None
    assert "hour" in tracking.API_LIMITS["otx"]["rate_limit"].lower()


def test_throttle_spacing(monkeypatch):
    reset_throttle_state()
    monkeypatch.setattr("source_throttle.time.monotonic", lambda: 0.0)

    async def _run():
        await throttle_before_request("otx")
        monkeypatch.setattr("source_throttle.time.monotonic", lambda: 0.1)
        await throttle_before_request("otx")

    asyncio.run(_run())
