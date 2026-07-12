"""Combined correlation priority score (Correlation v3).

Mirrors scoring/risk.py's additive-capped-contribution model: each
correlation signal (campaign, infrastructure, actor, temporal) contributes
up to a fixed point cap, scaled by its own confidence/strength, summed and
capped at 100. Lets an analyst triage from one ranked number instead of
four independent arrays.
"""

from __future__ import annotations

from typing import Any

CAP_CAMPAIGN = 40
CAP_INFRASTRUCTURE = 25
CAP_ACTOR = 20
CAP_TEMPORAL = 15

_CONFIDENCE_FRACTION = {"high": 1.0, "medium": 0.625, "low": 0.25}


def _confidence_fraction(value: str) -> float:
    return _CONFIDENCE_FRACTION.get((value or "").lower(), 0.0)


def _best_by_confidence(items: list[dict]) -> dict:
    return max(items, key=lambda i: _confidence_fraction(i.get("confidence")))


def _campaign_contribution(campaigns: list[dict]) -> tuple[float, str | None]:
    if not campaigns:
        return 0.0, None
    best = _best_by_confidence(campaigns)
    fraction = _confidence_fraction(best.get("confidence"))
    # CORR-PR-4: KEV/exploit status moved here from confidence.py -- it's a
    # priority (urgency) signal, not evidence the link itself is more certain.
    boosters = best.get("boosters") or {}
    booster_bonus = 0.15 if (boosters.get("kev") or boosters.get("exploit")) else 0.0
    points = round(CAP_CAMPAIGN * min(1.0, fraction + booster_bonus), 1)
    if points <= 0:
        return 0.0, None
    sentence = (
        f"Linked to a {best.get('confidence', 'low')}-confidence campaign "
        f"({best.get('label', 'OTX pulse')})."
    )
    if boosters.get("kev"):
        sentence += " Includes a KEV-listed member."
    elif boosters.get("exploit"):
        sentence += " Includes a publicly exploited member."
    return points, sentence


def _infrastructure_contribution(infrastructure: list[dict]) -> tuple[float, str | None]:
    if not infrastructure:
        return 0.0, None
    best = _best_by_confidence(infrastructure)
    fraction = _confidence_fraction(best.get("confidence"))
    ioc_bonus = min(0.2, (best.get("shared_ioc_count") or 0) * 0.02)
    points = round(CAP_INFRASTRUCTURE * min(1.0, fraction + ioc_bonus), 1)
    if points <= 0:
        return 0.0, None
    sentence = (
        f"Shares infrastructure with {best.get('cve_id_b', 'another CVE')} "
        f"({best.get('confidence', 'low')} confidence)."
    )
    return points, sentence


def _actor_contribution(actor: list[dict]) -> tuple[float, str | None]:
    if not actor:
        return 0.0, None
    sector_matches = [a for a in actor if a.get("user_sector_match")]
    pool = sector_matches or actor
    best = _best_by_confidence(pool)
    bonus = 0.3 if sector_matches else 0.0
    points = round(CAP_ACTOR * min(1.0, _confidence_fraction(best.get("confidence")) + bonus), 1)
    if points <= 0:
        return 0.0, None
    if sector_matches:
        sentence = f"{best.get('actor_name', 'An actor')} is historically associated with targeting your declared sector. Verify relevance to your environment."
    else:
        sentence = f"Linked to {best.get('actor_name', 'an actor')} via {best.get('source', 'OTX')}."
    return points, sentence


def _format_vendor_name(vendor: str) -> str:
    v = (vendor or "").strip().replace("_", " ")
    if not v:
        return "This product vendor"
    return v.title()


def _temporal_contribution(temporal: list[dict]) -> tuple[float, str | None]:
    if not temporal:
        return 0.0, None
    best = max(temporal, key=lambda t: t.get("anomaly_score", 0) or 0)
    score = float(best.get("anomaly_score", 0) or 0)
    points = round(CAP_TEMPORAL * min(1.0, score / 5.0), 1)
    if points <= 0:
        return 0.0, None
    vendor = _format_vendor_name(best.get("vendor", ""))
    week_count = int(best.get("current_week_count") or 0)
    avg_weekly = float(best.get("average_weekly_count") or 0)
    sentence = (
        f"Unusual CVE volume for {vendor}: {week_count} published this week "
        f"(~{score:.1f}× the normal weekly average of {avg_weekly:.1f})."
    )
    return points, sentence


def compute_correlation_priority(result: dict[str, Any]) -> dict[str, Any]:
    """
    Synthesize campaigns/infrastructure/actor/temporal into one ranked
    triage signal (0-100) with an explainable, sorted component breakdown.
    """
    contributions = {
        "campaign": _campaign_contribution(result.get("campaigns") or []),
        "infrastructure": _infrastructure_contribution(result.get("infrastructure") or []),
        "actor": _actor_contribution(result.get("actor") or []),
        "temporal": _temporal_contribution(result.get("temporal") or []),
    }

    components = []
    total = 0.0
    for name, (points, sentence) in contributions.items():
        total += points
        if points > 0:
            components.append({"signal": name, "points": points, "sentence": sentence})

    components.sort(key=lambda c: c["points"], reverse=True)
    return {"score": round(min(100.0, total), 1), "components": components}
