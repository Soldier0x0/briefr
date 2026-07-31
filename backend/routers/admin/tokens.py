"""Admin dashboard API — API keys health, search tokens, notifications, typography.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request

from database import get_db
from db.search_tokens import create_search_token, list_search_tokens, revoke_search_token
from dependencies import audit
from monitoring.api_key_health import build_api_key_health_payload, run_api_key_health_checks
from monitoring.notifications import build_operator_notifications
from preferences.display_validate import DEFAULT_DISPLAY_PREFS, sanitize_typography_px, sanitize_ui_variant
from preferences.repo import (
    get_instance_typography_default,
    get_instance_ui_variant_default,
    set_instance_typography_default,
    set_instance_ui_variant_default,
)

from .router import router


@router.get("/api-keys/health")
async def get_api_keys_health():
    """Configured provider key suffixes and last health ping results."""
    db = await get_db()
    try:
        return await build_api_key_health_payload(db)
    finally:
        await db.close()


@router.post("/api-keys/health/run")
async def run_api_keys_health(request: Request):
    """Trigger an immediate API key health ping sweep."""
    db = await get_db()
    try:
        stats = await run_api_key_health_checks(db)
        payload = await build_api_key_health_payload(db)
    finally:
        await db.close()
    await audit(request, "api_keys.health.run", f"checked={stats.get('checked', 0)}")
    return {"ok": True, "stats": stats, **payload}


@router.get("/search-tokens")
async def list_search_api_tokens():
    """List search service tokens (hashed; never returns plaintext)."""
    db = await get_db()
    try:
        tokens = await list_search_tokens(db)
    finally:
        await db.close()
    return {"data": tokens}


@router.post("/search-tokens")
async def create_search_api_token(request: Request):
    """Create a search token — plaintext returned once in the response."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = str((body or {}).get("name") or "").strip() or "Search token"
    name = name[:120]
    created_by = getattr(request.state, "user_username", "") or ""
    db = await get_db()
    try:
        created = await create_search_token(db, name=name, created_by=created_by)
        await db.commit()
    finally:
        await db.close()
    await audit(
        request,
        "search_tokens.create",
        f"id={created['id']} prefix={created['token_prefix']}",
    )
    return created


@router.delete("/search-tokens/{token_id}")
async def revoke_search_api_token(token_id: int, request: Request):
    """Revoke a search token (soft revoke)."""
    if token_id < 1:
        raise HTTPException(status_code=400, detail="Invalid token id")
    db = await get_db()
    try:
        ok = await revoke_search_token(db, token_id)
        await db.commit()
    finally:
        await db.close()
    if not ok:
        raise HTTPException(status_code=404, detail="Token not found or already revoked")
    await audit(request, "search_tokens.revoke", f"id={token_id}")
    return {"ok": True, "id": token_id}


@router.get("/notifications")
async def get_operator_notifications(
    limit: int = Query(default=40, ge=1, le=100),
):
    """Durable operator notification feed (audit log + monitor alerts)."""
    db = await get_db()
    try:
        return await build_operator_notifications(db, limit=limit)
    finally:
        await db.close()


@router.get("/display/typography-default")
async def read_instance_typography_default():
    db = await get_db()
    try:
        typography = await get_instance_typography_default(db)
        return {"typography_px": typography}
    finally:
        await db.close()


@router.put("/display/typography-default")
async def write_instance_typography_default(body: dict, request: Request):
    typography_px = body.get("typography_px")
    if not isinstance(typography_px, dict):
        raise HTTPException(status_code=422, detail="typography_px object is required")
    try:
        sanitized = sanitize_typography_px(typography_px)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db = await get_db()
    try:
        saved = await set_instance_typography_default(db, sanitized)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "display.typography_default", "updated")
    return {"typography_px": saved}


@router.get("/display/ui-variant-default")
async def read_instance_ui_variant_default():
    db = await get_db()
    try:
        ui_variant = await get_instance_ui_variant_default(db)
        return {"ui_variant": ui_variant or DEFAULT_DISPLAY_PREFS["ui_variant"]}
    finally:
        await db.close()


@router.put("/display/ui-variant-default")
async def write_instance_ui_variant_default(body: dict, request: Request):
    if "ui_variant" not in body:
        raise HTTPException(status_code=422, detail="ui_variant is required")
    try:
        sanitized = sanitize_ui_variant(body.get("ui_variant"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db = await get_db()
    try:
        saved = await set_instance_ui_variant_default(db, sanitized)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "display.ui_variant_default", f"ui_variant={saved}")
    return {"ui_variant": saved}

