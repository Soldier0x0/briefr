"""CORR-PR-8: read-time freshness decay on IOC edges."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation.confidence import confidence_for_ioc_edge
from correlation.freshness import freshness_context, numeric_edge_level


def _now() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_stale_domain_edge_decays_below_medium():
    old = (_now() - timedelta(days=200)).isoformat()
    level, why, factors = confidence_for_ioc_edge(
        "DOMAIN",
        degree=1,
        observed_at=old,
        now=_now(),
    )
    assert level == "low"
    assert why and "200d ago" in why
    assert any(f.get("factor") == "freshness" for f in factors)


def test_numeric_edge_level_200_day_domain_below_medium():
    level = numeric_edge_level("DOMAIN", degree=1, freshness=0.25)
    assert level == "low"


def test_null_observed_at_skips_decay_to_floor():
    old_ingest = (_now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    level, _why, factors = confidence_for_ioc_edge(
        "DOMAIN",
        degree=1,
        observed_at=None,
        ingested_at=old_ingest,
        now=_now(),
    )
    assert level == "medium"
    fresh = next(f for f in factors if f.get("factor") == "freshness")
    assert fresh.get("freshness_fallback") is True
    assert "decay skipped" in fresh["reason"]


def test_freshness_context_flags_missing_observation():
    ctx = freshness_context(
        "IP",
        observed_at=None,
        ingested_at=(_now() - timedelta(days=10)).isoformat(),
        now=_now(),
    )
    assert ctx["freshness_factor"] == 1.0
    assert ctx["freshness_fallback"] is True
