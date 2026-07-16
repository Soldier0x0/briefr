"""Meta endpoints (version/time/usage/AI summaries), moved verbatim from
main.py (V1.2 §5.2 router split, phase 3). No behavior change.

Two sub-routers because the meta routes were interleaved with the CVE group
in the pre-split main.py — main.py includes them in the exact pre-split
sequence so the OpenAPI route list stays byte-identical:

- info_router: GET /api/version, GET /api/time
- router:      /api/usage/ioc, /api/ai/summary (POST+GET),
               /api/investigation/summary

`/api/version` now reads the app version via `request.app` instead of the
module-level `app` object (same value, no shape change). `format_time_in_tz`
stays in routers/health.py (its primary consumer) and is imported here.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ai.summary import generate_executive_summary, generate_investigation_summary
from dependencies import require_user
from routers.health import format_time_in_tz
from tracking import get_ioc_usage_stats

logger = logging.getLogger(__name__)

BUILD_INFO_PATH = Path(__file__).resolve().parents[1] / ".build-info.json"

info_router = APIRouter()
router = APIRouter()


class InvestigationPivotRef(BaseModel):
    type: str | None = None
    id: str | None = None


class InvestigationItemRef(BaseModel):
    type: str
    id: str
    description: str = ""
    pivotFrom: InvestigationPivotRef | None = None


class InvestigationSummaryRequest(BaseModel):
    items: list[InvestigationItemRef] = Field(..., max_length=100)
    duration_minutes: int = Field(default=1, ge=1, le=10080)


class AiSummaryRequest(BaseModel):
    cves: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    iocs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    actors: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    investigation_duration: int = Field(default=1, ge=1, le=10080)


@info_router.get("/api/version")
async def app_version(request: Request):
    """Deployed version — commit and build time stamped by deploy/briefr-update.sh."""
    info: dict = {"version": request.app.version, "commit": None, "built_at": None}
    try:
        content = await asyncio.to_thread(BUILD_INFO_PATH.read_text)
        stamped = json.loads(content)
        info["commit"] = stamped.get("commit")
        info["built_at"] = stamped.get("built_at")
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read build info: %s", exc)
    return info


@info_router.get("/api/time")
async def server_time(
    tz: str | None = Query(
        default=None,
        description="IANA timezone name (e.g. Asia/Kolkata). Defaults to DEFAULT_TIMEZONE env var.",
    ),
):
    now_utc = datetime.now(timezone.utc)
    default_tz = os.environ.get("DEFAULT_TIMEZONE", "UTC")
    display_tz = tz or default_tz

    result = {
        "utc": {
            "iso": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "display": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "epoch": int(now_utc.timestamp()),
        },
        "local": format_time_in_tz(now_utc, display_tz),
    }

    if tz and tz != default_tz:
        result["default_tz"] = format_time_in_tz(now_utc, default_tz)

    return result


@router.get("/api/usage/ioc")
async def api_usage_ioc():
    """API quota counters for IOC Lookup enrichment sources."""
    now_utc = datetime.now(timezone.utc)
    stats = await get_ioc_usage_stats()
    return {
        "as_of_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today_date_utc": now_utc.strftime("%Y-%m-%d"),
        "this_month_utc": now_utc.strftime("%Y-%m"),
        "services": stats,
    }


@router.post("/api/ai/summary")
async def ai_summary(
    body: AiSummaryRequest,
    _user: dict = Depends(require_user),
):
    """AI executive summary for PDF export (multi-provider LLM router, template fallback)."""
    return await generate_executive_summary(
        cves=body.cves,
        iocs=body.iocs,
        actors=body.actors,
        investigation_duration=body.investigation_duration,
    )


@router.get("/api/ai/summary")
async def ai_summary_get(_user: dict = Depends(require_user)):
    """Discovery: summaries require POST with CVE/IOC/actor payloads (PDF export only)."""
    return {
        "detail": "Use POST /api/ai/summary with JSON body: cves, iocs, actors, investigation_duration",
    }


@router.post("/api/investigation/summary")
async def investigation_summary(
    body: InvestigationSummaryRequest,
    _user: dict = Depends(require_user),
):
    """Executive summary for investigation PDF (legacy; prefer /api/ai/summary)."""
    payload = [
        {
            "type": item.type,
            "id": item.id,
            "description": item.description,
            "pivot_from": (
                {"type": item.pivotFrom.type, "id": item.pivotFrom.id}
                if item.pivotFrom
                else None
            ),
        }
        for item in body.items
    ]
    return await generate_investigation_summary(payload, body.duration_minutes)
