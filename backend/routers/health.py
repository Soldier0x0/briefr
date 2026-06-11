"""Health endpoint, moved verbatim from main.py (V1.2 §5.2 router split,
phase 2). No behavior change. `format_time_in_tz` lives here because
`/api/health` is its primary consumer; `/api/time` (still in main.py until
the meta router lands) imports it from this module.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query

from database import (
    get_cve_count,
    get_db,
    get_last_updated,
    get_nvd_sync_watermark,
)
from feeds.case_study_feed import get_incident_feed_status
from resilient_client import get_feed_health
from scheduler import (
    get_ingest_intervals,
    get_ingest_status,
    get_next_scheduled_refresh_utc,
    get_refresh_schedule,
    refresh_in_progress,
)

router = APIRouter()


def format_time_in_tz(dt: datetime, tz_name: str) -> dict:
    try:
        tz = ZoneInfo(tz_name)
        local = dt.astimezone(tz)
        return {
            "iso": local.isoformat(),
            "display": local.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "timezone": tz_name,
            "utc_offset": local.strftime("%z"),
        }
    except (ZoneInfoNotFoundError, Exception):
        return {"error": f"Unknown timezone: {tz_name}"}


@router.get("/api/health")
async def health(
    tz: str | None = Query(
        default=None,
        description="IANA timezone name for local time display (e.g. Asia/Kolkata, America/New_York)",
    ),
):
    db = await get_db()
    try:
        cve_count = await get_cve_count(db)
        last_updated = await get_last_updated(db)
        nvd_sync_watermark = await get_nvd_sync_watermark(db)
    finally:
        await db.close()

    now_utc = datetime.now(timezone.utc)
    default_tz = os.environ.get("DEFAULT_TIMEZONE", "UTC")
    display_tz = tz or default_tz

    next_refresh_utc = get_next_scheduled_refresh_utc()
    refresh_schedule = get_refresh_schedule()
    ingest = get_ingest_status()
    incidents_status = await get_incident_feed_status()

    response: dict = {
        "status": "ok",
        "cve_count": cve_count,
        "feeds": {"incidents": incidents_status, "sources": get_feed_health()},
        "last_updated": last_updated,
        "nvd_sync_watermark": nvd_sync_watermark,
        "refresh_in_progress": refresh_in_progress(),
        "ingest": ingest,
        "next_nvd_sync_at_utc": next_refresh_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_nvd_sync_in_user_tz": format_time_in_tz(next_refresh_utc, display_tz),
        "ingest_intervals": get_ingest_intervals(),
        "next_refresh_at_utc": next_refresh_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_refresh_in_user_tz": format_time_in_tz(next_refresh_utc, display_tz),
        "next_refresh_in_scheduler_tz": format_time_in_tz(
            next_refresh_utc, refresh_schedule["timezone"]
        ),
        "refresh_schedule": refresh_schedule,
        "server_time_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "server_time_local": format_time_in_tz(now_utc, display_tz),
    }
    return response
