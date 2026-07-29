"""Outbound API call event persistence (Q2). Failures must not break callers."""

from __future__ import annotations

import asyncio
<<<<<<< HEAD
import csv
import io
=======
>>>>>>> 7288a21f (feat(admin): Phase C efficiency audit, database metrics, optimizations)
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator
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
INSERT INTO api_usage (service, date_utc, month_utc, count, last_called_at)
VALUES ($1, $2, $3, 0, $4)
ON CONFLICT (service, date_utc) DO UPDATE
SET last_called_at = EXCLUDED.last_called_at
"""

_TOUCH_USAGE_SQLITE = """
INSERT INTO api_usage (service, date_utc, month_utc, count, last_called_at)
VALUES (?, ?, ?, 0, ?)
ON CONFLICT(service, date_utc) DO UPDATE
SET last_called_at = excluded.last_called_at
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
            if (
                seg.upper().startswith("CVE-")
                or seg.isdigit()
                or (len(seg) >= 32 and all(c.isalnum() or c == "-" for c in seg))
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


_event_buffer: list[dict[str, Any]] = []
_buffer_lock = asyncio.Lock()
_flush_task: asyncio.Task[None] | None = None


def api_call_events_batch_ms() -> int:
    try:
        return max(0, int(os.environ.get("API_CALL_EVENTS_BATCH_MS", "0")))
    except (TypeError, ValueError):
        return 0


def reset_api_call_event_buffer_for_tests() -> None:
    global _flush_task
    _event_buffer.clear()
    if _flush_task is not None and not _flush_task.done():
        _flush_task.cancel()
    _flush_task = None


async def flush_api_call_event_buffer() -> int:
<<<<<<< HEAD
    async with _buffer_lock:
        batch = list(_event_buffer)
        _event_buffer.clear()
=======
    batch = list(_event_buffer)
    _event_buffer.clear()
>>>>>>> 7288a21f (feat(admin): Phase C efficiency audit, database metrics, optimizations)
    if not batch:
        return 0
    from database import get_db

    db = await get_db()
    try:
        for item in batch:
            await insert_api_call_event(db, **item)
        await db.commit()
    finally:
        await db.close()
    return len(batch)


async def _schedule_buffered_flush(batch_ms: int) -> None:
    global _flush_task

    async def _run() -> None:
        await asyncio.sleep(batch_ms / 1000.0)
        await flush_api_call_event_buffer()

    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.create_task(_run())


async def queue_api_call_event(**fields: Any) -> bool:
    """Buffer an event when batching is enabled. Returns True if buffered."""
    batch_ms = api_call_events_batch_ms()
    if batch_ms <= 0:
        return False
<<<<<<< HEAD
    async with _buffer_lock:
        _event_buffer.append(fields)
=======
    _event_buffer.append(fields)
>>>>>>> 7288a21f (feat(admin): Phase C efficiency audit, database metrics, optimizations)
    await _schedule_buffered_flush(batch_ms)
    return True


async def touch_api_usage_last_called(
    db: DbConnection, *, service: str, date_utc: str, when: datetime | None = None
) -> None:
    when = when or datetime.now(timezone.utc)
    ts_val: Any = when if is_postgres() else when.replace(tzinfo=None).isoformat(sep=" ")
    month_utc = date_utc[:7] if len(date_utc) >= 7 else when.strftime("%Y-%m")
    sql = _TOUCH_USAGE_PG if is_postgres() else _TOUCH_USAGE_SQLITE
    try:
        await db.execute(sql, (service, date_utc, month_utc, ts_val))
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
        # Match insert_api_call_event SQLite ts format (space sep, no tz).
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retain_days)
        ).replace(tzinfo=None).isoformat(sep=" ")
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

    def _as_dict(row: Any, keys: list[str]) -> dict:
        try:
            return dict(row)
        except Exception:
            return {
                key: (row[i] if i < len(row) else None)
                for i, key in enumerate(keys)
            }

    sources = []
    for r in source_rows or []:
        d = _as_dict(r, ["source", "calls", "ok_calls", "last_called_at"])
        last = d.get("last_called_at")
        if hasattr(last, "isoformat"):
            d["last_called_at"] = last.isoformat()
        sources.append(d)
    actors = [
        _as_dict(r, ["actor_type", "calls"]) for r in (actor_rows or [])
    ]
    return {"hours": hours, "by_source": sources, "by_actor": actors}


_EVENT_SELECT_COLUMNS = """
    ts, source, method, host, path_template, status_code, latency_ms,
    actor_type, actor_id, job_id, run_id, request_id
"""

_CSV_HEADER = [
    "ts",
    "source",
    "method",
    "host",
    "path_template",
    "status_code",
    "latency_ms",
    "actor_type",
    "actor_id",
    "job_id",
    "run_id",
    "request_id",
]


def _clamp_hours(hours: int) -> int:
    return max(1, min(int(hours), 168))


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), 500))


def _clamp_offset(offset: int) -> int:
    return max(0, int(offset))


