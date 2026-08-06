"""Admin dashboard API — logs, security, restart, audit, diagnostics, onboarding, ratelimit.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Query, Request, Response

import routers.admin as _admin_pkg
from database import get_db
from db.integrity import run_integrity_check
from dependencies import audit
from destructive_actions import require_confirm
from rate_limit import get_bucket_stats, get_top_consumers
from resilient_client import get_feed_health
from settings import production_posture_warnings, settings
from structured_logging import LOG_CATEGORIES, get_known_loggers, get_log_buffer

from .router import router


@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None),
    logger_name: str | None = Query(None, alias="logger"),
    request_id: str | None = Query(None),
    job_id: str | None = Query(None),
    run_id: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
    since: str | None = Query(None, max_length=40, description="ISO-8601 UTC lower bound (inclusive)"),
    until: str | None = Query(None, max_length=40, description="ISO-8601 UTC upper bound (inclusive)"),
):
    logs = get_log_buffer(
        limit=limit,
        level=level,
        logger_name=logger_name,
        request_id=request_id,
        job_id=job_id,
        run_id=run_id,
        category=category,
        search=search,
        since=since,
        until=until,
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
        auth_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM audit_log "
            "WHERE action IN ('auth.login_failed', 'auth.failure') "
            "AND created_at >= ?",
            (auth_cutoff,),
        )
        failed_auth = row[0]["cnt"] if row else 0
    finally:
        await db.close()

    return {
        "failed_auth_last_24h": failed_auth,
        "environment": settings.briefr_env,
        "posture_warnings": production_posture_warnings(),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_ioc_per_minute": settings.rate_limit_ioc_per_minute,
        "rate_limit_refresh_per_minute": settings.rate_limit_refresh_per_minute,
        "rate_limit_admin_read_per_minute": settings.rate_limit_admin_read_per_minute,
        "rate_limit_login_per_minute": settings.rate_limit_login_per_minute,
        "rate_limit_auth_refresh_per_minute": settings.rate_limit_auth_refresh_per_minute,
        "top_rate_limit_consumers": get_top_consumers(5),
    }


# ── Restart ────────────────────────────────────────────────────────────────


@router.post("/restart", status_code=202)
async def restart_backend(request: Request, background_tasks: BackgroundTasks, body: dict | None = None):
    drain = bool(body.get("drain", False)) if body else False
    confirm_text = (body or {}).get("confirm_text", "")
    try:
        require_confirm("system.restart.drain" if drain else "system.restart", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    await audit(request, "system.restart", "drain" if drain else "immediate")

    background_tasks.add_task(_admin_pkg.trigger_graceful_restart, drain)
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
    q: str | None = Query(None),
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
        if q:
            conditions.append("(target LIKE ? OR action LIKE ? OR metadata_json LIKE ?)")
            params.append(f"%{q}%")
            params.append(f"%{q}%")
            params.append(f"%{q}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM audit_log {where}",
            params,
        )
        total = count_row[0]["cnt"] if count_row else 0

        params_paginated = params + [limit, offset]
        rows = await db.execute_fetchall(
            f"""
            SELECT id, actor, action, target, metadata_json, created_at
            FROM audit_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params_paginated,
        )
    finally:
        await db.close()

    import json

    from redact import mask_audit_log_metadata, mask_audit_log_target

    masked_rows = []
    for row in rows:
        item = dict(row)
        item["target"] = mask_audit_log_target(item.get("action", ""), item.get("target"))
        raw_meta = item.pop("metadata_json", None)
        if raw_meta:
            try:
                parsed = json.loads(raw_meta)
            except json.JSONDecodeError:
                parsed = None
            item["metadata"] = mask_audit_log_metadata(item.get("action", ""), parsed)
        else:
            item["metadata"] = None
        masked_rows.append(item)

    return {"rows": masked_rows, "total": total}


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
    except Exception:
        checks.append({"name": "db checks", "passed": False, "detail": "db unavailable"})

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
    except Exception:
        checks.append({"name": "backup dir writable", "passed": False, "detail": "not writable or missing"})

    duration_ms = round(_time.time() * 1000 - start_ms)
    all_passed = all(c["passed"] for c in checks)
    await audit(request, "diagnostics.smoke", "pass" if all_passed else "fail")
    return {"ok": all_passed, "checks": checks, "duration_ms": duration_ms}


@router.post("/diagnostics/integrity")
async def check_integrity(request: Request):
    """Run database integrity checks (SQLite PRAGMA or PostgreSQL pg_catalog)."""
    db = await get_db()
    try:
        result = await run_integrity_check(db)
    finally:
        await db.close()

    await audit(request, "diagnostics.integrity", "pass" if result.ok else "fail")
    return result.as_dict()


@router.post("/diagnostics/corpus-drift")
async def check_security_corpus_drift(request: Request):
    """Regenerate the security architecture generated layer and report drift."""
    from security_architecture.corpus_drift import check_corpus_drift

    result = check_corpus_drift()
    await audit(request, "diagnostics.corpus_drift", "pass" if result["ok"] else "fail")
    return result


@router.get("/diagnostics/support-pack")
async def export_support_pack(
    request: Request,
    log_limit: int = Query(200, ge=1, le=500),
):
    """Export a redacted support pack (health + logs, no secrets) for operators."""
    from diagnostics.support_pack import build_support_pack

    payload = await build_support_pack(log_limit=log_limit)
    await audit(request, "diagnostics.support_pack", "export")
    stamp = payload.get("generated_at", "unknown").replace(":", "").replace("-", "")
    filename = f"briefr-support-pack-{stamp}.json"
    body = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Onboarding ─────────────────────────────────────────────────────────────


@router.get("/onboarding")
async def get_onboarding_checklist():
    """First-hour operator checklist with live completion state."""
    from onboarding.checklist import ONBOARDING_DISMISS_KEY, build_onboarding_checklist

    db = await get_db()
    try:
        checklist = await build_onboarding_checklist(db)
        dismissed_row = await db.execute_fetchall(
            "SELECT value FROM sync_state WHERE key = ?",
            (ONBOARDING_DISMISS_KEY,),
        )
        dismissed_at = dismissed_row[0]["value"] if dismissed_row else None
    finally:
        await db.close()

    return {
        **checklist,
        "dismissed": bool(dismissed_at),
        "dismissed_at": dismissed_at,
    }


@router.post("/onboarding/dismiss")
async def dismiss_onboarding_checklist(request: Request):
    """Hide the first-hour checklist until items change (operator ack)."""
    from db.timeutil import utcnow_str
    from onboarding.checklist import ONBOARDING_DISMISS_KEY

    stamp = utcnow_str()
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO sync_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ONBOARDING_DISMISS_KEY, stamp),
        )
        await db.commit()
    finally:
        await db.close()

    await audit(request, "onboarding.dismiss", stamp)
    return {"ok": True, "dismissed_at": stamp}


@router.get("/ratelimit")
async def get_ratelimit_dashboard():
    return {
        "enabled": settings.rate_limit_enabled,
        "buckets": get_bucket_stats(),
    }
