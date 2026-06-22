"""Shared route dependencies (V1.2 §5.2 router split).

Moved verbatim from main.py — admin-key gate and audit-log writer used by
the admin/refresh routes.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import asyncio
import logging
import os
import secrets
import signal
import sqlite3
import time

from fastapi import HTTPException, Request

from database import get_db, write_audit_log
from settings import settings

logger = logging.getLogger(__name__)


async def require_wallboard_token(request: Request) -> None:
    """When WALLBOARD_TOKEN is set, wallboard routes require a matching token."""
    if not settings.wallboard_token:
        return
    provided = (
        request.headers.get("X-BRIEFR-Wallboard-Token", "")
        or request.query_params.get("token", "")
    )
    if not secrets.compare_digest(provided, settings.wallboard_token):
        raise HTTPException(status_code=401, detail="Wallboard token required")


async def require_admin_key(request: Request) -> None:
    """When BRIEFR_ADMIN_API_KEY is set, admin routes require X-BRIEFR-Admin-Key."""
    if not settings.briefr_admin_api_key:
        return
    provided = request.headers.get("X-BRIEFR-Admin-Key", "")
    if not secrets.compare_digest(provided, settings.briefr_admin_api_key):
        from rate_limit import client_key as _client_key
        ip = _client_key(request)
        await audit(request, "auth.failure", ip)
        raise HTTPException(status_code=401, detail="Admin API key required")


async def require_user(request: Request) -> dict:
    """Built-in app login (decision 2026-06-11): require a valid `briefr_at`
    access-token cookie, and populate request.state.user_email/user_role for
    audit() to pick up."""
    from auth.tokens import decode_access_token

    token = request.cookies.get("briefr_at", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")
    request.state.user_email = payload.get("email", "")
    request.state.user_role = payload.get("role", "")
    return payload


async def require_admin(request: Request) -> dict | None:
    """Admin routes during the legacy-key soak window: accept EITHER a valid
    login session OR the legacy X-BRIEFR-Admin-Key header (when configured —
    matching require_admin_key's existing "unset key = open" dev convenience).
    Once ALLOW_LEGACY_ADMIN_KEY is flipped off, this collapses to require_user."""
    if settings.allow_legacy_admin_key:
        if not settings.briefr_admin_api_key:
            return None
        provided = request.headers.get("X-BRIEFR-Admin-Key", "")
        if provided and secrets.compare_digest(provided, settings.briefr_admin_api_key):
            return None
    return await require_user(request)


async def audit(request: Request, action: str, target: str = "") -> None:
    """Record an audited action. request.state.user_email is populated by
    require_user() once a session cookie is presented.

    Best-effort: write contention (e.g. bootstrap ingest holding the DB)
    must not turn an otherwise valid admin action into a 500.
    """
    actor = getattr(request.state, "user_email", None)
    try:
        db = await get_db()
        try:
            await write_audit_log(db, actor, action, target)
            await db.commit()
        finally:
            await db.close()
    except sqlite3.OperationalError as exc:
        logger.error("Audit log write failed (%s): %s", action, exc)


async def trigger_graceful_restart(drain: bool = False) -> None:
    """Shut the process down via SIGTERM instead of os._exit(0).

    uvicorn's installed signal handler runs the app's lifespan shutdown
    (stop_scheduler/close_pool/close_client in main.py) and finishes
    in-flight responses before the process exits. Requires the deploy unit
    to set Restart=on-failure or Restart=always (see deploy/briefr-backend.service)
    for the process to actually come back up.
    """
    if drain:
        from scheduler import any_ingest_lock_held

        deadline = time.time() + 120
        while any_ingest_lock_held() and time.time() < deadline:
            await asyncio.sleep(2)

    await asyncio.sleep(1)
    os.kill(os.getpid(), signal.SIGTERM)
