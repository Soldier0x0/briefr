"""Manual refresh endpoints (admin-gated), moved from main.py
(V1.2 §5.2 router split). One robustness fix on top of the verbatim move:
spawned ingest tasks are kept strongly referenced (review finding on PR #94).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import audit, require_admin
from rate_limit import rate_limit_refresh
from scheduler import (
    refresh_in_progress,
    run_daily_refresh,
    run_epss_sync,
    run_kev_sync,
    run_nvd_incremental_sync,
    run_weekly_mitre_refresh,
)
from task_registry import spawn_background_task

# §5.5: every /api/refresh* route shares one token bucket (per client IP).
router = APIRouter(dependencies=[Depends(rate_limit_refresh)])


def _spawn(coro) -> None:
    # Registered in task_registry: strong ref (PR #94) + shutdown drain (PR-R1).
    spawn_background_task(coro)


@router.post("/api/refresh")
async def manual_refresh(request: Request):
    await require_admin(request)
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
    await require_admin(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.nvd", "nvd")
    _spawn(run_nvd_incremental_sync())
    return {"status": "ok", "message": "NVD incremental sync started in background"}


@router.post("/api/refresh/kev")
async def manual_kev_refresh(request: Request):
    await require_admin(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.kev", "kev")
    _spawn(run_kev_sync())
    return {"status": "ok", "message": "KEV metadata sync started in background"}


@router.post("/api/refresh/epss")
async def manual_epss_refresh(request: Request):
    await require_admin(request)
    if refresh_in_progress():
        raise HTTPException(status_code=409, detail="An ingest job is already running.")
    await audit(request, "refresh.epss", "epss")
    _spawn(run_epss_sync())
    return {"status": "ok", "message": "EPSS score sync started in background"}


@router.post("/api/refresh/mitre")
async def manual_mitre_refresh(request: Request):
    await require_admin(request)
    await audit(request, "refresh.mitre", "attack+atlas")
    _spawn(run_weekly_mitre_refresh())
    return {
        "status": "ok",
        "message": "MITRE ATT&CK + ATLAS refresh started in background",
    }
