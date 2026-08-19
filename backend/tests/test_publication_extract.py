"""Tests for shared publication extractors."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publications.extract import extract_cve_ids, extract_technique_ids


def test_extract_cve_ids_normalizes_and_dedupes():
    text = "cve-2024-1234 and CVE-2024-1234 plus CVE-2025-99999"
    assert extract_cve_ids(text) == ["CVE-2024-1234", "CVE-2025-99999"]


def test_extract_technique_ids_includes_attack_and_atlas():
    text = "Uses T1059.001 and AML.T0043 for execution"
    ids = extract_technique_ids(text)
    assert "T1059.001" in ids
    assert "AML.T0043" in ids
