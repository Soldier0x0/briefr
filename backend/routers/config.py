"""Config endpoints — single-source v1.1b risk weights for frontend consumption.

GET /api/config/risk  →  weights dict keyed by component, version string.

The frontend (frontend/src/scoring/riskScore.js) fetches this once at startup
and uses the returned weights in calculateRiskScore, falling back to the
hardcoded constants when the request fails or the response is unavailable.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from fastapi import APIRouter

from scoring.risk import (
    WEIGHT_ASSET,
    WEIGHT_CVSS,
    WEIGHT_EPSS,
    WEIGHT_EXPLOIT,
    WEIGHT_KEV,
    WEIGHT_MOMENTUM,
)

router = APIRouter()


@router.get("/api/config/risk")
def get_risk_config() -> dict:
    """Return v1.1b risk score weights sourced from scoring/risk.py.

    Weights sum to 1.0. The frontend consumes this endpoint at startup and
    falls back to its bundled constants if the request fails.
    """
    weights = {
        "asset": WEIGHT_ASSET,
        "kev": WEIGHT_KEV,
        "epss": WEIGHT_EPSS,
        "exploit": WEIGHT_EXPLOIT,
        "cvss": WEIGHT_CVSS,
        "momentum": WEIGHT_MOMENTUM,
    }
    return {
        "version": "1.1b",
        "weights": weights,
    }
