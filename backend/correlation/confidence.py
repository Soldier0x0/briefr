"""Deterministic confidence rules and receipt builders (Correlation v2 Phase 2)."""

from __future__ import annotations

from typing import Any

from correlation.freshness import (
    corroboration_factor,
    freshness_context,
    numeric_edge_level,
)

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
    degree: int = 0,
    observed_at: Any = None,
    ingested_at: Any = None,
    now: Any = None,
    corroborated_by: list[str] | None = None,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """Return (confidence, why_not_higher, confidence_factors).

    `degree` (CORR-PR-3) is the IOC's cve_count from ioc_degree -- how many
    distinct CVEs share this indicator. Popular/shared IOCs create
    false-positive-looking clusters, so degree only ever lowers confidence
    and is applied last, after any confirmation-based bump, so a hub can't
    be rescued back up.

    `confidence_factors` (CORR-PR-5) exposes every step that moved the
    level, additive alongside the single `why_not_higher` string kept for
    compatibility (it becomes the last factor's reason).
    """
    t = (ioc_type or "").upper()
    confirmations = confirmations or {}
    factors: list[dict[str, Any]] = []

    if t == "HASH":
        level = "high"
    elif t == "DOMAIN":
        level = "medium"
    elif t == "URL":
        level = "medium"
    elif t == "IP":
        level = "low"
        if is_noise_ip:
            why = "Private or reserved IP range"
            factors.append({"factor": "noise_ip", "reason": why})
            return "low", why, factors
    else:
        level = "low"
    factors.append({"factor": "ioc_type", "value": t, "reason": f"{t.title() if t else 'Unknown'}-type indicator"})

    why: str | None = None

    if confirmations.get("greynoise") == "malicious":
        level = bump_confidence(level, 1)
        factors.append({"factor": "confirmation", "value": "greynoise_malicious", "reason": "GreyNoise classifies this IP as malicious"})
    elif confirmations.get("greynoise") in ("benign", "riot"):
        level = downrank_confidence(level, 1)
        why = "GreyNoise classifies this IP as benign noise"
        factors.append({"factor": "confirmation", "value": "greynoise_benign", "reason": why})
    if confirmations.get("malwarebazaar"):
        level = bump_confidence(level, 1, cap="high")
        factors.append({"factor": "confirmation", "value": "malwarebazaar", "reason": "MalwareBazaar sample match"})
    if confirmations.get("urlhaus_active"):
        level = bump_confidence(level, 1)
        factors.append({"factor": "confirmation", "value": "urlhaus_active", "reason": "URLhaus active distribution"})

    if t == "IP" and level == "low" and not why:
        why = "IP-only edges are weaker than domain or hash matches"
        factors.append({"factor": "ip_only", "reason": why})

    if degree > 10:
        why = f"Shared indicator hub — seen across {degree} CVEs"
        level = "low"
        factors.append({"factor": "degree", "value": degree, "reason": why})
    elif degree > 3:
        downranked = downrank_confidence(level, 1)
        if downranked != level:
            why = f"Shared indicator hub — seen across {degree} CVEs"
            factors.append({"factor": "degree", "value": degree, "reason": why})
        level = downranked

    fresh = freshness_context(
        t,
        observed_at=observed_at,
        ingested_at=ingested_at,
        now=now,
    )
    corroboration_k = 1 + (1 if corroborated_by else 0)
    corroboration = corroboration_factor(corroboration_k)
    fresh_level = numeric_edge_level(
        t,
        degree=degree,
        freshness=fresh["freshness_factor"],
        corroboration_k=corroboration_k,
    )
    if _level_index(fresh_level) < _level_index(level):
        level = fresh_level
        why = fresh["freshness_reason"]
    elif corroborated_by and _level_index(fresh_level) > _level_index(level):
        level = fresh_level
        if level == "high":
            why = None
    factors.append({
        "factor": "corroboration",
        "value": round(corroboration, 4),
        "reason": (
            "Independent ThreatFox observation corroborates this indicator"
            if corroborated_by
            else "Single community (OTX) source"
        ),
    })
    factors.append({
        "factor": "freshness",
        "value": fresh["freshness_factor"],
        "reason": fresh["freshness_reason"],
        **({"freshness_fallback": True} if fresh["freshness_fallback"] else {}),
    })

    return level, why, factors


def aggregate_infrastructure_confidence(
    edges: list[dict[str, Any]],
) -> tuple[str, list[dict], str | None, list[dict[str, Any]]]:
    """Collapse per-IOC edges into one peer confidence + merged evidence."""
    if not edges:
        return "low", [], None, []

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
            **(
                {"observed_at": edge["observed_at"]}
                if edge.get("observed_at") is not None
                else {}
            ),
            **(
                {"ingested_at": edge["ingested_at"]}
                if edge.get("ingested_at") is not None
                else {}
            ),
            **(
                {"freshness_factor": edge["freshness_factor"]}
                if edge.get("freshness_factor") is not None
                else {}
            ),
            **(
                {"freshness_reason": edge["freshness_reason"]}
                if edge.get("freshness_reason")
                else {}
            ),
            **(
                {"freshness_fallback": True}
                if edge.get("freshness_fallback")
                else {}
            ),
            **(
                {"corroborated_by": edge["corroborated_by"]}
                if edge.get("corroborated_by")
                else {}
            ),
        })

    why_parts = [
        e["why_not_higher"] for e in edges
        if e.get("confidence") == confidence and e.get("why_not_higher")
    ]
    why = why_parts[0] if why_parts else None

    # Factors from the edge(s) that set the aggregate level -- same
    # selection logic as `why` above, kept consistent rather than merging
    # every edge's factors into one undifferentiated list.
    factors_parts = [
        e["confidence_factors"] for e in edges
        if e.get("confidence") == confidence and e.get("confidence_factors")
    ]
    factors = factors_parts[0] if factors_parts else []

    return confidence, evidence, why, factors


def campaign_confidence(
    base: str,
    ioc_edges: list[dict[str, Any]],
    *,
    has_same_pulse: bool = True,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    level = base
    why: str | None = None
    factors: list[dict[str, Any]] = []
    if has_same_pulse:
        factors.append({"factor": "same_pulse", "reason": "Co-tagged in the same OTX pulse"})

    strong = [e for e in ioc_edges if (e.get("ioc_type") or "").upper() in ("HASH", "DOMAIN")]
    if has_same_pulse and strong:
        level = "high"
        factors.append({"factor": "shared_indicators", "reason": "Backed by shared hash or domain indicators"})
    elif has_same_pulse:
        level = bump_confidence(base, 0) if base else "medium"

    if not strong and not any((e.get("ioc_type") or "").upper() == "URL" for e in ioc_edges):
        if level == "high":
            level = "medium"
            why = "No shared hash or domain indicators"
            factors.append({"factor": "shared_indicators", "reason": why})

    return level, why, factors


def attribution_conflict(
    otx_adversary: str,
    mitre_actors: list[str],
) -> bool:
    if not otx_adversary or not mitre_actors:
        return False
    otx_lower = otx_adversary.lower()
    for name in mitre_actors:
        if not name:
            continue
        name_lower = name.lower()
        if name_lower in otx_lower or otx_lower in name_lower:
            return False
    return True
