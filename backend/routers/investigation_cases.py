"""Saved investigation workspace cases."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from database import get_db
from dependencies import require_user
from investigations.cases import (
    create_case,
    delete_case,
    get_case,
    list_cases,
    update_case,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CaseSnapshotBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=256)
    snapshot: dict


class CaseUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=256)
    snapshot: dict


@router.get("/api/investigations/cases")
async def investigations_cases_list(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        return {"cases": await list_cases(db, int(payload["sub"]))}
    finally:
        await db.close()


@router.post("/api/investigations/cases")
async def investigations_cases_create(
    body: CaseSnapshotBody,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        try:
            case_id = await create_case(
                db,
                int(payload["sub"]),
                body.snapshot,
                title=body.title,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        case = await get_case(db, int(payload["sub"]), case_id)
        return case
    finally:
        await db.close()


@router.get("/api/investigations/cases/{case_id}")
async def investigations_cases_get(
    case_id: str,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        case = await get_case(db, int(payload["sub"]), case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        return case
    finally:
        await db.close()


@router.put("/api/investigations/cases/{case_id}")
async def investigations_cases_update(
    case_id: str,
    body: CaseUpdateBody,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        try:
            updated = await update_case(
                db,
                int(payload["sub"]),
                case_id,
                body.snapshot,
                title=body.title,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="case not found")
        case = await get_case(db, int(payload["sub"]), case_id)
        return case
    finally:
        await db.close()


@router.delete("/api/investigations/cases/{case_id}")
async def investigations_cases_delete(
    case_id: str,
    payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        deleted = await delete_case(db, int(payload["sub"]), case_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="case not found")
        return {"ok": True}
    finally:
        await db.close()
