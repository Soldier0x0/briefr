"""Tests for ATLAS fields on GET /api/cves/{id}."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import (
    get_atlas_case_studies_for_cve,
    get_atlas_techniques_for_cve,
    init_db,
)


async def _seed_atlas_cve(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        INSERT INTO cves (
            cve_id, description, cvss_score, severity, published,
            affected_products, has_ai_context
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CVE-2024-ATLAS",
            "Remote code execution in TensorFlow serving.",
            9.1,
            "CRITICAL",
            "2024-06-01T00:00:00",
            json.dumps(["google:tensorflow"]),
            1,
        ),
    )
    await db.execute(
        """
        INSERT INTO atlas_techniques (
            technique_id, name, description, tactic, url
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            "AML.T0040",
            "AI Model Inference API Access",
            "Access to inference APIs.",
            "ML Attack Staging",
            "https://atlas.mitre.org/techniques/AML.T0040",
        ),
    )
    await db.execute(
        """
        INSERT INTO cve_atlas_map (cve_id, technique_id)
        VALUES (?, ?)
        """,
        ("CVE-2024-ATLAS", "AML.T0040"),
    )
    await db.execute(
        """
        INSERT INTO atlas_case_studies (
            study_id, name, summary, techniques, target, date, cve_ids
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "study-1",
            "TensorFlow Serving Abuse",
            "Adversary abused model API.",
            json.dumps(["AML.T0040"]),
            "ML platform",
            "2023-01-15",
            json.dumps(["CVE-2024-ATLAS"]),
        ),
    )
    await db.commit()


def test_cve_detail_atlas_helpers_return_linked_data(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def run() -> None:
        await init_db()
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await _seed_atlas_cve(db)

        techniques = await get_atlas_techniques_for_cve(db, "CVE-2024-ATLAS")
        studies = await get_atlas_case_studies_for_cve(db, "CVE-2024-ATLAS")

        assert len(techniques) == 1
        assert techniques[0]["technique_id"] == "AML.T0040"
        assert techniques[0]["name"] == "AI Model Inference API Access"

        assert len(studies) == 1
        assert studies[0]["study_id"] == "study-1"
        assert studies[0]["name"] == "TensorFlow Serving Abuse"

        row = await db.execute_fetchall(
            "SELECT has_ai_context FROM cves WHERE cve_id = ?",
            ("CVE-2024-ATLAS",),
        )
        assert row[0]["has_ai_context"] == 1
        await db.close()

    asyncio.run(run())


def test_get_cve_endpoint_includes_atlas_fields(tmp_path, monkeypatch):
    db_path = tmp_path / "api_atlas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await _seed_atlas_cve(db)
        await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves/CVE-2024-ATLAS")

    assert res.status_code == 200
    body = res.json()
    assert body["has_ai_context"] is True
    assert len(body["atlas_techniques"]) == 1
    assert body["atlas_techniques"][0]["technique_id"] == "AML.T0040"
    assert len(body["atlas_case_studies"]) == 1
    assert body["atlas_case_studies"][0]["study_id"] == "study-1"


def test_list_cves_includes_has_ai_context(tmp_path, monkeypatch):
    """CVE_SELECT must include has_ai_context — list/export should not default to False."""
    db_path = tmp_path / "list_atlas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await _seed_atlas_cve(db)
        await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves?search=CVE-2024-ATLAS")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["cve_id"] == "CVE-2024-ATLAS"
    assert data[0]["has_ai_context"] is True


def test_investigation_summary_endpoint_returns_200(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.post(
            "/api/investigation/summary",
            json={
                "items": [
                    {
                        "type": "cve",
                        "id": "CVE-2024-0001",
                        "description": "Critical RCE",
                    }
                ],
                "duration_minutes": 10,
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "template"
    assert "CVE-2024-0001" in body["executive_summary"]
