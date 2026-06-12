"""Tests for GET /api/config/risk — §5.3 single-source risk weights.

Verifies:
- Endpoint returns the expected JSON shape
- All six component keys are present
- Weights are sourced from scoring/risk.py constants (not duplicated)
- Weights sum exactly to 1.0
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.config import get_risk_config
from scoring.risk import (
    WEIGHT_ASSET,
    WEIGHT_CVSS,
    WEIGHT_EPSS,
    WEIGHT_EXPLOIT,
    WEIGHT_KEV,
    WEIGHT_MOMENTUM,
)

_EXPECTED_KEYS = ("asset", "kev", "epss", "exploit", "cvss", "momentum")


def _call() -> dict:
    return get_risk_config()


def test_config_risk_response_has_version_and_weights():
    result = _call()
    assert "version" in result
    assert "weights" in result


def test_config_risk_version_is_v11b():
    result = _call()
    assert result["version"] == "1.1b"


def test_config_risk_all_component_keys_present():
    weights = _call()["weights"]
    for key in _EXPECTED_KEYS:
        assert key in weights, f"Missing weight key: {key}"


def test_config_risk_weights_sum_to_one():
    weights = _call()["weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_config_risk_weights_match_python_constants():
    """Endpoint must read directly from scoring/risk.py — no copy-pasted values."""
    weights = _call()["weights"]
    assert weights["asset"] == WEIGHT_ASSET
    assert weights["kev"] == WEIGHT_KEV
    assert weights["epss"] == WEIGHT_EPSS
    assert weights["exploit"] == WEIGHT_EXPLOIT
    assert weights["cvss"] == WEIGHT_CVSS
    assert weights["momentum"] == WEIGHT_MOMENTUM


def test_config_risk_all_weights_are_positive():
    weights = _call()["weights"]
    for key, value in weights.items():
        assert value > 0, f"Weight {key}={value} must be positive"


def test_config_risk_registered_in_openapi():
    """Route must appear in the OpenAPI spec (wired into app correctly)."""
    from main import app

    routes = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    assert ("GET", "/api/config/risk") in routes
