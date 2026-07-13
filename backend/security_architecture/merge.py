"""TM-3: read-time merge of the Security Architecture Corpus with live
DB/API data -- MITRE coverage, control active flags, and the self-stack
CVE exposure merge (spec §4.5).

No new matching or scoring code lives here: this module is glue over the
existing shipping pipeline -- `routers.cves._stack_match_clause` and
`threat_model.scenarios.build_threat_scenarios` -- pointed at the
generated self-stack instead of a user's asset profile. Same fuzzy
term-matching limitation as user stacks; every self-stack row shows its
matched term (spec §4.5 honesty constraint).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from routers.cves import _stack_match_clause

# ENABLED-style env vars across the codebase default to "1" and treat these
# as falsy (see rate_limit_store, feeds/*_sync.py, ml/embeddings.py, etc.) --
# match that convention so a control's live_flag reads the same as every
# other runtime toggle.
_FALSY = {"0", "false", "no", "off"}

# TM-5 (spec §4.1 staleness decay): a curated record past review_date + this
# window renders STALE and is excluded from every coverage/compliance
# percentage that reads it. Shared here so the router's per-row `stale` flag,
# the Controls Active ratio, and the risk-register/review-history/PDF-export
# disclaimer all compute the same answer from one place -- three independent
# staleness calculations is how the PDF and the screen end up disagreeing.
STALE_WINDOW_DAYS = 90


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def is_stale(record: dict[str, Any], *, today: date | None = None) -> bool:
    """A curated record is stale once its review_date is more than
    STALE_WINDOW_DAYS in the past. Generated and live rows never carry a
    review_date judgment call, so they are never stale by definition (spec
    §4.1: staleness decay applies to the curated layer only)."""
    if record.get("origin") != "curated":
        return False
    rev_date = _as_date(record.get("review_date"))
    if rev_date is None:
        return False
    cutoff = (today or date.today()) - timedelta(days=STALE_WINDOW_DAYS)
    return rev_date < cutoff


def annotate_stale(rows: list[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    """Add a `stale: bool` field to every row -- the single source of truth
    the STALE badge, the percentage-exclusion math, and the PDF footer
    disclaimer all read (spec §4.1, §5.16)."""
    return [
        {**r, "stale": is_stale(r, today=today)} if isinstance(r, dict) else r
        for r in rows
    ]


def controls_active_ratio(controls: list[dict[str, Any]]) -> dict[str, int]:
    """Overview 'Controls Active' tile (spec §5.1: 'Live-flag-verified active
    / total controls'). A control whose review has lapsed is not a verified
    control -- stale controls are excluded from both the numerator and the
    denominator, so the tile's ratio is exactly the STALE-decay percentage
    the acceptance criteria require (§9.6)."""
    eligible = [c for c in controls if not is_stale(c)]
    active = sum(1 for c in eligible if resolve_control_active(c))
    return {"active": active, "total": len(eligible), "stale_excluded": len(controls) - len(eligible)}


def self_stack_terms(corpus: dict[str, Any]) -> list[str]:
    """Stack terms from the generated self_stack.yaml layer (§4.5). Empty
    until `scripts/generate_security_corpus.py` has run at least once."""
    entries = (corpus.get("self_stack") or {}).get("terms") or []
    return [e["term"] for e in entries if isinstance(e, dict) and e.get("term")]


def self_stack_query(corpus: dict[str, Any]) -> str:
    """Self-stack terms as a comma-separated string, the same shape
    `_stack_match_clause` and `build_threat_scenarios` accept for a user
    stack -- so the self-stack toggle is a parameter swap, not new code."""
    return ", ".join(self_stack_terms(corpus))


def resolve_control_active(control: dict[str, Any]) -> bool:
    """A control without a `live_flag` is structural (enforced unconditionally
    in code, e.g. parameterized SQL, TLS-only webhooks) -- its presence in
    the codebase *is* the live proof, so it reads active. A control with a
    `live_flag` reads the actual runtime env var.

    Most of this codebase's `*_ENABLED` flags are opt-*out* (default True
    when unset -- e.g. `RATE_LIMIT_ENABLED`, `settings.rate_limit_enabled:
    bool = True`), so that's the default here too. A control whose flag is
    opt-*in* instead (default False when unset -- e.g.
    `BRIEFR_REQUIRE_POSTGRES`, `settings.briefr_require_postgres: bool =
    False`) must say so explicitly via `live_flag_default_when_unset: false`
    in its corpus record; otherwise this would silently misreport an unset
    opt-in flag as active, which is exactly the confidently-wrong posture
    claim the module exists to avoid."""
    flag = control.get("live_flag")
    if not flag:
        return True
    raw = os.environ.get(flag)
    if raw is None:
        return bool(control.get("live_flag_default_when_unset", True))
    return raw.strip().lower() not in _FALSY


def enrich_controls(controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Controls inventory rows with a live `active` flag merged in (spec
    §5.9: 'mark control active: true/false from runtime')."""
    return [{**c, "active": resolve_control_active(c)} for c in controls]


