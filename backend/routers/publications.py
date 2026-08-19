"""Publication list and detail APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from db.publications import get_publication, get_publications_for_cve, list_publications
from routers._validators import require_cve_id

router = APIRouter()


@router.get("/api/publications")
async def publications_list(
    cve_id: str | None = Query(default=None, description="Filter by linked CVE"),
    source_key: str | None = Query(default=None),
    document_kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None, ge=1),
    mark_headlines: bool = Query(default=True, description="Set also_in_headlines when URL is in RSS snapshot"),
):
    db = await get_db()
    try:
        data, next_cursor = await list_publications(
            db,
            cve_id=require_cve_id(cve_id) if cve_id else None,
            source_key=source_key,
            document_kind=document_kind,
            limit=limit,
            cursor=cursor,
            mark_headlines=mark_headlines,
        )
    finally:
        await db.close()
    return {"data": data, "meta": {"next_cursor": next_cursor}}


@router.get("/api/publications/{publication_id}")
async def publication_detail(publication_id: int):
    if publication_id < 1:
        raise HTTPException(status_code=400, detail="Invalid publication id")
    db = await get_db()
    try:
        row = await get_publication(db, publication_id)
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Publication not found")
    return {"data": row}


@router.get("/api/cves/{cve_id}/publications")
async def cve_publications(
    cve_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    cve_key = require_cve_id(cve_id)
    db = await get_db()
    try:
        data = await get_publications_for_cve(db, cve_key, limit=limit)
    finally:
        await db.close()
    return {"data": data, "cve_id": cve_key}
