"""Unified Investigation Score — fuses risk, correlation, and intel freshness."""

from __future__ import annotations

from typing import Any

WEIGHT_RISK = 0.45
WEIGHT_CORRELATION = 0.40
WEIGHT_INTEL = 0.15


def _otx_freshness_score(campaigns: list[dict]) -> float:
    """0–1 boost from recent OTX campaign linkage."""
    if not campaigns:
        return 0.0
    best = 0.0
    for item in campaigns:
        conf = (item.get("confidence") or "").lower()
        conf_frac = {"high": 1.0, "medium": 0.65, "low": 0.35}.get(conf, 0.2)
        best = max(best, conf_frac)
    return min(1.0, best)


def compute_investigation_score(
    *,
    risk_total: float,
    correlation_priority: float,
    campaigns: list[dict] | None = None,
    in_brief_queue: bool = False,
) -> dict[str, Any]:
    """
    Single 0–100 triage headline combining existing BRIEFR scores.

    Components remain available separately — this does not replace Risk Score
    v1.1b or Correlation Priority; it fuses them for one ranked number.
    """
    risk = max(0.0, min(100.0, float(risk_total or 0)))
    correlation = max(0.0, min(100.0, float(correlation_priority or 0)))
    intel = _otx_freshness_score(campaigns or [])
    if in_brief_queue:
        intel = min(1.0, intel + 0.35)

    raw = (
        risk * WEIGHT_RISK
        + correlation * WEIGHT_CORRELATION
        + intel * 100.0 * WEIGHT_INTEL
    )
    total = round(min(100.0, raw), 1)

    components = [
        {
            "signal": "risk",
            "points": round(risk * WEIGHT_RISK, 1),
            "sentence": f"BRIEFR Risk Score contributes {risk:.0f}/100 (weight {int(WEIGHT_RISK * 100)}%).",
        },
        {
            "signal": "correlation",
            "points": round(correlation * WEIGHT_CORRELATION, 1),
            "sentence": (
                f"Correlation priority contributes {correlation:.0f}/100 "
                f"(weight {int(WEIGHT_CORRELATION * 100)}%)."
            ),
        },
    ]
    if intel > 0 or in_brief_queue:
        intel_points = round(intel * 100.0 * WEIGHT_INTEL, 1)
        parts = []
        if intel > 0:
            parts.append("OTX campaign linkage")
        if in_brief_queue:
            parts.append("Morning Brief action queue")
        components.append(
            {
                "signal": "intel_freshness",
                "points": intel_points,
                "sentence": f"{' and '.join(parts)} boost (+{intel_points:.1f} pts).",
            }
        )

    components.sort(key=lambda c: c["points"], reverse=True)

    return {
        "version": "1.0",
        "total": total,
        "score": total,
        "components": components,
        "weights": {
            "risk": WEIGHT_RISK,
            "correlation": WEIGHT_CORRELATION,
            "intel_freshness": WEIGHT_INTEL,
        },
    }
