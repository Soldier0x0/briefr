"""Admin dashboard API — scheduler jobs and outbound queue.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException, Request
from procrastinate.exceptions import AlreadyEnqueued

from database import get_db, set_sync_state_value
from dependencies import audit
from destructive_actions import require_confirm
from jobs.app import is_procrastinate_enabled, open_app
from jobs.tasks import health_ping, llm_product_extraction_tick
from task_registry import spawn_background_task

import routers.admin as _admin_pkg

from .helpers import (
    _get_all_scheduler_jobs,
    _get_scheduler_module,
    _job_lock_held,
)
from .router import router

logger = logging.getLogger(__name__)

# ── Durable outbound jobs (Procrastinate / Q1) ─────────────────────────────


@router.get("/api-usage/metering")
async def get_api_usage_metering(request: Request, hours: int = 24):
    """Outbound call metering summary (Q2): by source + actor_type."""
    from db.api_metering import metering_summary
    from tracking import get_usage_stats

    db = await get_db()
    try:
        summary = await metering_summary(db, hours=hours)
        usage = await get_usage_stats()
    finally:
        await db.close()
    return {"ok": True, **summary, "usage_rollups": usage}


@router.get("/jobs/outbound")
async def list_outbound_jobs(request: Request, limit: int = 50):
    """List recent Procrastinate jobs (allowlisted fields). Empty when disabled."""
    from db.outbound_jobs import list_recent_outbound_jobs
    from jobs.app import is_procrastinate_enabled

    enabled = is_procrastinate_enabled()
    if not enabled:
        return {"enabled": False, "jobs": [], "count": 0}
    db = await get_db()
    try:
        jobs = await list_recent_outbound_jobs(db, limit=limit)
    finally:
        await db.close()
    return {
        "enabled": True,
        "jobs": jobs,
        "count": len(jobs),
    }


@router.post("/jobs/outbound/ping")
async def ping_outbound_queue(request: Request):
    """Defer the no-op health_ping task so admins can verify queue writes."""
    if not is_procrastinate_enabled():
        raise HTTPException(503, "Durable outbound queue is disabled")

    app = await open_app()
    if app is None:
        raise HTTPException(503, "Durable outbound queue is unavailable")

    already_enqueued = False
    try:
        await health_ping.configure(queueing_lock="health_ping").defer_async(
            note="admin-canary"
        )
    except AlreadyEnqueued:
        already_enqueued = True
        logger.info("health_ping canary already queued - skipping duplicate")

    await audit(request, "jobs.outbound.ping", "jobs:health_ping")
    return {
        "ok": True,
        "task": "jobs:health_ping",
        "queueing_lock": "health_ping",
        "already_enqueued": already_enqueued,
        "message": (
            "health_ping already queued"
            if already_enqueued
            else "health_ping queued"
        ),
    }


# ── Scheduler ──────────────────────────────────────────────────────────────


@router.get("/scheduler")
async def get_scheduler(request: Request):
    return await _get_all_scheduler_jobs()


@router.post("/scheduler/pause")
async def pause_job(request: Request, body: dict):
    job_id = body.get("job_id", "")
    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        raise HTTPException(503, "Scheduler not running")
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job.pause()
    db = await get_db()
    try:
        await set_sync_state_value(db, f"scheduler.paused.{job_id}", "1")
        await db.commit()
    finally:
        await db.close()
    await audit(request, f"scheduler.pause.{job_id}", job_id)
    return {"ok": True, "job_id": job_id}


@router.post("/scheduler/resume")
async def resume_job(request: Request, body: dict):
    job_id = body.get("job_id", "")
    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        raise HTTPException(503, "Scheduler not running")
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job.resume()
    db = await get_db()
    try:
        await set_sync_state_value(db, f"scheduler.paused.{job_id}", "0")
        await db.commit()
    finally:
        await db.close()
    await audit(request, f"scheduler.resume.{job_id}", job_id)
    return {"ok": True, "job_id": job_id}


@router.post("/scheduler/pause-all")
async def pause_all_jobs(request: Request, body: dict | None = None):
    """Pause every ACTIVE job server-side in one call.

    Replaces the previous client-side loop over individual /scheduler/pause
    calls (SchedulerPage.jsx), which was non-atomic and gave no visibility
    into partial failures.
    """
    confirm_text = (body or {}).get("confirm_text", "")
    try:
        require_confirm("scheduler.pause_all", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        raise HTTPException(503, "Scheduler not running")

    to_pause = [job for job in scheduler.get_jobs() if job.next_run_time is not None]
    paused: list[str] = []
    db = await get_db()
    try:
        for job in to_pause:
            await set_sync_state_value(db, f"scheduler.paused.{job.id}", "1")
            paused.append(job.id)
        await db.commit()
    finally:
        await db.close()

    # Only flip the in-memory scheduler state once the DB commit has
    # succeeded — otherwise a failed commit leaves jobs paused in memory
    # but not persisted, out of sync with what /scheduler reports.
    for job in to_pause:
        job.pause()

    await audit(request, "scheduler.pause_all", ", ".join(paused) or "none")
    return {"ok": True, "paused": paused}


@router.post("/scheduler/resume-all")
async def resume_all_jobs(request: Request, body: dict | None = None):
    """Resume every paused job server-side in one call (see pause-all)."""
    confirm_text = (body or {}).get("confirm_text", "")
    try:
        require_confirm("scheduler.resume_all", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        raise HTTPException(503, "Scheduler not running")

    to_resume = [job for job in scheduler.get_jobs() if job.next_run_time is None]
    resumed: list[str] = []
    db = await get_db()
    try:
        for job in to_resume:
            await set_sync_state_value(db, f"scheduler.paused.{job.id}", "0")
            resumed.append(job.id)
        await db.commit()
    finally:
        await db.close()

    # See pause-all: only flip in-memory state after the DB commit succeeds.
    for job in to_resume:
        job.resume()

    await audit(request, "scheduler.resume_all", ", ".join(resumed) or "none")
    return {"ok": True, "resumed": resumed}


@router.get("/scheduler/history")
async def get_scheduler_history(request: Request):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT key, value FROM sync_state WHERE key LIKE 'scheduler.last_run.%'"
        )
    finally:
        await db.close()

    result = []
    for row in rows:
        job_id = row["key"].replace("scheduler.last_run.", "")
        try:
            raw = json.loads(row["value"])
            if isinstance(raw, list):
                history = raw
            elif isinstance(raw, dict):
                history = [raw]
            else:
                history = []
        except Exception:
            history = []

        latest = history[0] if history else {}
        result.append({
            "job_id": job_id,
            "last_run_utc": latest.get("last_run_utc") or latest.get("started_at"),
            "duration_seconds": latest.get("duration_seconds"),
            "records_upserted": latest.get("records_upserted"),
            "had_error": latest.get("had_error"),
            "error_message": latest.get("error_message", ""),
            "run_history": history,
        })

    result.sort(key=lambda x: x.get("last_run_utc") or "", reverse=True)
    return result


# Job-to-coroutine map for POST /api/admin/scheduler/run
_JOB_RUN_MAP: dict[str, str] = {
    "nvd_incremental_sync": "run_nvd_incremental_sync",
    "kev_metadata_sync": "run_kev_sync",
    "kev_backlog_reconcile": "run_kev_backlog_reconcile",
    "threatfox_sync": "run_threatfox_sync",
    "vulncheck_kev_sync": "run_vulncheck_kev_sync",
    "ioc_retro_match": "run_ioc_retro_match",
    "epss_score_sync": "run_epss_sync",
    "weekly_mitre_refresh": "run_weekly_mitre_refresh",
    "atlas_version_check": "run_atlas_version_check",
    "otx_nightly_correlation": "run_otx_nightly_sync",
    "otx_continuous_sync": "run_otx_continuous_sync",
    "incident_feed_refresh": "run_incident_feed_refresh",
    "nightly_correlation": "run_nightly_correlation",
    "vulnrichment_snapshot_sync": "run_vulnrichment_sync",
    "cvelistv5_incremental_sync": "run_cvelistv5_sync",
    "embeddings_backfill": "run_embeddings_sync",
    "catchup_tick": "run_catchup_tick",
    "llm_product_extraction": "run_llm_extraction_sync",
    "detection_context_sync": "run_detection_context_sync_job",
    "detection_context_llm": "run_detection_context_llm_job",
    "sigmahq_index_sync": "run_sigmahq_index_sync",
    "exploit_sources_sync": "run_exploit_sources_sync",
    "backup_deadman_check": "run_backup_deadman_check",
    "watchlist_monitor_alerts": "run_watchlist_monitor_alerts",
    "api_key_health_check": "run_api_key_health_check",
    "session_cleanup": "run_session_cleanup",
    "cache_retention_cleanup": "run_cache_retention_cleanup",
    "resource_metrics_sample": "run_resource_metrics_sample",
    "cpe_catalog_sync": "run_cpe_catalog_sync",
}

_LLM_MANUAL_DURABLE_PRIORITY = 10


async def _defer_manual_llm_product_extraction() -> bool:
    """Return True when admin Run/Retry enqueued the durable LLM job."""
    if not is_procrastinate_enabled():
        return False

    try:
        app = await open_app()
        if app is None:
            return False
        try:
            await llm_product_extraction_tick.configure(
                queueing_lock="llm_product_extraction",
                priority=_LLM_MANUAL_DURABLE_PRIORITY,
            ).defer_async(trigger="manual")
        except AlreadyEnqueued:
            logger.info(
                "Manual LLM product extraction already queued — skipping duplicate"
            )
        return True
    except Exception as exc:
        logger.warning(
            "Manual LLM product extraction defer failed — falling back to scheduler path: %s",
            exc,
        )
        return False


@router.post("/scheduler/run")
async def run_scheduler_job(request: Request, body: dict):
    """Trigger a scheduler job immediately."""
    job_id = body.get("job_id", "")
    if not job_id:
        raise HTTPException(400, "job_id is required")
    if job_id not in _JOB_RUN_MAP:
        raise HTTPException(400, f"Unknown job_id '{job_id}'. Valid: {sorted(_JOB_RUN_MAP.keys())}")

    if _job_lock_held(job_id):
        raise HTTPException(409, f"Job '{job_id}' is already running (lock held)")

    if _admin_pkg._job_is_disabled(job_id):
        raise HTTPException(
            400,
            f"Job '{job_id}' is disabled in configuration. Enable the required setting under API keys & config.",
        )

    sched = _get_scheduler_module()
    fn_name = _JOB_RUN_MAP[job_id]
    fn = getattr(sched, fn_name, None)
    if fn is None:
        raise HTTPException(500, f"Coroutine '{fn_name}' not found in scheduler module")

    if job_id == "llm_product_extraction" and await _defer_manual_llm_product_extraction():
        await audit(request, f"scheduler.run.{job_id}", job_id)
        return {
            "ok": True,
            "job_id": job_id,
            "message": f"Job '{job_id}' deferred to durable queue",
        }

    spawn_background_task(fn())
    await audit(request, f"scheduler.run.{job_id}", job_id)
    return {"ok": True, "job_id": job_id, "message": f"Job '{job_id}' started in background"}
