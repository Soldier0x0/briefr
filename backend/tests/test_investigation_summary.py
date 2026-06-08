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
    ]
    cves, iocs, actors = split_investigation_items(items)
    assert cves == [{"cve_id": "CVE-2024-0001", "description": "RCE"}]
    assert iocs == [{"value": "1.2.3.4", "description": "malicious IP"}]
    assert actors == [
        {"name": "APT29", "description": "nation-state"},
        {"name": "AML.T0051", "description": "prompt injection"},
    ]


def test_generate_investigation_summary_returns_template_without_api_keys(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

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
