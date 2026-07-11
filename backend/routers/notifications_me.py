"""In-app notification inbox for the signed-in user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_db
from db.user_notifications import (
    count_unread,
    dismiss_all_notifications,
    dismiss_notification,
    list_notifications,
    mark_scope_seen,
)
from dependencies import require_user

router = APIRouter(prefix="/api/me/notifications", tags=["me"])


class ScopeBody(BaseModel):
    scope: str = Field(pattern="^(analyst|operator)$")


def _require_scope(scope: str) -> str:
    if scope not in ("analyst", "operator"):
        raise HTTPException(status_code=422, detail="scope must be analyst or operator")
    return scope


@router.get("")
async def get_notifications(
    scope: str = Query("analyst"),
    limit: int = Query(30, ge=1, le=100),
    payload: dict = Depends(require_user),
):
    scope = _require_scope(scope)
    if scope == "operator" and payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Operator notifications require admin role")
    db = await get_db()
    try:
        user_id = int(payload["sub"])
        rows = await list_notifications(db, user_id=user_id, scope=scope, limit=limit)
        unread = await count_unread(db, user_id=user_id, scope=scope)
        return {"notifications": rows, "unread_count": unread}
    finally:
        await db.close()


@router.get("/unread-count")
async def get_unread_count(
    scope: str = Query("analyst"),
    payload: dict = Depends(require_user),
):
    scope = _require_scope(scope)
    if scope == "operator" and payload.get("role") != "admin":
        return {"unread_count": 0}
    db = await get_db()
    try:
        unread = await count_unread(db, user_id=int(payload["sub"]), scope=scope)
        return {"unread_count": unread}
    finally:
        await db.close()


@router.post("/seen")
async def mark_notifications_seen(
    body: ScopeBody,
    payload: dict = Depends(require_user),
):
    scope = _require_scope(body.scope)
    if scope == "operator" and payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Operator notifications require admin role")
    db = await get_db()
    try:
        updated = await mark_scope_seen(db, user_id=int(payload["sub"]), scope=scope)
        await db.commit()
        unread = await count_unread(db, user_id=int(payload["sub"]), scope=scope)
        return {"marked_seen": updated, "unread_count": unread}
    finally:
        await db.close()


@router.post("/{notification_id}/dismiss")
async def dismiss_one_notification(
    notification_id: int,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        ok = await dismiss_notification(
            db, user_id=int(payload["sub"]), notification_id=notification_id
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found")
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/dismiss-all")
async def dismiss_all(
    body: ScopeBody,
    payload: dict = Depends(require_user),
):
    scope = _require_scope(body.scope)
    if scope == "operator" and payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Operator notifications require admin role")
    db = await get_db()
    try:
        count = await dismiss_all_notifications(
            db, user_id=int(payload["sub"]), scope=scope
        )
        await db.commit()
        return {"dismissed": count}
    finally:
        await db.close()
