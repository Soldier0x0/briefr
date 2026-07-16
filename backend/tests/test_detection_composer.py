"""DC-1: evidence-composed detection pack (no LLM, no UI)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test


@pytest.fixture()
def composer_deps(monkeypatch):
    """Stub community / context / exploits / yara so composer unit tests stay offline."""
    import detection.composer as composer

    monkeypatch.setattr(
        composer,
        "find_sigma_rules",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        composer,
        "find_elastic_rules",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        composer,
        "get_detection_context",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        composer,
        "read_cve_exploits_from_db",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        composer,
        "find_yara_rules_for_cve",
        AsyncMock(return_value=[]),
    )
    return composer


def test_compose_empty_evidence_primary_none(composer_deps):
    composer = composer_deps

    async def run():
        return await composer.compose_detection_evidence(
            db=object(),
            cve_id="CVE-2026-0001",
            technique_ids=[],
            cwe_ids=["CWE-22"],
            include_community=False,
        )

    pack = run_db_test(run())
    assert pack["cve_id"] == "CVE-2026-0001"
    assert pack["community"]["has_community_rules"] is False
    assert pack["artifacts"] == []
    assert pack["observables"]["nuclei_urls"] == []
    assert pack["evidence_summary"]["primary_source"] == "none"
    assert pack["evidence_summary"]["community_count"] == 0


def test_compose_community_rules_primary_community(composer_deps):
    composer = composer_deps
    composer.find_sigma_rules = AsyncMock(
        return_value=[
            {
                "path": "rules/web.yml",
                "title": "Community path traversal",
                "source": "SigmaHQ",
            }
        ]
    )

    async def run():
        return await composer.compose_detection_evidence(
            db=object(),
            cve_id="CVE-2026-0002",
            technique_ids=["T1190"],
            include_community=True,
            github_token="tok",
        )

    pack = run_db_test(run())
    assert pack["community"]["has_community_rules"] is True
    assert pack["community"]["sigma_rules"][0]["title"] == "Community path traversal"
    assert pack["evidence_summary"]["community_count"] == 1
    assert pack["evidence_summary"]["primary_source"] == "community"
    composer.find_sigma_rules.assert_awaited()


def test_compose_nuclei_artifacts_from_context(composer_deps):
    composer = composer_deps
    composer.get_detection_context = AsyncMock(
        return_value={
            "cwe_ids": ["CWE-22"],
            "product": "widget",
            "class": "path_traversal",
            "artifacts": [
                {
                    "paths": ["/etc/passwd"],
                    "params": ["file"],
                    "keywords": ["../"],
                    "method": "GET",
                }
            ],
            "model": "nuclei-parser",
            "provider": "briefr-nuclei",
            "generated_at": "2026-07-16T00:00:00Z",
        }
    )
    composer.read_cve_exploits_from_db = AsyncMock(
        return_value=[
            {
                "source": "nuclei",
                "url": "https://github.com/projectdiscovery/nuclei-templates/blob/main/http/cves/2026/CVE-2026-0003.yaml",
                "title": "CVE-2026-0003",
            },
            {
                "source": "exploitdb",
                "url": "https://www.exploit-db.com/exploits/1",
                "title": "other",
            },
        ]
    )

    async def run():
        return await composer.compose_detection_evidence(
            db=object(),
            cve_id="CVE-2026-0003",
            include_community=False,
        )

    pack = run_db_test(run())
    assert pack["detection_class"] == "path_traversal"
    assert len(pack["artifacts"]) == 1
    assert pack["artifacts"][0]["paths"] == ["/etc/passwd"]
    assert pack["observables"]["nuclei_urls"] == [
        "https://github.com/projectdiscovery/nuclei-templates/blob/main/http/cves/2026/CVE-2026-0003.yaml"
    ]
    assert pack["evidence_summary"]["artifact_count"] == 1
    assert pack["evidence_summary"]["nuclei_count"] == 1
    assert pack["evidence_summary"]["primary_source"] == "nuclei_artifacts"


def test_compose_yara_primary_when_only_hashes(composer_deps):
    composer = composer_deps
    composer.find_yara_rules_for_cve = AsyncMock(
        return_value=[{"rule_name": "otx_hash", "hashes": ["aa" * 32]}]
    )

    async def run():
        return await composer.compose_detection_evidence(
            db=object(),
            cve_id="CVE-2026-0004",
            include_community=False,
        )

    pack = run_db_test(run())
    assert pack["observables"]["yara_rules"]
    assert pack["evidence_summary"]["primary_source"] == "yara"


def test_composer_module_does_not_import_llm_router():
    import detection.composer as composer
    import inspect

    src = inspect.getsource(composer)
    assert "llm_router" not in src
    assert "artifact_extract" not in src or "chat_completion" not in src
    assert "chat_completion" not in src
