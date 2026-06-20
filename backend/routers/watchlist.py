"""CVE watchlist — pin / snooze (Beta V1.3 Theme 1).

Single-user for now (no user_id column). Built-in app login will add
per-user keying later (ROADMAP amendment 2026-06-11).

Endpoints:
- GET    /api/watchlist              — active entries (pins + unexpired snoozes)
- POST   /api/watchlist              — pin or snooze a CVE
- DELETE /api/watchlist/snoozes     — clear all snoozed rows (UI migration)
- DELETE /api/watchlist/{cve_id}     — remove from watchlist

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import (
    cve_exists,
    delete_all_snooze_entries,
    delete_watchlist_entry,
    get_db,
    list_watchlist_entries,
    upsert_watchlist_entry,
)

router = APIRouter()

_CVE_ID_RE = re.compile(r"^CVE-\d{4}-\d+$", re.IGNORECASE)
_VALID_STATES = frozenset({"pin", "snooze"})
_DEFAULT_SNOOZE_DAYS = 7


class WatchlistUpsertBody(BaseModel):
    cve_id: str = Field(..., min_length=9, max_length=32)
    state: str = Field(..., description="pin or snooze")
    snooze_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Days to hide when state=snooze (default 7)",
    )


def _validate_cve_id(value: str) -> str:
    key = value.strip().upper()
    if not _CVE_ID_RE.fullmatch(key):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")
    return key


def _snooze_until_iso(days: int) -> str:
    until = datetime.now(timezone.utc) + timedelta(days=days)
    # SQLite datetime() comparisons expect space-separated UTC, not ISO-8601 Z.
    return until.strftime("%Y-%m-%d %H:%M:%S")


@router.get("/api/watchlist")
async def get_watchlist():
    """List active watchlist entries (pins and unexpired snoozes)."""
    db = await get_db()
    try:
        data = await list_watchlist_entries(db)
    finally:
        await db.close()
    return {"data": data, "count": len(data)}


@router.post("/api/watchlist")
async def set_watchlist_entry(body: WatchlistUpsertBody):
    """Pin or snooze a CVE. Replaces any existing watchlist row for that CVE."""
    cve_key = _validate_cve_id(body.cve_id)
    state = body.state.strip().lower()
    if state not in _VALID_STATES:
        raise HTTPException(status_code=400, detail="state must be pin or snooze")

    snooze_until: str | None = None
    if state == "snooze":
        days = body.snooze_days if body.snooze_days is not None else _DEFAULT_SNOOZE_DAYS
        snooze_until = _snooze_until_iso(days)

    db = await get_db()
    try:
        if not await cve_exists(db, cve_key):
            raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")
        row = await upsert_watchlist_entry(db, cve_key, state, snooze_until)
        await db.commit()
    finally:
        await db.close()

    return {"data": row}


@router.delete("/api/watchlist/snoozes")
async def clear_all_snoozes():
    """Remove all snoozed CVEs from the watchlist (restore them to the default feed)."""
    db = await get_db()
    try:
        deleted = await delete_all_snooze_entries(db)
        if deleted:
            await db.commit()
    finally:
        await db.close()
    return {"ok": True, "deleted": deleted}


@router.delete("/api/watchlist/{cve_id}")
async def remove_watchlist_entry(cve_id: str):
    """Remove a CVE from the watchlist (unpin / unsnooze)."""
    cve_key = _validate_cve_id(cve_id)

    db = await get_db()
    try:
        deleted = await delete_watchlist_entry(db, cve_key)
        if deleted:
            await db.commit()
    finally:
        await db.close()

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Watchlist entry for {cve_key} not found")

    return {"ok": True, "cve_id": cve_key}
