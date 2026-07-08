"""Tests for Sigma artifact injection (Sprint D4)."""

import json

from detection.context import build_detection_context
from detection.sigma_generator import generate_sigma_rule


def _load_rule(yaml_text: str) -> dict:
    import yaml

    return yaml.safe_load(yaml_text)


def test_generate_sigma_injects_artifact_keywords_and_meta():
    ctx = build_detection_context(
        cve_id="CVE-2024-0400",
        cwe_ids=["CWE-89"],
        affected_products=json.dumps(["acme:portal"]),
    )
    ctx["artifacts"] = [
        {
            "paths": ["/api/login"],
            "params": ["username"],
            "keywords": ["mysql syntax error"],
            "method": "POST",
        }
    ]
    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0400",
            "",
            cwe_ids=[],
            detection_context=ctx,
        )
    )
    assert rule["briefr_artifacts"][0]["paths"] == ["/api/login"]
    assert "mysql syntax error" in rule["detection"]["keywords"]
    assert "Nuclei paths" in rule["briefr_note"]
