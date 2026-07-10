"""Detection backlog API (V1.5 Theme 3).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from detection.backlog import dismiss_backlog_item, list_backlog_items
from preferences.repo import get_effective_stack_terms

router = APIRouter()


def _item_to_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "cve_id": row["cve_id"],
        "technique_id": row["technique_id"],
        "technique_name": row.get("technique_name") or row["technique_id"],
        "reason": row["reason"],
        "priority": row["priority"],
        "status": row["status"],
        "stack_terms": row.get("stack_terms") or "",
        "created_at": row.get("created_at"),
        "dismissed_at": row.get("dismissed_at"),
        "severity": row.get("severity"),
        "cvss_score": row.get("cvss_score"),
        "epss_score": row.get("epss_score"),
        "is_kev": bool(row.get("is_kev")),
        "kev_due_date": row.get("kev_due_date"),
    }


@router.get("/api/detection-backlog")
async def get_detection_backlog(
    status: str = Query(default="open"),
    stack: str = Query(default=""),
):
    """List KEV-driven detection backlog items (open gaps on the operator stack)."""
    db = await get_db()
    try:
        stack_filter = stack.strip()
        if not stack_filter:
            stack_filter = await get_effective_stack_terms(db)
        items = await list_backlog_items(db, status=status, stack=stack_filter or None)
    finally:
        await db.close()

    return {
        "items": [_item_to_dict(row) for row in items],
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "stack_terms": stack_filter.split(",") if stack_filter else [],
            "count": len(items),
        },
    }


@router.post("/api/detection-backlog/{item_id}/dismiss")
async def post_dismiss_backlog_item(item_id: int):
    """Soft-dismiss a backlog item (does not reopen on later KEV sync)."""
    db = await get_db()
    try:
        updated = await dismiss_backlog_item(db, item_id)
        if not updated:
            raise HTTPException(404, "Backlog item not found")
        await db.commit()
    finally:
        await db.close()
    return {"item": _item_to_dict(updated)}
