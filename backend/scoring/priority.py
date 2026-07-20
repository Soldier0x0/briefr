"""Operational Priority v1.2 — rule-based P1–P4 bands (ADR-002 + W3 EPSS + W5 exposure)."""

from __future__ import annotations

from typing import Any

from scoring.environment import TIER_RANK

VERSION = "operational-priority-1.2"

# W5 profile criticality values (OP/SSVC only; never Threat)
CRITICALITY_VALUES = frozenset({"MISSION_CRITICAL", "IMPORTANT", "SUPPORTING"})

PRIORITY_ORDER = ("P1", "P2", "P3", "P4")
PRIORITY_RANK = {band: idx for idx, band in enumerate(PRIORITY_ORDER)}

# Threat band → env tier → base priority (POSSIBLE and WEAK share a column)
_BASE_TABLE: dict[str, dict[str, str]] = {
    "CRIT": {
        "CONFIRMED": "P1",
        "LIKELY": "P1",
        "POSSIBLE": "P2",
        "WEAK": "P2",
        "UNKNOWN": "P1",
        "NO_MATCH": "P3",
    },
    "HIGH": {
        "CONFIRMED": "P1",
        "LIKELY": "P2",
        "POSSIBLE": "P2",
        "WEAK": "P2",
        "UNKNOWN": "P2",
        "NO_MATCH": "P3",
    },
    "MED": {
        "CONFIRMED": "P2",
        "LIKELY": "P2",
        "POSSIBLE": "P3",
        "WEAK": "P3",
        "UNKNOWN": "P3",
        "NO_MATCH": "P4",
    },
    "LOW": {
        "CONFIRMED": "P3",
        "LIKELY": "P3",
        "POSSIBLE": "P4",
        "WEAK": "P4",
        "UNKNOWN": "P4",
        "NO_MATCH": "P4",
    },
}

_RATIONALE: dict[tuple[str, str], str] = {
    ("CRIT", "CONFIRMED"): "Strong exploitation signals with confirmed vulnerable version in My Stack.",
    ("CRIT", "LIKELY"): "Strong exploitation signals; product overlap — verify exact version.",
    ("CRIT", "POSSIBLE"): "Strong exploitation signals; partial stack overlap — verify before treating as in-scope.",
    ("CRIT", "WEAK"): "Strong exploitation signals; weak textual overlap only — verify version.",
    ("CRIT", "UNKNOWN"): "Strong exploitation signals; environment not assessed — provisional priority.",
    ("CRIT", "NO_MATCH"): "Strong exploitation signals but no My Stack match — lower urgency for your environment.",
    ("HIGH", "CONFIRMED"): "High exploitation signals with a confirmed vulnerable version match in My Stack — investigate exposure.",
    ("HIGH", "LIKELY"): "High threat with unverified product overlap.",
    ("HIGH", "POSSIBLE"): "High threat with partial overlap — verify version.",
    ("HIGH", "WEAK"): "High threat with weak overlap — verify relevance.",
    ("HIGH", "UNKNOWN"): "High threat; environment unknown — provisional priority.",
    ("HIGH", "NO_MATCH"): "High threat but not matched to your profile.",
    ("MED", "CONFIRMED"): "Moderate threat affecting a confirmed asset — schedule investigation.",
    ("MED", "LIKELY"): "Moderate threat with product overlap.",
    ("MED", "POSSIBLE"): "Moderate threat with unverified overlap.",
    ("MED", "WEAK"): "Moderate threat with weak overlap.",
    ("MED", "UNKNOWN"): "Moderate threat; environment unknown — provisional priority.",
    ("MED", "NO_MATCH"): "Moderate threat with no stack match — informational.",
    ("LOW", "CONFIRMED"): "Low active threat but asset match — scheduled review.",
    ("LOW", "LIKELY"): "Low threat with product overlap.",
    ("LOW", "POSSIBLE"): "Low threat — informational.",
    ("LOW", "WEAK"): "Low threat — informational.",
    ("LOW", "UNKNOWN"): "Low active threat — informational unless environment changes.",
    ("LOW", "NO_MATCH"): "Low threat with no stack relevance.",
}


def correlation_escalation(correlation_result: dict[str, Any] | None) -> bool:
    """
    True when an active/emerging campaign has ≥1 high-confidence edge
    (same-pulse + shared hash/domain). IP-only weak edges do not qualify.
    """
    if not correlation_result:
        return False
    for camp in correlation_result.get("campaigns") or []:
        lifecycle = (camp.get("lifecycle") or "").lower()
        if lifecycle not in ("active", "emerging"):
            continue
        if (camp.get("confidence") or "").lower() != "high":
            continue
        if (camp.get("member_count") or 0) < 2:
            continue
        evidence = camp.get("evidence") or []
        has_same_pulse = any(e.get("type") == "same_pulse" for e in evidence)
        has_strong_ioc = any(
            e.get("type") == "shared_indicator"
            and (e.get("ioc_type") or "").upper() in ("HASH", "DOMAIN")
            for e in evidence
        )
        if has_same_pulse and has_strong_ioc:
            return True
    return False


def _base_priority(threat_band: str, env_tier: str) -> str:
    row = _BASE_TABLE.get(threat_band, _BASE_TABLE["LOW"])
    return row.get(env_tier, row.get("UNKNOWN", "P4"))


