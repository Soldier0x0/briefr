"""Tests for Threat Score v1.0 (ADR-002)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.threat import KEV_FLOOR, calculate_threat_score, threat_band


def _recent_kev_date() -> str:
    return (date.today() - timedelta(days=3)).isoformat()


def test_kev_floor_applies_at_least_80():
    cve = {
        "is_kev": True,
        "kev_date_added": _recent_kev_date(),
        "epss_score": 0.02,
        "cvss_score": 9.8,
        "has_poc": True,
        "public_exploits": [{"type": "poc"}],
    }
    result = calculate_threat_score(cve, momentum_score=0.8)
    assert result["score"] >= KEV_FLOOR
    assert result["band"] == "CRIT"
    assert result["kev_floor_applied"] is True


def test_cvss_only_low_threat():
    cve = {
        "is_kev": False,
        "cvss_score": 9.8,
        "epss_score": 0.05,
        "has_poc": False,
        "public_exploits": [],
    }
    result = calculate_threat_score(cve, momentum_score=0.1)
    assert result["band"] == "LOW"
    assert result["score"] < 40
    assert result["kev_floor_applied"] is False


def test_medium_cvss_kev_metasploit_crit():
    cve = {
        "is_kev": True,
        "kev_date_added": _recent_kev_date(),
        "cvss_score": 6.5,
        "epss_score": 0.9,
        "has_poc": True,
        "public_exploits": [{"type": "metasploit", "source": "Sploitus"}],
    }
    result = calculate_threat_score(cve, momentum_score=0.8)
    assert result["band"] == "CRIT"
    assert result["score"] >= 80


def test_epss_pass_through():
    cve = {
        "is_kev": False,
        "cvss_score": 5.0,
        "epss_score": 0.75,
        "has_poc": False,
        "public_exploits": [],
    }
    low = calculate_threat_score(cve, momentum_score=0.0)
    high_epss = calculate_threat_score({**cve, "epss_score": 0.95}, momentum_score=0.0)
    assert high_epss["score"] > low["score"]
    assert high_epss["components"]["epss"]["raw"] == pytest.approx(0.95)


def test_missing_epss_and_exploit_zero():
    cve = {
        "is_kev": False,
        "cvss_score": 7.0,
        "has_poc": False,
        "public_exploits": [],
    }
    result = calculate_threat_score(cve, momentum_score=0.0)
    assert result["components"]["epss"]["raw"] == 0.0
    assert result["components"]["exploit"]["raw"] == 0.0


def test_threat_bands():
    assert threat_band(80) == "CRIT"
    assert threat_band(79.9) == "HIGH"
    assert threat_band(60) == "HIGH"
    assert threat_band(59) == "MED"
    assert threat_band(40) == "MED"
    assert threat_band(39) == "LOW"


def test_cisa_kev_applies_floor():
    """W2: CISA KEV floor is 80 — applied only when is_kev is true."""
    cve = {
        "is_kev": True,
        "kev_date_added": _recent_kev_date(),
        "epss_score": 0.01,
        "cvss_score": 5.0,
    }
    threat = calculate_threat_score(cve, momentum_score=0.0)
    assert threat["score"] >= KEV_FLOOR
    assert threat["kev_floor_applied"] is True


def test_vulncheck_only_does_not_apply_kev_floor():
    """W2: VulnCheck-only exploitation must not receive the CISA KEV floor."""
    cve = {
        "is_kev": False,
        "is_vulncheck_exploited": True,
        "epss_score": 0.01,
        "cvss_score": 5.0,
    }
    threat = calculate_threat_score(cve, momentum_score=0.0)
    assert threat["score"] < KEV_FLOOR
    assert threat["kev_floor_applied"] is False
