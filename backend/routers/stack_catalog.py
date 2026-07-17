"""Software catalog autocomplete (Q3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_db
from db.software_catalog import suggest_software
from dependencies import require_user

router = APIRouter(prefix="/api/stack", tags=["stack"])


@router.get("/catalog/suggest")
async def catalog_suggest(
    q: str = Query("", min_length=0, max_length=128),
    limit: int = Query(20, ge=1, le=50),
    category: str | None = Query(None, max_length=32),
    payload: dict = Depends(require_user),
):
    """Typeahead for stack products. Requires ≥3 characters; shorter → empty list."""
    _ = payload
    query = (q or "").strip()
    if len(query) < 3:
        return {"ok": True, "query": query, "items": []}
    allowed = {
        "app", "library", "os", "web_server", "firewall", "database", "other"
    }
    cat = (category or "").strip().lower() or None
    if cat and cat not in allowed:
        raise HTTPException(400, f"Invalid category. Allowed: {sorted(allowed)}")
    db = await get_db()
    try:
        items = await suggest_software(db, query=query, limit=limit, category=cat)
    finally:
        await db.close()
    return {"ok": True, "query": query, "items": items}
