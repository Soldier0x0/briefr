"""Admin dashboard API — webhook delivery logs and health.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from typing import Any

from fastapi import Query, Request

from database import get_db

from .router import router

@router.get("/webhooks/log")
async def get_webhooks_log(
    request: Request,
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from database import _webhook_alert_types

    db = await get_db()
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if event_type:
            types = _webhook_alert_types(event_type)
            placeholders = ", ".join("?" for _ in types)
            conditions.append(f"alert_type IN ({placeholders})")
            params.extend(types)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM webhook_alert_log {where}", params
        )
        total = count_row[0]["cnt"] if count_row else 0

        rows = await db.execute_fetchall(
            f"""
            SELECT alert_type, target, alerted_at
            FROM webhook_alert_log
            {where}
            ORDER BY alerted_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
    finally:
        await db.close()

    return {
        "rows": [dict(r) for r in rows],
        "total": total,
    }


@router.get("/webhooks/delivery-log")
async def get_webhooks_delivery_log(
    request: Request,
    destination_id: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from redact import mask_webhook_delivery_error

    db = await get_db()
    try:
        from database import list_webhook_delivery_log

        rows, total = await list_webhook_delivery_log(
            db,
            destination_id=destination_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
    finally:
        await db.close()

    payload_rows = []
    for row in rows:
        item = dict(row)
        if item.get("error") is not None:
            item["error"] = mask_webhook_delivery_error(item["error"])
        payload_rows.append(item)

    return {
        "rows": payload_rows,
        "total": total,
    }


@router.get("/webhooks/health")
async def get_webhooks_health(request: Request):
    """Per-destination delivery health from webhook_delivery_log."""
    from database import build_webhook_destination_health, list_webhook_destinations

    db = await get_db()
    try:
        destinations = await list_webhook_destinations(db)
        health_rows = await build_webhook_destination_health(db)
    finally:
        await db.close()

    health_by_id = {row["destination_id"]: row for row in health_rows}
    merged = []
    for dest in destinations:
        h = health_by_id.get(dest["id"])
        merged.append({
            "id": dest["id"],
            "kind": dest["kind"],
            "label": dest.get("label"),
            "enabled": bool(dest.get("enabled")),
            "source": dest.get("source"),
            "last_status": h.get("last_status") if h else None,
            "last_event_type": h.get("last_event_type") if h else None,
            "last_attempt_at": h.get("last_attempt_at") if h else None,
            "last_success_at": h.get("last_success_at") if h else None,
            "last_failure_at": h.get("last_failure_at") if h else None,
            "last_error": h.get("last_error") if h else None,
            "ok_24h": h.get("ok_24h", 0) if h else 0,
            "failed_24h": h.get("failed_24h", 0) if h else 0,
        })

    return {"destinations": merged}