def _matched_term(cve_row: dict[str, Any], terms: list[str]) -> str | None:
    """Which self-stack term matched this CVE row -- shown on every live row
    per the every-status-word-explains-itself rule (spec §4.5)."""
    cve_id = (cve_row.get("cve_id") or "").upper()
    haystack = f"{cve_row.get('description') or ''} {cve_row.get('affected_products') or ''}".lower()
    for term in terms:
        if term.upper() == cve_id:
            return term
        if term.lower() and term.lower() in haystack:
            return term
    return None


async def self_stack_risk_rows(db: Any, corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """Live risk-register rows (origin: live) auto-derived from KEV / critical
    CVE hits on the generated self-stack (spec §4.5, §5.12). These rows
    cannot be closed by hand -- they exist only while the underlying query
    still matches, so there is nothing to store; recomputed at read time."""
    terms = self_stack_terms(corpus)
    if not terms:
        return []

    stack_clause, stack_params, _ = _stack_match_clause(", ".join(terms))
    if not stack_clause:
        return []

    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.severity, c.cvss_score, c.epss_score, c.is_kev, c.published,
               c.description, c.affected_products
        FROM cves c
        WHERE ({stack_clause}) AND (c.is_kev = 1 OR c.severity = 'CRITICAL')
        ORDER BY c.is_kev DESC, c.published DESC
        LIMIT 50
        """,
        stack_params,
    )

    live_rows = []
    for r in rows:
        row = dict(r)
        # The WHERE clause guarantees at least one term matched, but which
        # one is a second, looser scan (substring vs. the exact clause the
        # DB used) -- fall back to "unknown" rather than let a None slip
        # into the row's title/summary as the literal string "None".
        matched = _matched_term(row, terms) or "unknown"
        is_kev = bool(row.get("is_kev"))
        live_rows.append({
            "id": f"self-stack-{row['cve_id']}",
            "title": f"{row['cve_id']} — term match \"{matched}\"",
            "summary": (
                f"{'CISA KEV' if is_kev else 'Critical'} CVE matching BRIEFR's own "
                f"generated self-stack on the term \"{matched}\" (fuzzy term match, "
                f"not SBOM/PURL-precise -- see self-stack methodology)."
            ),
            "category": "self-exposure",
            "origin": "live",
            "status": "open",
            # The DB's own severity, not an invented one -- a KEV hit can be
            # HIGH, not CRITICAL; is_kev already carries the urgency signal
            # (badge + summary), inventing "critical" here would be exactly
            # the "opinion rendered as measurement" the central principle
            # (spec v2 note 3) forbids.
            "severity": (row.get("severity") or "").lower(),
            "cve_id": row["cve_id"],
            "matched_term": matched,
            "is_kev": is_kev,
            "cvss_score": row.get("cvss_score"),
            "epss_score": row.get("epss_score"),
            "published": row.get("published"),
        })
    return live_rows


async def self_cve_exposure_summary(db: Any, corpus: dict[str, Any]) -> dict[str, Any]:
    """Overview tile source: KEV + critical CVE count matching the self-stack
    (spec §5.1 'Self CVE Exposure')."""
    rows = await self_stack_risk_rows(db, corpus)
    return {
        "count": len(rows),
        "kev_count": sum(1 for r in rows if r["is_kev"]),
        "critical_count": sum(1 for r in rows if r["severity"] == "critical"),
        "terms": self_stack_terms(corpus),
    }


# ── TM-5: Review History (audit_log merge) ──────────────────────────────

# Security-relevant audit_log action prefixes (spec §4.2 "Review events:
# audit_log filtered by security-related actions", §5.14: "Merge audit_log
# security actions + corpus reviews.yaml"). Sourced from the real action
# strings passed to `audit()` across routers/*.py (grepped at TM-5 build
# time) -- auth events, backup/integrity/migration operations, config
# changes, restarts, and scheduler pause/resume are the security-adjacent
# subset; routine content refreshes (refresh.kev, hunt_packs.delete, ...)
# are operational noise, not security review events, and are excluded.
SECURITY_AUDIT_ACTION_PREFIXES = (
    "auth.",
    "backup.",
    "database.",
    "diagnostics.integrity",
    "config.apply",
    "system.restart",
    "scheduler.",
)


def is_security_audit_action(action: str) -> bool:
    return any(action.startswith(p) for p in SECURITY_AUDIT_ACTION_PREFIXES)


async def security_audit_log_events(db: Any, *, limit: int = 100) -> list[dict[str, Any]]:
    """Audit-log rows shaped as review-history entries (spec §5.14). Reuses
    the same `audit_log` table and `redact.mask_audit_log_target` masking
    helper the admin Audit Log view already uses (`routers/admin.py::
    get_audit_log`) -- not a duplicate query, not a duplicate redaction
    rule. This endpoint is analyst-scoped (Security Architecture has no
    admin-only gate), so it re-runs the same read directly rather than
    calling the admin-only router function."""
    from redact import mask_audit_log_target

    rows = await db.execute_fetchall(
        """
        SELECT id, actor, action, target, created_at
        FROM audit_log
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    events = []
    for row in rows:
        r = dict(row)
        action = r.get("action") or ""
        if not is_security_audit_action(action):
            continue
        target = mask_audit_log_target(action, r.get("target"))
        events.append({
            "id": f"audit-{r['id']}",
            "title": action,
            "summary": f"{r.get('actor') or 'system'} — {target}" if target else (r.get("actor") or "system"),
            "category": "audit-log",
            "origin": "live",
            "status": "logged",
            "actor": r.get("actor"),
            "action": action,
            "target": target,
            "occurred_at": r.get("created_at"),
        })
    return events


# ── TM-5: Global search ──────────────────────────────────────────────────

# Which corpus files' record lists participate in search, and the section id
# each hit should drill through to (spec §5.17 "Index built server-side from
# corpus + MITRE names + control titles + API paths").
_SEARCH_CORPUS_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("components", "components", "components"),
    ("api_inventory", "endpoints", "components"),
    ("scheduler_jobs", "jobs", "components"),
    ("db_tables", "tables", "components"),
    ("trust_boundaries", "trust_boundaries", "trust_boundaries"),
    ("controls", "controls", "controls"),
    ("abuse_cases", "abuse_cases", "abuse_cases"),
    ("threat_scenarios", "threat_scenarios", "threat_scenarios"),
    ("security_decisions", "security_decisions", "security_decisions"),
    ("risks", "risks", "risks"),
    ("reviews", "reviews", "reviews"),
)