def _build_events_filters(
    *,
    hours: int,
    source: str | None,
    actor_type: str | None,
) -> tuple[str, list[Any]]:
    """Return WHERE clause (without leading WHERE) and bind params."""
    hours = _clamp_hours(hours)
    clauses: list[str] = []
    params: list[Any] = []

    if is_postgres():
        clauses.append(f"ts >= NOW() - (${len(params) + 1}::text || ' hours')::interval")
        params.append(str(hours))
        if source:
            clauses.append(f"source = ${len(params) + 1}")
            params.append(source)
        if actor_type:
            clauses.append(f"COALESCE(actor_type, 'unknown') = ${len(params) + 1}")
            params.append(actor_type)
    else:
        clauses.append("ts >= datetime('now', ?)")
        params.append(f"-{hours} hours")
        if source:
            clauses.append("source = ?")
            params.append(source)
        if actor_type:
            clauses.append("COALESCE(actor_type, 'unknown') = ?")
            params.append(actor_type)

    return " AND ".join(clauses), params


def _row_to_event_dict(row: Any) -> dict[str, Any]:
    try:
        data = dict(row)
    except Exception:
        keys = [
            "ts",
            "source",
            "method",
            "host",
            "path_template",
            "status_code",
            "latency_ms",
            "actor_type",
            "actor_id",
            "job_id",
            "run_id",
            "request_id",
        ]
        data = {key: (row[i] if i < len(row) else None) for i, key in enumerate(keys)}

    ts = data.get("ts")
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()

    return {
        "ts": ts,
        "source": data.get("source"),
        "method": data.get("method"),
        "host": data.get("host"),
        "path_template": data.get("path_template"),
        "status": data.get("status_code"),
        "latency_ms": data.get("latency_ms"),
        "actor_type": data.get("actor_type"),
        "actor_id": data.get("actor_id"),
        "job_id": data.get("job_id"),
        "run_id": data.get("run_id"),
        "request_id": data.get("request_id"),
    }


def _row_to_csv_dict(row: Any) -> dict[str, Any]:
    try:
        data = dict(row)
    except Exception:
        data = {key: None for key in _CSV_HEADER}
    ts = data.get("ts")
    if hasattr(ts, "isoformat"):
        data["ts"] = ts.isoformat()
    return {key: data.get(key) for key in _CSV_HEADER}


async def query_api_call_events(
    db: DbConnection,
    *,
    hours: int = 24,
    source: str | None = None,
    actor_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated audit trail for outbound API call events."""
    hours = _clamp_hours(hours)
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    where_sql, params = _build_events_filters(
        hours=hours,
        source=source,
        actor_type=actor_type,
    )

    if is_postgres():
        count_sql = f"SELECT COUNT(*)::int AS total FROM api_call_events WHERE {where_sql}"
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        )
        list_params = [*params, limit, offset]
    else:
        count_sql = f"SELECT COUNT(*) AS total FROM api_call_events WHERE {where_sql}"
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC LIMIT ? OFFSET ?"
        )
        list_params = [*params, limit, offset]

    count_rows = await db.execute_fetchall(count_sql, tuple(params))
    count_row = count_rows[0] if count_rows else None
    total = int((count_row["total"] if count_row else 0) or 0)
    rows = await db.execute_fetchall(list_sql, tuple(list_params))
    events = [_row_to_event_dict(row) for row in (rows or [])]

    actor_breakdown: list[dict[str, Any]] = []
    if source:
        breakdown_where, breakdown_params = _build_events_filters(
            hours=hours,
            source=source,
            actor_type=None,
        )
        breakdown_sql = (
            "SELECT COALESCE(actor_type, 'unknown') AS actor_type, COUNT(*) AS calls "
            f"FROM api_call_events WHERE {breakdown_where} GROUP BY 1 ORDER BY calls DESC"
        )
        breakdown_rows = await db.execute_fetchall(breakdown_sql, tuple(breakdown_params))
        for row in breakdown_rows or []:
            try:
                item = dict(row)
            except Exception:
                item = {"actor_type": row[0], "calls": row[1]}
            actor_breakdown.append(
                {
                    "actor_type": item.get("actor_type"),
                    "calls": int(item.get("calls") or 0),
                }
            )

    return {
        "hours": hours,
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "actor_breakdown": actor_breakdown,
    }


async def iter_api_call_events_csv(
    db: DbConnection,
    *,
    hours: int = 24,
    source: str | None = None,
    actor_type: str | None = None,
) -> AsyncIterator[str]:
    """Stream CSV rows for audit export (header included)."""
    hours = _clamp_hours(hours)
    where_sql, params = _build_events_filters(
        hours=hours,
        source=source,
        actor_type=actor_type,
    )

    if is_postgres():
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC"
        )
    else:
        list_sql = (
            f"SELECT {_EVENT_SELECT_COLUMNS} FROM api_call_events "
            f"WHERE {where_sql} ORDER BY ts DESC"
        )

    def _emit(rows: list[Any]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_HEADER, extrasaction="ignore")
        if not rows:
            return ""
        for row in rows:
            writer.writerow(_row_to_csv_dict(row))
        return buf.getvalue()

    header_buf = io.StringIO()
    csv.writer(header_buf).writerow(_CSV_HEADER)
    yield header_buf.getvalue()

    rows = await db.execute_fetchall(list_sql, tuple(params))
    chunk = _emit(rows or [])
    if chunk:
        yield chunk
