"""Saved investigation workspace cases."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.tokens import create_access_token
from database import init_db
import database
from main import app
from tests.conftest import attach_pytest_session_cookie, run_db_test, seed_pytest_auth_user_if_missing, use_sqlite_backend

VALID_SNAPSHOT = {
    "root_id": "cve:CVE-2024-9100",
    "nodes": [
        {
            "node_id": "cve:CVE-2024-9100",
            "entity_type": "cve",
            "entity_id": "CVE-2024-9100",
            "label": "CVE-2024-9100",
        },
    ],
    "edges": [],
    "positions": [{"node_id": "cve:CVE-2024-9100", "x": 100, "y": 200}],
    "view": {"x": 0, "y": 0, "scale": 1},
    "filters": {"showRelatedCves": False},
}


def _seed_db(tmp_path, monkeypatch) -> None:
    async def seed():
        db_path = str(tmp_path / "cases.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()

    run_db_test(seed())
    seed_pytest_auth_user_if_missing()


@pytest.mark.no_auth
def test_cases_list_requires_session(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = TestClient(app)
    resp = client.get("/api/investigations/cases")
    assert resp.status_code == 401


def test_cases_crud_happy_path(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = TestClient(app)
    attach_pytest_session_cookie(client)

    create = client.post(
        "/api/investigations/cases",
        json={"snapshot": VALID_SNAPSHOT, "title": "Test case"},
    )
    assert create.status_code == 200
    body = create.json()
    case_id = body["id"]
    assert body["title"] == "Test case"
    assert body["root_node_id"] == "cve:CVE-2024-9100"
    assert body["snapshot"]["root_id"] == "cve:CVE-2024-9100"

    listed = client.get("/api/investigations/cases")
    assert listed.status_code == 200
    assert any(item["id"] == case_id for item in listed.json()["cases"])

    loaded = client.get(f"/api/investigations/cases/{case_id}")
    assert loaded.status_code == 200
    assert loaded.json()["title"] == "Test case"

    updated_snapshot = {
        **VALID_SNAPSHOT,
        "nodes": [
            *VALID_SNAPSHOT["nodes"],
            {
                "node_id": "ioc:ip:203.0.113.1",
                "entity_type": "ioc",
                "entity_id": "203.0.113.1",
                "label": "203.0.113.1",
            },
        ],
    }
    updated = client.put(
        f"/api/investigations/cases/{case_id}",
        json={"snapshot": updated_snapshot, "title": "Updated case"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated case"
    assert len(updated.json()["snapshot"]["nodes"]) == 2

    deleted = client.delete(f"/api/investigations/cases/{case_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    missing = client.get(f"/api/investigations/cases/{case_id}")
    assert missing.status_code == 404


def test_cases_wrong_owner_returns_404(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = TestClient(app)
    attach_pytest_session_cookie(client)

    create = client.post("/api/investigations/cases", json={"snapshot": VALID_SNAPSHOT})
    assert create.status_code == 200
    case_id = create.json()["id"]

    seed_pytest_auth_user_if_missing(user_id=2, username="other-user", role="admin")
    client.cookies.set("briefr_at", create_access_token(2, "other-user", "admin"))

    resp = client.get(f"/api/investigations/cases/{case_id}")
    assert resp.status_code == 404


def test_cases_oversize_snapshot_returns_422(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = TestClient(app)
    attach_pytest_session_cookie(client)

    nodes = [
        {
            "node_id": f"cve:CVE-2024-{index:04d}",
            "entity_type": "cve",
            "entity_id": f"CVE-2024-{index:04d}",
        }
        for index in range(501)
    ]
    resp = client.post(
        "/api/investigations/cases",
        json={"snapshot": {"root_id": nodes[0]["node_id"], "nodes": nodes, "edges": []}},
    )
    assert resp.status_code == 422


def test_cases_malformed_node_id_returns_422(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = TestClient(app)
    attach_pytest_session_cookie(client)

    bad = {
        **VALID_SNAPSHOT,
        "nodes": [{"node_id": "bad:id", "entity_type": "cve", "entity_id": "x"}],
    }
    resp = client.post("/api/investigations/cases", json={"snapshot": bad})
    assert resp.status_code == 422
