"""Tests for Operational Priority v1.0 (ADR-002)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.environment import classify_environment
from scoring.priority import (
    correlation_escalation,
    derive_operational_priority,
    operational_priority_sort_key,
)
from scoring.threat import calculate_threat_score


def _recent_kev_date() -> str:
    return (date.today() - timedelta(days=3)).isoformat()


def _scenario(
    *,
    cvss,
    is_kev=False,
    epss=0.0,
    has_poc=False,
    exploit_type=None,
    momentum=0.0,
    profile=None,
    backend_match=None,
    correlation=None,
):
    cve = {
        "is_kev": is_kev,
        "kev_date_added": _recent_kev_date() if is_kev else None,
        "cvss_score": cvss,
        "epss_score": epss,
        "has_poc": has_poc,
        "public_exploits": [{"type": exploit_type}] if exploit_type else [],
        "affected_products": ["vendor:product"],
    }
    threat = calculate_threat_score(cve, momentum_score=momentum)
    env = classify_environment(cve, profile, backend_match)
    corr_esc = correlation_escalation(correlation)
    op = derive_operational_priority(threat["band"], env["tier"], corr_escalation=corr_esc)
    return threat, env, op


def test_s1_kev_low_epss_unknown_provisional_p1():
    threat, env, op = _scenario(
        cvss=9.8, is_kev=True, epss=0.02, has_poc=True, exploit_type="poc", momentum=0.8
    )
    assert threat["score"] >= 80
    assert env["tier"] == "UNKNOWN"
    assert op["band"] == "P1"
    assert op["provisional"] is True


def test_s3_no_match_deescalates():
    profile = {"applications": [], "operatingSystems": [], "aiSystems": []}
    threat, env, op = _scenario(
        cvss=9.8,
        is_kev=True,
        epss=0.02,
        has_poc=True,
        exploit_type="poc",
        momentum=0.8,
        profile=profile,
        backend_match=0,
    )
    assert threat["score"] >= 80
    assert env["tier"] == "NO_MATCH"
    assert op["band"] == "P3"
    assert op["provisional"] is False


def test_s4_high_cvss_no_exploitation_p4():
    threat, env, op = _scenario(cvss=9.8, epss=0.05, momentum=0.1)
    assert threat["band"] == "LOW"
    assert env["tier"] == "UNKNOWN"
    assert op["band"] == "P4"


def test_s6_crit_possible_p2_not_p1():
    profile = {
        "applications": [{"product": "X", "cpeProduct": "x", "vendor": "v", "version": ""}],
        "operatingSystems": [],
        "aiSystems": [],
    }
    cve = {
        "is_kev": True,
        "kev_date_added": _recent_kev_date(),
        "cvss_score": 9.8,
        "epss_score": 0.9,
        "has_poc": True,
        "public_exploits": [{"type": "metasploit"}],
        "affected_products": ["v:product"],
    }
    threat = calculate_threat_score(cve, momentum_score=0.8)
    env = classify_environment(cve, profile, backend_match_score=0)
    op = derive_operational_priority(threat["band"], env["tier"])
    assert threat["band"] == "CRIT"
    assert env["tier"] in ("POSSIBLE", "LIKELY")
    assert op["band"] == "P2"


def test_s7_correlation_escalates_p3_to_p2():
    op = derive_operational_priority("MED", "UNKNOWN", corr_escalation=True)
    assert op["band"] == "P2"
    assert op["escalated_by_correlation"] is True


def test_corr_escalation_high_unknown_p2_to_p1_fe_parity():
    """W2: FE applyCorrelationEscalationToRiskScore must match this contract."""
    base = derive_operational_priority("HIGH", "UNKNOWN", corr_escalation=False)
    assert base["band"] == "P2"
    bumped = derive_operational_priority("HIGH", "UNKNOWN", corr_escalation=True)
    assert bumped["band"] == "P1"
    assert bumped["escalated_by_correlation"] is True
    assert bumped["base_band"] == "P2"

def test_correlation_escalation_requires_strong_edge():
    weak = {
        "campaigns": [
            {
                "lifecycle": "active",
                "confidence": "high",
                "member_count": 3,
                "evidence": [
                    {"type": "same_pulse", "pulse_id": "p1"},
                    {"type": "shared_indicator", "ioc_type": "IP", "value": "1.2.3.4"},
                ],
            }
        ]
    }
    strong = {
        "campaigns": [
            {
                "lifecycle": "active",
                "confidence": "high",
                "member_count": 3,
                "evidence": [
                    {"type": "same_pulse", "pulse_id": "p1"},
                    {"type": "shared_indicator", "ioc_type": "HASH", "value": "abc"},
                ],
            }
        ]
    }
    assert correlation_escalation(weak) is False
    assert correlation_escalation(strong) is True


def test_p4_never_escalated():
    op = derive_operational_priority("LOW", "NO_MATCH", corr_escalation=True)
    assert op["band"] == "P4"
    assert op["escalated_by_correlation"] is False


def test_sort_key_stable():
    k1 = operational_priority_sort_key("P2", 65.0, "UNKNOWN", "CVE-2024-0002")
    k2 = operational_priority_sort_key("P2", 65.0, "UNKNOWN", "CVE-2024-0001")
    assert k1 > k2
    k_high_threat = operational_priority_sort_key("P2", 70.0, "UNKNOWN", "CVE-2024-0001")
    k_low_threat = operational_priority_sort_key("P2", 60.0, "UNKNOWN", "CVE-2024-0001")
    assert k_high_threat < k_low_threat
