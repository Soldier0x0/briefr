"""Morning brief endpoint (V1.3 Theme 1)."""

from fastapi import APIRouter, Query

from brief.service import build_morning_brief
from database import get_db

router = APIRouter()


@router.get("/api/brief")
async def morning_brief(
    stack: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated stack terms (same matching as /api/cves stack filter)",
    ),
    since_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=50),
    kev_due_days: int = Query(default=14, ge=1, le=90),
):
    """Server-computed analyst morning brief — read-path queries only."""
    db = await get_db()
    try:
        return await build_morning_brief(
            db,
            stack=stack,
            since_hours=since_hours,
            limit=limit,
            kev_due_days=kev_due_days,
        )
    finally:
        await db.close()
