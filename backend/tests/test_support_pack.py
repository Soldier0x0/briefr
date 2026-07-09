"""Tests for GET /api/admin/diagnostics/support-pack."""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "support_pack.db"
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


def test_support_pack_requires_admin(tmp_path, monkeypatch):
    db_path = tmp_path / "support_pack_auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/diagnostics/support-pack")
    assert resp.status_code == 401


def test_support_pack_returns_redacted_bundle(admin_client):
    logging.getLogger("test.support_pack").info("Support pack log line")

    resp = admin_client.get("/api/admin/diagnostics/support-pack?log_limit=10")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers.get("content-type", "").startswith("application/json")

    data = json.loads(resp.text)
    assert data["support_pack_version"] == 1
    assert "generated_at" in data
    assert "health" in data
    assert "database" in data
    assert "security" in data
    assert "correlation" in data
    assert "diagnostics" in data
    assert "logs" in data

    db_url = data["database"].get("url", "")
    assert "password" not in db_url.lower()
    assert "***" in db_url or db_url == "not configured" or "sqlite" in db_url

    smoke = data["diagnostics"]["smoke"]
    assert "checks" in smoke
    assert isinstance(smoke["checks"], list)

    integrity = data["diagnostics"]["integrity"]
    assert "integrity_ok" in integrity
    assert "foreign_keys_ok" in integrity

    logs = data["logs"]["entries"]
    assert isinstance(logs, list)
    assert len(logs) <= 10


def test_support_pack_log_limit_bounds(admin_client):
    resp = admin_client.get("/api/admin/diagnostics/support-pack?log_limit=999")
    assert resp.status_code == 422

    resp = admin_client.get("/api/admin/diagnostics/support-pack?log_limit=0")
    assert resp.status_code == 422


def test_support_pack_redacts_secret_log_extras(admin_client):
    logger = logging.getLogger("test.support_pack.secrets")
    logger.info("Secret probe", extra={"NVD_API_KEY": "super-secret-key-value"})

    resp = admin_client.get("/api/admin/diagnostics/support-pack?log_limit=50")
    assert resp.status_code == 200
    body = resp.text
    assert "super-secret-key-value" not in body
    assert "[REDACTED]" in body