def _search_haystack(record: dict[str, Any]) -> str:
    parts = [
        record.get("title"), record.get("id"), record.get("summary"),
        record.get("path"), record.get("method"),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def search_corpus(corpus: dict[str, Any], query: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Search over the already mtime-cached corpus (spec §5.17). No index
    subsystem: this is a bounded linear scan over data `corpus_loader.
    get_corpus()` already holds in memory -- cheap enough to run on the
    request path (CLAUDE.md danger zone 6 only forbids *heavy* work there),
    and re-scanning on every keystroke is exactly as fresh as the corpus
    itself."""
    q = query.strip().lower()
    if not q:
        return []

    results: list[dict[str, Any]] = []
    for corpus_key, list_key, section in _SEARCH_CORPUS_SOURCES:
        for record in (corpus.get(corpus_key) or {}).get(list_key) or []:
            if not isinstance(record, dict):
                continue
            if q not in _search_haystack(record):
                continue
            results.append({
                "id": record.get("id") or record.get("path") or "",
                "title": record.get("title") or record.get("path") or record.get("id") or "",
                "summary": record.get("summary"),
                "type": corpus_key,
                "section": section,
            })
            if len(results) >= limit:
                return results
    return results


def search_mitre_techniques(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """MITRE technique names/ids matching the query (spec §5.17: index
    includes 'MITRE names'). `rows` are `mitre_techniques` table rows
    (id, technique_id, name, tactic) -- one bounded query, not a new table."""
    q = query.strip().lower()
    if not q:
        return []
    results = []
    for row in rows:
        haystack = f"{row.get('technique_id') or ''} {row.get('name') or ''}".lower()
        if q in haystack:
            results.append({
                "id": row.get("technique_id"),
                "title": f"{row.get('technique_id')} — {row.get('name')}",
                "summary": row.get("tactic"),
                "type": "mitre_technique",
                "section": "mitre_attack",
            })
    return results
