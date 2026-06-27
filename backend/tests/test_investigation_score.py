"""Tests for unified investigation score."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.investigation import compute_investigation_score


def test_investigation_score_bounds():
    result = compute_investigation_score(
        risk_total=80.0,
        correlation_priority=60.0,
        campaigns=[{"confidence": "high"}],
    )
    assert 0 <= result["total"] <= 100
    assert result["score"] == result["total"]
    assert len(result["components"]) >= 2


def test_investigation_score_zero_inputs():
    result = compute_investigation_score(risk_total=0.0, correlation_priority=0.0)
    assert result["total"] == 0.0
