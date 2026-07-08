"""Tests for Environment Relevance tiers v1.0 (ADR-002)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.environment import classify_environment


SAMPLE_CVE = {
    "cve_id": "CVE-2024-ENV",
    "description": "Apache Log4j remote code execution",
    "affected_products": ["apache:log4j"],
}


def test_unknown_without_profile():
    result = classify_environment(SAMPLE_CVE, profile=None, backend_match_score=None)
    assert result["tier"] == "UNKNOWN"
    assert result["score"] is None
    assert result["version_verified"] is False


def test_no_match_distinct_from_unknown():
    profile = {
        "applications": [{"product": "Unrelated", "cpeProduct": "other", "vendor": "x"}],
        "operatingSystems": [],
        "aiSystems": [],
    }
    cve = {**SAMPLE_CVE, "affected_products": ["totally:unrelated"]}
    result = classify_environment(cve, profile=profile, backend_match_score=0)
    assert result["tier"] == "NO_MATCH"
    assert result["score"] == 0.0


def test_confirmed_backend_cpe_100():
    profile = {"applications": [], "operatingSystems": [], "aiSystems": []}
    result = classify_environment(SAMPLE_CVE, profile=profile, backend_match_score=100)
    assert result["tier"] == "CONFIRMED"
    assert result["version_verified"] is True


def test_likely_product_match_without_version():
    profile = {
        "applications": [
            {"product": "Log4j", "cpeProduct": "log4j", "vendor": "apache", "version": ""}
        ],
        "operatingSystems": [],
        "aiSystems": [],
    }
    result = classify_environment(SAMPLE_CVE, profile=profile, backend_match_score=0)
    assert result["tier"] == "LIKELY"
    assert result["version_verified"] is False


def test_weak_description_overlap():
    profile = {
        "applications": [],
        "operatingSystems": [],
        "aiSystems": ["TensorFlow"],
    }
    cve = {
        **SAMPLE_CVE,
        "description": "Issue in TensorFlow model loading",
        "affected_products": ["google:tensorflow"],
    }
    result = classify_environment(cve, profile=profile, backend_match_score=0)
    assert result["tier"] in ("WEAK", "POSSIBLE")
