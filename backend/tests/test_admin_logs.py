"""Tests for /api/admin/logs and ring buffer + auth failure audit."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from structured_logging import (
    LOG_CATEGORIES,
    _ring_handler,
    configure_logging,
    derive_log_category,
)


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "logs.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_logs_endpoint_returns_structured_payload(admin_client):
    logger = logging.getLogger("test.admin.logs")
    logger.info("Test log entry for admin logs test")

    resp = admin_client.get("/api/admin/logs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "known_loggers" in data
    assert "categories" in data
    assert data["categories"] == list(LOG_CATEGORIES)
    assert data["buffer_capacity"] == 500
    assert isinstance(data["logs"], list)
    assert data["logs"]
    entry = data["logs"][0]
    for field in ("ts", "level", "logger", "message", "request_id", "category"):
        assert field in entry


def test_logs_endpoint_filters_by_level_and_request_id(admin_client):
    logger = logging.getLogger("test.admin.filters")
    logger.warning("Filter warning entry")

    resp = admin_client.get("/api/admin/logs?limit=50&level=WARNING")
    assert resp.status_code == 200
    warnings = resp.json()["logs"]
    assert warnings
    assert all(e["level"] == "WARNING" for e in warnings)

    req_id = resp.headers.get("X-Request-ID")
    assert req_id

    by_id = admin_client.get(f"/api/admin/logs?request_id={req_id}")
    assert by_id.status_code == 200
    matched = by_id.json()["logs"]
    assert matched
    assert all(e["request_id"] == req_id for e in matched)


def test_logs_endpoint_filters_by_category(admin_client):
    logging.getLogger("scheduler").info("Scheduler category test")
    logging.getLogger("backup.manager").info("Backup category test")

    resp = admin_client.get("/api/admin/logs?category=Scheduler&limit=20")
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert logs
    assert all(e["category"] == "Scheduler" for e in logs)


def test_logs_endpoint_filters_by_search(admin_client):
    logging.getLogger("test.admin.search").error("Detection lookup failed for CVE-2099-0001")
    logging.getLogger("test.admin.search").info("Unrelated informational entry")

    resp = admin_client.get("/api/admin/logs?search=Detection+lookup&limit=50")
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert logs
    assert all("detection lookup" in e["message"].lower() for e in logs)


def test_derive_log_category_mapping():
    assert derive_log_category("scheduler") == "Scheduler"
    assert derive_log_category("backup.manager") == "Backup"
    assert derive_log_category("webhooks.sender") == "Webhooks"
    assert derive_log_category("dependencies") == "Security"
    assert derive_log_category("feeds.nvd") == "Application"


def test_ring_buffer_respects_limit():
    logger = logging.getLogger("test.ring.limit")
    for i in range(20):
        logger.info("Limit test %d", i)

    results = _ring_handler.get_logs(limit=5)
    assert len(results) <= 5


def test_ring_buffer_redacts_secret_extras():
    logger = logging.getLogger("test.ring.redact")
    logger.info(
        "Should not expose password",
        extra={"password": "super_secret_value", "api_key": "sk-1234567890abcdef"},
    )

    results = _ring_handler.get_logs(limit=10, logger_name="test.ring.redact")
    assert results
    entry = results[0]
    assert entry["password"] == "[REDACTED]"
    assert entry["api_key"] == "[REDACTED]"
    assert "super_secret_value" not in str(entry)
    assert "sk-1234567890abcdef" not in str(entry)


def test_unauthenticated_admin_request_rejected(tmp_path, monkeypatch):
    """Admin routes require a session cookie — no legacy key fallback (Sprint A0)."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/system")
    assert resp.status_code == 401
