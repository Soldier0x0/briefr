"""Tests for GET /api/threat-model/scenarios."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "threat_model.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _seed_mitre_cve(client):
    import asyncio
    from database import get_db

    async def _run():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO mitre_techniques (technique_id, name, tactic, url, detection)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "T1190",
                    "Exploit Public-Facing Application",
                    "initial-access",
                    "https://attack.mitre.org/techniques/T1190/",
                    "Monitor web application logs for exploitation attempts.",
                ),
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-0001",
                    "Test CVE",
                    "HIGH",
                    9.0,
                    0.5,
                    1,
                    "2024-01-01",
                ),
            )
            await db.execute(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
                ("CVE-2024-0001", "T1190"),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(_run())


def test_scenarios_empty_without_stack(client):
    resp = client.get("/api/threat-model/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenarios"] == []
    assert data["meta"]["profile_required"] is True


def test_scenarios_with_stack_and_mapping(client):
    _seed_mitre_cve(client)
    resp = client.get("/api/threat-model/scenarios?stack=CVE-2024-0001")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 1
    scenario = data["scenarios"][0]
    assert scenario["technique_id"] == "T1190"
    assert scenario["cve_count"] == 1
    assert scenario["kev_count"] == 1
    assert scenario["evidence_cves"][0]["cve_id"] == "CVE-2024-0001"
    assert scenario["mitigations"]
    assert any(m["type"] == "patch" for m in scenario["mitigations"])
    assert "scenario" in scenario and len(scenario["scenario"]) > 20


def test_scenarios_handles_null_epss_score(client):
    """Regression: a technique whose CVEs all have NULL epss_score used to
    500 on Postgres. The ORDER BY referenced the SELECT-list alias
    max_epss inside a CASE expression -- SQLite resolves that alias
    anywhere, but Postgres only resolves a bare alias as the entire ORDER
    BY item, so nested inside CASE it tried (and failed) to find a real
    column named max_epss. Reproduced live via a throwaway Postgres
    container before fixing threat_model/scenarios.py to repeat the
    MAX(c.epss_score) aggregate instead of the alias."""
    import asyncio
    from database import get_db

    async def _seed_null_epss():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO mitre_techniques (technique_id, name, tactic, url) "
                "VALUES (?, ?, ?, ?)",
                ("T1059", "Command and Scripting Interpreter", "execution",
                 "https://attack.mitre.org/techniques/T1059/"),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, affected_products, "
                "severity, cvss_score, epss_score, is_kev, published) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("CVE-2024-9999", "Null EPSS test", '["docker:docker"]',
                 "HIGH", 7.5, None, 0, "2024-01-01"),
            )
            await db.execute(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
                ("CVE-2024-9999", "T1059"),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(_seed_null_epss())

    resp = client.get("/api/threat-model/scenarios?stack=docker")
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["technique_id"] == "T1059" for s in data["scenarios"])
