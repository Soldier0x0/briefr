"""Read helpers for Procrastinate job rows (admin list). Postgres only."""

from __future__ import annotations

from typing import Any

from db.config import is_postgres
from db.types import DbConnection

_LIST_PG = """
SELECT id, queue_name, task_name, status::text AS status, scheduled_at,
       attempts, priority, lock, queueing_lock
FROM procrastinate_jobs
ORDER BY id DESC
LIMIT $1
"""


async def list_recent_outbound_jobs(db: DbConnection, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return allowlisted fields from procrastinate_jobs (newest first)."""
    if not is_postgres():
        return []
    lim = max(1, min(int(limit), 200))
    try:
        rows = await db.execute_fetchall(_LIST_PG, (lim,))
    except Exception:
        # Schema not applied yet or table missing — empty list, not 500.
        return []
    out: list[dict[str, Any]] = []
    for r in rows or []:
        # asyncpg Record or mapping
        get = r.get if hasattr(r, "get") else lambda k, d=None: r[k] if k in r.keys() else d
        scheduled = get("scheduled_at")
        out.append({
            "id": get("id"),
            "queue": get("queue_name"),
            "task": get("task_name"),
            "status": get("status"),
            "scheduled_at": scheduled.isoformat() if scheduled is not None else None,
            "attempts": get("attempts"),
            "priority": get("priority"),
            "lock": get("lock"),
            "queueing_lock": get("queueing_lock"),
        })
    return out
