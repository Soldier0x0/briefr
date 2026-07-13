"""Security Architecture module API (TM-1 stub + TM-2 shell additions).

Mounted at /api/security-architecture/*. Session auth applies globally via
main.py's session_auth_middleware (this router isn't in auth_middleware.py's
public/admin-exempt prefixes) -- matches spec §4.4: "All routes: session
auth (analyst+)".

TM-1 shipped manifest + overview (raw counts only). TM-2 (shell UI +
Overview, threat-modeling-security-architecture.md §8) adds:

- `overview.tiles[]`: evidence tiles with visible inputs -- every value is a
  len() or a direct field match over corpus rows, no composite grades, no
  invented arithmetic (spec §9.4). Each tile carries a `section`/`filter`
  drill target so a UI click can land on the exact pre-filtered rows.
- `GET /section/{id}`: a generic read of any manifest data section's corpus
  rows, with `status`/`severity`/`type` query filters. This is a TM-2 shell
  convenience -- one generic endpoint instead of nine typed ones -- and is
  intentionally superseded by spec §4.4's typed endpoints (graph/mitre/
  stride/...) as TM-3+ builds live sections. Not a substitute for those.

MITRE coverage, self-stack CVE exposure, and endpoint<->control linkage
(attack surface) need machinery this branch doesn't have yet (self-stack
generation + merge.py is TM-3; endpoint<->control linkage is TM-4) -- they
are deliberately absent from the tile set rather than faked.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from security_architecture.corpus_loader import CorpusValidationError, get_corpus

router = APIRouter(prefix="/api/security-architecture")

STALE_WINDOW_DAYS = 90

# section_id (manifest.yaml `sections[]`) -> { type: (corpus_key, list_key) }.
# "components" fans out to all four generated-layer collections via the
# `type` query param -- they share one nav section because TM-1's manifest
# doesn't carry separate sections for endpoints/jobs/tables.
_SECTION_SOURCES: dict[str, dict[str, tuple[str, str]]] = {
    "components": {
        "components": ("components", "components"),
        "endpoints": ("api_inventory", "endpoints"),
        "jobs": ("scheduler_jobs", "jobs"),
        "tables": ("db_tables", "tables"),
    },
    "trust_boundaries": {"": ("trust_boundaries", "trust_boundaries")},
    "controls": {"": ("controls", "controls")},
    "abuse_cases": {"": ("abuse_cases", "abuse_cases")},
    "threat_scenarios": {"": ("threat_scenarios", "threat_scenarios")},
    "security_decisions": {"": ("security_decisions", "security_decisions")},
    "risks": {"": ("risks", "risks")},
    "reviews": {"": ("reviews", "reviews")},
}


def _rows(corpus: dict[str, Any], corpus_key: str, list_key: str) -> list[dict]:
    return list(corpus[corpus_key].get(list_key) or [])


def _count(rows: list[dict], **filters: str) -> int:
    return len([
        r for r in rows
        if isinstance(r, dict) and all(r.get(k) == v for k, v in filters.items())
    ])


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
    """Posture summary counts + drill-through evidence tiles (TM-2 §5.1)."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Corpus invalid: {exc}") from exc

    components = _rows(corpus, "components", "components")
    endpoints = _rows(corpus, "api_inventory", "endpoints")
    jobs = _rows(corpus, "scheduler_jobs", "jobs")
    tables = _rows(corpus, "db_tables", "tables")
    risks = _rows(corpus, "risks", "risks")
    controls = _rows(corpus, "controls", "controls")

    try:
        last_reviewed = corpus["manifest"]["last_reviewed"]
        review_date = last_reviewed if isinstance(last_reviewed, date) else date.fromisoformat(last_reviewed)
        days_since_review = (date.today() - review_date).days
    except (ValueError, TypeError):
        days_since_review = None

    tiles = [
        {
            "id": "components", "label": "System Components", "value": len(components),
            "help": "FastAPI router modules discovered by the corpus generator from backend/routers/.",
            "section": "components", "filter": {"type": "components"},
        },
        {
            "id": "endpoints", "label": "API Endpoints", "value": len(endpoints),
            "help": "Every live API endpoint across all routers, from OpenAPI route introspection.",
            "section": "components", "filter": {"type": "endpoints"},
        },
        {
            "id": "scheduler_jobs", "label": "Scheduler Jobs", "value": len(jobs),
            "help": "Background jobs registered in scheduler.py's add_job() calls.",
            "section": "components", "filter": {"type": "jobs"},
        },
        {
            "id": "db_tables", "label": "DB Tables", "value": len(tables),
            "help": "Database tables discovered from CREATE TABLE statements in the schema.",
            "section": "components", "filter": {"type": "tables"},
        },
        {
            "id": "open_risks", "label": "Open Risks", "value": _count(risks, status="open"),
            "help": "Curated risk-register rows with status=open. Empty until a security-review pass populates the register.",
            "section": "risks", "filter": {"status": "open"},
        },
        {
            "id": "critical_open_risks", "label": "Critical Open Risks",
            "value": _count(risks, status="open", severity="critical"),
            "help": "Curated risk-register rows with severity=critical and status=open.",
            "section": "risks", "filter": {"status": "open", "severity": "critical"},
        },
        {
            "id": "controls", "label": "Controls", "value": len(controls),
            "help": "Curated security controls inventory. Live active/inactive flags ship in TM-3.",
            "section": "controls", "filter": {},
        },
        {
            "id": "review_freshness", "label": "Review Freshness",
            "value": days_since_review if days_since_review is not None else "—",
            "unit": "days" if days_since_review is not None else None,
            "help": "Days since the corpus's manifest.last_reviewed date.",
            "section": "reviews", "filter": {},
        },
    ]

    return {
        "generated": {
            "components": len(components),
            "api_endpoints": len(endpoints),
            "scheduler_jobs": len(jobs),
            "db_tables": len(tables),
        },
        "curated": {
            "trust_boundaries": len(corpus["trust_boundaries"]["trust_boundaries"]),
            "controls": len(controls),
            "abuse_cases": len(corpus["abuse_cases"]["abuse_cases"]),
            "threat_scenarios": len(corpus["threat_scenarios"]["threat_scenarios"]),
            "security_decisions": len(corpus["security_decisions"]["security_decisions"]),
            "risks": len(risks),
            "reviews": len(corpus["reviews"]["reviews"]),
        },
        "last_reviewed": corpus["manifest"]["last_reviewed"],
        "tiles": tiles,
    }


