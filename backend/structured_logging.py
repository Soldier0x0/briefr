"""JSON structured logging with request IDs (V1.2 §5.5).

One JSON object per line on stderr (journald-friendly), every line carrying
a `request_id` field — surfaced in the V1.4 admin log viewer via an in-process
ring buffer. The request ID is set
per request by the `request_context` middleware in `main.py` (contextvar),
returned to clients in the `X-Request-ID` response header, and honoured when
a well-formed `X-Request-ID` arrives on the request.

`LOG_FORMAT=plain` restores the previous human-readable format for local dev.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import collections
import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from redact import scrub_log_text
from settings import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")
run_id_var: ContextVar[str] = ContextVar("run_id", default="")

PLAIN_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# LogRecord attributes that are bookkeeping, not user-supplied `extra` fields.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys()) | {
    "message",
    "asctime",
    "taskName",
}

# Extra field keys whose values must be redacted before storage/export.
_REDACT_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
_REDACT_EXACT = frozenset(
    {"PASSWORD", "SECRET", "TOKEN", "API_KEY", "APIKEY", "AUTHORIZATION"}
)

LOG_CATEGORIES = ("Application", "Scheduler", "Backup", "Webhooks", "Security")


def _should_redact_field(key: str) -> bool:
    key_upper = key.upper()
    return key_upper in _REDACT_EXACT or any(
        key_upper.endswith(suffix) for suffix in _REDACT_SUFFIXES
    )


def derive_log_category(logger_name: str) -> str:
    """Map a logger name to a V1.4 admin log category."""
    if not logger_name:
        return "Application"
    if logger_name == "scheduler" or logger_name.startswith("scheduler."):
        return "Scheduler"
    if logger_name.startswith("backup"):
        return "Backup"
    if logger_name.startswith("webhooks"):
        return "Webhooks"
    if logger_name in ("dependencies", "rate_limit"):
        return "Security"
    return "Application"


@asynccontextmanager
async def job_log_context(job_id: str):
    """Bind scheduler job_id/run_id for structured log entries in this task."""
    from jobs.context import outbound_context

    run_id = uuid.uuid4().hex[:12]
    token_job = job_id_var.set(job_id)
    token_run = run_id_var.set(run_id)
    try:
        with outbound_context(
            actor_type="job",
            job_id=job_id,
            run_id=run_id,
            trigger="scheduler",
        ):
            yield run_id
    finally:
        job_id_var.reset(token_job)
        run_id_var.reset(token_run)


def _record_to_entry(record: logging.LogRecord, *, include_category: bool) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        ),
        "level": record.levelname,
        "logger": record.name,
        "message": scrub_log_text(record.getMessage()),
        "request_id": getattr(record, "request_id", "") or request_id_var.get(),
    }
    job_id = getattr(record, "job_id", "") or job_id_var.get()
    run_id = getattr(record, "run_id", "") or run_id_var.get()
    if job_id:
        entry["job_id"] = job_id
    if run_id:
        entry["run_id"] = run_id
    if include_category:
        entry["category"] = derive_log_category(record.name)
    if record.exc_info and record.exc_info[0]:
        entry["error_type"] = record.exc_info[0].__name__
    for key, value in record.__dict__.items():
        if key not in _STANDARD_ATTRS and key not in entry:
            entry[key] = "[REDACTED]" if _should_redact_field(key) else value
    if record.exc_info:
        entry["exc_info"] = scrub_log_text(logging.Formatter().formatException(record.exc_info))
    if record.stack_info:
        entry["stack_info"] = scrub_log_text(logging.Formatter().formatStack(record.stack_info))
    return entry


class JsonFormatter(logging.Formatter):
    """One JSON object per log line; `extra={...}` kwargs become JSON keys."""

    def format(self, record: logging.LogRecord) -> str:
        entry = _record_to_entry(record, include_category=False)
        return json.dumps(entry, default=str, ensure_ascii=False)


_RING_BUFFER_SIZE = 500


class _RingBufferHandler(logging.Handler):
    """Fixed-size in-process log ring buffer for the admin log viewer."""

    def __init__(self, maxlen: int = _RING_BUFFER_SIZE):
        super().__init__()
        self._buf: collections.deque[dict[str, Any]] = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self._buf.appendleft(_record_to_entry(record, include_category=True))

    def get_logs(
        self,
        limit: int = 100,
        level: str | None = None,
        logger_name: str | None = None,
        request_id: str | None = None,
        job_id: str | None = None,
        run_id: str | None = None,
        category: str | None = None,
        search: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        needle = search.lower().strip() if search else None
        results = []
        for entry in self._buf:
            if level and entry["level"] != level.upper():
                continue
            if logger_name and entry.get("logger") != logger_name:
                continue
            if request_id and entry.get("request_id") != request_id:
                continue
            if job_id and entry.get("job_id") != job_id:
                continue
            if run_id and entry.get("run_id") != run_id:
                continue
            if category and entry.get("category") != category:
                continue
            # Entries carry ISO-8601 UTC timestamps, so lexicographic
            # comparison is chronological (Issue 30: server-side time range).
            if since and entry["ts"] < since:
                continue
            if until and entry["ts"] > until:
                continue
            if needle:
                haystack = " ".join(
                    str(entry.get(k) or "")
                    for k in ("message", "exc_info", "job_id", "run_id", "error_type")
                ).lower()
                if needle not in haystack:
                    continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results


_ring_handler = _RingBufferHandler()


def clear_log_buffer() -> None:
    """Empty the in-process ring buffer (test isolation)."""
    _ring_handler._buf.clear()


def ensure_ring_buffer_attached() -> None:
    """Re-attach the ring handler if Alembic fileConfig or another tool replaced root handlers."""
    root = logging.getLogger()
    if _ring_handler not in root.handlers:
        _ring_handler.setLevel(logging.INFO)
        root.addHandler(_ring_handler)


def get_log_buffer(
    limit: int = 100,
    level: str | None = None,
    logger_name: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    category: str | None = None,
    search: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    return _ring_handler.get_logs(
        limit=limit,
        level=level,
        logger_name=logger_name,
        request_id=request_id,
        job_id=job_id,
        run_id=run_id,
        category=category,
        search=search,
        since=since,
        until=until,
    )


def get_known_loggers() -> list[str]:
    """Return sorted list of distinct logger names seen in the ring buffer."""
    seen: set[str] = set()
    for entry in _ring_handler._buf:
        name = entry.get("logger", "")
        if name:
            seen.add(name)
    return sorted(seen)


def configure_logging() -> None:
    """Install the root handler and unify uvicorn's loggers under it.

    Called at `main.py` import time. Under the production launch path
    (`uvicorn main:app` CLI), uvicorn configures its own loggers before the
    app module is imported, so the rerouting below is what the journal sees.
    """
    handler = logging.StreamHandler(sys.stderr)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(PLAIN_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    # Route uvicorn's startup/error loggers through the root handler so the
    # journal output is uniformly structured.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # In JSON mode the briefr.access middleware line (which carries the
    # request_id, status and duration) replaces uvicorn's plain access log;
    # keeping both would double every per-request line in the journal.
    if settings.log_format == "json":
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.handlers = []
        access_logger.propagate = False

    ensure_ring_buffer_attached()
