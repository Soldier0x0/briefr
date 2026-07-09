"""Tests for first-hour onboarding checklist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "onboarding.db"
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


def test_onboarding_requires_admin(tmp_path, monkeypatch):
    db_path = tmp_path / "onboarding_auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/onboarding")
    assert resp.status_code == 401


def test_onboarding_returns_checklist_items(admin_client):
    resp = admin_client.get("/api/admin/onboarding")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 5
    assert len(data["items"]) == 5
    assert "done_count" in data
    assert data["dismissed"] is False
    ids = {item["id"] for item in data["items"]}
    assert ids == {
        "cve_ingest",
        "stack_terms",
        "backup_ready",
        "feeds_healthy",
        "production_posture",
    }


def test_onboarding_stack_done_when_env_set(admin_client, monkeypatch):
    monkeypatch.setenv("BRIEFR_STACK_TERMS", "nginx, apache")
    resp = admin_client.get("/api/admin/onboarding")
    assert resp.status_code == 200
    stack = next(i for i in resp.json()["items"] if i["id"] == "stack_terms")
    assert stack["done"] is True


def test_onboarding_dismiss_persists(admin_client):
    resp = admin_client.post("/api/admin/onboarding/dismiss")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp2 = admin_client.get("/api/admin/onboarding")
    assert resp2.status_code == 200
    assert resp2.json()["dismissed"] is True
    assert resp2.json()["dismissed_at"]
