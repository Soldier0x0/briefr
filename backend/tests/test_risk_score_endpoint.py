"""Integration tests for POST /api/cves/{cve_id}/risk."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
import database as db_module
from main import app
from tests.conftest import run_db_test


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "risk.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setenv("PLAYWRIGHT_SMOKE", "1")

    async def _setup():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (
                    cve_id, description, cvss_score, severity, is_kev,
                    epss_score, has_poc, affected_products, source_urls
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-RISK",
                    "Test vulnerability for risk scoring",
                    9.8,
                    "CRITICAL",
                    1,
                    0.42,
                    1,
                    json.dumps(["vendor:product"]),
                    json.dumps([]),
                ),
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (cve_id, date_added, due_date)
                VALUES (?, ?, ?)
                """,
                ("CVE-2024-RISK", "2026-06-01", "2026-07-01"),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_setup())
    with TestClient(app) as test_client:
        yield test_client


def test_risk_endpoint_returns_canonical_score(client):
    res = client.post("/api/cves/CVE-2024-RISK/risk", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["cve_id"] == "CVE-2024-RISK"
    assert "threat" in body
    assert "environment" in body
    assert "operational_priority" in body
    assert "legacy_risk_v11b" in body
    assert "momentum" in body
    assert body["environment"]["tier"] == "UNKNOWN"
    assert body["operational_priority"]["band"] in ("P1", "P2", "P3", "P4")
    assert 0 <= body["threat"]["score"] <= 100
    legacy = body["legacy_risk_v11b"]
    assert legacy["components"]["asset"]["score"] == 0.5
    assert 0 <= legacy["total"] <= 100


def test_risk_endpoint_invalid_id(client):
    res = client.post("/api/cves/not-a-cve/risk", json={})
    assert res.status_code == 400


def test_risk_endpoint_with_profile(client):
    profile = {
        "applications": [
            {"product": "Product", "cpeProduct": "product", "vendor": "vendor", "version": ""}
        ],
        "operatingSystems": [],
        "aiSystems": [],
    }
    res = client.post(
        "/api/cves/CVE-2024-RISK/risk",
        json={"profile": profile},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["hasProfile"] is True
    assert body["environment"]["tier"] != "UNKNOWN"
