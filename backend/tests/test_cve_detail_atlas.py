"""Tests for ATLAS fields on GET /api/cves/{id}."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import (
    get_atlas_case_studies_for_cve,
    get_atlas_techniques_for_cve,
    get_db,
    init_db,
    replace_atlas_techniques,
)
from tests.conftest import run_db_test


async def _seed_atlas_cve(db) -> None:
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
        db = await get_db()
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

    run_db_test(run())


def test_get_cve_endpoint_includes_atlas_fields(tmp_path, monkeypatch):
    db_path = tmp_path / "api_atlas.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def seed() -> None:
        await init_db()
        db = await get_db()
        await _seed_atlas_cve(db)
        await db.close()

    run_db_test(seed())

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

    async def seed() -> None:
        await init_db()
        db = await get_db()
        await _seed_atlas_cve(db)
        await db.close()

    run_db_test(seed())

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
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def seed() -> None:
        await init_db()

    run_db_test(seed())

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


def test_replace_atlas_techniques_drops_stale_fk_mappings(tmp_path, monkeypatch):
    async def run():
        import database

        db_path = str(tmp_path / "atlas-fk.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO atlas_techniques (
                    technique_id, name, description, tactic, tactic_id, url
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "AML.T0016",
                    "Old technique",
                    "Stale row",
                    "Reconnaissance",
                    "AML.TA0001",
                    "https://atlas.mitre.org/techniques/AML.T0016",
                ),
            )
            await db.execute(
                "INSERT INTO cve_atlas_map (cve_id, technique_id) VALUES (?, ?)",
                ("CVE-2024-ATLAS", "AML.T0016"),
            )
            await db.commit()

            await replace_atlas_techniques(
                db,
                [
                    {
                        "technique_id": "AML.T0040",
                        "name": "AI Model Inference API Access",
                        "description": "Access to inference APIs.",
                        "tactic": "ML Attack Staging",
                        "tactic_id": "AML.TA0002",
                        "url": "https://atlas.mitre.org/techniques/AML.T0040",
                    }
                ],
            )
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT technique_id FROM atlas_techniques ORDER BY technique_id"
            )
            assert [r["technique_id"] for r in rows] == ["AML.T0040"]
            stale = await db.execute_fetchall(
                "SELECT 1 FROM cve_atlas_map WHERE technique_id = ?",
                ("AML.T0016",),
            )
            assert stale == []
        finally:
            await db.close()

    run_db_test(run())
