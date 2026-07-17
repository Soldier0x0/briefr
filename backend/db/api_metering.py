"""Outbound API call event persistence (Q2). Failures must not break callers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from db.config import is_postgres
from db.types import DbConnection

logger = logging.getLogger(__name__)

_INSERT_PG = """
INSERT INTO api_call_events (
    ts, source, pacing_key, method, host, path_template,
    status_code, ok, latency_ms,
    actor_type, actor_id, job_id, run_id, queue_task, request_id, error_class
) VALUES (
    $1, $2, $3, $4, $5, $6,
    $7, $8, $9,
    $10, $11, $12, $13, $14, $15, $16
)
"""

_INSERT_SQLITE = """
INSERT INTO api_call_events (
    ts, source, pacing_key, method, host, path_template,
    status_code, ok, latency_ms,
    actor_type, actor_id, job_id, run_id, queue_task, request_id, error_class
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_TOUCH_USAGE_PG = """
UPDATE api_usage SET last_called_at = $1
WHERE service = $2 AND date_utc = $3
"""

_TOUCH_USAGE_SQLITE = """
UPDATE api_usage SET last_called_at = ?
WHERE service = ? AND date_utc = ?
"""


def path_template_from_url(url: str) -> tuple[str | None, str | None]:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or None
        path = parsed.path or "/"
        # Collapse UUID/CVE-looking segments for grouping
        parts = []
        for seg in path.split("/"):
            if not seg:
                continue
            if seg.upper().startswith("CVE-") or (
                len(seg) >= 32 and all(c.isalnum() or c == "-" for c in seg)
            ):
                parts.append("{id}")
            else:
                parts.append(seg)
        return host, "/" + "/".join(parts) if parts else "/"
    except Exception:
        return None, None


async def insert_api_call_event(
    db: DbConnection,
    *,
    source: str,
    method: str,
    url: str,
    status_code: int | None,
    ok: bool,
    latency_ms: int,
    actor_type: str | None = None,
    actor_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    queue_task: str | None = None,
    request_id: str | None = None,
    error_class: str | None = None,
    pacing_key: str | None = None,
    ts: datetime | None = None,
) -> None:
    host, path_template = path_template_from_url(url)
    when = ts or datetime.now(timezone.utc)
    ts_val: Any = when if is_postgres() else when.replace(tzinfo=None).isoformat(sep=" ")
    params = (
        ts_val,
        source,
        pacing_key or source,
        method.upper(),
        host,
        path_template,
        status_code,
        bool(ok),
        int(latency_ms),
        actor_type,
        actor_id,
        job_id,
        run_id,
        queue_task,
        request_id,
        error_class,
    )
    sql = _INSERT_PG if is_postgres() else _INSERT_SQLITE
    await db.execute(sql, params)


async def touch_api_usage_last_called(
    db: DbConnection, *, service: str, date_utc: str, when: datetime | None = None
) -> None:
    when = when or datetime.now(timezone.utc)
    ts_val: Any = when if is_postgres() else when.replace(tzinfo=None).isoformat(sep=" ")
    sql = _TOUCH_USAGE_PG if is_postgres() else _TOUCH_USAGE_SQLITE
    try:
        await db.execute(sql, (ts_val, service, date_utc))
    except Exception:
        # Column may be missing on old SQLite schemas — ignore.
        pass


async def purge_api_call_events(db: DbConnection, *, retain_days: int = 30) -> int:
    retain_days = max(1, int(retain_days))
    if is_postgres():
        cutoff = datetime.now(timezone.utc) - timedelta(days=retain_days)
        cur = await db.execute(
            "DELETE FROM api_call_events WHERE ts < $1",
            (cutoff,),
        )
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retain_days)).isoformat()
        cur = await db.execute(
            "DELETE FROM api_call_events WHERE ts < ?",
            (cutoff,),
        )
    return int(getattr(cur, "rowcount", 0) or 0)


async def metering_summary(db: DbConnection, *, hours: int = 24) -> dict[str, Any]:
    """Per-source + actor_type breakdown for admin UI."""
    hours = max(1, min(int(hours), 168))
    if is_postgres():
        source_rows = await db.execute_fetchall(
            """
            SELECT source,
                   COUNT(*)::int AS calls,
                   COUNT(*) FILTER (WHERE ok)::int AS ok_calls,
                   MAX(ts) AS last_called_at
            FROM api_call_events
            WHERE ts >= NOW() - ($1::text || ' hours')::interval
            GROUP BY source
            ORDER BY calls DESC
            LIMIT 50
            """,
            (str(hours),),
        )
        actor_rows = await db.execute_fetchall(
            """
            SELECT COALESCE(actor_type, 'unknown') AS actor_type,
                   COUNT(*)::int AS calls
            FROM api_call_events
            WHERE ts >= NOW() - ($1::text || ' hours')::interval
            GROUP BY 1
            ORDER BY calls DESC
            """,
            (str(hours),),
        )
    else:
        source_rows = await db.execute_fetchall(
            """
            SELECT source, COUNT(*) AS calls,
                   SUM(CASE WHEN ok THEN 1 ELSE 0 END) AS ok_calls,
                   MAX(ts) AS last_called_at
            FROM api_call_events
            WHERE ts >= datetime('now', ?)
            GROUP BY source
            ORDER BY calls DESC
            LIMIT 50
            """,
            (f"-{hours} hours",),
        )
        actor_rows = await db.execute_fetchall(
            """
            SELECT COALESCE(actor_type, 'unknown') AS actor_type, COUNT(*) AS calls
            FROM api_call_events
            WHERE ts >= datetime('now', ?)
            GROUP BY 1
            ORDER BY calls DESC
            """,
            (f"-{hours} hours",),
        )

    def _as_dict(row: Any) -> dict:
        try:
            return dict(row)
        except Exception:
            return {
                "source": row[0] if len(row) > 0 else None,
                "calls": row[1] if len(row) > 1 else 0,
            }

    sources = []
    for r in source_rows or []:
        d = _as_dict(r)
        last = d.get("last_called_at")
        if hasattr(last, "isoformat"):
            d["last_called_at"] = last.isoformat()
        sources.append(d)
    actors = [_as_dict(r) for r in (actor_rows or [])]
    return {"hours": hours, "by_source": sources, "by_actor": actors}
