"""Freshness decay helpers — read-time only (CORR-PR-8)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

from correlation.config import get_freshness_floor, get_freshness_half_life_days

_IOC_BASE_SCORE = {
    "HASH": 0.9,
    "DOMAIN": 0.6,
    "URL": 0.65,
    "IP": 0.3,
}


def parse_observation_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = f"{text}T00:00:00+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def degree_factor(degree: int) -> float:
    d = max(0, int(degree or 0))
    if d <= 3:
        return 1.0
    return 1.0 / (1.0 + math.log2(d / 3))


def freshness_multiplier(ioc_type: str, age_days: float) -> float:
    half_life = get_freshness_half_life_days(ioc_type)
    age = max(0.0, float(age_days))
    floor = get_freshness_floor()
    return max(floor, 0.5 ** (age / half_life))


def score_to_confidence_level(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def numeric_edge_level(ioc_type: str, *, degree: int, freshness: float) -> str:
    t = (ioc_type or "").upper()
    if t in ("IPV4", "IPV6"):
        t = "IP"
    base = _IOC_BASE_SCORE.get(t, 0.3)
    score = base * degree_factor(degree) * freshness
    return score_to_confidence_level(score)


def freshness_context(
    ioc_type: str,
    *,
    observed_at: Any,
    ingested_at: Any,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Return freshness metadata for an IOC edge (read-time, never stored)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    observed_dt = parse_observation_dt(observed_at)
    ingested_dt = parse_observation_dt(ingested_at)
    used_fallback = observed_dt is None

    if observed_dt is not None:
        anchor = observed_dt
    elif ingested_dt is not None:
        anchor = ingested_dt
    else:
        return {
            "freshness_factor": 1.0,
            "age_days": None,
            "observed_at": None,
            "ingested_at": str(ingested_at).strip() if ingested_at else None,
            "freshness_reason": "No observation timestamp available",
            "freshness_fallback": True,
        }

    age_days = max(0.0, (now - anchor).total_seconds() / 86400.0)
    raw_factor = freshness_multiplier(ioc_type, age_days)

    if used_fallback:
        factor = 1.0
        reason = (
            "Observation time unknown — staleness decay skipped "
            f"(ingested {int(age_days)}d ago)"
        )
    else:
        factor = raw_factor
        half_life = get_freshness_half_life_days(ioc_type)
        reason = (
            f"Indicator observed {int(age_days)}d ago "
            f"({ioc_type.upper()} half-life {half_life}d)"
        )

    return {
        "freshness_factor": round(factor, 4),
        "age_days": round(age_days, 2),
        "observed_at": observed_dt.isoformat() if observed_dt else None,
        "ingested_at": ingested_dt.isoformat() if ingested_dt else (
            str(ingested_at).strip() if ingested_at else None
        ),
        "freshness_reason": reason,
        "freshness_fallback": used_fallback,
    }
