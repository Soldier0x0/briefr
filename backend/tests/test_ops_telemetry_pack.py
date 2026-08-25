"""Tests for GET /api/admin/diagnostics/ops-telemetry-pack."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "ops_telemetry.db"
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


def test_ops_telemetry_pack_requires_admin(tmp_path, monkeypatch):
    db_path = tmp_path / "ops_telemetry_auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/diagnostics/ops-telemetry-pack")
    assert resp.status_code == 401


def test_ops_telemetry_pack_rejects_bad_window(admin_client):
    resp = admin_client.get("/api/admin/diagnostics/ops-telemetry-pack?window=2d")
    assert resp.status_code == 422


def test_ops_telemetry_pack_schema_and_filename(admin_client):
    resp = admin_client.get("/api/admin/diagnostics/ops-telemetry-pack?window=1d")
    assert resp.status_code == 200
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "briefr-ops-telemetry-1d-" in disposition
    assert disposition.endswith('.json"') or ".json" in disposition
    data = json.loads(resp.text)
    assert data["ops_telemetry_pack_version"] == 1
    assert data["window"] == "1d"
    assert data["window_hours"] == 24
    assert isinstance(data["limitations"], list) and len(data["limitations"]) >= 4
    assert "resource_metrics" in data
    assert "samples" in data["resource_metrics"]
    assert "outbound_http" in data
    assert "scheduler" in data
    assert "efficiency" in data
    assert isinstance(data["sample_interval_seconds"], int)
    joined = " ".join(data["limitations"]).lower()
    assert "job" in joined
    assert "downsample" in joined or "500" in joined


def test_ops_telemetry_pack_sample_interval_from_env(admin_client, monkeypatch):
    monkeypatch.setenv("RESOURCE_SAMPLE_INTERVAL_SECONDS", "90")
    resp = admin_client.get("/api/admin/diagnostics/ops-telemetry-pack?window=1d")
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data["sample_interval_seconds"] == 90
