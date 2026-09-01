"""Admin token router regression tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import database
import rate_limit
from db import config as db_config
from db import connection as db_connection
from db import init as db_init
from main import app
from settings import settings

@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "admin_tokens_health.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    rate_limit.refresh_bucket._buckets.pop("testclient", None)

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client

def test_api_keys_health_endpoint_does_not_500_from_missing_get_db(admin_client):
    resp = admin_client.get("/api/admin/api-keys/health")

    assert resp.status_code != 500, resp.text
    assert "get_db is not defined" not in resp.text
    assert resp.status_code == 200
    assert "providers" in resp.json()
