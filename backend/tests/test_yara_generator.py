"""Tests for YARA template generation from OTX hashes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.yara_generator import build_yara_rules_from_hashes


def test_build_yara_sha256():
    h = "a" * 64
    rules = build_yara_rules_from_hashes("CVE-2024-1234", [h], pulse_name="Test Pulse")
    assert len(rules) == 1
    assert rules[0]["hash_type"] == "sha256"
    assert h in rules[0]["yara"]
    assert 'import "hash"' in rules[0]["yara"]
    assert "CVE-2024-1234" in rules[0]["yara"]


def test_build_yara_skips_invalid():
    rules = build_yara_rules_from_hashes("CVE-2024-1", ["not-a-hash", ""])
    assert rules == []
