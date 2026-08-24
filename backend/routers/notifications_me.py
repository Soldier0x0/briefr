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
    mark_one_read,
    mark_scope_read,
    undo_dismiss_notification,
)
from dependencies import require_user

router = APIRouter(prefix="/api/me/notifications", tags=["me"])


class ScopeBody(BaseModel):
    scope: str = Field(pattern="^(analyst|operator|all)$")


def _require_scope(scope: str) -> str:
    if scope not in ("analyst", "operator", "all"):
        raise HTTPException(
            status_code=422, detail="scope must be analyst, operator, or all"
        )
    return scope


def _require_scope_access(scope: str, role: str) -> None:
    if scope in ("operator", "all") and role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Operator and all-scope notifications require admin role",
        )


@router.get("")
async def get_notifications(
    scope: str = Query("analyst"),
    view: str = Query("inbox"),
    limit: int = Query(30, ge=1, le=100),
    payload: dict = Depends(require_user),
):
    scope = _require_scope(scope)
    _require_scope_access(scope, payload.get("role", ""))
    db = await get_db()
    try:
        user_id = int(payload["sub"])
        try:
            rows = await list_notifications(
                db, user_id=user_id, scope=scope, limit=limit, view=view
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    if scope in ("operator", "all") and payload.get("role") != "admin":
        if scope == "operator":
            return {"unread_count": 0}
        raise HTTPException(
            status_code=403,
            detail="Operator and all-scope notifications require admin role",
        )
    db = await get_db()
    try:
        unread = await count_unread(db, user_id=int(payload["sub"]), scope=scope)
        return {"unread_count": unread}
    finally:
        await db.close()


@router.post("/read-all")
async def mark_all_read(
    body: ScopeBody,
    payload: dict = Depends(require_user),
):
    scope = _require_scope(body.scope)
    _require_scope_access(scope, payload.get("role", ""))
    db = await get_db()
    try:
        user_id = int(payload["sub"])
        updated = await mark_scope_read(db, user_id=user_id, scope=scope)
        await db.commit()
        unread = await count_unread(db, user_id=user_id, scope=scope)
        return {"marked_read": updated, "unread_count": unread}
    finally:
        await db.close()


@router.post("/seen")
async def mark_notifications_seen(
    body: ScopeBody,
    payload: dict = Depends(require_user),
):
    """Alias of read-all for backward compatibility."""
    return await mark_all_read(body, payload)


@router.post("/{notification_id}/read")
async def read_one_notification(
    notification_id: int,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        ok = await mark_one_read(
            db, user_id=int(payload["sub"]), notification_id=notification_id
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found")
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{notification_id}/restore")
async def restore_one_notification(
    notification_id: int,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        ok = await undo_dismiss_notification(
            db, user_id=int(payload["sub"]), notification_id=notification_id
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found")
        await db.commit()
        return {"ok": True}
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
    _require_scope_access(scope, payload.get("role", ""))
    db = await get_db()
    try:
        count = await dismiss_all_notifications(
            db, user_id=int(payload["sub"]), scope=scope
        )
        await db.commit()
        return {"dismissed": count}
    finally:
        await db.close()
