"""V1.2 §5.5 — JSON structured logging with request IDs: formatter output,
X-Request-ID propagation, and the briefr.access per-request log line."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import rate_limit
from main import app, request_context
from structured_logging import JsonFormatter, request_id_var

# ----------------------------------------------------------- formatter tests


def _format_record(logger_name="test", msg="hello %s", args=("world",), **kwargs):
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=kwargs.get("exc_info"),
    )
    for key, value in kwargs.get("extra", {}).items():
        setattr(record, key, value)
    return JsonFormatter().format(record)


def test_formatter_emits_parseable_json_with_core_keys():
    entry = json.loads(_format_record())
    assert entry["level"] == "INFO"
    assert entry["logger"] == "test"
    assert entry["message"] == "hello world"
    assert "ts" in entry
    assert "request_id" in entry


def test_formatter_includes_request_id_from_contextvar():
    token = request_id_var.set("req-abc123")
    try:
        entry = json.loads(_format_record())
    finally:
        request_id_var.reset(token)
    assert entry["request_id"] == "req-abc123"


def test_formatter_prefers_explicit_request_id_extra():
    token = request_id_var.set("from-contextvar")
    try:
        entry = json.loads(_format_record(extra={"request_id": "from-extra"}))
    finally:
        request_id_var.reset(token)
    assert entry["request_id"] == "from-extra"


def test_formatter_includes_extra_fields():
    entry = json.loads(
        _format_record(extra={"status": 200, "duration_ms": 12.5, "path": "/x"})
    )
    assert entry["status"] == 200
    assert entry["duration_ms"] == 12.5
    assert entry["path"] == "/x"


def test_formatter_includes_exception_info():
    try:
        raise ValueError("boom")
    except ValueError:
        entry = json.loads(_format_record(exc_info=sys.exc_info()))
    assert "ValueError: boom" in entry["exc_info"]


# ----------------------------------------------------------- middleware tests


def test_every_response_carries_a_generated_request_id():
    with TestClient(app) as client:
        resp = client.get("/api/config/risk")
        assert resp.status_code == 200
        request_id = resp.headers.get("X-Request-ID", "")
        assert len(request_id) == 16
        int(request_id, 16)  # uuid4 hex prefix


def test_wellformed_incoming_request_id_is_echoed():
    with TestClient(app) as client:
        resp = client.get("/api/config/risk", headers={"X-Request-ID": "trace-42.A_b"})
        assert resp.headers["X-Request-ID"] == "trace-42.A_b"


def test_malformed_incoming_request_id_is_replaced():
    with TestClient(app) as client:
        resp = client.get(
            "/api/config/risk", headers={"X-Request-ID": "bad value with spaces!"}
        )
        request_id = resp.headers["X-Request-ID"]
        assert request_id != "bad value with spaces!"
        assert len(request_id) == 16


def test_access_log_line_carries_request_metadata(caplog):
    with TestClient(app) as client:
        with caplog.at_level(logging.INFO, logger="briefr.access"):
            resp = client.get("/api/config/risk")
    records = [r for r in caplog.records if r.name == "briefr.access"]
    assert records, "expected one briefr.access record per request"
    record = records[-1]
    assert record.method == "GET"
    assert record.path == "/api/config/risk"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert record.request_id == resp.headers["X-Request-ID"]
    # The captured record must serialize to a JSON line with the same fields.
    entry = json.loads(JsonFormatter().format(record))
    assert entry["request_id"] == resp.headers["X-Request-ID"]
    assert entry["status"] == 200


def test_unhandled_exception_logged_with_request_id(caplog):
    """Review finding: uvicorn logs tracebacks after the contextvar reset,
    so the middleware itself must emit an error line while the ID is set."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/boom",
        "raw_path": b"/api/boom",
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("203.0.113.5", 1234),
        "headers": [(b"x-request-id", b"crash-trace-1")],
    }
    request = Request(scope)

    async def failing_call_next(_request):
        raise ValueError("boom")

    with caplog.at_level(logging.ERROR, logger="briefr.access"):
        with pytest.raises(ValueError):
            asyncio.run(request_context(request, failing_call_next))

    records = [r for r in caplog.records if r.name == "briefr.access"]
    assert records, "expected an error record for the unhandled exception"
    record = records[-1]
    assert record.request_id == "crash-trace-1"
    assert record.path == "/api/boom"
    assert record.status == 500
    assert record.exc_info is not None
    entry = json.loads(JsonFormatter().format(record))
    assert entry["request_id"] == "crash-trace-1"
    assert "ValueError: boom" in entry["exc_info"]
    # The contextvar must still have been reset after the failure.
    assert request_id_var.get() == ""


def test_429_responses_also_carry_request_id():
    with TestClient(app) as client:
        rate_limit.ioc_bucket._buckets["testclient"] = (0.0, time.monotonic())
        try:
            resp = client.post("/api/ioc/lookup", json={"value": "1.2.3.4", "type": "ip"})
            assert resp.status_code == 429
            assert resp.headers.get("X-Request-ID")
        finally:
            rate_limit.ioc_bucket._buckets.pop("testclient", None)
