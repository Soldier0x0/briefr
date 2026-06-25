"""Continuous OTX background sync — spends hourly API budget across the day.

Runs on a short interval (default 5 min) and uses up to OTX_CONTINUOUS_BUDGET_PER_RUN
API calls per invocation for CVE pulse fetch + pulse IOC prefetch. Pacing (2 req/sec)
and hourly quota gates are enforced by source_throttle + tracking.has_quota.
"""

from __future__ import annotations

import logging
import os

from tracking import get_hour_usage, has_quota
from source_rate_limits import get_otx_hourly_limit

logger = logging.getLogger(__name__)


def otx_continuous_enabled() -> bool:
    return os.environ.get("OTX_CONTINUOUS_SYNC_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_otx_continuous_budget_per_run() -> int:
    return max(1, int(os.environ.get("OTX_CONTINUOUS_BUDGET_PER_RUN", "600")))


def get_otx_continuous_interval_minutes() -> int:
    return max(1, int(os.environ.get("OTX_CONTINUOUS_INTERVAL_MINUTES", "5")))


async def run_otx_continuous_sync(api_key: str) -> dict:
    """
    Spend API budget on prioritized CVE pulse refresh, then pulse IOC prefetch.

    Returns stats: api_calls, cve_pulses_stored, pulse_iocs_fetched, stop_reason.
    """
    from correlation.config import get_otx_ioc_sync_max_per_run
    from correlation.engine import prefetch_pulse_iocs_for_nightly
    from database import (
        get_cves_missing_otx_pulses,
        get_db,
        store_otx_cve_pulses,
    )
    from feeds.otx import fetch_cve_pulses, fetch_pulse_iocs

    if not api_key:
        return {"api_calls": 0, "stop_reason": "no_api_key"}

    budget = get_otx_continuous_budget_per_run()
    hourly_limit = get_otx_hourly_limit()
    hour_used = await get_hour_usage("otx")
    remaining_hour = max(0, hourly_limit - hour_used)
    budget = min(budget, remaining_hour)
    if budget <= 0:
        return {"api_calls": 0, "stop_reason": "hourly_quota_exhausted"}

    stats = {
        "api_calls": 0,
        "cve_pulses_stored": 0,
        "pulse_iocs_fetched": 0,
        "stop_reason": "budget_exhausted",
    }

    db = await get_db()
    try:
        missing_cves = await get_cves_missing_otx_pulses(db, limit=min(budget, 500))
        for cve_id in missing_cves:
            if stats["api_calls"] >= budget or not await has_quota("otx"):
                break
            try:
                pulses = await fetch_cve_pulses(cve_id, api_key)
                stats["api_calls"] += 1
                if not pulses:
                    continue
                await store_otx_cve_pulses(db, cve_id, pulses)
                await db.commit()
                stats["cve_pulses_stored"] += len(pulses)
            except Exception as exc:
                logger.warning("OTX continuous CVE skip %s: %s", cve_id, exc)
    finally:
        await db.close()

    ioc_budget = min(
        get_otx_ioc_sync_max_per_run(),
        budget - stats["api_calls"],
    )
    if ioc_budget > 0 and await has_quota("otx"):
        # prefetch_pulse_iocs_for_nightly tracks its own API calls via fetch_pulse_iocs
        fetched = await prefetch_pulse_iocs_for_nightly(
            api_key, max_pulses=min(ioc_budget, 200)
        )
        stats["pulse_iocs_fetched"] = fetched
        stats["api_calls"] += fetched

    if stats["api_calls"] < budget and await has_quota("otx"):
        stats["stop_reason"] = "work_queue_empty"
    elif not await has_quota("otx"):
        stats["stop_reason"] = "hourly_quota_exhausted"

    return stats