def _escalate_band(band: str) -> str:
    idx = PRIORITY_RANK.get(band, 3)
    if idx == 0 or idx >= 3:
        return band
    return PRIORITY_ORDER[idx - 1]


def derive_operational_priority(
    threat_band: str,
    env_tier: str,
    corr_escalation: bool = False,
    *,
    epss: float | None = None,
    epss_rising: bool = False,
    internet_facing: bool | None = None,
    criticality: str | None = None,
    is_kev: bool | None = None,
) -> dict[str, Any]:
    """Deterministic P1–P4 band from threat × environment, optional EPSS/exposure/correlation bumps.

    EPSS rules are additive (ADR-002 addendum / W3): they never change Threat and
    never de-escalate KEV/CRIT dominance. Escalations stack with correlation but
    never past P1. Missing EPSS is treated as 0.0.

    W5 exposure (ADR-002 addendum): optional profile flags affect OP only.
    Absent flags preserve pre-W5 bands. Rule — CISA KEV path (``threat_band``
    CRIT or ``is_kev``) + ``internet_facing=True`` + env tier not NO_MATCH →
    prefer P1 when the working band would otherwise be P2 (e.g. CRIT×POSSIBLE/
    WEAK). ``criticality`` is accepted for explainability / future OP use; SSVC
    consumes it today. Never mutates Threat.
    """
    base = _base_priority(threat_band, env_tier)
    provisional = env_tier == "UNKNOWN"
    escalated = False
    band = base
    epss_val = 0.0 if epss is None else float(epss)
    env_ge_possible = TIER_RANK.get(env_tier, 0) >= TIER_RANK["POSSIBLE"]
    epss_notes: list[str] = []
    exposure_notes: list[str] = []

    # Absolute EPSS ≥ 0.5: one-band escalate for HIGH/MED when Environment ≥ POSSIBLE
    if (
        threat_band in ("HIGH", "MED")
        and epss_val >= 0.5
        and env_ge_possible
        and band != "P1"
    ):
        bumped = _escalate_band(band)
        if bumped != band:
            band = bumped
            epss_notes.append("Escalated one band due to EPSS ≥ 0.5.")

    # Rising EPSS: allow P3→P2 when Environment ≥ POSSIBLE (base would be P3)
    if epss_rising and env_ge_possible and base == "P3" and band == "P3":
        band = "P2"
        epss_notes.append("Escalated P3→P2 due to rising EPSS.")

    # W5: KEV/CRIT + internet-facing + env not NO_MATCH → prefer P1 over P2
    kev_path = threat_band == "CRIT" or is_kev is True
    if (
        kev_path
        and internet_facing is True
        and env_tier != "NO_MATCH"
        and band == "P2"
    ):
        band = "P1"
        exposure_notes.append(
            "Escalated P2→P1: CISA KEV / CRIT threat with internet-facing asset "
            "(Environment not NO_MATCH)."
        )

    if corr_escalation and band in ("P2", "P3"):
        prev = band
        band = _escalate_band(band)
        escalated = band != prev

    rationale = _RATIONALE.get((threat_band, env_tier), f"{threat_band} threat in {env_tier} environment.")
    if provisional:
        rationale = (
            f"{rationale} Environment unknown — priority may change once a profile is loaded."
        )
    for note in epss_notes:
        rationale = f"{rationale} {note}"
    for note in exposure_notes:
        rationale = f"{rationale} {note}"
    if escalated:
        rationale = (
            f"{rationale} Escalated one band due to high-confidence active campaign linkage."
        )

    return {
        "version": VERSION,
        "band": band,
        "provisional": provisional,
        "escalated_by_correlation": escalated,
        "rationale": rationale,
        "base_band": base,
    }


def extract_profile_exposure_flags(profile: dict | None) -> dict[str, Any]:
    """Pull optional W5 exposure fields from a My Stack / risk profile dict.

    Absent keys → None (today's OP/SSVC behaviour). Invalid criticality → None.
    Optional ``privileged_service`` / ``ot_safety`` are bools when present.
    """
    out: dict[str, Any] = {
        "internet_facing": None,
        "criticality": None,
        "privileged_service": None,
        "ot_safety": None,
    }
    if not isinstance(profile, dict):
        return out

    if "internet_facing" in profile:
        raw = profile.get("internet_facing")
        if raw is not None:
            out["internet_facing"] = bool(raw)

    crit_raw = profile.get("criticality")
    if isinstance(crit_raw, str):
        crit = crit_raw.strip().upper()
        if crit in CRITICALITY_VALUES:
            out["criticality"] = crit

    for key in ("privileged_service", "ot_safety"):
        if key in profile and profile.get(key) is not None:
            out[key] = bool(profile.get(key))

    return out



def operational_priority_sort_key(
    op_band: str,
    threat_score: float,
    env_tier: str,
    cve_id: str,
) -> tuple[int, float, int, str]:
    """P1 first, then Threat desc, Environment tier rank, cve_id asc."""
    return (
        PRIORITY_RANK.get(op_band, 3),
        -float(threat_score or 0),
        -TIER_RANK.get(env_tier, 0),
        (cve_id or "").upper(),
    )
