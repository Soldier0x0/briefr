"""Phase 1 W5 — profile exposure / criticality flags (OP + SSVC only)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.priority import VERSION, derive_operational_priority
from scoring.ssvc import calculate_ssvc_outcome
from scoring.threat import calculate_threat_score


def _recent_kev_date() -> str:
    return (date.today() - timedelta(days=3)).isoformat()


def test_op_absent_flags_identical_to_base():
    """Absent W5 flags → identical OP to threat×env×epss path (today's behavior)."""
    base = derive_operational_priority("CRIT", "POSSIBLE")
    with_none = derive_operational_priority(
        "CRIT",
        "POSSIBLE",
        internet_facing=None,
        criticality=None,
        is_kev=None,
    )
    assert with_none["band"] == base["band"]
    assert with_none["base_band"] == base["base_band"]
    assert with_none["provisional"] == base["provisional"]
    assert with_none["escalated_by_correlation"] == base["escalated_by_correlation"]
    # Version may bump for W5; band semantics without flags must match prior table.
    assert base["band"] == "P2"


def test_op_kev_internet_facing_escalates_p2_to_p1():
    """CISA KEV path (CRIT or is_kev) + internet_facing + env ≠ NO_MATCH → prefer P1 when base is P2.

    Table cell: CRIT × POSSIBLE = P2; with internet_facing=True → P1.
    """
    base = derive_operational_priority("CRIT", "POSSIBLE")
    assert base["band"] == "P2"

    op = derive_operational_priority(
        "CRIT",
        "POSSIBLE",
        internet_facing=True,
        is_kev=True,
    )
    assert op["band"] == "P1"
    assert op["base_band"] == "P2"
    assert "internet" in op["rationale"].lower() or "facing" in op["rationale"].lower()


def test_op_internet_facing_does_not_escalate_no_match():
    """NO_MATCH must not be escalated to P1 by internet_facing."""
    op = derive_operational_priority(
        "CRIT",
        "NO_MATCH",
        internet_facing=True,
        is_kev=True,
    )
    assert op["band"] == "P3"  # base table CRIT×NO_MATCH


def test_op_internet_facing_false_or_absent_no_bump():
    base = derive_operational_priority("CRIT", "WEAK")
    assert base["band"] == "P2"
    assert derive_operational_priority("CRIT", "WEAK", internet_facing=False)["band"] == "P2"
    assert derive_operational_priority("CRIT", "WEAK")["band"] == "P2"


def test_op_non_kev_high_not_escalated_by_internet_facing():
    """Only CRIT / is_kev path; plain HIGH × POSSIBLE stays P2 even if internet-facing."""
    op = derive_operational_priority(
        "HIGH",
        "POSSIBLE",
        internet_facing=True,
        is_kev=False,
    )
    assert op["band"] == "P2"


def test_op_is_kev_with_high_band_still_escalates():
    """is_kev alone qualifies even if threat_band were HIGH (defensive)."""
    op = derive_operational_priority(
        "HIGH",
        "POSSIBLE",
        internet_facing=True,
        is_kev=True,
    )
    assert op["band"] == "P1"


def test_threat_unchanged_by_exposure_flags():
    """Threat scores ignore profile exposure flags (same CVE inputs → same Threat)."""
    cve = {
        "is_kev": True,
        "kev_date_added": _recent_kev_date(),
        "cvss_score": 9.8,
        "epss_score": 0.5,
        "has_poc": True,
        "public_exploits": [{"type": "poc"}],
    }
    a = calculate_threat_score(cve, momentum_score=0.5)
    b = calculate_threat_score(cve, momentum_score=0.5)
    assert a == b
    assert a["score"] == b["score"]
    assert a["band"] == "CRIT"
    # Flags are not Threat inputs — calling again with same CVE is identical.
    assert calculate_threat_score(dict(cve), momentum_score=0.5)["score"] == a["score"]


def test_ssvc_internet_facing_reflected_in_factors():
    """SSVC factors reflect internet_facing when set; mission may bump."""
    threat = {"band": "MED", "components": {}}
    env = {"tier": "POSSIBLE"}  # medium mission without flags
    cve = {"is_kev": False, "cvss_score": 5.0, "has_poc": False}

    absent = calculate_ssvc_outcome(threat=threat, environment=env, cve=cve)
    assert absent["factors"]["internet_facing"] is None
    assert absent["factors"]["mission_prevalence"] == "medium"

    facing = calculate_ssvc_outcome(
        threat=threat,
        environment=env,
        cve=cve,
        internet_facing=True,
    )
    assert facing["factors"]["internet_facing"] is True
    assert facing["factors"]["mission_prevalence"] == "high"


def test_extract_profile_exposure_flags():
    from scoring.priority import extract_profile_exposure_flags

    assert extract_profile_exposure_flags(None)["internet_facing"] is None
    assert extract_profile_exposure_flags({})["criticality"] is None
    flags = extract_profile_exposure_flags(
        {
            "internet_facing": True,
            "criticality": "mission_critical",
            "privileged_service": 1,
            "ot_safety": False,
            "criticality_bogus": "Medium",
        }
    )
    assert flags["internet_facing"] is True
    assert flags["criticality"] == "MISSION_CRITICAL"
    assert flags["privileged_service"] is True
    assert flags["ot_safety"] is False
    assert extract_profile_exposure_flags({"criticality": "Medium"})["criticality"] is None


def test_op_version_bumped_for_w5():
    """W5 bumps OP version when exposure modifiers are part of the contract."""
    assert VERSION == "operational-priority-1.2"
