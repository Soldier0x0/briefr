"""Admin dashboard API endpoints.

All routes require the X-BRIEFR-Admin-Key header (when BRIEFR_ADMIN_API_KEY is
configured) and share the same token-bucket rate limit as the refresh routes.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import shutil
import tarfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse

from database import (
    DB_PATH,
    EPSS_BACKFILL_DONE_KEY,
    NVD_SYNC_WATERMARK_KEY,
    delete_all_snooze_entries,
    get_db,
    get_nvd_sync_watermark,
    get_sync_state_value,
    purge_legacy_rejected_cves,
    set_sync_state_value,
)
from dependencies import audit, require_admin_key, trigger_graceful_restart
from rate_limit import get_top_consumers, rate_limit_refresh
from resilient_client import get_feed_health, reset_circuit
from settings import settings
from structured_logging import LOG_CATEGORIES, get_log_buffer, get_known_loggers

router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(require_admin_key), Depends(rate_limit_refresh)],
)

_BUILD_INFO_PATH = Path(__file__).resolve().parents[1] / ".build-info.json"
_DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")

_backup_running = asyncio.Event()

# ── Lock map for scheduler jobs ────────────────────────────────────────────
_JOB_LOCK_MAP: dict[str, str] = {
    "nvd_incremental_sync": "_nvd_lock",
    "kev_metadata_sync": "_kev_lock",
    "epss_score_sync": "_epss_lock",
    "weekly_mitre_refresh": "_mitre_refresh_lock",
    "otx_nightly_correlation": "_otx_lock",
    "nightly_correlation": "_correlation_lock",
    "vulnrichment_snapshot_sync": "_vulnrichment_lock",
    "cvelistv5_incremental_sync": "_cvelistv5_lock",
    "embeddings_backfill": "_embeddings_lock",
    "llm_product_extraction": "_llm_extraction_lock",
    "exploit_sources_sync": "_exploit_sources_lock",
}

WRITABLE_CONFIG_KEYS = {
    "NVD_SYNC_INTERVAL_HOURS", "KEV_SYNC_INTERVAL_MINUTES", "EPSS_SYNC_INTERVAL_HOURS",
    "INCIDENT_FEED_REFRESH_MINUTES", "VULNRICHMENT_SYNC_INTERVAL_HOURS",
    "VULNRICHMENT_BRANCH", "CVELISTV5_SYNC_INTERVAL_MINUTES", "CVELISTV5_BRANCH",
    "CVELISTV5_INITIAL_SINCE_DAYS", "CIRCUIT_FAILURE_THRESHOLD", "CIRCUIT_COOLDOWN_SECONDS",
    "NVD_SYNC_OVERLAP_MINUTES", "SCHEDULER_TIMEZONE",
    "MITRE_REFRESH_HOUR", "MITRE_REFRESH_MINUTE",
    "CORRELATION_HOUR", "CORRELATION_MINUTE", "CORRELATION_TIMEZONE",
    "OTX_CORRELATION_HOUR", "OTX_CORRELATION_MINUTE", "OTX_CORRELATION_TIMEZONE",
    "CACHE_REFRESH_HOUR", "CACHE_REFRESH_MINUTE",
    "EXPLOIT_SOURCES_SYNC_ENABLED", "EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS",
    "EXPLOIT_SOURCES_THROTTLE_SECONDS",
    "MAX_CVES_PER_FETCH", "NVD_DAYS_BACK", "KEV_CROSS_FETCH_NVD",
    "ATLAS_YAML_URL", "MITRE_CVE_MAPPINGS_JSON_URL",
    "EMBEDDINGS_ENABLED", "EMBEDDINGS_SYNC_INTERVAL_HOURS", "EMBEDDINGS_MAX_PER_RUN",
    "EMBEDDINGS_MODEL", "EMBEDDINGS_CACHE_DIR",
    "LLM_PRODUCT_EXTRACTION_ENABLED", "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS",
    "LLM_PRODUCT_EXTRACTION_MAX_PER_RUN",
    "BACKUP_ENABLED", "BACKUP_RETENTION_COUNT", "BACKUP_INTERVAL_HOURS",
    "BACKUP_DIR", "BACKUP_AGE_KEY_FILE",
    "BRIEFR_STACK_TERMS", "LOG_FORMAT", "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_IOC_PER_MINUTE", "RATE_LIMIT_REFRESH_PER_MINUTE",
    "DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "WEBHOOK_GENERIC_URL", "WEBHOOK_GENERIC_ENABLED", "WEBHOOK_GENERIC_EVENTS",
    "WEBHOOK_GENERIC_LABEL", "DISCORD_WEBHOOK_ENABLED", "DISCORD_WEBHOOK_EVENTS",
    "TELEGRAM_WEBHOOK_ENABLED", "TELEGRAM_WEBHOOK_EVENTS",
    "ALLOWED_ORIGINS", "DEFAULT_TIMEZONE", "BRIEFR_ENV",
    "DATABASE_URL", "DATABASE_POOL_SIZE",
    # API keys — writable so operator can set them without SSH
    "NVD_API_KEY", "VIRUSTOTAL_API_KEY", "ABUSEIPDB_API_KEY", "GREYNOISE_API_KEY",
    "GITHUB_TOKEN", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "OTX_API_KEY",
    "CIRCL_API_KEY", "ABUSECH_AUTH_KEY",
}

# Keys that are also writable via apply-all (includes BRIEFR_ADMIN_API_KEY for rotation)
APPLY_ALL_EXTRA_KEYS = {"BRIEFR_ADMIN_API_KEY"}

INTEGER_KEYS = {
    "NVD_SYNC_INTERVAL_HOURS", "KEV_SYNC_INTERVAL_MINUTES", "EPSS_SYNC_INTERVAL_HOURS",
    "INCIDENT_FEED_REFRESH_MINUTES", "VULNRICHMENT_SYNC_INTERVAL_HOURS",
    "CVELISTV5_SYNC_INTERVAL_MINUTES", "CVELISTV5_INITIAL_SINCE_DAYS",
    "CIRCUIT_FAILURE_THRESHOLD", "CIRCUIT_COOLDOWN_SECONDS", "NVD_SYNC_OVERLAP_MINUTES",
    "MITRE_REFRESH_HOUR", "MITRE_REFRESH_MINUTE",
    "CORRELATION_HOUR", "CORRELATION_MINUTE",
    "OTX_CORRELATION_HOUR", "OTX_CORRELATION_MINUTE",
    "CACHE_REFRESH_HOUR", "CACHE_REFRESH_MINUTE",
    "EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS", "EXPLOIT_SOURCES_THROTTLE_SECONDS",
    "MAX_CVES_PER_FETCH", "NVD_DAYS_BACK",
    "EMBEDDINGS_SYNC_INTERVAL_HOURS", "EMBEDDINGS_MAX_PER_RUN",
    "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS", "LLM_PRODUCT_EXTRACTION_MAX_PER_RUN",
    "BACKUP_RETENTION_COUNT", "BACKUP_INTERVAL_HOURS",
    "RATE_LIMIT_IOC_PER_MINUTE", "RATE_LIMIT_REFRESH_PER_MINUTE",
    "DATABASE_POOL_SIZE",
}

RESTART_REQUIRED_KEYS = {
    "LOG_FORMAT", "RATE_LIMIT_ENABLED", "RATE_LIMIT_IOC_PER_MINUTE",
    "RATE_LIMIT_REFRESH_PER_MINUTE", "CIRCUIT_FAILURE_THRESHOLD", "CIRCUIT_COOLDOWN_SECONDS",
    "SCHEDULER_TIMEZONE", "CORRELATION_TIMEZONE", "OTX_CORRELATION_TIMEZONE",
    "EMBEDDINGS_ENABLED", "LLM_PRODUCT_EXTRACTION_ENABLED",
    "DATABASE_URL", "DATABASE_POOL_SIZE",
}


# ── Helpers ────────────────────────────────────────────────────────────────


def _read_build_info() -> dict[str, Any]:
    try:
        with _BUILD_INFO_PATH.open() as f:
            return json.load(f)
    except Exception:
        return {}


def _mask_key(value: str) -> str:
    """Show last 4 chars or 'not configured'."""
    if not value:
        return "not configured"
    return f"…{value[-4:]}"


def _mask_url(value: str) -> str:
    """Show first 30 chars + '[masked]' or 'not configured'."""
    if not value:
        return "not configured"
    return value[:30] + "…[masked]"


def _age_seconds(ts: float | None) -> float | None:
    if ts is None:
        return None
    return time.time() - ts


def _iso_to_age_seconds(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _get_scheduler_module():
    import scheduler as _sched
    return _sched


def _job_lock_held(job_id: str) -> bool:
    sched = _get_scheduler_module()
    lock_name = _JOB_LOCK_MAP.get(job_id)
    if not lock_name:
        return False
    lock = getattr(sched, lock_name, None)
    return lock.locked() if lock else False


_OPT_IN_DISABLED_JOBS = {
    "embeddings_backfill": ("EMBEDDINGS_ENABLED", "0"),
    "llm_product_extraction": ("LLM_PRODUCT_EXTRACTION_ENABLED", "0"),
    "exploit_sources_sync": ("EXPLOIT_SOURCES_SYNC_ENABLED", "1"),  # enabled=1 means NOT disabled
}


def _job_is_disabled(job_id: str) -> bool:
    """Return True if the job is env-gated and its gate is off."""
    gate = _OPT_IN_DISABLED_JOBS.get(job_id)
    if not gate:
        return False
    env_key, default_value = gate
    current = os.environ.get(env_key, default_value)
    return current.lower() in ("0", "false", "no", "off")


async def _get_job_last_run(db: aiosqlite.Connection, job_id: str) -> list[dict[str, Any]]:
    """Return history array (newest first), or empty list if none."""
    try:
        rows = await db.execute_fetchall(
            "SELECT value FROM sync_state WHERE key = ?",
            (f"scheduler.last_run.{job_id}",),
        )
        if not rows:
            return []
        raw = json.loads(rows[0]["value"])
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            # Migrate old single-dict format
            return [raw]
        return []
    except Exception:
        return []


def _build_job_info(job: Any, history: list[dict]) -> dict[str, Any]:
    paused = job.next_run_time is None
    lock_held = _job_lock_held(job.id)
    disabled = _job_is_disabled(job.id)
    next_run = None
    if job.next_run_time is not None:
        try:
            next_run = job.next_run_time.astimezone(timezone.utc).isoformat()
        except Exception:
            next_run = str(job.next_run_time)

    if disabled:
        status = "DISABLED"
    elif lock_held:
        status = "LOCKED"
    elif paused:
        status = "PAUSED"
    else:
        status = "ACTIVE"

    latest = history[0] if history else {}
    return {
        "id": job.id,
        "name": job.name,
        "next_run_time": next_run,
        "paused": paused,
        "lock_held": lock_held,
        "status": status,
        "last_run_utc": latest.get("last_run_utc") or latest.get("started_at"),
        "last_run_duration_seconds": latest.get("duration_seconds"),
        "last_run_records_upserted": latest.get("records_upserted"),
        "last_run_had_error": latest.get("had_error"),
        "last_error_message": (latest.get("error_message") or "")[:500],
        "run_history": history,
    }


async def _get_all_scheduler_jobs() -> list[dict[str, Any]]:
    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        return []
    jobs = scheduler.get_jobs()
    db = await get_db()
    try:
        result = []
        for job in jobs:
            history = await _get_job_last_run(db, job.id)
            result.append(_build_job_info(job, history))
        return result
    finally:
        await db.close()


def _get_active_locks() -> list[dict[str, Any]]:
    """Return info on jobs whose lock is currently held."""
    sched = _get_scheduler_module()
    result = []
    for job_id, lock_name in _JOB_LOCK_MAP.items():
        lock = getattr(sched, lock_name, None)
        if lock and lock.locked():
            result.append({"job_id": job_id, "lock_name": lock_name})
    return result


# ── System endpoint ────────────────────────────────────────────────────────


@router.get("/system")
async def get_system(request: Request):
    from scheduler import any_ingest_lock_held
    from feeds.case_study_feed import get_incident_feed_status

    db = await get_db()
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

        # DB integrity
        ic_rows = await db.execute_fetchall("PRAGMA integrity_check")
        integrity_ok = (
            len(ic_rows) == 1 and ic_rows[0][0].lower() == "ok"
        ) if ic_rows else False
        integrity_msg = ic_rows[0][0] if ic_rows else "unknown"
        db_integrity = {"ok": integrity_ok, "message": integrity_msg}

        # Failed auth last 24h
        auth_row = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM audit_log "
            "WHERE action = 'auth.failure' AND created_at >= datetime('now', '-24 hours')"
        )
        failed_auth = auth_row[0]["cnt"] if auth_row else 0
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
                archives = sorted(
                    [f for f in bdir.iterdir() if f.suffix in (".gz",) and "tar" in f.stem],
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                # Also include .age files
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

    # Disk usage for DB (read at call time so test monkeypatches apply)
    import database as _database
    db_dir = os.path.dirname(os.path.abspath(_database.DB_PATH)) or "."
    du = shutil.disk_usage(db_dir)
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
        },
        "open_circuit_count": open_circuit_count,
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
    }


# ── Backups ────────────────────────────────────────────────────────────────


@router.get("/backups")
async def list_backups_endpoint(request: Request):
    from backup.manager import list_backups

    raw = list_backups()
    result = []
    for backup in raw:
        archive_path_str = backup.get("archive", "")
        integrity = "unknown"
        reason = ""
        if archive_path_str:
            ap = pathlib.Path(archive_path_str)
            if ap.exists() and not ap.name.endswith(".age"):
                try:
                    with tarfile.open(ap, "r:gz") as tar:
                        member = tar.getmember("manifest.json")
                        content = tar.extractfile(member)
                        if content:
                            manifest = json.loads(content.read())
                            integrity = manifest.get("integrity", "unknown")
                            reason = manifest.get("reason", "")
                except Exception:
                    integrity = "unknown"
        result.append({
            "filename": backup.get("name", ""),
            "size_bytes": backup.get("size_bytes", 0),
            "created_at": backup.get("mtime_utc", ""),
            "encrypted": backup.get("encrypted", False),
            "integrity": integrity,
            "reason": reason,
        })
    return result


@router.post("/backups/verify/{filename}")
async def verify_backup(filename: str, request: Request):
    await audit(request, "backup.verify", filename)
    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    safe_path = pathlib.Path(backup_dir).resolve() / pathlib.Path(filename).name
    if not safe_path.exists():
        raise HTTPException(404, "Backup file not found")
    try:
        with tarfile.open(safe_path, "r:gz") as tar:
            member = tar.getmember("manifest.json")
            content = tar.extractfile(member)
            if content:
                manifest = json.loads(content.read())
                return {
                    "ok": True,
                    "filename": filename,
                    "details": f"Manifest parsed. integrity={manifest.get('integrity', 'unknown')}",
                }
        return {"ok": True, "filename": filename, "details": "Archive opened successfully"}
    except Exception as exc:
        return {"ok": False, "filename": filename, "details": str(exc)[:300]}


@router.post("/backups/run")
async def run_backup_endpoint(request: Request):
    from backup.manager import run_backup

    if _backup_running.is_set():
        raise HTTPException(409, "Backup already in progress")
    _backup_running.set()
    try:
        result = await asyncio.to_thread(run_backup, reason="manual-admin")
        archive_path = result.get("archive", "")
        filename = pathlib.Path(archive_path).name if archive_path else ""
        size_bytes = 0
        if archive_path and pathlib.Path(archive_path).exists():
            size_bytes = pathlib.Path(archive_path).stat().st_size
        await audit(request, "backup.run", filename)
        return {"ok": True, "filename": filename, "size_bytes": size_bytes}
    finally:
        _backup_running.clear()


@router.post("/backups/upload")
async def upload_backup(request: Request, file: UploadFile = File(...)):
    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    filename = pathlib.Path(file.filename or "").name

    safe_path = pathlib.Path(backup_dir).resolve() / filename
    if not str(safe_path).startswith(str(pathlib.Path(backup_dir).resolve())):
        raise HTTPException(400, "Invalid filename")
    if not re.fullmatch(r"briefr-[^/\\]+\.tar\.gz(\.age)?", filename):
        raise HTTPException(400, "Invalid filename pattern")

    content_length = request.headers.get("content-length")
    max_bytes = 500 * 1024 * 1024
    if content_length and int(content_length) > max_bytes:
        raise HTTPException(413, "File too large (max 500 MB)")

    pathlib.Path(backup_dir).mkdir(parents=True, exist_ok=True)
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "File too large (max 500 MB)")

    safe_path.write_bytes(data)
    await audit(request, "backup.upload", filename)
    return {"ok": True, "filename": filename, "size_bytes": len(data)}


# ── Storage ────────────────────────────────────────────────────────────────

_STORAGE_TABLES = [
    "cves", "kev_deadlines", "epss_history", "mitre_techniques", "mitre_groups",
    "atlas_techniques", "atlas_case_studies", "cve_technique_map", "cve_atlas_map",
    "group_technique_map", "otx_cve_pulses", "otx_pulse_iocs", "cve_exploits",
    "cve_change_history", "ioc_cache", "feed_cache", "correlation_infrastructure",
    "correlation_actor", "correlation_temporal", "cve_embeddings", "api_usage",
    "audit_log", "sync_state", "watchlist", "hunt_packs", "webhook_alert_log",
]


@router.get("/storage")
async def get_storage(request: Request):
    db = await get_db()
    try:
        counts: dict[str, int] = {}
        for table in _STORAGE_TABLES:
            try:
                rows = await db.execute_fetchall(f"SELECT COUNT(*) as cnt FROM {table}")
                counts[table] = rows[0]["cnt"] if rows else 0
            except Exception:
                counts[table] = -1
    finally:
        await db.close()

    import database as _database
    db_path = os.path.abspath(_database.DB_PATH)
    db_size_bytes = 0
    try:
        db_size_bytes = os.path.getsize(db_path)
    except Exception:
        pass

    # DB partition disk usage
    db_dir = os.path.dirname(db_path) or "."
    db_partition: dict[str, Any] = {"free": 0, "total": 0, "used": 0}
    try:
        du = shutil.disk_usage(db_dir)
        db_partition = {"free": du.free, "total": du.total, "used": du.used}
    except Exception:
        pass

    # Backup partition disk usage
    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    backup_partition: dict[str, Any] = {"free": 0, "total": 0, "used": 0}
    try:
        if pathlib.Path(backup_dir).exists():
            du2 = shutil.disk_usage(backup_dir)
            backup_partition = {"free": du2.free, "total": du2.total, "used": du2.used}
        else:
            # Fall back to the same partition as the DB
            backup_partition = db_partition.copy()
    except Exception:
        backup_partition = db_partition.copy()

    # Archive count
    archive_count = 0
    try:
        bdir = pathlib.Path(backup_dir)
        if bdir.is_dir():
            archive_count = sum(
                1 for f in bdir.iterdir()
                if f.name.endswith(".tar.gz") or f.name.endswith(".tar.gz.age")
            )
    except Exception:
        pass

    return {
        "tables": counts,
        "db_size_bytes": db_size_bytes,
        "db_path": db_path,
        # legacy flat fields for backward compat
        "disk_free_bytes": db_partition["free"],
        "disk_total_bytes": db_partition["total"],
        # structured partition objects (new)
        "db_partition": db_partition,
        "backup_partition": backup_partition,
        "archive_count": archive_count,
        "backup_dir": backup_dir,
    }


_PURGE_CONFIRM_MAP = {
    "ioc_cache": "clear",
    "feed_cache": "clear",
    "epss_history_old": "prune",
    "change_history_old": "prune",
    "rejected_cves": "purge",
    "nvd_watermark": "backfill",
    "epss_backfill_reset": None,  # no confirm required
}


@router.post("/storage/purge")
async def purge_storage(request: Request, body: dict):
    target = body.get("target", "")
    confirm_text = body.get("confirm_text", body.get("confirm", ""))
    days_back = body.get("days_back")

    if target not in _PURGE_CONFIRM_MAP:
        raise HTTPException(400, f"Unknown target '{target}'. Valid: {sorted(_PURGE_CONFIRM_MAP.keys())}")

    required_confirm = _PURGE_CONFIRM_MAP[target]
    if required_confirm is not None and confirm_text != required_confirm:
        raise HTTPException(400, f"confirm_text must be '{required_confirm}' for target '{target}'")

    db = await get_db()
    try:
        rows_deleted = 0
        if target == "ioc_cache":
            cursor = await db.execute("DELETE FROM ioc_cache")
            rows_deleted = cursor.rowcount
        elif target == "feed_cache":
            cursor = await db.execute("DELETE FROM feed_cache")
            rows_deleted = cursor.rowcount
        elif target == "epss_history_old":
            cursor = await db.execute(
                "DELETE FROM epss_history WHERE recorded_date < date('now', '-90 days')"
            )
            rows_deleted = cursor.rowcount
        elif target == "change_history_old":
            cursor = await db.execute(
                "DELETE FROM cve_change_history WHERE changed_at < datetime('now', '-90 days')"
            )
            rows_deleted = cursor.rowcount
        elif target == "rejected_cves":
            rows_deleted = await purge_legacy_rejected_cves(db)
        elif target == "nvd_watermark":
            # Clear NVD watermark so next sync re-fetches from NVD_DAYS_BACK
            await db.execute("DELETE FROM sync_state WHERE key = ?", (NVD_SYNC_WATERMARK_KEY,))
            rows_deleted = 1
            # Also update NVD_DAYS_BACK if provided
            if days_back is not None:
                try:
                    days_back_int = int(days_back)
                    if 1 <= days_back_int <= 3650:
                        os.environ["NVD_DAYS_BACK"] = str(days_back_int)
                except (ValueError, TypeError):
                    pass
        elif target == "epss_backfill_reset":
            await db.execute("DELETE FROM sync_state WHERE key = ?", (EPSS_BACKFILL_DONE_KEY,))
            rows_deleted = 1
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"storage.purge.{target}", str(rows_deleted))
    return {"ok": True, "rows_deleted": rows_deleted, "target": target}


# ── Storage export ─────────────────────────────────────────────────────────


@router.get("/storage/export")
async def export_db(request: Request, background_tasks: BackgroundTasks):
    """Stream a consistent briefr.db snapshot using VACUUM INTO.

    Direct file streaming in WAL mode can yield a torn read — WAL frames
    may not be fully checkpointed to the main .db file.  VACUUM INTO writes a
    fully-checkpointed, defragmented copy to a temp file which is then served.
    The temp file is cleaned up after the response is sent.
    """
    import tempfile as _tempfile
    import database as _database

    # Read DB_PATH at call time so test monkeypatches on database.DB_PATH apply.
    db_path = os.path.abspath(_database.DB_PATH)
    if not os.path.exists(db_path):
        raise HTTPException(404, "Database file not found")

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"briefr-{date_str}.db"

    tmp_dir = _tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"briefr-export-{int(time.time())}.db")

    db = await get_db()
    try:
        await db.execute(f"VACUUM INTO '{tmp_path}'")
    except Exception as exc:
        raise HTTPException(500, f"Failed to create database export: {exc}")
    finally:
        await db.close()

    await audit(request, "storage.db_export", filename)
    background_tasks.add_task(os.remove, tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=filename,
    )


# ── Watchlist ──────────────────────────────────────────────────────────────


@router.get("/watchlist")
async def get_admin_watchlist(
    request: Request,
    state: str = Query("all"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if state not in ("pin", "snooze", "all"):
        raise HTTPException(400, "state must be 'pin', 'snooze', or 'all'")

    db = await get_db()
    try:
        if state == "all":
            rows = await db.execute_fetchall(
                """
                SELECT w.cve_id, w.state, w.snooze_until, w.created_at,
                       c.severity, c.epss_score, c.is_kev, c.cvss_score
                FROM watchlist w LEFT JOIN cves c ON w.cve_id = c.cve_id
                ORDER BY w.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT w.cve_id, w.state, w.snooze_until, w.created_at,
                       c.severity, c.epss_score, c.is_kev, c.cvss_score
                FROM watchlist w LEFT JOIN cves c ON w.cve_id = c.cve_id
                WHERE w.state = ?
                ORDER BY w.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (state, limit, offset),
            )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/watchlist/{cve_id}")
