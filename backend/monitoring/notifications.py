"""Operator notification center — durable events from audit log and monitors."""

from __future__ import annotations

from typing import Any

from monitoring.api_key_health import build_api_key_health_payload


async def build_operator_notifications(db, *, limit: int = 40) -> dict[str, Any]:
    """Aggregate recent operator-visible events (Issue 8 tail)."""
    limit = max(1, min(int(limit), 100))
    audit_rows = await db.execute_fetchall(
        """
        SELECT id, actor, action, target, created_at
        FROM audit_log
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (limit,),
    )

    job_rows = await db.execute_fetchall(
        """
        SELECT key, value
        FROM sync_state
        WHERE key LIKE 'job_last_run:%'
        ORDER BY key ASC
        """
    )

    job_errors: list[dict[str, Any]] = []
    for row in job_rows:
        key = row["key"] or ""
        job_id = key.split("job_last_run:", 1)[-1]
        raw = row["value"] or ""
        if not raw or '"had_error": true' not in raw.lower():
            continue
        job_errors.append(
            {
                "type": "job_error",
                "job_id": job_id,
                "summary": raw[:240],
                "created_at": None,
            }
        )

    health = await build_api_key_health_payload(db)
    key_alerts = [
        {
            "type": "api_key_unhealthy",
            "provider": row["provider"],
            "summary": row.get("error") or "Health ping failed",
            "created_at": row.get("last_checked_at"),
        }
        for row in health.get("providers", [])
        if row.get("configured") and row.get("healthy") is False
    ]

    events: list[dict[str, Any]] = []
    for row in audit_rows:
        events.append(
            {
                "type": "audit",
                "id": row["id"],
                "actor": row["actor"],
                "action": row["action"],
                "summary": row["target"],
                "created_at": row["created_at"],
            }
        )

    events.extend(key_alerts)
    events.extend(job_errors[:10])

    return {
        "events": events[:limit],
        "counts": {
            "audit": len(audit_rows),
            "api_key_alerts": len(key_alerts),
            "job_errors": len(job_errors),
        },
        "api_key_health_checked_at": health.get("checked_at"),
    }
