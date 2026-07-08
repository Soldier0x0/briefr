"""Threat Score v1.0 — asset-independent exploitation credibility (ADR-002)."""

from __future__ import annotations

from typing import Any

from scoring.risk import (
    _boolish,
    _exploit_score_v11b,
    _kev_score_v11b,
    _num,
)

VERSION = "threat-1.0"
KEV_FLOOR = 80.0

# Renormalized v1.1b weights (non-asset sum 0.65 → 1.0)
WEIGHT_KEV = 0.25 / 0.65
WEIGHT_EPSS = 0.15 / 0.65
WEIGHT_EXPLOIT = 0.10 / 0.65
WEIGHT_CVSS = 0.10 / 0.65
WEIGHT_MOMENTUM = 0.05 / 0.65

THREAT_WEIGHTS = {
    "kev": WEIGHT_KEV,
    "epss": WEIGHT_EPSS,
    "exploit": WEIGHT_EXPLOIT,
    "cvss": WEIGHT_CVSS,
    "momentum": WEIGHT_MOMENTUM,
}


def threat_band(score: float) -> str:
    if score >= 80:
        return "CRIT"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MED"
    return "LOW"


def calculate_threat_score(cve: dict, momentum_score: float = 0.0) -> dict[str, Any]:
    """
    Asset-independent Threat Score (0–100) with KEV floor.

    Reuses v1.1b component raws; EPSS missing → 0 (never fabricated).
    """
    if not cve:
        return {}

    kev_raw = _kev_score_v11b(cve)
    epss_raw = _num(cve.get("epss_score"), 0.0)
    exploit_raw = _exploit_score_v11b(cve)
    cvss_raw = _num(cve.get("cvss_score"), 0.0) / 10.0
    momentum_raw = max(0.0, min(1.0, float(momentum_score or 0)))

    raw_scores = {
        "kev": kev_raw,
        "epss": epss_raw,
        "exploit": exploit_raw,
        "cvss": cvss_raw,
        "momentum": momentum_raw,
    }

    additive = sum(raw_scores[k] * THREAT_WEIGHTS[k] for k in raw_scores) * 100.0
    additive = round(additive * 10) / 10

    kev_floor_applied = False
    if _boolish(cve.get("is_kev")):
        score = max(additive, KEV_FLOOR)
        kev_floor_applied = score > additive
    else:
        score = additive
    score = round(score * 10) / 10

    components: dict[str, dict[str, Any]] = {}
    for key, raw in raw_scores.items():
        w = THREAT_WEIGHTS[key]
        components[key] = {
            "raw": raw,
            "weight": w,
            "points": round(raw * w * 100 * 10) / 10,
        }

    return {
        "version": VERSION,
        "score": score,
        "band": threat_band(score),
        "components": components,
        "kev_floor_applied": kev_floor_applied,
        "additive_score": additive,
    }
