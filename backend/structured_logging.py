"""JSON structured logging with request IDs (V1.2 §5.5).

One JSON object per line on stderr (journald-friendly), every line carrying
a `request_id` field — surfaced in the V1.4 admin log viewer via an in-process
ring buffer. The request ID is set
per request by the `request_context` middleware in `main.py` (contextvar),
returned to clients in the `X-Request-ID` response header, and honoured when
a well-formed `X-Request-ID` arrives on the request.

`LOG_FORMAT=plain` restores the previous human-readable format for local dev.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import collections
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from settings import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

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


def _record_to_entry(record: logging.LogRecord, *, include_category: bool) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        ),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
        "request_id": getattr(record, "request_id", "") or request_id_var.get(),
    }
    if include_category:
        entry["category"] = derive_log_category(record.name)
    for key, value in record.__dict__.items():
        if key not in _STANDARD_ATTRS and key not in entry:
            entry[key] = "[REDACTED]" if _should_redact_field(key) else value
    if record.exc_info:
        entry["exc_info"] = logging.Formatter().formatException(record.exc_info)
    if record.stack_info:
        entry["stack_info"] = logging.Formatter().formatStack(record.stack_info)
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
        category: str | None = None,
        search: str | None = None,
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
            if category and entry.get("category") != category:
                continue
            if needle:
                message = (entry.get("message") or "").lower()
                exc_info = (entry.get("exc_info") or "").lower()
                if needle not in message and needle not in exc_info:
                    continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results


_ring_handler = _RingBufferHandler()


def get_log_buffer(
    limit: int = 100,
    level: str | None = None,
    logger_name: str | None = None,
    request_id: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    return _ring_handler.get_logs(
        limit=limit,
        level=level,
        logger_name=logger_name,
        request_id=request_id,
        category=category,
        search=search,
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

    _ring_handler.setLevel(logging.INFO)
    root.addHandler(_ring_handler)
