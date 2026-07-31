"""Per-user stack profile — server-backed replacement for briefr_stack localStorage.

Wave 2 PR 3: terms + optional asset profile JSON keyed by user_id.
Frontend migration to this API lands in Wave 2 PR 4.

Wave 2 PR 5: display preferences + timezone via GET/PATCH /api/me/preferences.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import get_db
from dependencies import require_user
from preferences.repo import get_user_preferences, get_user_stack, patch_user_preferences, upsert_user_stack
from preferences.validate import sanitize_profile, validate_stack_terms

router = APIRouter(prefix="/api/me", tags=["me"])


class StackBody(BaseModel):
    stack_terms: str = Field(default="", max_length=4096)
    profile: dict | None = None


class PreferencesPatch(BaseModel):
    font_scale: str | None = None
    density: str | None = None
    show_technical_ids: bool | None = None
    poll_interval_seconds: int | None = None
    utc_time: bool | None = None
    reduce_motion: bool | None = None
    notification_sound: bool | None = None
    ui_variant: str | None = None
    typography_px: dict[str, int] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    remember_profile_on_server: bool | None = None


@router.get("/stack")
async def read_stack(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        return await get_user_stack(db, int(payload["sub"]))
    finally:
        await db.close()


@router.put("/stack")
async def write_stack(body: StackBody, payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        stack_terms = validate_stack_terms(body.stack_terms)
        update_profile = "profile" in body.model_fields_set
        profile = sanitize_profile(body.profile) if update_profile else None
        result = await upsert_user_stack(
            db,
            int(payload["sub"]),
            stack_terms,
            profile,
            update_profile=update_profile,
        )
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await db.close()


@router.get("/preferences")
async def read_preferences(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        return await get_user_preferences(db, int(payload["sub"]))
    finally:
        await db.close()


@router.patch("/preferences")
async def write_preferences(body: PreferencesPatch, payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        patch = body.model_dump(exclude_unset=True)
        if not patch:
            raise HTTPException(status_code=422, detail="at least one preference field is required")
        result = await patch_user_preferences(db, int(payload["sub"]), patch)
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await db.close()
