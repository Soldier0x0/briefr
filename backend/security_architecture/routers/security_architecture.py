"""Security Architecture module API (TM-1 stub).

Mounted at /api/security-architecture/*. Session auth applies globally via
main.py's session_auth_middleware (this router isn't in auth_middleware.py's
public/admin-exempt prefixes) -- matches spec §4.4: "All routes: session
auth (analyst+)".

Only manifest + overview ship in TM-1, per its acceptance criteria. The
richer per-section endpoints (graph, stride, mitre, controls, ...) and the
overview's real drill-through tiles (§5.1 -- live DB queries for MITRE
coverage, self-stack CVE exposure, etc.) are TM-2/TM-3/TM-5 scope, not
invented here. This stub reports only what the TM-1 corpus actually has:
counts from the generated layer, and honest zeros from the still-empty
curated layer.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from security_architecture.corpus_loader import CorpusValidationError, get_corpus

router = APIRouter(prefix="/api/security-architecture")


@router.get("/manifest")
async def get_manifest():
    """Corpus version, schema version, and the section index."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Corpus invalid: {exc}") from exc

    manifest = corpus["manifest"]
    return {
        "version": manifest["version"],
        "schema_version": manifest["schema_version"],
        "last_reviewed": manifest["last_reviewed"],
        "sections": manifest.get("sections", []),
    }


@router.get("/overview")
async def get_overview():
    """Posture summary counts. Additive-only stub -- see module docstring."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Corpus invalid: {exc}") from exc

    return {
        "generated": {
            "components": len(corpus["components"]["components"]),
            "api_endpoints": len(corpus["api_inventory"]["endpoints"]),
            "scheduler_jobs": len(corpus["scheduler_jobs"]["jobs"]),
            "db_tables": len(corpus["db_tables"]["tables"]),
        },
        "curated": {
            "trust_boundaries": len(corpus["trust_boundaries"]["trust_boundaries"]),
            "controls": len(corpus["controls"]["controls"]),
            "abuse_cases": len(corpus["abuse_cases"]["abuse_cases"]),
            "threat_scenarios": len(corpus["threat_scenarios"]["threat_scenarios"]),
            "security_decisions": len(corpus["security_decisions"]["security_decisions"]),
            "risks": len(corpus["risks"]["risks"]),
            "reviews": len(corpus["reviews"]["reviews"]),
        },
        "last_reviewed": corpus["manifest"]["last_reviewed"],
    }
