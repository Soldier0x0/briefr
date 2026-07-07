"""Per-user stack profile — server-backed replacement for briefr_stack localStorage.

Wave 2 PR 3: terms + optional asset profile JSON keyed by user_id.
Frontend migration to this API lands in Wave 2 PR 4.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import get_db
from dependencies import require_user
from preferences.repo import get_user_stack, upsert_user_stack
from preferences.validate import sanitize_profile, validate_stack_terms

router = APIRouter(prefix="/api/me", tags=["me"])


class StackBody(BaseModel):
    stack_terms: str = Field(default="", max_length=4096)
    profile: dict | None = None


@router.get("/stack")
async def read_stack(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        return await get_user_stack(db, int(payload["sub"]))
    finally:
        await db.close()


@router.put("/stack")
async def write_stack(body: StackBody, payload: dict = Depends(require_user)):
    try:
        stack_terms = validate_stack_terms(body.stack_terms)
        profile = sanitize_profile(body.profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db = await get_db()
    try:
        result = await upsert_user_stack(db, int(payload["sub"]), stack_terms, profile)
        await db.commit()
        return result
    finally:
        await db.close()
