"""Wallboard read-only API (Beta V1.4 Theme 4).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import audit, require_admin, require_user, require_wallboard_token
from rate_limit import rate_limit_wallboard
from settings import settings
from wallboard.service import get_wallboard_payload
from wallboard.session import COOKIE_NAME, TTL_SECONDS, issue_session_token, wallboard_token_matches
from wallboard.token_store import (
    get_effective_wallboard_token,
    get_token_generation,
    issue_issuance_token,
    revoke_wallboard_tokens,
    rotation_status,
    rotate_wallboard_token,
)

public_router = APIRouter(dependencies=[Depends(rate_limit_wallboard)])

router = APIRouter(
    dependencies=[Depends(rate_limit_wallboard), Depends(require_wallboard_token)],
)


@router.get("/api/wallboard")
async def wallboard():
    """Aggregated intel posture payload for kiosk / TV displays."""
    return await get_wallboard_payload()


@public_router.get("/api/wallboard/config")
async def wallboard_config():
    """Public kiosk flags — no secrets."""
    status = await rotation_status()
    return {
        "auto_token_enabled": status["auto_token_enabled"],
        "manual_fallback": True,
        "rotation_interval_hours": status["rotation_interval_hours"],
        "issuance_token_minutes": status["issuance_token_minutes"],
        "poll_interval_seconds": 90,
    }


@public_router.post("/api/wallboard/session")
async def create_wallboard_session(request: Request, response: Response):
    """Exchange WALLBOARD_TOKEN or issuance JWT for a signed httpOnly session cookie."""
    effective = await get_effective_wallboard_token()
    if not effective:
        raise HTTPException(status_code=400, detail="Wallboard token not configured on server")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required") from None
    token = str(body.get("token", "")).strip()
    if not await wallboard_token_matches(token):
        raise HTTPException(status_code=401, detail="Invalid wallboard token")
    generation = await get_token_generation() if settings.wallboard_auto_token else 0
    session = issue_session_token(generation=generation)
    response.set_cookie(
        COOKIE_NAME,
        session,
        max_age=TTL_SECONDS,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    return {"ok": True}


@public_router.delete("/api/wallboard/session")
async def clear_wallboard_session(response: Response):
    """Clear wallboard session cookie."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@public_router.post("/api/wallboard/token")
async def issue_wallboard_kiosk_token(request: Request, response: Response, payload: dict = Depends(require_user)):
    """Authenticated analysts: obtain a short-lived wallboard token and session cookie."""
    if not settings.wallboard_auto_token:
        raise HTTPException(status_code=404, detail="Wallboard auto-token is disabled")
    effective = await get_effective_wallboard_token()
    if not effective:
        raise HTTPException(status_code=400, detail="Wallboard token not configured on server")

    generation = await get_token_generation()
    username = str(payload.get("username") or "analyst")
    token, expires_at = issue_issuance_token(username=username, generation=generation)
    session = issue_session_token(generation=generation)
    response.set_cookie(
        COOKIE_NAME,
        session,
        max_age=TTL_SECONDS,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    await audit(
        request,
        "wallboard.token_issued",
        target=username,
        metadata={"generation": generation},
    )
    return {
        "ok": True,
        "token": token,
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@public_router.post("/api/wallboard/revoke")
async def revoke_wallboard_sessions(request: Request, _payload: dict = Depends(require_admin)):
    """Admin: invalidate all wallboard issuance JWTs and session cookies."""
    result = await revoke_wallboard_tokens(actor=getattr(request.state, "user_username", None))
    await audit(request, "wallboard.revoke", metadata=result)
    return {"ok": True, **result}


@public_router.post("/api/wallboard/rotate")
async def rotate_wallboard_sessions(request: Request, _payload: dict = Depends(require_admin)):
    """Admin: rotate the active kiosk token and bump generation."""
    result = await rotate_wallboard_token(actor=getattr(request.state, "user_username", None))
    await audit(request, "wallboard.rotate", metadata=result)
    return {"ok": True, **result}
