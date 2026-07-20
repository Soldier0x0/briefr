"""Tests for SSVC annotation (Phase 1 W4 / Task 11)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.environment import classify_environment
from scoring.ssvc import OUTCOMES, VERSION, calculate_ssvc_outcome
from scoring.threat import calculate_threat_score


def _recent_kev_date() -> str:
    return (date.today() - timedelta(days=3)).isoformat()


def _threat_env(
    *,
    cvss=0.0,
    is_kev=False,
    epss=0.0,
    has_poc=False,
    exploit_type=None,
    momentum=0.0,
    profile=None,
    backend_match=None,
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
    return cve, threat, env


def test_cisa_kev_confirmed_env_is_act():
    """CISA KEV + CONFIRMED-like environment → Act (documented W4 choice)."""
    profile = {"applications": [{"product": "x"}], "operatingSystems": [], "aiSystems": []}
    cve, threat, env = _threat_env(
        cvss=9.8,
        is_kev=True,
        profile=profile,
        backend_match=100,
    )
    assert env["tier"] == "CONFIRMED"
    assert threat["band"] == "CRIT"

    ssvc = calculate_ssvc_outcome(threat=threat, environment=env, cve=cve)
    assert ssvc["outcome"] == "Act"
    assert ssvc["factors"]["exploitation"] == "active"
    assert ssvc["factors"]["mission_prevalence"] == "high"
    assert "Act" in ssvc["path"]
    assert ssvc["version"] == VERSION


def test_low_threat_no_match_is_track():
    """LOW threat + NO_MATCH environment → Track."""
    profile = {
        "applications": [{"product": "unrelated-app"}],
        "operatingSystems": [],
        "aiSystems": [],
    }
    cve, threat, env = _threat_env(
        cvss=3.1,
        is_kev=False,
        epss=0.0,
        profile=profile,
        backend_match=0,
    )
    assert threat["band"] == "LOW"
    assert env["tier"] == "NO_MATCH"

    ssvc = calculate_ssvc_outcome(threat=threat, environment=env, cve=cve)
    assert ssvc["outcome"] == "Track"
    assert ssvc["factors"]["exploitation"] == "none"
    assert ssvc["factors"]["mission_prevalence"] == "low"


def test_outcomes_only_four_strings():
    """Every outcome must be one of Act | Attend | Track* | Track."""
    cases = [
        dict(cvss=9.8, is_kev=True, backend_match=100),
        dict(cvss=7.0, is_kev=True, backend_match=0),
        dict(cvss=5.0, has_poc=True, backend_match=None),
        dict(cvss=2.0, is_kev=False, backend_match=0),
        dict(cvss=9.0, exploit_type="poc", backend_match=80),
        dict(cvss=None, is_kev=False, backend_match=None),
    ]
    profile = {"applications": [{"product": "x"}], "operatingSystems": [], "aiSystems": []}
    seen = set()
    for kwargs in cases:
        bm = kwargs.pop("backend_match", None)
        # cvss None → omit key so threat treats missing
        cvss = kwargs.pop("cvss", 0.0)
        cve_kwargs = {**kwargs}
        if cvss is not None:
            cve_kwargs["cvss"] = cvss
        else:
            cve_kwargs["cvss"] = None
        cve, threat, env = _threat_env(
            profile=profile if bm is not None else None,
            backend_match=bm,
            **{k: v for k, v in cve_kwargs.items() if k != "cvss"},
            cvss=cvss if cvss is not None else 0.0,
        )
        if cvss is None:
            cve["cvss_score"] = None
        ssvc = calculate_ssvc_outcome(threat=threat, environment=env, cve=cve)
        assert ssvc["outcome"] in OUTCOMES
        seen.add(ssvc["outcome"])
        assert isinstance(ssvc["path"], str) and ssvc["path"]
        assert "factors" in ssvc

    # Sanity: we exercised more than one outcome in the fixture set
    assert len(seen) >= 2


def test_w5_flags_accepted_as_none_without_change():
    """Optional internet_facing / criticality may be None (W5 will flesh)."""
    cve, threat, env = _threat_env(cvss=4.0, is_kev=False)
    a = calculate_ssvc_outcome(threat=threat, environment=env, cve=cve)
    b = calculate_ssvc_outcome(
        threat=threat,
        environment=env,
        cve=cve,
        internet_facing=None,
        criticality=None,
    )
    assert a == b


def test_mission_critical_flag_can_raise_to_act_with_kev():
    """When W5 criticality is provided with Active exploitation → Act path."""
    cve, threat, env = _threat_env(cvss=8.0, is_kev=True)  # UNKNOWN env
    assert env["tier"] == "UNKNOWN"
    ssvc = calculate_ssvc_outcome(
        threat=threat,
        environment=env,
        cve=cve,
        criticality="MISSION_CRITICAL",
    )
    assert ssvc["outcome"] == "Act"
    assert ssvc["factors"]["mission_prevalence"] == "high"
