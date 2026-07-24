"""Wallboard read-only API (Beta V1.4 Theme 4).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import require_wallboard_token
from rate_limit import rate_limit_wallboard
from settings import settings
from wallboard.service import get_wallboard_payload
from wallboard.session import COOKIE_NAME, TTL_SECONDS, issue_session_token, wallboard_token_matches

public_router = APIRouter(dependencies=[Depends(rate_limit_wallboard)])

router = APIRouter(
    dependencies=[Depends(rate_limit_wallboard), Depends(require_wallboard_token)],
)


@router.get("/api/wallboard")
async def wallboard():
    """Aggregated intel posture payload for kiosk / TV displays."""
    return await get_wallboard_payload()


@public_router.post("/api/wallboard/session")
async def create_wallboard_session(request: Request, response: Response):
    """Exchange WALLBOARD_TOKEN for a signed httpOnly session cookie."""
    if not settings.wallboard_token:
        raise HTTPException(status_code=400, detail="Wallboard token not configured on server")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required")
    token = str(body.get("token", "")).strip()
    if not wallboard_token_matches(token):
        raise HTTPException(status_code=401, detail="Invalid wallboard token")
    session = issue_session_token()
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
