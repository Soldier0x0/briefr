"""Admin dashboard API — watchlist, hunt packs, IOC cache admin.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import urllib.parse

from fastapi import HTTPException, Query, Request

from database import delete_all_snooze_entries, get_db
from dependencies import audit
from destructive_actions import require_confirm

from .router import router

# ── Watchlist ──────────────────────────────────────────────────────────────


@router.get("/watchlist")
async def get_admin_watchlist(
    request: Request,
    state: str = Query("all"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if state not in ("pin", "snooze", "all"):
        raise HTTPException(400, "state must be 'pin', 'snooze', or 'all'")

    db = await get_db()
    try:
        if state == "all":
            rows = await db.execute_fetchall(
                """
                SELECT w.cve_id, w.state, w.snooze_until, w.created_at,
                       c.severity, c.epss_score, c.is_kev, c.cvss_score
                FROM watchlist w LEFT JOIN cves c ON w.cve_id = c.cve_id
                ORDER BY w.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT w.cve_id, w.state, w.snooze_until, w.created_at,
                       c.severity, c.epss_score, c.is_kev, c.cvss_score
                FROM watchlist w LEFT JOIN cves c ON w.cve_id = c.cve_id
                WHERE w.state = ?
                ORDER BY w.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (state, limit, offset),
            )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/watchlist/{cve_id}")
async def delete_watchlist_entry(cve_id: str, request: Request):
    db = await get_db()
    try:
        await db.execute("DELETE FROM watchlist WHERE cve_id = ?", (cve_id.upper(),))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "watchlist.remove", cve_id)
    return {"ok": True, "cve_id": cve_id}


@router.post("/watchlist/clear-snoozes")
async def clear_all_snoozes(request: Request, body: dict | None = None):
    confirm_text = (body or {}).get("confirm_text", "")
    try:
        require_confirm("watchlist.clear_snoozes", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    db = await get_db()
    try:
        rows_deleted = await delete_all_snooze_entries(db)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "watchlist.clear_snoozes", str(rows_deleted))
    return {"ok": True, "rows_deleted": rows_deleted}


# ── Hunt packs ─────────────────────────────────────────────────────────────


@router.get("/hunt-packs")
async def get_admin_hunt_packs(
    request: Request,
    technique_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    try:
        if technique_id:
            rows = await db.execute_fetchall(
                """
                SELECT id, technique_id, cve_id, title, priority, created_at, updated_at
                FROM hunt_packs
                WHERE technique_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (technique_id, limit, offset),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT id, technique_id, cve_id, title, priority, created_at, updated_at
                FROM hunt_packs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/hunt-packs/{pack_id}")
async def delete_hunt_pack(pack_id: int, request: Request):
    db = await get_db()
    try:
        await db.execute("DELETE FROM hunt_packs WHERE id = ?", (pack_id,))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "hunt_packs.delete", str(pack_id))
    return {"ok": True, "id": pack_id}


# ── IOC cache ──────────────────────────────────────────────────────────────


@router.get("/ioc-cache")
async def get_ioc_cache(
    request: Request,
    ioc_type: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    db = await get_db()
    try:
        params: list = []
        conditions = []
        if ioc_type:
            conditions.append("ioc_type = ?")
            params.append(ioc_type)
        if search:
            conditions.append("value LIKE ?")
            params.append(f"%{search}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        rows = await db.execute_fetchall(
            f"""
            SELECT value, ioc_type, cached_at,
                   CAST((julianday('now') - julianday(cached_at)) * 86400 AS INTEGER) AS age_seconds
            FROM ioc_cache
            {where}
            ORDER BY cached_at DESC
            LIMIT ?
            """,
            params,
        )
    finally:
        await db.close()

    return [dict(row) for row in rows]


@router.delete("/ioc-cache/{value:path}")
async def delete_ioc_cache_entry(value: str, request: Request):
    decoded = urllib.parse.unquote(value)
    db = await get_db()
    try:
        await db.execute("DELETE FROM ioc_cache WHERE value = ?", (decoded,))
        await db.commit()
    finally:
        await db.close()
    await audit(request, "ioc_cache.delete", decoded)
    return {"ok": True, "value": decoded}

