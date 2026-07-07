"""Tests for legacy POST /api/investigation/summary wiring."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.summary import generate_investigation_summary, split_investigation_items


def test_split_investigation_items_maps_types():
    items = [
        {"type": "cve", "id": "CVE-2024-0001", "description": "RCE"},
        {"type": "ioc", "id": "1.2.3.4", "description": "malicious IP"},
        {"type": "actor", "id": "APT29", "description": "nation-state"},
        {"type": "technique", "id": "AML.T0051", "description": "prompt injection"},
        {"type": "cve", "id": "", "description": "skipped"},
        None,
        "not-a-dict",
        42,
    ]
    cves, iocs, actors = split_investigation_items(items)
    assert cves == [{"cve_id": "CVE-2024-0001", "description": "RCE"}]
    assert iocs == [{"value": "1.2.3.4", "description": "malicious IP"}]
    assert actors == [
        {"name": "APT29", "description": "nation-state"},
        {"name": "AML.T0051", "description": "prompt injection"},
    ]


def test_generate_investigation_summary_returns_template_without_api_keys(monkeypatch):
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    result = asyncio.run(
        generate_investigation_summary(
            [
                {"type": "cve", "id": "CVE-2024-9999", "description": "Test issue"},
            ],
            duration_minutes=15,
        )
    )

    assert "executive_summary" in result
    assert isinstance(result["executive_summary"], str)
    assert result["executive_summary"]
    assert isinstance(result["key_findings"], list)
    assert result["source"] == "template"
    assert "CVE-2024-9999" in result["executive_summary"]


def test_investigation_summary_rejects_invalid_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "inv.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("GROQ_API_KEY", "")
    for key in ("GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(key, "")
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.post(
            "/api/investigation/summary",
            json={
                "items": [{"type": "cve", "id": "CVE-2024-0001", "description": "RCE"}],
                "duration_minutes": 0,
            },
        )
        assert res.status_code == 422

        res = client.post(
            "/api/investigation/summary",
            json={
                "items": [{"type": "cve", "id": "CVE-2024-0001", "description": "RCE"}],
                "duration_minutes": 10081,
            },
        )
        assert res.status_code == 422

        res = client.post(
            "/api/investigation/summary",
            json={
                "items": [{"type": "cve", "id": "CVE-2024-0001", "description": "RCE"}],
                "duration_minutes": 10080,
            },
        )
        assert res.status_code == 200
