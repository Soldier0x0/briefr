"""Admin dashboard API — backups, storage, DB explorer, resources.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
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
from datetime import datetime, timezone
from typing import Any

from path_safety import PathValidationError, resolve_backup_archive

from fastapi import BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse

from database import (
    EPSS_BACKFILL_DONE_KEY,
    NVD_SYNC_WATERMARK_KEY,
    get_db,
    purge_legacy_rejected_cves,
)
from dependencies import audit
from destructive_actions import list_actions, require_confirm
from rate_limit import rate_limit_db_explorer

from .helpers import _backup_running
from .router import router

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
    try:
        safe_path = resolve_backup_archive(filename, backup_dir=backup_dir)
    except PathValidationError as exc:
        if "file not found" in str(exc).lower():
            raise HTTPException(404, "Backup file not found") from exc
        raise HTTPException(400, str(exc)) from exc
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
    except Exception:
        return {
            "ok": False,
            "filename": filename,
            "details": "Backup verification failed. Check server logs for details.",
        }


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
    "group_technique_map", "otx_cve_pulses", "otx_pulse_iocs", "otx_pulses",
    "cve_exploits",
    "cve_change_history", "ioc_cache", "feed_cache",
    "correlation_actor", "correlation_temporal", "correlation_campaigns",
    "correlation_campaign_members", "correlation_suppressions", "cve_embeddings", "embeddings",
    "api_usage",
    "audit_log", "sync_state", "app_settings", "watchlist", "hunt_packs", "webhook_alert_log",
]


def _partition_stats(dir_path: str) -> dict[str, Any]:
    path = os.path.abspath(dir_path)
    out: dict[str, Any] = {"free": 0, "total": 0, "used": 0, "path": path, "device_id": None}
    try:
        du = shutil.disk_usage(path)
        out.update({"free": du.free, "total": du.total, "used": du.used})
        out["device_id"] = os.stat(path).st_dev
    except OSError:
        pass
    return out


@router.get("/storage")
async def get_storage(request: Request):
    from storage_metrics import (
        estimate_growth_bytes_per_day,
        fetch_table_sizes,
        read_host_disk_io,
    )

    db = await get_db()
    table_sizes: list[dict[str, Any]] = []
    try:
        counts: dict[str, int] = {}
        for table in _STORAGE_TABLES:
            try:
                rows = await db.execute_fetchall(f"SELECT COUNT(*) as cnt FROM {table}")
                counts[table] = rows[0]["cnt"] if rows else 0
            except Exception:
                counts[table] = -1
        table_sizes = await fetch_table_sizes(db)
    finally:
        await db.close()

    # Get DB size from pg_database_size
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT pg_database_size(current_database()) as size")
        db_size_bytes = int(rows[0]["size"]) if rows else 0
    finally:
        await db.close()

    # DB partition disk usage - use current working directory for Postgres
    db_partition = _partition_stats(".")

    # Backup partition disk usage — always resolve path independently (never copy db_partition metadata)
    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    backup_partition = _partition_stats(backup_dir)

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

    growth_estimate = estimate_growth_bytes_per_day(db_size_bytes, backup_dir)
    disk_io = read_host_disk_io(".")

    return {
        "tables": counts,
        "table_sizes": table_sizes,
        "growth_estimate": growth_estimate,
        "disk_io": disk_io,
        "db_size_bytes": db_size_bytes,
        "db_path": "postgresql",
        # legacy flat fields for backward compat
        "disk_free_bytes": db_partition["free"],
        "disk_total_bytes": db_partition["total"],
        # structured partition objects (new)
        "db_partition": db_partition,
        "backup_partition": backup_partition,
        "archive_count": archive_count,
        "backup_dir": backup_dir,
    }


# ── DB explorer (read-only, deny-by-default) ─────────────────────────────────

@router.get("/db-explorer/tables", dependencies=[Depends(rate_limit_db_explorer)])
async def get_db_explorer_tables(request: Request):
    """Allowlisted tables with row counts and column metadata — no arbitrary SQL."""
    from db.explorer import fetch_table_catalog

    db = await get_db()
    try:
        tables = await fetch_table_catalog(db)
    finally:
        await db.close()
    return {"tables": tables, "read_only": True}


@router.get("/db-explorer/tables/{table_name}/rows", dependencies=[Depends(rate_limit_db_explorer)])
async def get_db_explorer_rows(
    request: Request,
    table_name: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
    filter_column: str | None = Query(None),
    filter_value: str | None = Query(None),
):
    """Paginated read-only rows for one allowlisted table."""
    from db.explorer import fetch_table_rows

    db = await get_db()
    try:
        try:
            payload = await fetch_table_rows(
                db,
                table_name,
                limit=limit,
                offset=offset,
                filter_column=filter_column,
                filter_value=filter_value,
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="Table not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()

    audit_target = table_name
    if filter_column and filter_value:
        audit_target = f"{table_name}:{filter_column}={filter_value[:80]}"
    await audit(request, f"db.explorer.browse.{table_name}", audit_target)

    return payload


_PURGE_TARGETS = frozenset({
    "ioc_cache", "feed_cache", "epss_history_old", "change_history_old",
    "rejected_cves", "nvd_watermark", "epss_backfill_reset",
})


@router.get("/destructive-actions")
async def get_destructive_actions(request: Request):
    """Registry of confirm-gated destructive actions, for the frontend to
    render confirm dialogs generically instead of hardcoding confirm words."""
    return list_actions()


@router.post("/storage/purge")
async def purge_storage(request: Request, body: dict):
    target = body.get("target", "")
    confirm_text = body.get("confirm_text", body.get("confirm", ""))
    days_back = body.get("days_back")

    if target not in _PURGE_TARGETS:
        raise HTTPException(400, f"Unknown target '{target}'. Valid: {sorted(_PURGE_TARGETS)}")

    try:
        require_confirm(f"storage.purge.{target}", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

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
            from database import purge_old_epss_history

            rows_deleted = await purge_old_epss_history(db)
        elif target == "change_history_old":
            from database import purge_old_cve_change_history

            rows_deleted = await purge_old_cve_change_history(db)
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


async def _run_export_dump(tmp_path: pathlib.Path) -> None:
    from backup.postgres_util import run_pg_dump_sql
    from db.config import resolve_database_url

    db_url = resolve_database_url()
    if not db_url.startswith(("postgresql", "postgres")):
        raise HTTPException(500, "DATABASE_URL not configured")
    await run_pg_dump_sql(db_url, tmp_path)


@router.get("/storage/export")
async def export_db(request: Request, background_tasks: BackgroundTasks):
    """Stream a consistent database dump using pg_dump (PostgreSQL)."""
    import tempfile as _tempfile

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"briefr-{date_str}.sql"
    tmp_path = pathlib.Path(_tempfile.gettempdir()) / f"briefr-export-{int(time.time())}.sql"
    try:
        await _run_export_dump(tmp_path)
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(500, "Database export timed out") from None
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Database export failed: %s", exc)
        raise HTTPException(500, "Failed to create database export") from None

    await audit(request, "storage.db_export", filename)
    background_tasks.add_task(os.remove, tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/sql",
        filename=filename,
    )


# ── Resource metrics (RB-2) ────────────────────────────────────────────────


@router.get("/resources")
async def get_resources(window: str = "1d"):
    if window not in ("1d", "3d", "7d", "30d"):
        raise HTTPException(400, "window must be 1d, 3d, 7d, or 30d")
    from db.resource_metrics import fetch_resources_response
    from host_profile import collect_host_profile
    from db.connection import get_pool_stats

    db = await get_db()
    try:
        result = await fetch_resources_response(db, window)
        db_file_bytes = 0
        try:
            rows = await db.execute_fetchall(
                "SELECT pg_database_size(current_database()) as size"
            )
            db_file_bytes = int(rows[0]["size"]) if rows else 0
        except Exception:
            db_file_bytes = 0
        result["host_profile"] = collect_host_profile(db_path="postgresql")
        result["pool_stats"] = get_pool_stats()
        result["db_file_bytes"] = db_file_bytes
        return result
    finally:
        await db.close()


@router.get("/resources/host-profile")
async def get_resources_host_profile():
    """Lightweight live host snapshot for admin capacity bars (poll every ~15s)."""
    from host_profile import collect_host_profile

    return collect_host_profile(db_path="postgresql")


@router.get("/resources/efficiency")
async def get_resources_efficiency():
    from efficiency_audit import build_efficiency_report

    db = await get_db()
    try:
        return await build_efficiency_report(db, db_path="postgresql")
    finally:
        await db.close()

