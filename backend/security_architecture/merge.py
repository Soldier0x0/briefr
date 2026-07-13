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
from typing import Any

from routers.cves import _stack_match_clause

# ENABLED-style env vars across the codebase default to "1" and treat these
# as falsy (see rate_limit_store, feeds/*_sync.py, ml/embeddings.py, etc.) --
# match that convention so a control's live_flag reads the same as every
# other runtime toggle.
_FALSY = {"0", "false", "no", "off"}


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
    `live_flag` reads the actual runtime env var, same truthiness convention
    as the rest of the codebase's *_ENABLED flags."""
    flag = control.get("live_flag")
    if not flag:
        return True
    return os.environ.get(flag, "1").strip().lower() not in _FALSY


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
        SELECT cve_id, severity, cvss_score, epss_score, is_kev, published,
               description, affected_products
        FROM cves
        WHERE ({stack_clause}) AND (is_kev = 1 OR severity = 'CRITICAL')
        ORDER BY is_kev DESC, published DESC
        LIMIT 50
        """,
        stack_params,
    )

    live_rows = []
    for r in rows:
        row = dict(r)
        matched = _matched_term(row, terms)
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
            "severity": "critical" if is_kev else (row.get("severity") or "").lower(),
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
