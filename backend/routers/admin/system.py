"""Admin dashboard API — system overview and correlation status.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import os
import pathlib
import shutil
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request

from database import (
    EPSS_BACKFILL_DONE_KEY,
    get_db,
    get_feed_cache,
    get_nvd_sync_watermark,
    get_sync_state_value,
    set_feed_cache,
)
from db.integrity import run_integrity_check
from resilient_client import get_api_queue_status, get_feed_health

from .helpers import (
    _get_active_locks,
    _get_all_scheduler_jobs,
    _iso_to_age_seconds,
    _read_build_info,
)
from .router import router

@router.get("/system")
async def get_system(request: Request):
    from scheduler import any_ingest_lock_held
    from feeds.case_study_feed import get_incident_feed_status

    db = await get_db()
    sigmahq_index: dict = {
        "enabled": True,
        "ok": False,
        "rules_active": 0,
        "rules_retired": 0,
        "cve_links": 0,
        "commit_sha": "",
        "archive_sha256": "",
        "synced_at": "",
        "age_seconds": None,
    }
    try:
        # CVE count
        row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
        cve_count = row[0]["cnt"] if row else 0

        # NVD sync watermark
        watermark = await get_nvd_sync_watermark(db)
        last_nvd_sync_age_seconds = _iso_to_age_seconds(watermark)

        # EPSS backfill done
        epss_done_val = await get_sync_state_value(db, EPSS_BACKFILL_DONE_KEY)
        epss_backfill_done = epss_done_val == "1"

        # DB integrity (full scan is expensive — cache it, this endpoint is polled)
        cached_integrity = await get_feed_cache(db, "admin_db_integrity", max_age_hours=1 / 6)
        if cached_integrity is not None:
            db_integrity = cached_integrity
        else:
            result = await run_integrity_check(db)
            db_integrity = result.as_summary()
            await set_feed_cache(db, "admin_db_integrity", db_integrity)

        # Failed auth last 24h (Python cutoff — works on SQLite TEXT and Postgres)
        auth_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        auth_row = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM audit_log "
            "WHERE action IN ('auth.login_failed', 'auth.failure') "
            "AND created_at >= ?",
            (auth_cutoff,),
        )
        failed_auth = auth_row[0]["cnt"] if auth_row else 0

        from detection.sigmahq_index import get_sigmahq_index_status

        try:
            sigmahq_index = await get_sigmahq_index_status(db)
        except Exception:
            pass

        from database import build_webhook_destination_health, list_webhook_destinations

        webhook_destinations = await list_webhook_destinations(db)
        webhook_health_rows = await build_webhook_destination_health(db)
        health_by_dest = {row["destination_id"]: row for row in webhook_health_rows}
        webhook_failing = []
        for dest in webhook_destinations:
            if not dest.get("enabled"):
                continue
            health = health_by_dest.get(dest["id"])
            if health and health.get("last_status") not in (None, "ok"):
                webhook_failing.append({
                    "id": dest["id"],
                    "kind": dest.get("kind"),
                    "label": dest.get("label") or dest["id"],
                    "last_error": health.get("last_error"),
                    "last_event_type": health.get("last_event_type"),
                })
    finally:
        await db.close()

    # Backup age
    backup_enabled = os.environ.get("BACKUP_ENABLED", "1").strip() == "1"
    backup_dir = os.environ.get("BACKUP_DIR", "")
    last_backup_age_seconds = None
    backup_disk_free_bytes = None
    backup_disk_total_bytes = None
    if backup_enabled and backup_dir:
        try:
            bdir = pathlib.Path(backup_dir)
            if bdir.is_dir():
                # Include .tar.gz and age-encrypted archives.
                archives_all = sorted(
                    [f for f in bdir.iterdir() if f.name.endswith(".tar.gz") or f.name.endswith(".tar.gz.age")],
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                if archives_all:
                    newest_mtime = archives_all[0].stat().st_mtime
                    last_backup_age_seconds = time.time() - newest_mtime
                du = shutil.disk_usage(backup_dir)
                backup_disk_free_bytes = du.free
                backup_disk_total_bytes = du.total
        except Exception:
            pass

    backup_interval_hours = int(os.environ.get("BACKUP_INTERVAL_HOURS", "6"))
    backup_threshold_seconds = 2 * backup_interval_hours * 3600

    # Disk usage for DB (Postgres uses current working directory)
    du = shutil.disk_usage(".")
    disk_free_bytes = du.free
    disk_total_bytes = du.total

    # Feed health
    feed_sources = get_feed_health()
    open_circuit_count = sum(1 for s in feed_sources.values() if s.get("circuit_open"))

    incidents = await get_incident_feed_status()

    # Scheduler jobs
    scheduler_jobs = await _get_all_scheduler_jobs()

    # Version
    version_info = _read_build_info()

    active_locks = _get_active_locks()
    jobs_with_errors = [j for j in scheduler_jobs if j.get("last_run_had_error")]

    return {
        "cve_count": cve_count,
        "last_nvd_sync_age_seconds": last_nvd_sync_age_seconds,
        "last_backup_age_seconds": last_backup_age_seconds,
        "backup_threshold_seconds": backup_threshold_seconds,
        "disk_free_bytes": disk_free_bytes,
        "disk_total_bytes": disk_total_bytes,
        "backup_disk_free_bytes": backup_disk_free_bytes,
        "backup_disk_total_bytes": backup_disk_total_bytes,
        "db_integrity": db_integrity,
        "scheduler_jobs": scheduler_jobs,
        "feeds": {
            "sources": feed_sources,
            "incidents": incidents,
            "sigmahq_index": sigmahq_index,
        },
        "open_circuit_count": open_circuit_count,
        "api_queue": get_api_queue_status(),
        "jobs_with_errors_count": len(jobs_with_errors),
        "active_locks": active_locks,
        "recent_errors": [
            {
                "job_id": j["id"],
                "error": (j.get("last_error_message") or "")[:80],
                "last_run_utc": j.get("last_run_utc"),
            }
            for j in jobs_with_errors
        ],
        "refresh_in_progress": any_ingest_lock_held(),
        "epss_backfill_done": epss_backfill_done,
        "version": version_info,
        "failed_auth_last_24h": failed_auth,
        "webhooks": {
            "failing_count": len(webhook_failing),
            "failing": webhook_failing,
        },
    }


@router.get("/correlation/status")
async def get_correlation_status():
    """Operator diagnostics: last campaign build, OTX IOC coverage, backlog."""
    from correlation.status import get_correlation_admin_status

    db = await get_db()
    try:
        return await get_correlation_admin_status(db)
    finally:
        await db.close()

