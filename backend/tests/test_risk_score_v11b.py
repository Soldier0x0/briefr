"""Tests for canonical server-side Risk Score v1.1b."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.asset_match import (
    asset_score_from_backend,
    profile_to_match_assets,
    resolve_asset_component,
)
from scoring.risk import _exploit_score_v11b, calculate_risk_score, get_risk_weights


SAMPLE_CVE = {
    "cve_id": "CVE-2024-0001",
    "description": "Apache Log4j remote code execution",
    "summary": "Critical RCE in Log4j",
    "cvss_score": 10.0,
    "severity": "CRITICAL",
    "is_kev": True,
    "epss_score": 0.95,
    "has_poc": True,
    "kev_date_added": "2026-06-01",
    "affected_products": ["apache:log4j"],
    "source_urls": [],
    "public_exploits": [{"type": "metasploit", "source": "Sploitus"}],
}


def test_risk_weights_sum_to_one():
    weights = get_risk_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_risk_score_bounds_and_shape():
    result = calculate_risk_score(
        SAMPLE_CVE,
        profile=None,
        backend_match_score=None,
        momentum_score=0.2,
    )
    assert 0 <= result["total"] <= 100
    assert result["total"] == result["score"]
    assert set(result["components"]) == {
        "asset",
        "kev",
        "epss",
        "exploit",
        "cvss",
        "momentum",
    }
    assert result["components"]["asset"]["score"] == 0.5
    assert result["hasProfile"] is False
    assert result["momentumScore"] == pytest.approx(0.2)


def test_backend_cpe_match_maps_to_asset_tiers():
    score, label = asset_score_from_backend(100)
    assert score == 1.0
    assert "exact CPE" in label
    score, _ = asset_score_from_backend(55)
    assert score == 0.55


def test_profile_to_match_assets_flattens():
    profile = {
        "operatingSystems": [{"product": "Windows", "version": "11"}],
        "applications": [
            {"product": "Log4j", "cpeProduct": "log4j", "vendor": "apache", "version": "2.14"}
        ],
        "aiSystems": ["TensorFlow"],
    }
    assets = profile_to_match_assets(profile)
    assert len(assets) == 3
    assert assets[1]["product"] == "log4j"


def test_profile_to_match_assets_tolerates_non_string_products():
    profile = {
        "operatingSystems": [{"product": 12345}],
        "applications": [{"cpeProduct": "log4j", "vendor": "apache"}],
        "aiSystems": [999, {"product": "TensorFlow"}],
    }
    assets = profile_to_match_assets(profile)
    assert {"product": "12345", "version": "", "vendor": ""} in assets
    assert {"product": "log4j", "version": "", "vendor": "apache"} in assets
    assert {"product": "TensorFlow", "version": "", "vendor": ""} in assets


def test_exploit_score_ignores_none_exploit_fields():
    cve = {
        **SAMPLE_CVE,
        "public_exploits": [{"type": "poc", "title": None, "source": None, "url": None}],
        "source_urls": [],
    }
    score = _exploit_score_v11b(cve)
    assert score == 0.55


def test_fuzzy_asset_match_when_cpe_score_zero():
    profile = {
        "applications": [
            {"product": "Log4j", "cpeProduct": "log4j", "vendor": "apache", "version": ""}
        ],
        "operatingSystems": [],
        "aiSystems": [],
    }
    cve = {
        **SAMPLE_CVE,
        "affected_products": ["apache:log4j"],
    }
    score, match_type = resolve_asset_component(cve, profile, backend_match_score=0)
    assert score >= 0.9
    assert "log4j" in match_type.lower() or "Log4j" in match_type
