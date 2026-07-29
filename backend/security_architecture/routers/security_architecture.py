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
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from database import get_db
from routers.forge import build_coverage_map, count_coverage_summary
from security_architecture import graphs, merge
from security_architecture.corpus_loader import CorpusValidationError, get_corpus
from security_architecture.frameworks import aggregate as fw_aggregate
from security_architecture.frameworks import scope as fw_scope
from security_architecture.graphs import ArchitectureGraphError
from threat_model.scenarios import build_threat_scenarios

logger = logging.getLogger(__name__)

_CORPUS_UNAVAILABLE = (
    "Security corpus is invalid or unavailable. Regenerate the security corpus or check server logs."
)


def _raise_corpus_unavailable(exc: Exception) -> None:
    logger.exception("Security corpus validation failed")
    raise HTTPException(status_code=500, detail=_CORPUS_UNAVAILABLE) from exc


router = APIRouter(prefix="/api/security-architecture")

# Staleness computation lives in merge.py (single source of truth shared by
# the router, the Controls Active ratio, and the PDF export disclaimer --
# spec §4.1, TM-5 build note in merge.py's STALE_WINDOW_DAYS docstring).
STALE_WINDOW_DAYS = merge.STALE_WINDOW_DAYS

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
        _raise_corpus_unavailable(exc)

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
        _raise_corpus_unavailable(exc)

    components = _rows(corpus, "components", "components")
    endpoints = _rows(corpus, "api_inventory", "endpoints")
    jobs = _rows(corpus, "scheduler_jobs", "jobs")
    tables = _rows(corpus, "db_tables", "tables")
    risks = _rows(corpus, "risks", "risks")
    controls = _rows(corpus, "controls", "controls")
    _controls_ratio = merge.controls_active_ratio(controls)

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
            "id": "controls", "label": "Controls Active",
            "value": f"{_controls_ratio['active']}/{_controls_ratio['total']}",
            "help": (
                "Live-flag-verified active controls out of total controls (spec §5.1). "
                "A control whose review has lapsed past the 90-day staleness window is excluded "
                "from both sides of this ratio -- it is not a verified-active control."
            ),
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
        "help": f"KEV or critical CVEs matching BRIEFR's own generated self-stack ({len(exposure['terms'])} dependency terms from requirements.txt / package.json) through structured CPE product/version scoring. See each row's match basis.",
        "section": "risks", "filter": {"origin": "live"},
    })

    attack_surface = graphs.build_attack_surface(corpus)
    tiles.append({
        "id": "unreviewed_endpoints", "label": "Unreviewed Endpoints",
        "value": attack_surface["unreviewed_endpoints"],
        "help": f"Generated endpoint inventory rows ({attack_surface['total_endpoints']} total) with no curated control's related_apis covering them yet.",
        "section": "attack_surface", "filter": {},
    })

    stale_count = _count_stale_curated_records(corpus)
    tiles.append({
        "id": "stale_records", "label": "Stale Records",
        "value": stale_count,
        "help": f"Curated records past the {STALE_WINDOW_DAYS}-day review window across every curated collection (spec §4.1 staleness decay). Excluded from coverage/compliance percentages.",
        "section": "stale", "filter": {},
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
        _raise_corpus_unavailable(exc)

    effective_stack = merge.self_stack_query(corpus) if self_stack else stack

    db = await get_db()
    try:
        result = await build_threat_scenarios(db, effective_stack)
    finally:
        await db.close()

    result["meta"]["catalog"] = "self-stack" if self_stack else "stack"
    return result


# section_id -> workspace builder (TM-6 analyst framework workspaces). Each
# is a projection of the same live scoped-CWE aggregation (frameworks/
# aggregate.py) -- one live DB read, four lenses.
_FRAMEWORK_BUILDERS = {
    "cwe": fw_aggregate.cwe_workspace,
    "owasp": fw_aggregate.owasp_workspace,
    "capec": fw_aggregate.capec_workspace,
    "stride": fw_aggregate.stride_workspace,
}


async def _current_user_id(request: Request) -> int | None:
    """Soft user-id resolve from the access-token cookie -- None when absent.

    The Security Architecture module is already auth-gated globally by
    main.py's session middleware (this router isn't in the public-prefix
    allowlist), so framework reads don't re-gate with require_user. User
    identity is needed only to resolve the `stack` scope to the caller's
    saved stack; without it, `stack` falls back to an explicit ?stack= param
    or reports itself unavailable (frameworks/scope.py) rather than erroring."""
    from auth.tokens import decode_access_token

    token = request.cookies.get("briefr_at", "")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub") or 0)
        return user_id if user_id > 0 else None
    except Exception:
        return None


@router.get("/frameworks/{framework_id}")
async def get_framework(
    framework_id: str,
    request: Request,
    scope: str = Query(default="all"),
    stack: str | None = Query(default=None, max_length=500),
    severity: str | None = Query(default=None, max_length=20),
):
    """Analyst framework workspace over the user's live threat surface (TM-6).

    `framework_id` is one of cwe/owasp/capec/stride. `scope` selects the live
    CVE set (all | stack | watchlist | kev); `stack=` overrides the saved
    stack for the `stack` scope; `severity=` narrows to one severity. Every
    row's count drills through to the exact `example_cves` behind it, and the
    response reports `sample_size` vs `total_in_scope` so a capped aggregation
    is visibly capped (frameworks/scope.py, aggregate.py)."""
    builder = _FRAMEWORK_BUILDERS.get(framework_id)
    if builder is None:
        raise HTTPException(status_code=404, detail=f"Unknown framework: {framework_id}")

    user_id = await _current_user_id(request)
    db = await get_db()
    try:
        scoped = await fw_scope.fetch_scoped_cwe_rows(
            db, scope, explicit_stack=stack, user_id=user_id, severity=severity
        )
    finally:
        await db.close()

    return builder(scoped)


@router.get("/graph/architecture")
async def get_architecture_graph():
    """System architecture graph (spec §5.2, §8 TM-4). Nodes/edges are
    exactly `graphs/architecture.json`'s generated-layer content -- no
    read-time filtering here, so 'graph nodes match generator output
    exactly' holds by construction. Layout (x/y) is intentionally absent:
    presentation isn't a code fact (advisor note during TM-4 build) --
    the frontend computes a deterministic cluster+index layout."""
    try:
        return graphs.get_architecture_graph()
    except ArchitectureGraphError as exc:
        logger.exception("Architecture graph unavailable")
        raise HTTPException(
            status_code=500,
            detail="Architecture graph is unavailable. Regenerate the security corpus or check server logs.",
        ) from exc


@router.get("/graph/attack-surface")
async def get_attack_surface():
    """Attack surface = generated endpoint inventory × linked controls,
    counts only (spec §8 TM-4) -- every endpoint's linked_control_count is
    visible on the row, so 'Unreviewed Endpoints' (count 0) is never an
    invented severity, just an endpoint with no curated control record
    covering it yet."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        _raise_corpus_unavailable(exc)
    return graphs.build_attack_surface(corpus)


@router.get("/context/{node_id}")
async def get_node_context(node_id: str):
    """Context-rail payload for an architecture-graph node selection (spec
    §5.2, §8 TM-4: 'node selection populates the context rail'). `node_id`
    is the graph's own node id (e.g. `routers-cves`, `table:cves`,
    `job:nvd_incremental_sync`) -- a single path param, not the spec §4.4
    two-segment `/context/{entity_type}/{id}` form, since the graph node id
    already encodes its kind via prefix and this keeps the frontend's graph
    click handler a one-field lookup."""
    try:
        corpus = get_corpus()
        graph = graphs.get_architecture_graph()
    except (CorpusValidationError, ArchitectureGraphError) as exc:
        logger.exception("Security architecture context unavailable")
        raise HTTPException(
            status_code=500,
            detail="Security architecture context is unavailable. Check server logs.",
        ) from exc

    context = graphs.build_node_context(node_id, corpus, graph)
    if context is None:
        raise HTTPException(status_code=404, detail=f"Unknown node: {node_id}")
    return context


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
        _raise_corpus_unavailable(exc)

    rows = _rows(corpus, corpus_key, list_key)
    live_self_stack = None

    if section_id == "controls":
        rows = merge.enrich_controls(rows)

    # Skip the query entirely when the requested filters can't include live
    # rows anyway: origin=curated excludes them by definition, and stale=true
    # only ever matches curated rows (live rows carry no review_date).
    if section_id == "risks":
        live_self_stack = merge.empty_self_stack_risk_stats()
        if origin != "curated" and not stale:
            db = await get_db()
            try:
                live_rows, live_self_stack = await merge.self_stack_risk_rows_with_stats(db, corpus)
            finally:
                await db.close()
            rows = [*rows, *live_rows]

    # TM-5 (spec §5.14): Review History merges curated reviews.yaml with
    # live audit_log security events -- reuses the audit_log table + the
    # admin Audit Log view's own redaction helper (merge.py docstring), not
    # a duplicate query or a duplicate masking rule.
    if section_id == "reviews" and origin != "curated":
        db = await get_db()
        try:
            audit_events = await merge.security_audit_log_events(db)
        finally:
            await db.close()
        rows = [*rows, *audit_events]

    # Single source of truth for staleness (merge.py) -- every curated row
    # carries a visible `stale` flag regardless of whether ?stale is set, so
    # the frontend badge and this filter always agree.
    rows = merge.annotate_stale(rows)

    if status:
        rows = [r for r in rows if isinstance(r, dict) and r.get("status") == status]
    if severity:
        rows = [r for r in rows if isinstance(r, dict) and r.get("severity") == severity]
    if origin:
        rows = [r for r in rows if isinstance(r, dict) and r.get("origin") == origin]
    if stale:
        rows = [r for r in rows if isinstance(r, dict) and r.get("stale")]

    payload = {
        "section": section_id,
        "type": resolved_type,
        "available_types": list(sources.keys()),
        "count": len(rows),
        "items": rows,
    }
    if section_id == "risks":
        payload["live_self_stack"] = live_self_stack
    return payload


def _all_curated_rows_by_section(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """Every curated-layer row across every section, each tagged with the
    nav section + type it drills through to (spec §5.1 'Stale Records' tile,
    §9.6 STALE decay acceptance). Iterates `_SECTION_SOURCES` rather than
    hand-listing corpus files, so a new curated section is picked up
    automatically."""
    items: list[dict[str, Any]] = []
    for section_id, sources in _SECTION_SOURCES.items():
        for type_key, (corpus_key, list_key) in sources.items():
            for row in _rows(corpus, corpus_key, list_key):
                if isinstance(row, dict) and row.get("origin") == "curated":
                    items.append({**row, "section": section_id, "type": type_key})
    return items


def _count_stale_curated_records(corpus: dict[str, Any]) -> int:
    return sum(1 for r in _all_curated_rows_by_section(corpus) if merge.is_stale(r))


@router.get("/stale")
async def get_stale_records():
    """Every curated record past the review window, across all sections
    (spec §5.1 'Stale Records' tile drill-through). Not a manifest nav
    section of its own -- reached only via the Overview tile, same pattern
    as `components` fanning across four generated collections."""
    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        _raise_corpus_unavailable(exc)

    rows = merge.annotate_stale(_all_curated_rows_by_section(corpus))
    stale_rows = [r for r in rows if r.get("stale")]
    return {"count": len(stale_rows), "items": stale_rows}


@router.get("/search")
async def search(q: str = Query(default="", max_length=200)):
    """Global search (spec §5.17): corpus entities (components, endpoints,
    jobs, tables, controls, abuse cases, threat scenarios, decisions, risks,
    reviews) plus live MITRE technique names -- exactly the sources the spec
    lists. No index subsystem: a bounded scan over the already mtime-cached
    corpus (merge.search_corpus docstring) plus one MITRE query."""
    if not q.strip():
        return {"query": q, "count": 0, "results": []}

    try:
        corpus = get_corpus()
    except CorpusValidationError as exc:
        _raise_corpus_unavailable(exc)

    results = merge.search_corpus(corpus, q)

    db = await get_db()
    try:
        technique_rows = await db.execute_fetchall(
            "SELECT technique_id, name, tactic FROM mitre_techniques", ()
        )
    finally:
        await db.close()
    results.extend(merge.search_mitre_techniques([dict(r) for r in technique_rows], q))

    return {"query": q, "count": len(results), "results": results}
