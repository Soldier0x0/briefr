"""Shared route dependencies (V1.2 §5.2 router split).

Session/role gates and the audit-log writer used by the admin/refresh
routes.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import asyncio
import hashlib
import logging
import os
import secrets
import signal
import time

from fastapi import HTTPException, Request

from database import get_db, write_audit_log
from settings import settings

logger = logging.getLogger(__name__)


async def require_wallboard_token(request: Request) -> None:
    """When WALLBOARD_TOKEN is set, wallboard routes require a matching token.
    Header-only (Sprint A7): `?token=` was dropped because query strings leak
    into access logs and browser history."""
    if not settings.wallboard_token:
        return
    provided = request.headers.get("X-BRIEFR-Wallboard-Token", "")
    # Compare SHA-256 digests: compare_digest short-circuits on unequal
    # lengths, which would leak the configured token's length via timing.
    if not secrets.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(settings.wallboard_token.encode()).digest(),
    ):
        raise HTTPException(status_code=401, detail="Wallboard token required")


async def require_user(request: Request) -> dict:
    """Built-in app login (decision 2026-06-11): require a valid `briefr_at`
    access-token cookie, and populate request.state.user_username/user_role for
    audit() to pick up."""
    from auth.tokens import decode_access_token

    token = request.cookies.get("briefr_at", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not payload.get("username"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    request.state.user_username = payload["username"]
    request.state.user_role = payload.get("role", "")
    return payload


async def require_admin(request: Request) -> dict:
    """Admin routes require a valid login session with the admin role.
    The legacy X-BRIEFR-Admin-Key path was removed (Sprint A0) — it failed
    open when the key was unset. Role is re-read from the users table so
    demotions take effect without waiting for JWT expiry."""
    payload = await require_user(request)
    try:
        user_id = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from auth.repo import get_user_by_id

    db = await get_db()
    try:
        user = await get_user_by_id(db, user_id)
    finally:
        await db.close()

    if not user or not user.get("is_active", 1):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    request.state.user_role = user["role"]
    return {**payload, "role": user["role"]}


async def audit(request: Request, action: str, target: str = "") -> None:
    """Record an audited action. request.state.user_username is populated by
    require_user() once a session cookie is presented.

    Best-effort: write contention (e.g. bootstrap ingest holding the DB)
    must not turn an otherwise valid admin action into a 500.
    """
    actor = getattr(request.state, "user_username", None)
    try:
        db = await get_db()
        try:
            await write_audit_log(db, actor, action, target)
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:
        # Broad on purpose: ``DatabaseError`` covers both dialects; audit-write
        # failure must never 500 the admin action it records.
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
