"""JSON structured logging with request IDs (V1.2 §5.5).

One JSON object per line on stderr (journald-friendly), every line carrying
a `request_id` field — prep for the V1.4 log viewer. The request ID is set
per request by the `request_context` middleware in `main.py` (contextvar),
returned to clients in the `X-Request-ID` response header, and honoured when
a well-formed `X-Request-ID` arrives on the request.

`LOG_FORMAT=plain` restores the previous human-readable format for local dev.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from settings import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

PLAIN_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# LogRecord attributes that are bookkeeping, not user-supplied `extra` fields.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys()) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per log line; `extra={...}` kwargs become JSON keys."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # The access log passes request_id explicitly (survives deferred
            # formatting); everything else inherits the contextvar.
            "request_id": getattr(record, "request_id", "") or request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in entry:
                entry[key] = value
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


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
