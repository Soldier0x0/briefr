"""DC-2: emit composed Sigma/SIEM/YARA from an evidence pack (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _evidence(
    *,
    cve_id: str = "CVE-2026-DC2",
    primary_source: str = "none",
    artifacts: list | None = None,
    yara_rules: list | None = None,
    community_count: int = 0,
    product: str = "widget",
    technique_ids: list | None = None,
    detection_class: str = "path_traversal",
    detection_context: dict | None = None,
) -> dict:
    arts = artifacts or []
    yara = yara_rules or []
    return {
        "cve_id": cve_id,
        "technique_ids": technique_ids or [],
        "detection_class": detection_class,
        "community": {
            "sigma_rules": [{"title": "community"}] if community_count else [],
            "elastic_rules": [],
            "has_community_rules": community_count > 0,
        },
        "artifacts": arts,
        "observables": {"nuclei_urls": [], "yara_rules": yara},
        "detection_context": detection_context
        or ({"class": detection_class, "artifacts": arts, "product": product} if arts else None),
        "evidence_summary": {
            "community_count": community_count,
            "artifact_count": len(arts),
            "nuclei_count": 0,
            "primary_source": primary_source,
        },
        "product": product,
    }


def test_emit_composed_detection_importable():
    from detection.composer import emit_composed_detection

    assert callable(emit_composed_detection)


def test_emit_empty_evidence_uses_template_fallback():
    from detection.composer import emit_composed_detection

    out = emit_composed_detection(
        _evidence(primary_source="none"),
        description="Path traversal in widget",
        cwe_ids=["CWE-22"],
    )
    assert out["compose_basis"] == "template_fallback"
    assert out["generated_sigma_meta"]["compose_basis"] == "template_fallback"
    assert out["generated_sigma"]
    assert "detection_class" in out["siem_queries"]
    assert out["yara_rules"] == []


def test_emit_artifacts_inject_sigma_and_siem():
    from detection.composer import emit_composed_detection

    arts = [
        {
            "paths": ["/api/widget/traverse"],
            "params": ["file"],
            "keywords": ["briefr-dc2-marker"],
            "method": "GET",
            "provenance": "nuclei",
        }
    ]
    out = emit_composed_detection(
        _evidence(
            primary_source="nuclei_artifacts",
            artifacts=arts,
            detection_class="path_traversal",
        ),
        description="Path traversal",
        cwe_ids=["CWE-22"],
    )
    assert out["compose_basis"] == "nuclei_artifacts"
    rule = yaml.safe_load(out["generated_sigma"])
    assert "briefr-dc2-marker" in rule["detection"]["keywords"]
    assert "/api/widget/traverse" in out["siem_queries"]["elastic_kql"]["query"]
    assert "/api/widget/traverse" in out["siem_queries"]["splunk_spl"]["query"]
    assert 'has_any ("/api/widget/traverse", "briefr-dc2-marker")' in out[
        "siem_queries"
    ]["sentinel_kql"]["query"]
    # QRadar AQL must not get a naive suffix that breaks LAST/WHERE clauses.
    assert "/api/widget/traverse" not in out["siem_queries"]["qradar_aql"]["query"]


def test_artifact_tokens_wrap_string_fields():
    from detection.composer import _artifact_tokens

    tokens = _artifact_tokens(
        [{"paths": "/api/v1", "keywords": "marker", "params": []}]
    )
    assert tokens == ["/api/v1", "marker"]


def test_emit_community_basis_passes_yara_through():
    from detection.composer import emit_composed_detection

    yara = [{"rule_name": "otx_hash", "hash": "aa" * 32}]
    out = emit_composed_detection(
        _evidence(
            primary_source="community",
            community_count=1,
            yara_rules=yara,
        ),
        cwe_ids=["CWE-22"],
    )
    assert out["compose_basis"] == "community"
    assert out["yara_rules"] == yara
