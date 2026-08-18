"""HTTP surface for investigation graph APIs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import attach_pytest_session_cookie, run_db_test, use_sqlite_backend

from correlation.campaigns import build_campaigns_from_pulses
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database
from main import app


async def _seed_routes_db(db) -> None:
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
        VALUES ('CVE-2024-9100', 'Routes seed', '2024-01-01', 0, 0, 0.5)
        """
    )
    await db.execute(
        """
        INSERT INTO mitre_techniques (technique_id, name, tactic, url)
        VALUES ('T1204', 'User Execution', 'execution', '')
        """
    )
    await db.execute(
        """
        INSERT INTO cve_technique_map (cve_id, technique_id)
        VALUES ('CVE-2024-9100', 'T1204')
        """
    )
    pulses = [
        {
            "pulse_id": "pulse-routes-1",
            "pulse_name": "Routes pulse",
            "author": "analyst",
            "created_date": "2024-01-10",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-9100", pulses)
    await replace_otx_pulse_iocs(
        db,
        "pulse-routes-1",
        [{"ioc_type": "IPv4", "ioc_value": "203.0.113.10", "description": ""}],
    )
    await build_campaigns_from_pulses(db)
    await db.commit()


@pytest.mark.no_auth
def test_resolve_requires_session(tmp_path, monkeypatch):
    async def seed():
        db_path = str(tmp_path / "routes-auth.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_routes_db(db)
        finally:
            await db.close()

    run_db_test(seed())
    client = TestClient(app)
    resp = client.get("/api/investigations/resolve", params={"q": "CVE-2024-9100"})
    assert resp.status_code == 401


def test_resolve_cve_and_relationships(tmp_path, monkeypatch):
    async def seed():
        db_path = str(tmp_path / "routes-ok.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_routes_db(db)
        finally:
            await db.close()

    run_db_test(seed())
    client = TestClient(app)
    attach_pytest_session_cookie(client)

    resolve = client.get("/api/investigations/resolve", params={"q": "cve-2024-9100"})
    assert resolve.status_code == 200
    body = resolve.json()
    assert body["root"]["entity_id"] == "CVE-2024-9100"
    assert body["query"] == "CVE-2024-9100"

    entity = client.get("/api/investigations/entities/cve/CVE-2024-9100")
    assert entity.status_code == 200
    assert entity.json()["node_id"] == "cve:CVE-2024-9100"

    relationships = client.get(
        "/api/investigations/entities/cve/CVE-2024-9100/relationships",
        params={"limit": 1},
    )
    assert relationships.status_code == 200
    graph = relationships.json()
    assert graph["truncated"] is True
    assert graph["root"]["node_id"] == "cve:CVE-2024-9100"
    assert len(graph["edges"]) == 1


def test_invalid_entity_type_returns_422(tmp_path, monkeypatch):
    async def seed():
        db_path = str(tmp_path / "routes-invalid.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()

    run_db_test(seed())
    client = TestClient(app)
    attach_pytest_session_cookie(client)
    resp = client.get("/api/investigations/entities/actor/G1")
    assert resp.status_code == 422


def test_depth_three_returns_422(tmp_path, monkeypatch):
    async def seed():
        db_path = str(tmp_path / "routes-depth.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()

    run_db_test(seed())
    client = TestClient(app)
    attach_pytest_session_cookie(client)
    resp = client.get(
        "/api/investigations/entities/cve/CVE-2024-9100/relationships",
        params={"depth": 3},
    )
    assert resp.status_code == 422


def test_resolve_unknown_entity_returns_404(tmp_path, monkeypatch):
    async def seed():
        db_path = str(tmp_path / "routes-miss.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()

    run_db_test(seed())
    client = TestClient(app)
    attach_pytest_session_cookie(client)
    resp = client.get("/api/investigations/resolve", params={"q": "CVE-2099-0001"})
    assert resp.status_code == 404
    assert resp.json()["knowledge_state"] == "unknown"
