"""Tests for /api/security-architecture/* read API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_api.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_manifest_endpoint(client):
    res = client.get("/api/security-architecture/manifest")
    assert res.status_code == 200
    body = res.json()
    assert body["manifest"]["title"]
    assert body["counts"]["components"] >= 10


def test_overview_endpoint(client):
    res = client.get("/api/security-architecture/overview")
    assert res.status_code == 200
    body = res.json()
    cards = body["summary_cards"]
    assert "overall_posture" in cards
    assert "open_risks" in cards
    assert len(body["architecture_overview"]) >= 10


def test_search_endpoint(client):
    res = client.get("/api/security-architecture/search", params={"q": "jwt"})
    assert res.status_code == 200
    results = res.json()["results"]
    assert any(r["id"] == "jwt-session" for r in results)


def test_context_endpoint(client):
    res = client.get("/api/security-architecture/context/component/frontend")
    assert res.status_code == 200
    body = res.json()
    assert body["entity"]["id"] == "frontend"
    assert body["entity_type"] == "component"
