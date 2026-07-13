"""Security Architecture module API (TM-1 stub + TM-2 shell + TM-3 live
sections).

Mounted at /api/security-architecture/*. Session auth applies globally via
main.py's session_auth_middleware (this router isn't in auth_middleware.py's
public/admin-exempt prefixes) -- matches spec §4.4: "All routes: session
auth (analyst+)".

TM-1 shipped manifest + overview (raw counts only). TM-2 added shell UI +
Overview evidence tiles + the generic `/section/{id}` drill-through read.

TM-3 (threat-modeling-security-architecture.md §8) adds the first *live*
sections -- no new matching/scoring code, all glue over the existing
shipping pipeline (security_architecture/merge.py docstring has the full
rationale):

- `GET /mitre`: ATT&CK coverage matrix, reusing
  `routers.forge.build_coverage_map` (same query the Forge tab uses) instead
  of duplicating it.
- `GET /threat-scenarios`: wraps `threat_model.scenarios.build_threat_scenarios`
  -- `?stack=` for the user's stack (Forge parity, `?self_stack=1` swaps in
  the generated self-stack (spec §4.5) instead. Output shape is identical to
  `/api/threat-model/scenarios` by construction (same function).
- `/section/controls` rows gain a live `active` flag
  (`merge.enrich_controls`).
- `/section/risks` rows gain live-derived (`origin: live`) rows auto-derived
  from KEV/critical CVE hits on the self-stack (`merge.self_stack_risk_rows`).
- `/overview` gains a "Self CVE Exposure" tile and a "MITRE Detection
  Coverage" tile, both live.

Endpoint<->control linkage (attack surface) is still TM-4 -- deliberately
absent here rather than faked.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from routers.forge import build_coverage_map, count_coverage_summary
from security_architecture import merge
from security_architecture.corpus_loader import CorpusValidationError, get_corpus
from threat_model.scenarios import build_threat_scenarios

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
    """Posture summary counts + drill-through evidence tiles (TM-2 §5.1,
    TM-3 adds the two live tiles at the end)."""
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
            "help": "Curated security controls inventory, seeded by a real security-review pass (TM-3). Click through to see each control's live active/inactive flag.",
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

    db = await get_db()
    try:
        coverage_summary = await count_coverage_summary(db)
        exposure = await merge.self_cve_exposure_summary(db, corpus)
    finally:
        await db.close()

    covered = coverage_summary["covered"]
    total = coverage_summary["total"]
    tiles.append({
        "id": "mitre_detection_coverage", "label": "MITRE Detection Coverage",
        "value": f"{covered}/{total}" if total else "—",
        "help": "Techniques with a saved hunt pack or bundled community template, out of every technique linked to a CVE in the database (live mitre_techniques / cve_technique_map, same query as Forge coverage).",
        "section": "mitre_attack", "filter": {},
    })
    tiles.append({
        "id": "self_cve_exposure", "label": "Self CVE Exposure",
        "value": exposure["count"],
        "help": f"KEV or critical CVEs matching BRIEFR's own generated self-stack ({len(exposure['terms'])} dependency terms from requirements.txt / package.json). Term match, not SBOM-precise -- see the matched term on each row.",
        "section": "risks", "filter": {"origin": "live"},
    })

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
        "self_exposure": exposure,
        "last_reviewed": corpus["manifest"]["last_reviewed"],
        "tiles": tiles,
    }


@router.get("/mitre")
async def get_mitre(
    stack: str | None = Query(default=None, max_length=500),
):
    """ATT&CK coverage matrix (spec §5.6). Reuses the exact query Forge's
    coverage map uses (`routers.forge.build_coverage_map`) -- not a
    reimplementation, so 'coverage matches DB' holds by construction."""
    db = await get_db()
    try:
        return await build_coverage_map(db, stack)
    finally:
        await db.close()


@router.get("/threat-scenarios")
async def get_threat_scenarios(
    stack: str | None = Query(default=None, max_length=500),
    self_stack: bool = False,
):
    """Stack-scoped / self-stack ATT&CK threat scenarios (spec §5.10, §4.5).

    Wraps `threat_model.scenarios.build_threat_scenarios` -- identical
    output shape to `/api/threat-model/scenarios` by construction, so
    'scenarios match Forge API output' holds without a parallel
    implementation. `self_stack=true` swaps in the generated self-stack
    terms instead of the `stack` query param (mirrors Forge's profileStack
    toggle pattern, computed server-side from the corpus, never per-request
    from scratch)."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Corpus invalid: {exc}") from exc

    effective_stack = merge.self_stack_query(corpus) if self_stack else stack

    db = await get_db()
    try:
        result = await build_threat_scenarios(db, effective_stack)
    finally:
        await db.close()

    result["meta"]["catalog"] = "self-stack" if self_stack else "stack"
    return result


@router.get("/section/{section_id}")
async def get_section(
    section_id: str,
    type: str = "",
    status: str = "",
    severity: str = "",
    origin: str = "",
    stale: bool = False,
):
    """Generic read of a manifest data section's corpus rows (TM-2 shell
    convenience -- see module docstring for why this isn't the typed
    per-section endpoint set from spec §4.4).

    TM-3 additions: `controls` rows get a live `active` flag; `risks` rows
    gain live-derived self-stack rows (`origin: live`, spec §4.5) alongside
    the curated register; both routes only touch the DB when their section
    actually needs it."""
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

    if section_id == "controls":
        rows = merge.enrich_controls(rows)

    # Skip the query entirely when the requested filters can't include live
    # rows anyway: origin=curated excludes them by definition, and stale=true
    # only ever matches curated rows (live rows carry no review_date).
    if section_id == "risks" and origin != "curated" and not stale:
        db = await get_db()
        try:
            live_rows = await merge.self_stack_risk_rows(db, corpus)
        finally:
            await db.close()
        rows = [*rows, *live_rows]

    if status:
        rows = [r for r in rows if isinstance(r, dict) and r.get("status") == status]
    if severity:
        rows = [r for r in rows if isinstance(r, dict) and r.get("severity") == severity]
    if origin:
        rows = [r for r in rows if isinstance(r, dict) and r.get("origin") == origin]
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
