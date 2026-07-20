"""SSVC annotation v1.0 — parallel to OP; does not change Threat or replace P-band.

Deterministic Deployer-flavoured mapping from existing Threat / Environment /
CVE signals (ADR-002 Phase 1 W4). Outcomes align with the documentation
crosswalk P1↔Act, P2↔Attend, P3↔Track*, P4↔Track — OP remains the primary
action surface; this object is an annotation only.
"""

from __future__ import annotations

from typing import Any

VERSION = "ssvc-annotation-1.0"

OUTCOMES = ("Act", "Attend", "Track*", "Track")

# Exploitation status (SSVC-style)
EXPLOITATION_NONE = "none"
EXPLOITATION_POC = "poc"
EXPLOITATION_ACTIVE = "active"

# Technical impact (coarse)
IMPACT_PARTIAL = "partial"
IMPACT_TOTAL = "total"

# Mission prevalence (from Environment + optional W5 flags)
MISSION_LOW = "low"
MISSION_MEDIUM = "medium"
MISSION_HIGH = "high"

_HIGH_ENV = frozenset({"CONFIRMED", "LIKELY"})
_MED_ENV = frozenset({"POSSIBLE", "WEAK"})
# UNKNOWN / NO_MATCH → low unless W5 flags bump (internet_facing / criticality)


def _component_raw(threat: dict, key: str) -> float:
    comp = (threat or {}).get("components") or {}
    entry = comp.get(key) or {}
    try:
        return float(entry.get("raw") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _boolish(value: Any) -> bool:
    return value is True or value == 1 or value == "1" or value == "true"


def _cvss(cve: dict) -> float | None:
    raw = (cve or {}).get("cvss_score")
    if raw is None or raw == "":
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def exploitation_status(threat: dict, cve: dict) -> str:
    """Map Threat/KEV/exploit signals → none | poc | active.

    Active: CISA KEV (``is_kev``) or Threat kev raw > 0, or weaponised /
    Metasploit-grade exploit (exploit raw ≥ 0.88).
    PoC: public PoC / exploit evidence (exploit raw ≥ 0.35 or ``has_poc``).
    None: otherwise.
    """
    cve = cve or {}
    if _boolish(cve.get("is_kev")) or _component_raw(threat, "kev") > 0.0:
        return EXPLOITATION_ACTIVE
    exploit_raw = _component_raw(threat, "exploit")
    if exploit_raw >= 0.88:
        return EXPLOITATION_ACTIVE
    if exploit_raw >= 0.35 or _boolish(cve.get("has_poc")):
        return EXPLOITATION_POC
    return EXPLOITATION_NONE


def technical_impact(cve: dict) -> str:
    """Coarse technical impact from CVSS when present.

    CVSS ≥ 7.0 → total; otherwise (including missing CVSS) → partial.
    Missing CVSS defaults to partial so absence does not fabricate Act.
    """
    score = _cvss(cve)
    if score is not None and score >= 7.0:
        return IMPACT_TOTAL
    return IMPACT_PARTIAL


def mission_prevalence(
    environment: dict,
    *,
    internet_facing: bool | None = None,
    criticality: str | None = None,
) -> str:
    """Mission prevalence from Environment tier + optional W5 profile flags.

    Tier map: CONFIRMED/LIKELY → high; POSSIBLE/WEAK → medium;
    UNKNOWN/NO_MATCH → low. Optional ``criticality`` / ``internet_facing``
    may bump (W5); ``None`` leaves tier-only behaviour.
    """
    tier = ((environment or {}).get("tier") or "UNKNOWN").upper()

    if criticality == "MISSION_CRITICAL":
        base = MISSION_HIGH
    elif criticality == "SUPPORTING":
        base = MISSION_LOW
    elif criticality == "IMPORTANT":
        base = MISSION_MEDIUM
    elif tier in _HIGH_ENV:
        base = MISSION_HIGH
    elif tier in _MED_ENV:
        base = MISSION_MEDIUM
    else:
        base = MISSION_LOW

    # internet_facing bumps when provided (W5); never fabricates high from NO_MATCH alone
    if internet_facing is True:
        if base == MISSION_MEDIUM:
            base = MISSION_HIGH
        elif base == MISSION_LOW and tier != "NO_MATCH":
            base = MISSION_MEDIUM

    if criticality == "MISSION_CRITICAL":
        return MISSION_HIGH
    if criticality == "SUPPORTING" and internet_facing is not True:
        return MISSION_LOW

    return base


def _decide(exploitation: str, impact: str, mission: str) -> tuple[str, str]:
    """Return (outcome, path) for the annotation decision tree.

    Documented mapping (pick Act for CISA KEV + relevant env):
    - Active + high mission → Act
    - Active + medium mission → Attend
    - Active + low mission → Attend if total impact else Track*
    - PoC + high + total → Attend; PoC + high/medium → Track*; else Track
    - None + high + total → Track*; else Track
    """
    if exploitation == EXPLOITATION_ACTIVE:
        if mission == MISSION_HIGH:
            return "Act", "active+high→Act"
        if mission == MISSION_MEDIUM:
            return "Attend", "active+medium→Attend"
        if impact == IMPACT_TOTAL:
            return "Attend", "active+low+total→Attend"
        return "Track*", "active+low+partial→Track*"

    if exploitation == EXPLOITATION_POC:
        if mission == MISSION_HIGH and impact == IMPACT_TOTAL:
            return "Attend", "poc+high+total→Attend"
        if mission in (MISSION_HIGH, MISSION_MEDIUM):
            return "Track*", f"poc+{mission}→Track*"
        return "Track", "poc+low→Track"

    # none
    if mission == MISSION_HIGH and impact == IMPACT_TOTAL:
        return "Track*", "none+high+total→Track*"
    return "Track", f"none+{mission}→Track"


def calculate_ssvc_outcome(
    *,
    threat: dict,
    environment: dict,
    cve: dict,
    internet_facing: bool | None = None,
    criticality: str | None = None,
    privileged_service: bool | None = None,
    ot_safety: bool | None = None,
) -> dict:
    """Return SSVC annotation ``{version, outcome, factors, path}``.

    Outcomes are exactly ``Act`` | ``Attend`` | ``Track*`` | ``Track``.
    Does not mutate Threat or Operational Priority.
    Optional W5 flags (``internet_facing``, ``criticality``, …) affect
    mission prevalence / factors only when present.
    """
    threat = threat or {}
    environment = environment or {}
    cve = cve or {}

    exploitation = exploitation_status(threat, cve)
    impact = technical_impact(cve)
    mission = mission_prevalence(
        environment,
        internet_facing=internet_facing,
        criticality=criticality,
    )
    outcome, path = _decide(exploitation, impact, mission)

    if outcome not in OUTCOMES:
        outcome = "Track"
        path = f"{path}|fallback→Track"

    factors = {
        "exploitation": exploitation,
        "technical_impact": impact,
        "mission_prevalence": mission,
        "environment_tier": (environment.get("tier") or "UNKNOWN"),
        "threat_band": threat.get("band"),
        "internet_facing": internet_facing,
        "criticality": criticality,
        "privileged_service": privileged_service,
        "ot_safety": ot_safety,
    }

    return {
        "version": VERSION,
        "outcome": outcome,
        "factors": factors,
        "path": path,
    }
