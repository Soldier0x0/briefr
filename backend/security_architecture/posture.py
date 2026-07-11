"""Overview posture aggregates from corpus + optional live flags.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from security_architecture.corpus_loader import SecurityArchitectureCorpus


def _mean_compliance(categories: list[dict[str, Any]]) -> float:
    if not categories:
        return 0.0
    values = [float(c.get("compliance_pct") or 0) for c in categories]
    return round(sum(values) / len(values), 1)


def _residual_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(str(value).lower(), 0)


def build_overview(corpus: SecurityArchitectureCorpus) -> dict[str, Any]:
    """Compute landing-page summary cards from corpus records."""
    controls = corpus.controls
    implemented = sum(1 for c in controls if str(c.get("review_status", "")).lower() == "current")
    open_risks = [r for r in corpus.risks if str(r.get("status", "open")).lower() == "open"]
    critical_risks = [
        r for r in open_risks if str(r.get("severity", "")).lower() == "critical"
    ]
    critical_threat_count = len(critical_risks) + sum(
        1
        for a in corpus.abuse_cases
        if str(a.get("remaining_risk", "")).lower() in ("high", "critical")
    )

    framework_pct = _mean_compliance(
        corpus.owasp_top10 + corpus.owasp_api + corpus.nist_csf + corpus.asvs
    )
    controls_pct = round((implemented / len(controls)) * 100, 1) if controls else 0.0

    boundaries = corpus.trust_boundaries
    highest_boundary = max(boundaries, key=lambda b: _residual_rank(b.get("residual_risk", "low")))
    attack_score = corpus.attack_surface_graph.get("score", 0)

    review_dates = [r.get("review_date") for r in corpus.reviews if r.get("review_date")]
    freshness_days = None
    if review_dates:
        latest = max(review_dates)
        try:
            dt = datetime.strptime(str(latest)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            freshness_days = (datetime.now(timezone.utc) - dt).days
        except ValueError:
            freshness_days = None

    posture_score = round(
        min(
            100.0,
            (controls_pct * 0.35) + (framework_pct * 0.35) + max(0.0, 100 - float(attack_score)) * 0.3,
        ),
        1,
    )
    posture_grade = (
        "A" if posture_score >= 90 else "B+" if posture_score >= 80 else "B" if posture_score >= 70 else "C"
    )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary_cards": {
            "overall_posture": {"grade": posture_grade, "score": posture_score},
            "critical_threats": critical_threat_count,
            "open_risks": len(open_risks),
            "security_controls": {"implemented": implemented, "total": len(controls)},
            "framework_coverage_pct": framework_pct,
            "trust_boundaries": {
                "count": len(boundaries),
                "highest_residual_risk": highest_boundary.get("residual_risk", "low"),
            },
            "attack_surface_score": attack_score,
            "review_freshness_days": freshness_days,
        },
        "architecture_overview": corpus.architecture_graph.get("overview_stack", []),
    }
