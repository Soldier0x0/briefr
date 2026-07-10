"""Redacted operator support pack — health + logs, no secrets (V1.4 / Wave 4).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from datetime import datetime, timezone
from typing import Any

from database import get_cve_count, get_db, get_last_updated, get_nvd_sync_watermark
from db.integrity import run_integrity_check
from db.config import is_postgres, resolve_database_url
from db.connection import get_pool_stats
from correlation.status import get_correlation_admin_status
from resilient_client import get_api_queue_status, get_feed_health
from scheduler import get_ingest_status, refresh_in_progress
from scheduler_locks import locked_jobs
from settings import production_posture_warnings, settings
from structured_logging import get_log_buffer

_BUILD_INFO_PATH = pathlib.Path(__file__).resolve().parents[1] / ".build-info.json"
SUPPORT_PACK_VERSION = 1


def _read_build_info() -> dict[str, Any]:
    try:
        with _BUILD_INFO_PATH.open() as f:
            return json.load(f)
    except Exception:
        return {}


def _redact_database_url(url: str) -> str:
    if not url:
        return "not configured"
    return re.sub(r"://[^@]+@", "://***@", url)


def _database_meta() -> dict[str, Any]:
    db_url = resolve_database_url()
    db_host = db_url.split("@")[-1] if "@" in db_url else ("sqlite" if not is_postgres() else db_url)
    meta: dict[str, Any] = {
        "backend": "postgresql" if is_postgres() else "sqlite",
        "host": _redact_database_url(db_host) if is_postgres() else db_host,
        "url": _redact_database_url(db_url),
    }
    pool = get_pool_stats()
    if pool is not None:
        meta["pool"] = pool
    return meta


async def _run_smoke_checks() -> dict[str, Any]:
    start_ms = time.time() * 1000
    checks: list[dict[str, Any]] = []

    try:
        db = await get_db()
        try:
            cve_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
            cve_count = cve_row[0]["cnt"] if cve_row else 0
            kev_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM kev_deadlines")
            kev_count = kev_row[0]["cnt"] if kev_row else 0
            result = await run_integrity_check(db)
            integrity_ok = result.integrity_ok
        finally:
            await db.close()
        checks.append({"name": "cves > 0", "passed": cve_count > 0, "detail": f"{cve_count} CVEs"})
        checks.append({"name": "kev_deadlines > 0", "passed": kev_count > 0, "detail": f"{kev_count} KEV entries"})
        checks.append({
            "name": "db integrity_check",
            "passed": integrity_ok,
            "detail": result.message,
        })
    except Exception as exc:
        checks.append({"name": "db checks", "passed": False, "detail": str(exc)[:200]})

    feed_health = get_feed_health()
    healthy_sources = [k for k, v in feed_health.items() if not v.get("circuit_open")]
    checks.append(
        {
            "name": "feed sources healthy",
            "passed": len(healthy_sources) > 0,
            "detail": f"{len(healthy_sources)}/{len(feed_health)} sources healthy",
        }
    )

    backup_dir = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    try:
        bdir = pathlib.Path(backup_dir)
        backup_ok = bdir.exists() and os.access(backup_dir, os.W_OK)
        checks.append({"name": "backup dir writable", "passed": backup_ok, "detail": backup_dir})
    except Exception as exc:
        checks.append({"name": "backup dir writable", "passed": False, "detail": str(exc)[:100]})

    duration_ms = round(time.time() * 1000 - start_ms)
    all_passed = all(c["passed"] for c in checks)
    return {"ok": all_passed, "checks": checks, "duration_ms": duration_ms}


async def _run_integrity_check() -> dict[str, Any]:
    db = await get_db()
    try:
        result = await run_integrity_check(db)
    finally:
        await db.close()
    return result.as_dict()


async def build_support_pack(*, log_limit: int = 200) -> dict[str, Any]:
    """Assemble a redacted JSON bundle for operator support / `briefr doctor`."""
    log_limit = max(1, min(log_limit, 500))
    now = datetime.now(timezone.utc)

    db = await get_db()
    try:
        cve_count = await get_cve_count(db)
        last_updated = await get_last_updated(db)
        nvd_sync_watermark = await get_nvd_sync_watermark(db)
        correlation = await get_correlation_admin_status(db)
    finally:
        await db.close()

    smoke = await _run_smoke_checks()
    integrity = await _run_integrity_check()
    feed_health = get_feed_health()
    open_circuits = sum(1 for v in feed_health.values() if v.get("circuit_open"))

    return {
        "support_pack_version": SUPPORT_PACK_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": _read_build_info(),
        "environment": settings.briefr_env,
        "health": {
            "status": "ok",
            "cve_count": cve_count,
            "last_updated": last_updated,
            "nvd_sync_watermark": nvd_sync_watermark,
            "refresh_in_progress": refresh_in_progress(),
            "ingest": get_ingest_status(),
            "feeds": feed_health,
            "open_circuit_count": open_circuits,
            "api_queue": get_api_queue_status(),
        },
        "database": _database_meta(),
        "security": {
            "posture_warnings": production_posture_warnings(),
            "rate_limit_enabled": settings.rate_limit_enabled,
        },
        "correlation": correlation,
        "diagnostics": {
            "smoke": smoke,
            "integrity": integrity,
        },
        "scheduler": {
            "active_locks": [{"job_id": job_id} for job_id in locked_jobs()],
        },
        "logs": {
            "buffer_capacity": 500,
            "limit": log_limit,
            "entries": get_log_buffer(limit=log_limit),
        },
    }
