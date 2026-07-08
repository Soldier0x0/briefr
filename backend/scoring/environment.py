"""Environment Relevance tiers v1.0 — categorical, never folded into Threat (ADR-002)."""

from __future__ import annotations

from typing import Any, Optional

from scoring.asset_match import resolve_asset_component

VERSION = "environment-1.0"

TIER_RANK = {
    "CONFIRMED": 5,
    "LIKELY": 4,
    "POSSIBLE": 3,
    "WEAK": 2,
    "UNKNOWN": 1,
    "NO_MATCH": 0,
}


def classify_environment(
    cve: dict,
    profile: Optional[dict],
    backend_match_score: Optional[int] = None,
) -> dict[str, Any]:
    """
    Map asset-match signals to a six-tier Environment Relevance enum.

    UNKNOWN when profile is None; NO_MATCH when profile loaded and score is 0.
    """
    if profile is None:
        return {
            "version": VERSION,
            "tier": "UNKNOWN",
            "score": None,
            "version_verified": False,
            "evidence_label": "No asset profile loaded",
        }

    asset_score, match_type = resolve_asset_component(
        cve, profile, backend_match_score
    )
    backend_score = int(backend_match_score or 0)
    mt_lower = (match_type or "").lower()

    if asset_score == 0.0:
        return {
            "version": VERSION,
            "tier": "NO_MATCH",
            "score": 0.0,
            "version_verified": False,
            "evidence_label": match_type or "No matching assets in your profile",
        }

    if backend_score >= 100:
        return {
            "version": VERSION,
            "tier": "CONFIRMED",
            "score": asset_score,
            "version_verified": True,
            "evidence_label": match_type,
        }

    if asset_score >= 1.0 and "exact cpe match" in mt_lower:
        return {
            "version": VERSION,
            "tier": "CONFIRMED",
            "score": asset_score,
            "version_verified": True,
            "evidence_label": match_type,
        }

    if asset_score >= 0.9 or (asset_score >= 0.8 and "os match" in mt_lower):
        return {
            "version": VERSION,
            "tier": "LIKELY",
            "score": asset_score,
            "version_verified": False,
            "evidence_label": match_type,
        }

    if asset_score >= 0.65:
        return {
            "version": VERSION,
            "tier": "POSSIBLE",
            "score": asset_score,
            "version_verified": False,
            "evidence_label": match_type,
        }

    if asset_score >= 0.35:
        return {
            "version": VERSION,
            "tier": "WEAK",
            "score": asset_score,
            "version_verified": False,
            "evidence_label": match_type,
        }

    return {
        "version": VERSION,
        "tier": "NO_MATCH",
        "score": asset_score,
        "version_verified": False,
        "evidence_label": match_type or "No matching assets in your profile",
    }
