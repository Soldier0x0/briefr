"""ATLAS v6 YAML pointer resolution and parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.atlas import (
    _load_yaml_mapping,
    _pointer_target,
    _resolve_pointer_url,
    parse_atlas_yaml,
)

V6_FIXTURE = """
format-version: 6.0.0
matrix:
  id: ATLAS-matrix
  object-type: matrix
tactics:
  AML.TA0002:
    id: AML.TA0002
    name: Reconnaissance
    object-type: tactic
techniques:
  AML.T0040:
    id: AML.T0040
    name: AI Model Inference API Access
    description: Access model via API.
    object-type: technique
case-studies:
  AML.CS0099:
    id: AML.CS0099
    name: Sample 2026 Study
    description: A recent AI incident involving CVE-2026-10001.
    date: '2026-05-01'
    type: Incident
    target: LLM deployment
    object-type: case-study
relationships:
  AML.T0040:
    achieves:
      - source: AML.T0040
        target: AML.TA0002
        relationship-type: achieves
  AML.CS0099:
    employs:
      - source: AML.CS0099
        target: AML.T0040
        relationship-type: employs
"""


def test_pointer_target_detects_alias_files():
    assert _pointer_target("v6/ATLAS-latest.yaml\n") == "v6/ATLAS-latest.yaml"
    assert _pointer_target("ATLAS-2026.05.yaml") == "ATLAS-2026.05.yaml"
    assert _pointer_target("format-version: 6\nmatrix: {}\n") is None


def test_resolve_pointer_url_relative():
    base = "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS-latest.yaml"
    assert _resolve_pointer_url(base, "v6/ATLAS-latest.yaml").endswith("/dist/v6/ATLAS-latest.yaml")


def test_parse_v6_atlas_yaml_extracts_techniques_and_studies():
    data = _load_yaml_mapping(V6_FIXTURE)
    techniques, studies = parse_atlas_yaml(data)

    assert len(techniques) == 1
    assert techniques[0]["technique_id"] == "AML.T0040"
    assert techniques[0]["tactic"] == "Reconnaissance"

    assert len(studies) == 1
    study = studies[0]
    assert study["study_id"] == "AML.CS0099"
    assert study["date"] == "2026-05-01"
    assert study["study_type"] == "Incident"
    assert "CVE-2026-10001" in study["cve_ids"]
    assert study["techniques"] == ["AML.T0040"]
