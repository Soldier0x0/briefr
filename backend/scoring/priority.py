"""Operational Priority v1.0 — rule-based P1–P4 bands (ADR-002)."""

from __future__ import annotations

from typing import Any

from scoring.environment import TIER_RANK

VERSION = "operational-priority-1.0"

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
    ("CRIT", "CONFIRMED"): "Critical threat with confirmed vulnerable version in your stack.",
    ("CRIT", "LIKELY"): "Critical threat; product overlap — verify exact version.",
    ("CRIT", "POSSIBLE"): "Critical threat; partial stack overlap — verify before treating as in-scope.",
    ("CRIT", "WEAK"): "Critical threat; weak textual overlap only — verify version.",
    ("CRIT", "UNKNOWN"): "Critical threat; environment unknown — provisional priority.",
    ("CRIT", "NO_MATCH"): "Critical threat but no asset profile match — lower urgency for your stack.",
    ("HIGH", "CONFIRMED"): "High threat with confirmed version match — investigate immediately.",
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
) -> dict[str, Any]:
    """Deterministic P1–P4 band from threat × environment, optional correlation bump."""
    base = _base_priority(threat_band, env_tier)
    provisional = env_tier == "UNKNOWN"
    escalated = False
    band = base

    if corr_escalation and band in ("P2", "P3"):
        band = _escalate_band(band)
        escalated = band != base

    rationale = _RATIONALE.get((threat_band, env_tier), f"{threat_band} threat in {env_tier} environment.")
    if provisional:
        rationale = (
            f"{rationale} Environment unknown — priority may change once a profile is loaded."
        )
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
