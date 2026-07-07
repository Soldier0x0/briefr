"""Tests for CWE-aware Sigma rule generation (Sprint D1)."""

from __future__ import annotations

import yaml

from detection.sigma_generator import (
    CWE_TEMPLATES,
    generate_sigma_rule,
    _normalize_cwe_id,
    _resolve_template,
)


def _load_rule(yaml_text: str) -> dict:
    data = yaml.safe_load(yaml_text)
    assert isinstance(data, dict)
    return data


def test_normalize_cwe_id():
    assert _normalize_cwe_id("cwe-22") == "CWE-22"
    assert _normalize_cwe_id("22") == "CWE-22"
    assert _normalize_cwe_id(" CWE-78 ") == "CWE-78"


def test_technique_template_wins_over_cwe():
    template, basis, matched = _resolve_template("T1190", ["CWE-22"])
    assert basis == "attack_technique"
    assert matched == ""
    assert template["tactic"] == "initial_access"

    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0001",
            "T1190",
            cwe_ids=["CWE-22"],
        )
    )
    assert rule["briefr_basis"] == "attack_technique"
    assert rule["logsource"] == {"category": "webserver"}


def test_cwe22_path_traversal_without_technique():
    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0002",
            "",
            cwe_ids=["CWE-22"],
        )
    )
    assert rule["briefr_basis"] == "cwe"
    assert "../" in rule["detection"]["keywords"]
    assert rule["level"] == "high"
    assert rule["briefr_confidence"] == "MEDIUM"
    assert "cwe.22" in rule["tags"]


def test_cwe79_low_confidence_note():
    rule = _load_rule(generate_sigma_rule("CVE-2024-0003", "", cwe_ids=["CWE-79"]))
    assert rule["briefr_basis"] == "cwe"
    assert rule["level"] == "low"
    assert rule["briefr_confidence"] == "LOW"
    assert "false-positive" in rule["briefr_note"].lower()


def test_generic_fallback_when_cwe_unmapped():
    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0004",
            "",
            cwe_ids=["CWE-9999"],
        )
    )
    assert rule["briefr_basis"] == "generic"
    assert rule["detection"]["keywords"] == [
        "exploit",
        "attack",
        "injection",
        "overflow",
    ]


def test_first_mapped_cwe_wins():
    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0005",
            "",
            cwe_ids=["CWE-9999", "CWE-89"],
        )
    )
    assert rule["briefr_basis"] == "cwe"
    assert "UNION SELECT" in rule["detection"]["keywords"]


def test_cwe_template_registry_covers_spec_set():
    expected = {
        "CWE-22",
        "CWE-23",
        "CWE-35",
        "CWE-78",
        "CWE-89",
        "CWE-79",
        "CWE-502",
        "CWE-94",
        "CWE-95",
        "CWE-434",
        "CWE-918",
        "CWE-611",
        "CWE-287",
        "CWE-288",
        "CWE-306",
        "CWE-416",
        "CWE-787",
        "CWE-119",
        "CWE-122",
        "CWE-798",
    }
    assert expected.issubset(set(CWE_TEMPLATES))
