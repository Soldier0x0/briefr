"""Deterministic confidence rules and receipt builders (Correlation v2 Phase 2)."""

from __future__ import annotations

from typing import Any

_LEVELS = ("low", "medium", "high")


def _level_index(level: str) -> int:
    try:
        return _LEVELS.index(level)
    except ValueError:
        return 0


def bump_confidence(level: str, steps: int = 1, cap: str = "high") -> str:
    idx = min(_level_index(level) + steps, _level_index(cap))
    return _LEVELS[idx]


def downrank_confidence(level: str, steps: int = 1, floor: str = "low") -> str:
    idx = max(_level_index(level) - steps, _level_index(floor))
    return _LEVELS[idx]


def confidence_for_ioc_edge(
    ioc_type: str,
    *,
    confirmations: dict[str, Any] | None = None,
    is_noise_ip: bool = False,
) -> tuple[str, str | None]:
    """Return (confidence, why_not_higher)."""
    t = (ioc_type or "").upper()
    confirmations = confirmations or {}

    if t == "HASH":
        level = "high"
    elif t == "DOMAIN":
        level = "medium"
    elif t == "URL":
        level = "medium"
    elif t == "IP":
        level = "low"
        if is_noise_ip:
            return "low", "Private or reserved IP range"
    else:
        level = "low"

    why: str | None = None

    if confirmations.get("greynoise") == "malicious":
        level = bump_confidence(level, 1)
    elif confirmations.get("greynoise") in ("benign", "riot"):
        level = downrank_confidence(level, 1)
        why = "GreyNoise classifies this IP as benign noise"
    if confirmations.get("malwarebazaar"):
        level = bump_confidence(level, 1, cap="high")
    if confirmations.get("urlhaus_active"):
        level = bump_confidence(level, 1)

    if t == "IP" and level == "low" and not why:
        why = "IP-only edges are weaker than domain or hash matches"

    return level, why


def aggregate_infrastructure_confidence(
    edges: list[dict[str, Any]],
) -> tuple[str, list[dict], str | None]:
    """Collapse per-IOC edges into one peer confidence + merged evidence."""
    if not edges:
        return "low", [], None

    levels = [e.get("confidence", "low") for e in edges]
    max_idx = max(_level_index(l) for l in levels)
    confidence = _LEVELS[max_idx]
    evidence = []
    for edge in edges:
        evidence.append({
            "type": "shared_indicator",
            "ioc_type": edge.get("ioc_type", ""),
            "value": edge.get("ioc_value", ""),
            **({"confirmation": edge["confirmation"]} if edge.get("confirmation") else {}),
        })

    why_parts = [e["why_not_higher"] for e in edges if e.get("why_not_higher")]
    why = why_parts[0] if why_parts else None
    return confidence, evidence, why


def campaign_confidence(
    base: str,
    ioc_edges: list[dict[str, Any]],
    *,
    has_same_pulse: bool = True,
) -> tuple[str, str | None]:
    level = base
    why: str | None = None

    strong = [e for e in ioc_edges if (e.get("ioc_type") or "").upper() in ("HASH", "DOMAIN")]
    if has_same_pulse and strong:
        level = "high"
    elif has_same_pulse:
        level = bump_confidence(base, 0) if base else "medium"

    if not strong and not any((e.get("ioc_type") or "").upper() == "URL" for e in ioc_edges):
        if level == "high":
            level = "medium"
            why = "No shared hash or domain indicators"

    return level, why


def attribution_conflict(
    otx_adversary: str,
    mitre_actors: list[str],
) -> bool:
    if not otx_adversary or not mitre_actors:
        return False
    otx_lower = otx_adversary.lower()
    for name in mitre_actors:
        if name and name.lower() not in otx_lower and otx_lower not in name.lower():
            return True
    return False
