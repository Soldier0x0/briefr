"""Manual refresh endpoints (admin-gated), moved verbatim from main.py
(V1.2 §5.2 router split — no behavior change).

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


@router.post("/api/refresh")
async def manual_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(
            status_code=409,
            detail="An ingest job is already running. Wait for it to finish before starting another.",
        )
    await audit(request, "refresh.full", "nvd+kev+epss")
    asyncio.create_task(run_daily_refresh())
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
    asyncio.create_task(run_nvd_incremental_sync())
    return {"status": "ok", "message": "NVD incremental sync started in background"}


@router.post("/api/refresh/kev")
async def manual_kev_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.kev", "kev")
    asyncio.create_task(run_kev_sync())
    return {"status": "ok", "message": "KEV metadata sync started in background"}


@router.post("/api/refresh/epss")
async def manual_epss_refresh(request: Request):
    require_admin_key(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.epss", "epss")
    asyncio.create_task(run_epss_sync())
    return {"status": "ok", "message": "EPSS score sync started in background"}


@router.post("/api/refresh/mitre")
async def manual_mitre_refresh(request: Request):
    require_admin_key(request)
    await audit(request, "refresh.mitre", "attack+atlas")
    asyncio.create_task(run_weekly_mitre_refresh())
    return {
        "status": "ok",
        "message": "MITRE ATT&CK + ATLAS refresh started in background",
    }
