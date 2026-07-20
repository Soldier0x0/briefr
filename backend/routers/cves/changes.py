"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from fastapi import APIRouter, HTTPException, Query

from database import get_db, get_recent_cve_changes

changes_router = APIRouter()


@changes_router.get("/api/changes")
async def cve_changes(
    limit: int = Query(default=50, ge=1, le=500),
    field: str | None = Query(default=None, description="Filter: cvss_score, epss_score, is_kev, has_poc"),
    since_hours: int | None = Query(default=24, ge=1, le=168),
):
    """Recent tracked field changes for analyst awareness."""
    allowed = {"cvss_score", "epss_score", "is_kev", "has_poc"}
    if field is not None and field not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"field must be one of: {', '.join(sorted(allowed))}",
        )

    db = await get_db()
    try:
        changes = await get_recent_cve_changes(
            db,
            limit=limit,
            field_name=field,
            since_hours=since_hours,
        )
    finally:
        await db.close()

    return {"data": changes, "count": len(changes)}
