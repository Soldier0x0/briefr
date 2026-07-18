"""Semantic / hybrid CVE search API (Embeddings E3).

``GET /api/search/semantic`` — design §7.1.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from services.semantic_search import run_semantic_search

router = APIRouter()

_ALLOWED_MODES = frozenset({"hybrid", "keyword", "semantic"})


@router.get("/api/search/semantic")
async def search_semantic(
    q: str = Query(default="", max_length=500),
    mode: str = Query(default="hybrid"),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Hybrid (default), keyword, or semantic CVE search.

    Falls back to keyword when embeddings are disabled, the model is missing,
    or the vector index is cold. ``meta.method`` reports the path used.
    """
    mode_norm = (mode or "hybrid").strip().lower()
    if mode_norm not in _ALLOWED_MODES:
        raise HTTPException(
            status_code=400,
            detail="mode must be one of: hybrid, keyword, semantic",
        )

    db = await get_db()
    try:
        payload = await run_semantic_search(
            db, q, mode=mode_norm, limit=limit  # type: ignore[arg-type]
        )
    finally:
        await db.close()
    return payload
