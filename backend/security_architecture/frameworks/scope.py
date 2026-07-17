"""TM-6: resolve a framework Scope selector into a bounded, live query over
the ingested CVE corpus.

Scopes (spec reframe -- the user's own threat surface, not BRIEFR's):

- ``all``       -- the whole ingested corpus
- ``stack``     -- CVEs matching the user's saved asset stack (or an explicit
                   ``stack=`` override), via the shipping
                   ``routers.cves._stack_match_clause`` -- same matching Forge
                   uses, no new code
- ``watchlist`` -- CVEs the user is tracking (``watchlist`` table)
- ``kev``       -- CISA KEV entries only

Aggregation reads only the columns it needs (``cve_id``, ``severity``,
``is_kev``, ``epss_score``, ``published``, ``cwe_ids``) and is bounded by a
cap, prioritising KEV then most-recent, so a whole-corpus scope stays a
request-path-safe read (CLAUDE.md danger zone 6). The sample size and total
in scope are both returned so a capped aggregation is never mistaken for a
complete one (every-number-shows-its-inputs).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
from typing import Any

from routers.cves import _stack_match_clause

VALID_SCOPES = ("all", "stack", "watchlist", "kev")

# Cap on rows pulled for in-Python CWE aggregation. KEV + most-recent are
# prioritised so the capped window is the most decision-relevant slice; the
# response always reports total_in_scope alongside sample_size so a truncated
# aggregation is visibly truncated.
DEFAULT_ROW_CAP = 20000

_VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def _parse_cwe_ids(raw: Any) -> list[str]:
    """Parse a cves.cwe_ids TEXT JSON array into a de-duped, upper-cased list
    of ``CWE-<n>`` strings. Malformed / empty values yield []."""
    if not raw:
        return []
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        try:
            values = json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values if isinstance(values, list) else []:
        s = str(v).strip().upper()
        if s.startswith("CWE-") and s not in seen:
            seen.add(s)
            out.append(s)
    return out


async def _resolve_stack_terms(
    db: Any, explicit_stack: str | None, user_id: int | None
) -> str:
    """The stack string to match on: an explicit ``stack=`` override wins,
    else the user's saved stack (``/api/me/stack``). '' when neither exists."""
    if explicit_stack and explicit_stack.strip():
        return explicit_stack.strip()
    if user_id is None:
        return ""
    from preferences.repo import get_user_stack

    saved = await get_user_stack(db, user_id)
    return (saved or {}).get("stack_terms") or ""


async def build_scope_where(
    db: Any,
    scope: str,
    *,
    explicit_stack: str | None = None,
    user_id: int | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """Build the WHERE clause + params for a scope, plus descriptive meta.

    Returns ``{where, params, scope, terms, unavailable, reason}``. ``where``
    is a SQL fragment (without the ``WHERE`` keyword) over the ``cves c``
    table; ``params`` are its bound values. ``unavailable`` is True when the
    scope cannot be satisfied (e.g. ``stack`` with no stack set) -- callers
    return an honest empty result with ``reason`` rather than a silent
    whole-corpus fallback."""
    if scope not in VALID_SCOPES:
        scope = "all"

    clauses: list[str] = []
    params: list[Any] = []
    terms: list[str] = []
    unavailable = False
    reason: str | None = None

    if scope == "stack":
        stack_str = await _resolve_stack_terms(db, explicit_stack, user_id)
        stack_clause, stack_params, stack_terms = _stack_match_clause(stack_str)
        if not stack_clause:
            unavailable = True
            reason = (
                "No stack set. Save an asset stack in your profile (or pass "
                "?stack=term1,term2) to scope frameworks to your own technology."
            )
        else:
            clauses.append(stack_clause)
            params.extend(stack_params)
            terms = stack_terms
    elif scope == "watchlist":
        clauses.append("c.cve_id IN (SELECT cve_id FROM watchlist)")
    elif scope == "kev":
        clauses.append("c.is_kev = 1")

    if severity:
        sev = severity.strip().upper()
        if sev in _VALID_SEVERITIES:
            clauses.append("c.severity = ?")
            params.append(sev)

    where = " AND ".join(f"({c})" for c in clauses) if clauses else "1=1"
    return {
        "where": where,
        "params": params,
        "scope": scope,
        "terms": terms,
        "unavailable": unavailable,
        "reason": reason,
    }


async def fetch_scoped_cwe_rows(
    db: Any,
    scope: str,
    *,
    explicit_stack: str | None = None,
    user_id: int | None = None,
    severity: str | None = None,
    row_cap: int = DEFAULT_ROW_CAP,
) -> dict[str, Any]:
    """Live CVE rows (id/severity/is_kev/epss/published + parsed cwe_ids) for
    the scope, bounded by ``row_cap``, plus ``total_in_scope`` and
    ``cve_with_cwe`` counts. The single live read every framework aggregator
    is a projection of."""
    scope_meta = await build_scope_where(
        db, scope, explicit_stack=explicit_stack, user_id=user_id, severity=severity
    )
    if scope_meta["unavailable"]:
        return {
            "rows": [],
            "total_in_scope": 0,
            "sample_size": 0,
            "cve_with_cwe": 0,
            "scope": scope_meta["scope"],
            "terms": scope_meta["terms"],
            "unavailable": True,
            "reason": scope_meta["reason"],
        }

    where = scope_meta["where"]
    params = scope_meta["params"]

    total_row = await db.execute_fetchall(
        f"SELECT COUNT(*) AS n FROM cves c WHERE {where}", tuple(params)
    )
    total_in_scope = int(dict(total_row[0])["n"]) if total_row else 0

    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.severity, c.cvss_score, c.epss_score, c.is_kev,
               c.published, c.cwe_ids
        FROM cves c
        WHERE {where}
        ORDER BY c.is_kev DESC, c.published DESC
        LIMIT ?
        """,
        (*params, row_cap),
    )

    parsed: list[dict[str, Any]] = []
    cve_with_cwe = 0
    for r in rows:
        row = dict(r)
        cwe_ids = _parse_cwe_ids(row.get("cwe_ids"))
        if cwe_ids:
            cve_with_cwe += 1
        parsed.append({
            "cve_id": row.get("cve_id"),
            "severity": (row.get("severity") or "").upper(),
            "cvss_score": row.get("cvss_score"),
            "epss_score": row.get("epss_score"),
            "is_kev": bool(row.get("is_kev")),
            "published": row.get("published"),
            "cwe_ids": cwe_ids,
        })

    return {
        "rows": parsed,
        "total_in_scope": total_in_scope,
        "sample_size": len(parsed),
        "cve_with_cwe": cve_with_cwe,
        "scope": scope_meta["scope"],
        "terms": scope_meta["terms"],
        "unavailable": False,
        "reason": None,
    }
