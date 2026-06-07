"""Tests for BRIEFR intelligence sentences and risk score v1.1a."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.risk import calculate_risk_score
from templates.intelligence import (
    epss_sentence,
    exploit_sentence,
    kev_sentence,
    patch_sentence,
    severity_sentence,
)


def test_severity_critical():
    text = severity_sentence("CRITICAL", 9.8)
    assert "9.8" in text
    assert "CRITICAL" in text


def test_epss_kev_suffix():
    text = epss_sentence(0.85, True)
    assert "85" in text
    assert "CISA" in text


def test_kev_not_listed():
    assert "not currently listed" in kev_sentence(False, None, None)


def test_exploit_metasploit_priority():
    text = exploit_sentence([{"type": "poc"}, {"type": "metasploit"}])
    assert "Metasploit" in text


def test_risk_score_bounds():
    cve = {
        "cve_id": "CVE-2024-0001",
        "cvss_score": 10.0,
        "severity": "CRITICAL",
        "is_kev": True,
        "epss_score": 0.95,
        "has_poc": True,
        "kev_date_added": "2026-06-01",
    }
    result = calculate_risk_score(
        cve, None, [{"type": "metasploit"}]
    )
    assert 0 <= result["score"] <= 100
    assert len(result["breakdown"]) == 6  # v1.1b: asset, kev, epss, exploit, cvss, momentum
    assert result["components"]["asset"] == 0.5


def test_patch_sentence():
    assert "Apply" in patch_sentence(True, "vendor update 2.0")
