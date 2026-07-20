"""Admin dashboard API — Catch-up mode controls.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request

import catchup_mode as cm
from api_queue import get_api_queue_status
from dependencies import audit

from .router import router


@router.get("/catchup")
async def get_catchup(request: Request):
    status = cm.get_catchup_status()
    if not status.get("db_persisted", True):
        status = await cm.persist_catchup_status(status)
    else:
        status = {k: v for k, v in status.items() if k != "db_persisted"}
    return {**status, "api_queue": _api_queue_summary()}


@router.post("/catchup/start")
async def start_catchup(request: Request, body: dict[str, Any]):
    try:
        status = cm.start_catchup(
            duration_hours=_duration_hours(body),
            ends_at=_ends_at(body),
            started_by=getattr(request.state, "user_username", None),
        )
    except cm.CatchupConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except cm.CatchupValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    status = await cm.persist_catchup_status(status)
    await audit(request, "catchup.start", _audit_target(status))
    return status


@router.post("/catchup/stop")
async def stop_catchup(request: Request, body: dict[str, Any] | None = None):
    status = cm.stop_catchup(reason="ended_early")
    status = await cm.persist_catchup_status(status)
    await audit(request, "catchup.stop", status.get("cleared_reason") or "")
    return status


def _api_queue_summary() -> dict[str, Any]:
    queue = get_api_queue_status()
    return {
        "total_queued": queue.get("total_queued", 0),
        "total_active": queue.get("total_active", 0),
        "has_pending": queue.get("has_pending", False),
    }


def _duration_hours(body: dict[str, Any]) -> float | None:
    value = body.get("duration_hours")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="duration_hours must be a number")


def _ends_at(body: dict[str, Any]) -> datetime | None:
    value = body.get("ends_at")
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="ends_at must be an ISO-8601 datetime")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="ends_at must be an ISO-8601 datetime")


def _audit_target(status: dict[str, Any]) -> str:
    if status.get("ends_at"):
        return str(status["ends_at"])
    return str(status.get("duration_hours") or "")
