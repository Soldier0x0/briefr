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
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File

from database import (
    DB_PATH,
    EPSS_BACKFILL_DONE_KEY,
    delete_all_snooze_entries,
    get_db,
    get_nvd_sync_watermark,
    get_sync_state_value,
    purge_legacy_rejected_cves,
    set_sync_state_value,
)
from dependencies import audit, require_admin_key
from rate_limit import get_top_consumers, rate_limit_refresh
from resilient_client import get_feed_health, reset_circuit
from settings import settings
from structured_logging import get_log_buffer

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
    "LLM_PRODUCT_EXTRACTION_ENABLED", "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS",
    "LLM_PRODUCT_EXTRACTION_MAX_PER_RUN",
    "BACKUP_ENABLED", "BACKUP_RETENTION_COUNT", "BACKUP_INTERVAL_HOURS",
    "BRIEFR_STACK_TERMS", "LOG_FORMAT", "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_IOC_PER_MINUTE", "RATE_LIMIT_REFRESH_PER_MINUTE",
    "DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
}

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
}

RESTART_REQUIRED_KEYS = {
    "LOG_FORMAT", "RATE_LIMIT_ENABLED", "RATE_LIMIT_IOC_PER_MINUTE",
    "RATE_LIMIT_REFRESH_PER_MINUTE", "CIRCUIT_FAILURE_THRESHOLD", "CIRCUIT_COOLDOWN_SECONDS",
    "SCHEDULER_TIMEZONE", "CORRELATION_TIMEZONE", "OTX_CORRELATION_TIMEZONE",
    "EMBEDDINGS_ENABLED", "LLM_PRODUCT_EXTRACTION_ENABLED",
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


async def _get_job_last_run(db: aiosqlite.Connection, job_id: str) -> dict[str, Any] | None:
    try:
        rows = await db.execute_fetchall(
            "SELECT value FROM sync_state WHERE key = ?",
            (f"scheduler.last_run.{job_id}",),
        )
        if not rows:
            return None
        return json.loads(rows[0]["value"])
    except Exception:
        return None


def _build_job_info(job: Any, last_run: dict | None) -> dict[str, Any]:
    paused = job.next_run_time is None
    next_run = None
    if job.next_run_time is not None:
        try:
            next_run = job.next_run_time.astimezone(timezone.utc).isoformat()
        except Exception:
            next_run = str(job.next_run_time)
    return {
        "id": job.id,
        "name": job.name,
        "next_run_time": next_run,
        "paused": paused,
        "lock_held": _job_lock_held(job.id),
        "last_run_utc": last_run.get("last_run_utc") if last_run else None,
        "last_run_duration_seconds": last_run.get("duration_seconds") if last_run else None,
        "last_run_records_upserted": last_run.get("records_upserted") if last_run else None,
        "last_run_had_error": last_run.get("had_error") if last_run else None,
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
            last_run = await _get_job_last_run(db, job.id)
            result.append(_build_job_info(job, last_run))
        return result
    finally:
        await db.close()


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

    # Disk usage for DB
    db_dir = os.path.dirname(os.path.abspath(DB_PATH)) or "."
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

    db_path = os.path.abspath(DB_PATH)
    db_size_bytes = 0
    try:
        db_size_bytes = os.path.getsize(db_path)
    except Exception:
        pass

    return {
        "tables": counts,
        "db_size_bytes": db_size_bytes,
        "db_path": db_path,
    }


@router.post("/storage/purge")
async def purge_storage(request: Request, body: dict):
    target = body.get("target", "")
    confirm = body.get("confirm", "")
    if confirm != "delete":
        raise HTTPException(400, "confirm must be 'delete'")

    valid_targets = {"ioc_cache", "feed_cache", "epss_history_old", "change_history_old", "rejected_cves"}
    if target not in valid_targets:
        raise HTTPException(400, f"Unknown target '{target}'. Valid: {sorted(valid_targets)}")

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
            cursor = await db.execute("DELETE FROM epss_history WHERE date < date('now', '-90 days')")
            rows_deleted = cursor.rowcount
        elif target == "change_history_old":
            cursor = await db.execute(
                "DELETE FROM cve_change_history WHERE changed_at < datetime('now', '-90 days')"
            )
            rows_deleted = cursor.rowcount
        elif target == "rejected_cves":
            rows_deleted = await purge_legacy_rejected_cves(db)
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"storage.purge.{target}", str(rows_deleted))
    return {"ok": True, "rows_deleted": rows_deleted}


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
            "TELEGRAM_BOT_TOKEN": _mask_key(_env("TELEGRAM_BOT_TOKEN")),
            "TELEGRAM_CHAT_ID": _env("TELEGRAM_CHAT_ID") or "not configured",
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

    masked = _mask_key(value) if key in {"DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN"} else value
    return {
        "ok": True,
        "key": key,
        "masked_value": masked,
        "warning_restart_required": key in RESTART_REQUIRED_KEYS,
    }


@router.post("/config/webhook-test")
async def test_webhook(request: Request, body: dict):
    from webhooks.sender import send_test_message

    channel = body.get("channel", "")
    if channel not in ("discord", "telegram"):
        raise HTTPException(400, "channel must be 'discord' or 'telegram'")

    result = await send_test_message(channel, "BRIEFR admin webhook test")
    await audit(request, f"webhook.test.{channel}", channel)
    return result


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
            data = json.loads(row["value"])
        except Exception:
            data = {}
        result.append({
            "job_id": job_id,
            "last_run_utc": data.get("last_run_utc"),
            "duration_seconds": data.get("duration_seconds"),
            "records_upserted": data.get("records_upserted"),
            "had_error": data.get("had_error"),
        })

    result.sort(key=lambda x: x.get("last_run_utc") or "", reverse=True)
    return result


# ── Feed circuit breaker ───────────────────────────────────────────────────


@router.post("/feeds/{source_id}/reset-circuit")
async def reset_feed_circuit(source_id: str, request: Request):
    try:
        reset_circuit(source_id)
    except KeyError:
        raise HTTPException(404, f"Source '{source_id}' not found in health registry")
    await audit(request, f"feed.circuit_reset.{source_id}", source_id)
    return {"ok": True, "source_id": source_id}


# ── Logs ───────────────────────────────────────────────────────────────────


@router.get("/logs")
async def get_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None),
    request_id: str | None = Query(None),
):
    return get_log_buffer(limit=limit, level=level, request_id=request_id)


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
async def restart_backend(request: Request, background_tasks: BackgroundTasks):
    await audit(request, "system.restart", "")

    async def _do_restart():
        from scheduler import stop_scheduler
        from resilient_client import close_client

        stop_scheduler()
        await close_client()
        os._exit(0)

    background_tasks.add_task(_do_restart)
    return {"status": "restarting"}


# ── Audit log ──────────────────────────────────────────────────────────────


@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    actor: str | None = Query(None),
):
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if action:
            conditions.append("action = ?")
            params.append(action)
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
