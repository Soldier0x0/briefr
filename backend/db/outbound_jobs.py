"""Read helpers for Procrastinate job rows (admin list). Postgres only."""

from __future__ import annotations

import logging
from typing import Any

from db.config import is_postgres
from db.types import DbConnection

logger = logging.getLogger(__name__)

# pg-only: procrastinate_jobs exists only on Postgres
_LIST_PG = """
SELECT id, queue_name, task_name, status::text AS status, scheduled_at,
       attempts, priority, lock, queueing_lock
FROM procrastinate_jobs
ORDER BY id DESC
LIMIT $1
"""


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


async def list_recent_outbound_jobs(db: DbConnection, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return allowlisted fields from procrastinate_jobs (newest first)."""
    if not is_postgres():
        return []
    lim = max(1, min(int(limit), 200))
    try:
        rows = await db.execute_fetchall(_LIST_PG, (lim,))
    except Exception as exc:
        logger.warning("Failed to fetch recent outbound jobs: %s", exc)
        return []
    out: list[dict[str, Any]] = []
    for r in rows or []:
        scheduled = _row_get(r, "scheduled_at")
        out.append({
            "id": _row_get(r, "id"),
            "queue": _row_get(r, "queue_name"),
            "task": _row_get(r, "task_name"),
            "status": _row_get(r, "status"),
            "scheduled_at": scheduled.isoformat() if scheduled is not None else None,
            "attempts": _row_get(r, "attempts"),
            "priority": _row_get(r, "priority"),
            "lock": _row_get(r, "lock"),
            "queueing_lock": _row_get(r, "queueing_lock"),
        })
    return out
