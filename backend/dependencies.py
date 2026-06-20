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


async def audit(request: Request, action: str, target: str = "") -> None:
    """Record an audited action. Actor stays empty until built-in app login
    ships (decision 2026-06-11); request.state.user_email is the future hook.

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