@router.get("/section/{section_id}")
async def get_section(section_id: str, type: str = "", status: str = "", severity: str = "", stale: bool = False):
    """Generic read of a manifest data section's corpus rows (TM-2 shell
    convenience -- see module docstring for why this isn't the typed
    per-section endpoint set from spec §4.4)."""
    sources = _SECTION_SOURCES.get(section_id)
    if sources is None:
        raise HTTPException(status_code=404, detail=f"Unknown section: {section_id}")

    resolved_type = type if type in sources else next(iter(sources))
    corpus_key, list_key = sources[resolved_type]

    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Corpus invalid: {exc}") from exc

    rows = _rows(corpus, corpus_key, list_key)
    if status:
        rows = [r for r in rows if isinstance(r, dict) and r.get("status") == status]
    if severity:
        rows = [r for r in rows if isinstance(r, dict) and r.get("severity") == severity]
    if stale:
        cutoff = (date.today() - timedelta(days=STALE_WINDOW_DAYS)).isoformat()

        def _is_stale(r: dict) -> bool:
            rev_date = r.get("review_date")
            if not rev_date:
                return False
            if isinstance(rev_date, date):
                rev_date = rev_date.isoformat()
            return str(rev_date) < cutoff

        rows = [
            r for r in rows
            if isinstance(r, dict) and r.get("origin") == "curated" and _is_stale(r)
        ]

    return {
        "section": section_id,
        "type": resolved_type,
        "available_types": list(sources.keys()),
        "count": len(rows),
        "items": rows,
    }
