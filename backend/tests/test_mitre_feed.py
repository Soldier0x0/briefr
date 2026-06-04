"""Tests for MITRE ATT&CK feed parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.mitre import (
    parse_cve_mappings_csv,
    parse_enterprise_attack_stix,
    technique_url,
)


def test_technique_url_subtechnique():
    assert technique_url("T1059.001").endswith("/T1059/001/")


def test_parse_stix_includes_detection_and_tactics():
    data = {
        "objects": [
            {
                "type": "x-mitre-detection-strategy",
                "id": "x-mitre-detection-strategy--abc",
                "name": "Detect T1190",
                "description": "Monitor web logs for exploitation patterns.",
            },
            {
                "type": "relationship",
                "id": "relationship--1",
                "relationship_type": "detects",
                "source_ref": "x-mitre-detection-strategy--abc",
                "target_ref": "attack-pattern--xyz",
            },
            {
                "type": "attack-pattern",
                "id": "attack-pattern--xyz",
                "name": "Exploit Public-Facing Application",
                "description": "A" * 600,
                "kill_chain_phases": [
                    {"phase_name": "initial-access"},
                    {"phase_name": "execution"},
                ],
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T1190"},
                ],
                "x_mitre_platforms": ["Linux"],
            },
        ]
    }
    rows = parse_enterprise_attack_stix(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["technique_id"] == "T1190"
    assert "Initial Access" in row["tactic"]
    assert "Execution" in row["tactic"]
    assert len(row["description"]) <= 500
    assert "Monitor web logs" in row["detection"]
    assert len(row["detection"]) <= 400


def test_parse_cve_mappings_csv():
    csv_text = "CVE ID,Primary Impact,Secondary Impact,Exploitation Technique,Uncategorized\nCVE-2024-0001,T1190,,,\n"
    mapping = parse_cve_mappings_csv(csv_text)
    assert mapping["CVE-2024-0001"] == ["T1190"]

def test_parse_cve_mappings_csv_handles_utf8_bom():
    raw = (
        b"\xef\xbb\xbfCVE ID,Primary Impact,Secondary Impact,Exploitation Technique,Uncategorized\n"
        b"CVE-2024-0001,T1059,,,\n"
    )
    csv_text = raw.decode("utf-8-sig", errors="replace")
    assert parse_cve_mappings_csv(csv_text) == {"CVE-2024-0001": ["T1059"]}
