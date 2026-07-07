"""Tests for unified detection class router (Sprint D3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.class_router import (
    _resolve_detection_class,
    resolve_detection_class,
)
from detection.sigma_generator import generate_sigma_rule
from detection.siem_queries import get_siem_queries


def test_resolve_detection_class_from_cve_dict():
    assert _resolve_detection_class(
        {"mitre_technique": "T1190", "cwe_ids": ["CWE-22"]}
    ) == "web_exploit"
    assert _resolve_detection_class({"cwe_ids": json.dumps(["CWE-89"])}) == "sqli"
    assert _resolve_detection_class({"cwe_ids": ["CWE-9999"]}) == "generic"


def test_sigma_and_siem_agree_on_class_without_technique():
    cve = {"cwe_ids": ["CWE-22"]}
    detection_class = _resolve_detection_class(cve)

    rule = yaml.safe_load(
        generate_sigma_rule("CVE-2024-0022", "", cwe_ids=["CWE-22"])
    )
    siem = get_siem_queries("", cve_id="CVE-2024-0022", cwe_ids=["CWE-22"])

    assert detection_class == "path_traversal"
    assert rule["briefr_class"] == "path_traversal"
    assert siem["detection_class"] == "path_traversal"
    assert siem["title"] == "Path Traversal"
    assert "Directory traversal" in siem["log_patterns"][0]


def test_technique_template_wins_for_siem_but_class_still_resolves():
    siem = get_siem_queries("T1190", cwe_ids=["CWE-89"])
    assert siem["detection_class"] == "web_exploit"
    assert siem["title"] == "Exploit Public-Facing Application"


def test_siem_class_fallback_for_sqli():
    siem = get_siem_queries("", cwe_ids=["CWE-89"])
    assert siem["detection_class"] == "sqli"
    assert siem["title"] == "SQL Injection"
    assert any("UNION SELECT" in p for p in siem["log_patterns"])


def test_resolve_detection_class_technique_prefix():
    assert resolve_detection_class("T1059.003", ["CWE-78"]) == "script_execution"
