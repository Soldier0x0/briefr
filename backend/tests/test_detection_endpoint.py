"""Tests for GET /api/cves/{cve_id}/detection (Sprint D5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as db_module
from database import get_db, init_db
from main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "detection.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")

    import asyncio

    async def _setup():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (
                    cve_id, description, cvss_score, severity, cwe_ids,
                    affected_products, mitre_technique
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-DET5",
                    "Path traversal in widget",
                    7.5,
                    "HIGH",
                    json.dumps(["CWE-22"]),
                    json.dumps(["acme:widget"]),
                    "",
                ),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(_setup())

    async def _fake_sigma(*_args, **_kwargs):
        return [{"path": "rules/community.yml", "title": "Community rule", "source": "SigmaHQ"}]

    async def _fake_elastic(*_args, **_kwargs):
        return []

    async def _fake_yara(*_args, **_kwargs):
        return []

    monkeypatch.setattr("routers.cves.find_sigma_rules", _fake_sigma)
    monkeypatch.setattr("routers.cves.find_elastic_rules", _fake_elastic)
    monkeypatch.setattr("detection.yara_generator.find_yara_rules_for_cve", _fake_yara)

    with TestClient(app) as test_client:
        yield test_client


def test_detection_always_returns_generated_sigma_supplement(client):
    res = client.get("/api/cves/CVE-2024-DET5/detection")
    assert res.status_code == 200
    body = res.json()
    assert body["has_community_rules"] is True
    assert body["generated_sigma"]
    assert "briefr_basis" in body["generated_sigma"]
    meta = body["generated_sigma_meta"]
    assert meta["briefr_basis"] == "cwe"
    assert meta["briefr_class"] == "path_traversal"
    assert meta["status"] == "experimental"
    assert body["siem_queries"]["detection_class"] == "path_traversal"
