"""Correlation cluster list (Phase 4)."""

from fastapi import APIRouter, Query

from correlation.clusters import list_correlation_clusters
from database import get_db

router = APIRouter()


@router.get("/api/correlation/clusters")
async def correlation_clusters(
    stack: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated stack terms (same matching as /api/cves stack filter)",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    include_stale: bool = Query(
        default=False,
        description="Include campaigns with lifecycle=stale",
    ),
):
    """Precomputed campaign clusters for brief/feed consumers."""
    db = await get_db()
    try:
        return await list_correlation_clusters(
            db,
            stack=stack,
            limit=limit,
            include_stale=include_stale,
        )
    finally:
        await db.close()
