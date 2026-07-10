"""Config endpoints — single-source v1.1b risk weights for frontend consumption.

GET /api/config/risk  →  weights dict keyed by component, version string.

The frontend (frontend/src/scoring/riskScore.js) fetches weights for display only;
the canonical score is computed server-side via POST /api/cves/{cve_id}/risk.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
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

    Weights sum to 1.0. Used by the UI for formula display; scoring runs on
    the server via POST /api/cves/{cve_id}/risk.
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