async def delete_watchlist_entry(cve_id: str, request: Request):
    db = await get_db()
    try:
        await db.execute("DELETE FROM watchlist WHERE cve_id = ?", (cve_id.upper(),))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "watchlist.remove", cve_id)
    return {"ok": True, "cve_id": cve_id}


@router.post("/watchlist/clear-snoozes")
async def clear_all_snoozes(request: Request):
    db = await get_db()
    try:
        rows_deleted = await delete_all_snooze_entries(db)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "watchlist.clear_snoozes", str(rows_deleted))
    return {"ok": True, "rows_deleted": rows_deleted}


# ── Hunt packs ─────────────────────────────────────────────────────────────


@router.get("/hunt-packs")
async def get_admin_hunt_packs(
    request: Request,
    technique_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    try:
        if technique_id:
            rows = await db.execute_fetchall(
                """
                SELECT id, technique_id, cve_id, title, priority, created_at, updated_at
                FROM hunt_packs
                WHERE technique_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (technique_id, limit, offset),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT id, technique_id, cve_id, title, priority, created_at, updated_at
                FROM hunt_packs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/hunt-packs/{pack_id}")
async def delete_hunt_pack(pack_id: int, request: Request):
    db = await get_db()
    try:
        await db.execute("DELETE FROM hunt_packs WHERE id = ?", (pack_id,))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "hunt_packs.delete", str(pack_id))
    return {"ok": True, "id": pack_id}


# ── IOC cache ──────────────────────────────────────────────────────────────


@router.get("/ioc-cache")
async def get_ioc_cache(
    request: Request,
    ioc_type: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    db = await get_db()
    try:
        params: list = []
        conditions = []
        if ioc_type:
            conditions.append("ioc_type = ?")
            params.append(ioc_type)
        if search:
            conditions.append("value LIKE ?")
            params.append(f"%{search}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        rows = await db.execute_fetchall(
            f"""
            SELECT value, ioc_type, cached_at,
                   CAST((julianday('now') - julianday(cached_at)) * 86400 AS INTEGER) AS age_seconds
            FROM ioc_cache
            {where}
            ORDER BY cached_at DESC
            LIMIT ?
            """,
            params,
        )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/ioc-cache/{value:path}")
async def delete_ioc_cache_entry(value: str, request: Request):
    decoded = urllib.parse.unquote(value)
    db = await get_db()
    try:
        await db.execute("DELETE FROM ioc_cache WHERE value = ?", (decoded,))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "ioc_cache.delete", decoded)
    return {"ok": True, "value": decoded}


# ── Config ─────────────────────────────────────────────────────────────────


def _get_config_response() -> dict[str, Any]:
    def _env(key: str, default: str = "") -> str:
        return os.environ.get(key, default)

    def _env_int(key: str, default: int) -> int:
        try:
            return int(os.environ.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    # Mask age key file
    age_key_raw = _env("BACKUP_AGE_KEY_FILE")
    if age_key_raw and pathlib.Path(age_key_raw).is_file() and pathlib.Path(age_key_raw).stat().st_size > 0:
        age_key_masked = "*** set ***"
    else:
        age_key_masked = "not configured"

    allowed_origins_raw = _env("ALLOWED_ORIGINS", "http://localhost:5173")
    allowed_origins_list = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

    return {
        "dotenv_path": str(_DOTENV_PATH.resolve()),
        "scheduler": {
            "NVD_SYNC_INTERVAL_HOURS": _env_int("NVD_SYNC_INTERVAL_HOURS", 1),
            "KEV_SYNC_INTERVAL_MINUTES": _env_int("KEV_SYNC_INTERVAL_MINUTES", 15),
            "EPSS_SYNC_INTERVAL_HOURS": _env_int("EPSS_SYNC_INTERVAL_HOURS", 6),
            "INCIDENT_FEED_REFRESH_MINUTES": _env_int("INCIDENT_FEED_REFRESH_MINUTES", 30),
            "VULNRICHMENT_SYNC_INTERVAL_HOURS": _env_int("VULNRICHMENT_SYNC_INTERVAL_HOURS", 6),
            "VULNRICHMENT_BRANCH": _env("VULNRICHMENT_BRANCH", "develop"),
            "CVELISTV5_SYNC_INTERVAL_MINUTES": _env_int("CVELISTV5_SYNC_INTERVAL_MINUTES", 30),
            "CVELISTV5_BRANCH": _env("CVELISTV5_BRANCH", "main"),
            "CVELISTV5_INITIAL_SINCE_DAYS": _env_int("CVELISTV5_INITIAL_SINCE_DAYS", 7),
            "CIRCUIT_FAILURE_THRESHOLD": _env_int("CIRCUIT_FAILURE_THRESHOLD", 3),
            "CIRCUIT_COOLDOWN_SECONDS": _env_int("CIRCUIT_COOLDOWN_SECONDS", 60),
            "NVD_SYNC_OVERLAP_MINUTES": _env_int("NVD_SYNC_OVERLAP_MINUTES", 15),
            "SCHEDULER_TIMEZONE": _env("SCHEDULER_TIMEZONE", "Asia/Kolkata"),
            "MITRE_REFRESH_HOUR": _env_int("MITRE_REFRESH_HOUR", 2),
            "MITRE_REFRESH_MINUTE": _env_int("MITRE_REFRESH_MINUTE", 0),
            "CORRELATION_HOUR": _env_int("CORRELATION_HOUR", 1),
            "CORRELATION_MINUTE": _env_int("CORRELATION_MINUTE", 0),
            "CORRELATION_TIMEZONE": _env("CORRELATION_TIMEZONE", "Asia/Kolkata"),
            "OTX_CORRELATION_HOUR": _env_int("OTX_CORRELATION_HOUR", 2),
            "OTX_CORRELATION_MINUTE": _env_int("OTX_CORRELATION_MINUTE", 0),
            "OTX_CORRELATION_TIMEZONE": _env("OTX_CORRELATION_TIMEZONE", "Asia/Kolkata"),
            "CACHE_REFRESH_HOUR": _env_int("CACHE_REFRESH_HOUR", 6),
            "CACHE_REFRESH_MINUTE": _env_int("CACHE_REFRESH_MINUTE", 0),
            "EXPLOIT_SOURCES_SYNC_ENABLED": _env("EXPLOIT_SOURCES_SYNC_ENABLED", "1"),
            "EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS": _env_int("EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS", 24),
            "EXPLOIT_SOURCES_THROTTLE_SECONDS": _env_int("EXPLOIT_SOURCES_THROTTLE_SECONDS", 2),
        },
        "ingest": {
            "MAX_CVES_PER_FETCH": _env_int("MAX_CVES_PER_FETCH", 2000),
            "NVD_DAYS_BACK": _env_int("NVD_DAYS_BACK", 14),
            "KEV_CROSS_FETCH_NVD": _env_int("KEV_CROSS_FETCH_NVD", 1),
            "ATLAS_YAML_URL": _env("ATLAS_YAML_URL", ""),
            "MITRE_CVE_MAPPINGS_JSON_URL": _env("MITRE_CVE_MAPPINGS_JSON_URL", ""),
            "DB_PATH": _env("DB_PATH", "briefr.db"),
        },
        "ml": {
            "EMBEDDINGS_ENABLED": _env("EMBEDDINGS_ENABLED", "0"),
            "EMBEDDINGS_MODEL": _env("EMBEDDINGS_MODEL", "BAAI/bge-small-en-v1.5"),
            "EMBEDDINGS_CACHE_DIR": _env("EMBEDDINGS_CACHE_DIR", ""),
            "EMBEDDINGS_SYNC_INTERVAL_HOURS": _env_int("EMBEDDINGS_SYNC_INTERVAL_HOURS", 6),
            "EMBEDDINGS_MAX_PER_RUN": _env_int("EMBEDDINGS_MAX_PER_RUN", 2000),
            "LLM_PRODUCT_EXTRACTION_ENABLED": _env("LLM_PRODUCT_EXTRACTION_ENABLED", "0"),
            "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS": _env_int("LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS", 6),
            "LLM_PRODUCT_EXTRACTION_MAX_PER_RUN": _env_int("LLM_PRODUCT_EXTRACTION_MAX_PER_RUN", 25),
            "POC_GITHUB_SYNC_ENABLED": _env("POC_GITHUB_SYNC_ENABLED", "1"),
            "EXPLOITDB_SYNC_ENABLED": _env("EXPLOITDB_SYNC_ENABLED", "1"),
            "METASPLOIT_SYNC_ENABLED": _env("METASPLOIT_SYNC_ENABLED", "1"),
            "NUCLEI_SYNC_ENABLED": _env("NUCLEI_SYNC_ENABLED", "1"),
        },
        "backup": {
            "BACKUP_ENABLED": _env("BACKUP_ENABLED", "1"),
            "BACKUP_DIR": _env("BACKUP_DIR", "/var/lib/briefr/backups"),
            "BACKUP_RETENTION_COUNT": _env_int("BACKUP_RETENTION_COUNT", 100),
            "BACKUP_INTERVAL_HOURS": _env_int("BACKUP_INTERVAL_HOURS", 6),
            "BACKUP_LOG_MAX_BYTES": _env_int("BACKUP_LOG_MAX_BYTES", 5242880),
            "BACKUP_LOG_BACKUP_COUNT": _env_int("BACKUP_LOG_BACKUP_COUNT", 5),
            "BACKUP_AGE_KEY_FILE": age_key_masked,
        },
        "app": {
            "BRIEFR_ENV": _env("BRIEFR_ENV", "development"),
            "DEFAULT_TIMEZONE": _env("DEFAULT_TIMEZONE", "Asia/Kolkata"),
            "ALLOWED_ORIGINS": allowed_origins_list,
            "BRIEFR_STACK_TERMS": _env("BRIEFR_STACK_TERMS", ""),
            "LOG_FORMAT": _env("LOG_FORMAT", "json"),
            "RATE_LIMIT_ENABLED": _env("RATE_LIMIT_ENABLED", "1"),
            "RATE_LIMIT_IOC_PER_MINUTE": _env_int("RATE_LIMIT_IOC_PER_MINUTE", 30),
            "RATE_LIMIT_REFRESH_PER_MINUTE": _env_int("RATE_LIMIT_REFRESH_PER_MINUTE", 10),
        },
        "api_keys": {
            "NVD_API_KEY": _mask_key(_env("NVD_API_KEY")),
            "VIRUSTOTAL_API_KEY": _mask_key(_env("VIRUSTOTAL_API_KEY")),
            "ABUSEIPDB_API_KEY": _mask_key(_env("ABUSEIPDB_API_KEY")),
            "GREYNOISE_API_KEY": _mask_key(_env("GREYNOISE_API_KEY")),
            "GITHUB_TOKEN": _mask_key(_env("GITHUB_TOKEN")),
            "GROQ_API_KEY": _mask_key(_env("GROQ_API_KEY")),
        },
        "webhooks": {
            "DISCORD_WEBHOOK_URL": _mask_url(_env("DISCORD_WEBHOOK_URL")),
            "DISCORD_WEBHOOK_ENABLED": _env("DISCORD_WEBHOOK_ENABLED", "1"),
            "DISCORD_WEBHOOK_EVENTS": _env("DISCORD_WEBHOOK_EVENTS", ""),
            "TELEGRAM_BOT_TOKEN": _mask_key(_env("TELEGRAM_BOT_TOKEN")),
            "TELEGRAM_CHAT_ID": _env("TELEGRAM_CHAT_ID") or "not configured",
            "TELEGRAM_WEBHOOK_ENABLED": _env("TELEGRAM_WEBHOOK_ENABLED", "1"),
            "TELEGRAM_WEBHOOK_EVENTS": _env("TELEGRAM_WEBHOOK_EVENTS", ""),
            "WEBHOOK_GENERIC_URL": _mask_url(_env("WEBHOOK_GENERIC_URL")),
            "WEBHOOK_GENERIC_ENABLED": _env("WEBHOOK_GENERIC_ENABLED", "1"),
            "WEBHOOK_GENERIC_LABEL": _env("WEBHOOK_GENERIC_LABEL") or "not configured",
            "WEBHOOK_GENERIC_EVENTS": _env("WEBHOOK_GENERIC_EVENTS", ""),
        },
    }


@router.get("/config")
async def get_config(request: Request):
    return _get_config_response()


@router.post("/config")
async def set_config(request: Request, body: dict):
    from dotenv import set_key as dotenv_set_key

    key = body.get("key", "")
    value = str(body.get("value", ""))

    if not key or key == "BRIEFR_ADMIN_API_KEY" or key not in WRITABLE_CONFIG_KEYS:
        raise HTTPException(400, f"Key '{key}' is not writable via this API")

    if key in INTEGER_KEYS:
        try:
            int(value)
        except (ValueError, TypeError):
            raise HTTPException(400, f"Key '{key}' requires an integer value")

    dotenv_path = str(_DOTENV_PATH.resolve())
    dotenv_set_key(dotenv_path, key, value)
    os.environ[key] = value

    # Propagate to the live settings object so the change takes effect without
    # a restart for keys that settings already tracks.
    attr = key.lower()
    if hasattr(settings, attr):
        try:
            current = getattr(settings, attr)
            if isinstance(current, bool):
                setattr(settings, attr, value.lower() not in ("0", "false", "no", "off"))
            elif isinstance(current, int):
                setattr(settings, attr, int(value))
            else:
                setattr(settings, attr, value)
        except Exception:
            pass

    await audit(request, f"config.set.{key}", value[:100])

    masked = _mask_key(value) if key in {"DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "WEBHOOK_GENERIC_URL"} else value
    return {
        "ok": True,
        "key": key,
        "masked_value": masked,
        "warning_restart_required": key in RESTART_REQUIRED_KEYS,
    }


@router.post("/config/apply-all")
async def apply_all_config(request: Request, background_tasks: BackgroundTasks):
    """Write multiple config keys to .env and trigger a restart."""
    from dotenv import set_key as dotenv_set_key

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Body must be a JSON array of {key, value} objects")

    if not isinstance(body, list):
        raise HTTPException(400, "Body must be a JSON array of {key, value} objects")

    dotenv_path = str(_DOTENV_PATH.resolve())
    allowed = WRITABLE_CONFIG_KEYS | APPLY_ALL_EXTRA_KEYS
    errors: list[str] = []
    validated: list[tuple[str, str]] = []

    # Pass 1: validate all items before writing anything
    for item in body:
        if not isinstance(item, dict):
            errors.append(f"Invalid item: {item!r}")
            continue
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))

        if not key:
            errors.append("Empty key in item")
            continue
        if key not in allowed:
            errors.append(f"Key '{key}' is not in the writable allowlist")
            continue
        if key in INTEGER_KEYS:
            try:
                int(value)
            except (ValueError, TypeError):
                errors.append(f"Key '{key}' requires an integer value")
                continue
        validated.append((key, value))

    if errors:
        raise HTTPException(400, {"errors": errors, "partial_keys": []})

    # Pass 2: write only after full validation passes
    changed_keys: list[str] = []
    for key, value in validated:
        dotenv_set_key(dotenv_path, key, value)
        os.environ[key] = value
        changed_keys.append(key)

    if not changed_keys:
        return {"ok": True, "changed_keys": [], "message": "No changes to apply"}

    changed_summary = ", ".join(changed_keys[:10])
    await audit(request, "config.apply", changed_summary)

    background_tasks.add_task(trigger_graceful_restart)
    return {
        "ok": True,
        "changed_keys": changed_keys,
        "message": f"Applied {len(changed_keys)} key(s); restarting backend",
    }


@router.post("/config/webhook-test")
async def test_webhook(request: Request, body: dict):
    from webhooks.destinations import load_destinations
    from webhooks.sender import send_test_message

    destination_id = body.get("destination_id") or body.get("channel", "")
    destinations = await load_destinations()
    valid_ids = {dest.id for dest in destinations}
    if destination_id not in valid_ids:
        raise HTTPException(
            400,
            f"destination_id must be one of: {', '.join(sorted(valid_ids)) or 'none configured'}",
        )

    result = await send_test_message(destination_id, "BRIEFR admin webhook test")
    await audit(request, f"webhook.test.{destination_id}", destination_id)
    return result


@router.get("/webhooks/destinations")
async def get_webhook_destinations(request: Request):
    from webhooks.destinations import load_destinations

    destinations = await load_destinations()
    rows = []
    for dest in destinations:
        rows.append(
            {
                "id": dest.id,
                "kind": dest.kind,
                "label": dest.label,
                "enabled": dest.enabled,
                "event_types": dest.event_types,
                "source": dest.source,
                "health_source": dest.health_source,
            }
        )
    return {"destinations": rows}


@router.patch("/webhooks/destinations/{destination_id}")
async def patch_webhook_destination(request: Request, destination_id: str, body: dict):
    from webhooks.destinations import ALL_EVENT_TYPES, load_destinations, parse_event_types, sync_env_destinations_to_db

    enabled = body.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise HTTPException(400, "enabled must be a boolean")

    event_types = body.get("event_types")
    if event_types is not None:
        if not isinstance(event_types, list):
            raise HTTPException(400, "event_types must be an array")
        normalized = parse_event_types(event_types)
        unknown = [item for item in normalized if item not in ALL_EVENT_TYPES]
        if unknown:
            raise HTTPException(400, f"unknown event_types: {', '.join(unknown)}")
        event_types = normalized

    label = body.get("label")
    if label is not None and not isinstance(label, str):
        raise HTTPException(400, "label must be a string")

    if enabled is None and event_types is None and label is None:
        raise HTTPException(400, "no fields to update")

    await sync_env_destinations_to_db()
    if not any(dest.id == destination_id for dest in await load_destinations()):
        raise HTTPException(404, f"Destination '{destination_id}' not found")

    db = await get_db()
    try:
        from database import update_webhook_destination

        updated = await update_webhook_destination(
            db,
            destination_id,
            enabled=enabled,
            event_types=event_types,
            label=label.strip() if isinstance(label, str) else None,
        )
        if not updated:
            raise HTTPException(404, f"Destination '{destination_id}' not found")
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"webhook.destination.update.{destination_id}", destination_id)
    from webhooks.destinations import load_destinations

    dest = next((item for item in await load_destinations() if item.id == destination_id), None)
    if dest is None:
        raise HTTPException(404, f"Destination '{destination_id}' not found")
    return {
        "ok": True,
        "destination": {
            "id": dest.id,
            "kind": dest.kind,
            "label": dest.label,
            "enabled": dest.enabled,
            "event_types": dest.event_types,
            "source": dest.source,
            "health_source": dest.health_source,
        },
    }


# ── Database engine & migration ────────────────────────────────────────────


@router.get("/database")
async def get_database_info(request: Request):
    from db.config import is_postgres, resolve_database_url

    current_url = resolve_database_url()
    info: dict[str, Any] = {
        "engine": "postgresql" if is_postgres(current_url) else "sqlite",
    }
    if is_postgres(current_url):
        info["postgres_dsn_redacted"] = re.sub(r"://[^@]+@", "://***@", current_url)
    else:
        db_path = Path(DB_PATH)
        info["sqlite_path"] = str(db_path)
        info["sqlite_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0
    return info


@router.post("/database/test-connection")
async def test_database_connection(request: Request, body: dict):
    from migration.sqlite_to_postgres import test_connection

    database_url = str(body.get("database_url", "")).strip()
    if not database_url:
        raise HTTPException(400, "database_url is required")
    return await test_connection(database_url)


@router.post("/database/migrate")
async def start_database_migration(request: Request, background_tasks: BackgroundTasks, body: dict):
    from db.config import is_postgres
    from migration.sqlite_to_postgres import reserve_migration_slot, run_migration

    database_url = str(body.get("database_url", "")).strip()
    confirm_text = str(body.get("confirm_text", "")).strip()
    if not database_url:
        raise HTTPException(400, "database_url is required")
    if not is_postgres(database_url):
        raise HTTPException(400, "database_url must be a postgresql:// URL")
    if confirm_text != "migrate":
        raise HTTPException(400, "Type 'migrate' to confirm")

    # Reserve the slot synchronously (not in the background task) so a second
    # rapid request can't slip past the check before the first task starts.
    try:
        await reserve_migration_slot()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))

    await audit(request, "database.migrate.start", re.sub(r"://[^@]+@", "://***@", database_url))
    background_tasks.add_task(run_migration, database_url, DB_PATH, _reserved=True)
    return {"ok": True, "message": "Migration started — poll /api/admin/database/migrate/status"}


@router.get("/database/migrate/status")
async def get_database_migration_status(request: Request):
    from migration.sqlite_to_postgres import get_status

    return get_status()


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
    "epss_score_sync": "run_epss_sync",
    "weekly_mitre_refresh": "run_weekly_mitre_refresh",
    "otx_nightly_correlation": "run_otx_nightly_sync",
    "incident_feed_refresh": "run_incident_feed_refresh",
    "nightly_correlation": "run_nightly_correlation",
    "vulnrichment_snapshot_sync": "run_vulnrichment_sync",
    "cvelistv5_incremental_sync": "run_cvelistv5_sync",
    "embeddings_backfill": "run_embeddings_sync",
    "llm_product_extraction": "run_llm_extraction_sync",
    "exploit_sources_sync": "run_exploit_sources_sync",
    "backup_deadman_check": "run_backup_deadman_check",
}


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

    sched = _get_scheduler_module()
    fn_name = _JOB_RUN_MAP[job_id]
    fn = getattr(sched, fn_name, None)
    if fn is None:
        raise HTTPException(500, f"Coroutine '{fn_name}' not found in scheduler module")

    asyncio.create_task(fn())
    await audit(request, f"scheduler.run.{job_id}", job_id)
    return {"ok": True, "job_id": job_id, "message": f"Job '{job_id}' started in background"}


# ── Feed circuit breaker ───────────────────────────────────────────────────


@router.post("/feeds/{source_id}/reset-circuit")
async def reset_feed_circuit(source_id: str, request: Request):
    try:
        reset_circuit(source_id)
    except KeyError:
        raise HTTPException(404, f"Source '{source_id}' not found in health registry")
    await audit(request, f"feed.circuit_reset.{source_id}", source_id)
    return {"ok": True, "source_id": source_id}


# ── Webhooks log ───────────────────────────────────────────────────────────


@router.get("/webhooks/log")
async def get_webhooks_log(
    request: Request,
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from database import _webhook_alert_types

    db = await get_db()
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if event_type:
            types = _webhook_alert_types(event_type)
            placeholders = ", ".join("?" for _ in types)
            conditions.append(f"alert_type IN ({placeholders})")
            params.extend(types)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM webhook_alert_log {where}", params
        )
        total = count_row[0]["cnt"] if count_row else 0

        rows = await db.execute_fetchall(
            f"""
            SELECT alert_type, target, alerted_at
            FROM webhook_alert_log
            {where}
            ORDER BY alerted_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
    finally:
        await db.close()

    return {
        "rows": [dict(r) for r in rows],
        "total": total,
    }


@router.get("/webhooks/delivery-log")
async def get_webhooks_delivery_log(
    request: Request,
    destination_id: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    try:
        from database import list_webhook_delivery_log

        rows, total = await list_webhook_delivery_log(
            db,
            destination_id=destination_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
    finally:
        await db.close()

    return {
        "rows": [dict(r) for r in rows],
        "total": total,
    }


# ── Logs ───────────────────────────────────────────────────────────────────


@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None),
    logger_name: str | None = Query(None, alias="logger"),
    request_id: str | None = Query(None),
    category: str | None = Query(None),
):
    logs = get_log_buffer(
        limit=limit,
        level=level,
        logger_name=logger_name,
        request_id=request_id,
        category=category,
    )
    known = get_known_loggers()

    return {
        "logs": logs,
        "known_loggers": known,
        "categories": list(LOG_CATEGORIES),
        "buffer_capacity": 500,
    }


# ── Security ───────────────────────────────────────────────────────────────


@router.get("/security")
async def get_security(request: Request):
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM audit_log "
            "WHERE action = 'auth.failure' AND created_at >= datetime('now', '-24 hours')"
        )
        failed_auth = row[0]["cnt"] if row else 0
    finally:
        await db.close()

    return {
        "admin_key_set": bool(settings.briefr_admin_api_key),
        "failed_auth_last_24h": failed_auth,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_ioc_per_minute": settings.rate_limit_ioc_per_minute,
        "rate_limit_refresh_per_minute": settings.rate_limit_refresh_per_minute,
        "top_rate_limit_consumers": get_top_consumers(5),
    }


# ── Restart ────────────────────────────────────────────────────────────────


@router.post("/restart", status_code=202)
async def restart_backend(request: Request, background_tasks: BackgroundTasks, body: dict | None = None):
    drain = bool(body.get("drain", False)) if body else False
    await audit(request, "system.restart", "drain" if drain else "immediate")

    background_tasks.add_task(trigger_graceful_restart, drain)
    return {"status": "draining" if drain else "restarting"}


# ── Audit log ──────────────────────────────────────────────────────────────


@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    action_prefix: str | None = Query(None),
    actor: str | None = Query(None),
):
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if action:
            conditions.append("action = ?")
            params.append(action)
        elif action_prefix:
            conditions.append("action LIKE ?")
            params.append(f"{action_prefix}%")
        if actor:
            conditions.append("actor = ?")
            params.append(actor)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM audit_log {where}",
            params,
        )
        total = count_row[0]["cnt"] if count_row else 0

        params_paginated = params + [limit, offset]
        rows = await db.execute_fetchall(
            f"""
            SELECT id, actor, action, target, created_at
            FROM audit_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params_paginated,
        )
    finally:
        await db.close()

    return {"rows": [dict(row) for row in rows], "total": total}


# ── Diagnostics ────────────────────────────────────────────────────────────


@router.post("/diagnostics/smoke")
async def run_smoke_test(request: Request):
    """Run in-process smoke checks and return a checklist result."""
    import time as _time

    start_ms = _time.time() * 1000
    checks: list[dict[str, Any]] = []

    # 1. API health check (via in-process DB)
    try:
        db = await get_db()
        try:
            cve_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
            cve_count = cve_row[0]["cnt"] if cve_row else 0
            kev_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM kev_deadlines")
            kev_count = kev_row[0]["cnt"] if kev_row else 0
            ic_rows = await db.execute_fetchall("PRAGMA integrity_check")
            integrity_ok = len(ic_rows) == 1 and ic_rows[0][0].lower() == "ok"
        finally:
            await db.close()
        checks.append({"name": "cves > 0", "passed": cve_count > 0, "detail": f"{cve_count} CVEs"})
        checks.append({"name": "kev_deadlines > 0", "passed": kev_count > 0, "detail": f"{kev_count} KEV entries"})
        checks.append({"name": "db integrity_check", "passed": integrity_ok, "detail": ic_rows[0][0] if ic_rows else "?"})
    except Exception as exc:
        checks.append({"name": "db checks", "passed": False, "detail": str(exc)[:200]})

    # 2. At least one feed source healthy
    feed_health = get_feed_health()
    healthy_sources = [k for k, v in feed_health.items() if not v.get("circuit_open")]
    checks.append({
        "name": "feed sources healthy",
        "passed": len(healthy_sources) > 0,
        "detail": f"{len(healthy_sources)}/{len(feed_health)} sources healthy",
    })

    # 3. Backup dir exists and writable
    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    try:
        bdir = pathlib.Path(backup_dir)
        backup_ok = bdir.exists() and os.access(backup_dir, os.W_OK)
        checks.append({"name": "backup dir writable", "passed": backup_ok, "detail": backup_dir})
    except Exception as exc:
        checks.append({"name": "backup dir writable", "passed": False, "detail": str(exc)[:100]})

    duration_ms = round(_time.time() * 1000 - start_ms)
    all_passed = all(c["passed"] for c in checks)
    await audit(request, "diagnostics.smoke", "pass" if all_passed else "fail")
    return {"ok": all_passed, "checks": checks, "duration_ms": duration_ms}


@router.post("/diagnostics/integrity")
async def check_integrity(request: Request):
    """Run PRAGMA integrity_check and foreign_key_check."""
    db = await get_db()
    try:
        ic_rows = await db.execute_fetchall("PRAGMA integrity_check")
        fk_rows = await db.execute_fetchall("PRAGMA foreign_key_check")
    finally:
        await db.close()

    integrity_ok = len(ic_rows) == 1 and ic_rows[0][0].lower() == "ok"
    foreign_keys_ok = len(fk_rows) == 0
    msg = ic_rows[0][0] if ic_rows else "unknown"
    await audit(request, "diagnostics.integrity", "pass" if integrity_ok and foreign_keys_ok else "fail")
    return {
        "ok": integrity_ok and foreign_keys_ok,
        "integrity_ok": integrity_ok,
        "foreign_keys_ok": foreign_keys_ok,
        "message": msg,
        "foreign_key_violations": len(fk_rows),
    }
