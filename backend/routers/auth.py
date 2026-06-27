"""Built-in app login (decision 2026-06-11): /api/auth/login, /logout,
/refresh, /me. Replaces the shared X-BRIEFR-Admin-Key during the dual-auth
soak window (see settings.allow_legacy_admin_key / dependencies.require_admin).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from auth.passwords import DUMMY_HASH, PASSWORD_MAX_LEN, validate_password_strength, verify_password
from auth.repo import (
    count_users,
    create_session,
    create_user,
    get_session_by_token,
    get_user_by_id,
    list_active_sessions,
    revoke_all_sessions_for_user,
    revoke_session,
    rotate_session,
    update_last_login,
)
from auth.repo import get_user_by_username as _get_user_by_username
from auth.tokens import create_access_token, generate_refresh_token
from auth.usernames import validate_username
from database import get_db
from dependencies import audit, require_user
from pydantic import BaseModel, Field, field_validator
from rate_limit import check_login_username_rate_limit, rate_limit_auth_refresh, rate_limit_login
from settings import settings

router = APIRouter(prefix="/api/auth")

ACCESS_COOKIE = "briefr_at"
REFRESH_COOKIE = "briefr_rt"
_AUTH_FAILURE = "Invalid username or password"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LEN)
    remember_me: bool = False

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class SetupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LEN)

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return validate_username(value)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


def _refresh_expiry() -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return expires.strftime("%Y-%m-%d %H:%M:%S")


def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        token,
        max_age=settings.jwt_access_token_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


def _set_refresh_cookie(response: Response, token: str, remember_me: bool) -> None:
    max_age = settings.refresh_token_days * 86400 if remember_me else None
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=max_age,
        path="/api/auth",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response, _rl=Depends(rate_limit_login)
):
    try:
        username = validate_username(body.username)
    except ValueError:
        verify_password(body.password, DUMMY_HASH)
        raise HTTPException(status_code=401, detail=_AUTH_FAILURE)

    check_login_username_rate_limit(username)

    db = await get_db()
    try:
        user = await _get_user_by_username(db, username)
        if user is None or not user["is_active"]:
            verify_password(body.password, DUMMY_HASH)
            await audit(request, "auth.login_failed", username)
            raise HTTPException(status_code=401, detail=_AUTH_FAILURE)

        if not verify_password(body.password, user["password_hash"]):
            await audit(request, "auth.login_failed", user["username"])
            raise HTTPException(status_code=401, detail=_AUTH_FAILURE)

        refresh_token = generate_refresh_token()
        await create_session(
            db,
            user["id"],
            refresh_token,
            _refresh_expiry(),
            user_agent=request.headers.get("user-agent", "")[:255],
            ip=request.client.host if request.client else "",
            remember_me=body.remember_me,
        )
        await update_last_login(db, user["id"])
        await db.commit()
    finally:
        await db.close()

    access_token = create_access_token(user["id"], user["username"], user["role"])
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token, body.remember_me)

    request.state.user_username = user["username"]
    await audit(request, "auth.login", user["username"])

    return {"username": user["username"], "role": user["role"]}


@router.post("/logout")
async def logout(request: Request, response: Response):
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    if refresh_token:
        db = await get_db()
        try:
            session = await get_session_by_token(db, refresh_token)
            if session is not None and session["revoked_at"] is None:
                await revoke_session(db, session["id"])
                await db.commit()
        finally:
            await db.close()

    _clear_auth_cookies(response)
    return {"status": "ok"}


@router.post("/refresh")
async def refresh(
    request: Request, response: Response, _rl=Depends(rate_limit_auth_refresh)
):
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = await get_db()
    try:
        session = await get_session_by_token(db, refresh_token)
        if session is None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if session["revoked_at"] is not None:
            # Replay of an already-rotated (or logged-out) token: treat as
            # theft and kill every session for this user.
            await revoke_all_sessions_for_user(db, session["user_id"])
            await db.commit()
            await audit(request, "auth.token_reuse_detected", str(session["user_id"]))
            error_response = JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            _clear_auth_cookies(error_response)
            return error_response

        user = await get_user_by_id(db, session["user_id"])
        if user is None or not user["is_active"]:
            raise HTTPException(status_code=401, detail="Not authenticated")

        new_refresh_token = generate_refresh_token()
        rotated = await rotate_session(db, session, new_refresh_token, _refresh_expiry())
        await db.commit()
    finally:
        await db.close()

    access_token = create_access_token(user["id"], user["username"], user["role"])
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, new_refresh_token, remember_me=bool(rotated["remember_me"]))

    return {"username": user["username"], "role": user["role"]}


@router.get("/me")
async def me(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        user = await get_user_by_id(db, int(payload["sub"]))
    finally:
        await db.close()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "username": user["username"],
        "role": user["role"],
        "last_login_at": user["last_login_at"],
    }


# ── First-run setup (decision 2026-06-22) ──────────────────────────────────
# Bootstraps the first admin account so a fresh install doesn't require
# running scripts/create_user.py by hand. Permanently disabled the instant
# any user row exists — this is not self-service signup, it only ever fires
# once. scripts/create_user.py remains the only way to add a second account
# or reset a password afterward.


@router.get("/setup-required")
async def setup_required():
    db = await get_db()
    try:
        required = await count_users(db) == 0
    finally:
        await db.close()
    return {"required": required}


@router.post("/setup")
async def setup(
    body: SetupRequest, request: Request, response: Response, _rl=Depends(rate_limit_login)
):
    db = await get_db()
    try:
        if await count_users(db) > 0:
            raise HTTPException(status_code=409, detail="Setup already completed")

        user = await create_user(db, body.username, body.password, role="admin")

        refresh_token = generate_refresh_token()
        await create_session(
            db,
            user["id"],
            refresh_token,
            _refresh_expiry(),
            user_agent=request.headers.get("user-agent", "")[:255],
            ip=request.client.host if request.client else "",
            remember_me=False,
        )
        await update_last_login(db, user["id"])
        await db.commit()
    finally:
        await db.close()

    access_token = create_access_token(user["id"], user["username"], user["role"])
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token, remember_me=False)

    request.state.user_username = user["username"]
    await audit(request, "auth.setup_completed", user["username"])

    return {"username": user["username"], "role": user["role"]}


@router.get("/sessions")
async def get_sessions(request: Request, payload: dict = Depends(require_user)):
    user_id = int(payload["sub"])
    current_rt = request.cookies.get(REFRESH_COOKIE, "")
    db = await get_db()
    try:
        sessions = await list_active_sessions(db, user_id)
        user = await get_user_by_id(db, user_id)
    finally:
        await db.close()

    from auth.tokens import hash_refresh_token as _hash_rt
    current_hash = _hash_rt(current_rt) if current_rt else None

    result = []
    for s in sessions:
        result.append({
            **s,
            "is_current": s["refresh_token_hash"] == current_hash,
            "remember_me": bool(s["remember_me"]),
        })

    return {
        "user": {
            "username": user["username"] if user else payload.get("sub"),
            "role": user["role"] if user else payload.get("role"),
            "last_login_at": user["last_login_at"] if user else None,
        },
        "sessions": result,
    }


@router.delete("/sessions/{session_id}")
async def revoke_session_endpoint(
    session_id: int, request: Request, payload: dict = Depends(require_user)
):
    user_id = int(payload["sub"])
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id, user_id FROM sessions WHERE id = ? AND revoked_at IS NULL",
            (session_id,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")
        if rows[0]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not your session")
        await revoke_session(db, session_id)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "auth.session_revoked", str(session_id))
    return {"status": "revoked"}
