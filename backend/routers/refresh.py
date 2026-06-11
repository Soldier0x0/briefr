"""Manual refresh endpoints (admin-gated), moved from main.py
(V1.2 §5.2 router split). One robustness fix on top of the verbatim move:
spawned ingest tasks are kept strongly referenced (review finding on PR #94).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from dependencies import audit, require_admin_key
from scheduler import (
    refresh_in_progress,
    run_daily_refresh,
    run_epss_sync,
    run_kev_sync,
    run_nvd_incremental_sync,
    run_weekly_mitre_refresh,
)

router = APIRouter()

# The event loop only holds weak references to tasks; keep strong references
# so a fire-and-forget ingest can't be garbage collected mid-run.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.post("/api/refresh")
async def manual_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(
            status_code=409,
            detail="An ingest job is already running. Wait for it to finish before starting another.",
        )
    await audit(request, "refresh.full", "nvd+kev+epss")
    _spawn(run_daily_refresh())
    return {
        "status": "ok",
        "message": "Full ingest started (NVD, then KEV, then EPSS) in background",
    }


@router.post("/api/refresh/nvd")
async def manual_nvd_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.nvd", "nvd")
    _spawn(run_nvd_incremental_sync())
    return {"status": "ok", "message": "NVD incremental sync started in background"}


@router.post("/api/refresh/kev")
async def manual_kev_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.kev", "kev")
    _spawn(run_kev_sync())
    return {"status": "ok", "message": "KEV metadata sync started in background"}


@router.post("/api/refresh/epss")
async def manual_epss_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.epss", "epss")
    _spawn(run_epss_sync())
    return {"status": "ok", "message": "EPSS score sync started in background"}


@router.post("/api/refresh/mitre")
async def manual_mitre_refresh(request: Request):
    require_admin_key(request)
    await audit(request, "refresh.mitre", "attack+atlas")
    _spawn(run_weekly_mitre_refresh())
    return {
        "status": "ok",
        "message": "MITRE ATT&CK + ATLAS refresh started in background",
    }
