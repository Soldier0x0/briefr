"""TM-6: project one live scoped-CWE aggregation into the four framework
workspaces (CWE / OWASP / CAPEC / STRIDE).

Every workspace is built from the same ``fetch_scoped_cwe_rows`` output, so
all four describe the *same* live set of CVEs through four lenses. Counting
rules that keep the numbers honest (spec central principle):

- A CVE carrying several CWEs contributes **once** to each distinct category /
  pattern it maps to (distinct-CVE counts, never CWE-occurrence sums that
  double-count a single advisory).
- CWEs with no mapping in ``reference.py`` are not dropped: OWASP / CAPEC /
  STRIDE each return an explicit ``unmapped`` bucket (CVEs whose every CWE is
  unmapped) so the parts still reconcile with the whole.
- Each row ships ``example_cves`` (KEV/EPSS-prioritised) as its drill-through
  evidence -- the exact advisories behind the count.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from typing import Any, Callable

from security_architecture.frameworks import reference

_EXAMPLE_LIMIT = 8


def _example_sort_key(cve: dict[str, Any]) -> tuple:
    # KEV first, then EPSS desc, then CVE id desc (recent-ish) -- the most
    # decision-relevant advisories surface as the drill-through examples.
    return (
        0 if cve.get("is_kev") else 1,
        -(cve.get("epss_score") or 0.0),
        _cve_sort_id(cve.get("cve_id")),
    )


def _cve_sort_id(cve_id: str | None) -> tuple:
    # Sort CVE ids by (year, number) descending without lexical surprises.
    if not cve_id:
        return (0, 0)
    parts = cve_id.split("-")
    try:
        return (-int(parts[1]), -int(parts[2]))
    except (IndexError, ValueError):
        return (0, 0)


def _example_cves(cves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(cves, key=_example_sort_key)[:_EXAMPLE_LIMIT]
    return [
        {"cve_id": c["cve_id"], "is_kev": c["is_kev"], "severity": c["severity"]}
        for c in ordered
    ]


def _kev_count(cves: list[dict[str, Any]]) -> int:
    return sum(1 for c in cves if c.get("is_kev"))


def cwe_workspace(scoped: dict[str, Any]) -> dict[str, Any]:
    """Weakness classes present in the scope, most-frequent first."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for cve in scoped["rows"]:
        for cwe in cve["cwe_ids"]:
            buckets.setdefault(cwe, []).append(cve)

    items = [
        {
            "id": cwe,
            "cwe_id": cwe,
            "name": reference.cwe_name(cwe),
            "cve_count": len(cves),
            "kev_count": _kev_count(cves),
            "owasp": reference.owasp_categories_for_cwe(cwe),
            "stride": reference.stride_categories_for_cwe(cwe),
            "example_cves": _example_cves(cves),
        }
        for cwe, cves in buckets.items()
    ]
    items.sort(key=lambda i: (-i["cve_count"], -i["kev_count"], i["id"]))
    return {
        "framework": "cwe",
        "items": items,
        "distinct_cwes": len(items),
        **_scope_meta(scoped),
    }


def _category_workspace(
    scoped: dict[str, Any],
    *,
    framework: str,
    categories: list[dict[str, Any]],
    cwe_to_cats: Callable[[str], list[str]],
) -> dict[str, Any]:
    """Shared OWASP/STRIDE rollup: distinct CVEs per category, with an explicit
    unmapped bucket. ``categories`` provides id/title/summary; ``cwe_to_cats``
    maps a CWE to the category ids it belongs to."""
    cves_by_cat: dict[str, dict[str, dict[str, Any]]] = {c["id"]: {} for c in categories}
    cwes_by_cat: dict[str, set[str]] = {c["id"]: set() for c in categories}
    unmapped_cves: dict[str, dict[str, Any]] = {}

    for cve in scoped["rows"]:
        cats_for_cve: set[str] = set()
        for cwe in cve["cwe_ids"]:
            for cat_id in cwe_to_cats(cwe):
                cats_for_cve.add(cat_id)
                cwes_by_cat[cat_id].add(cwe)
        if cats_for_cve:
            for cat_id in cats_for_cve:
                cves_by_cat[cat_id][cve["cve_id"]] = cve
        elif cve["cwe_ids"]:
            # Has CWEs, but none map to this framework -- honest unmapped bucket.
            unmapped_cves[cve["cve_id"]] = cve

    items = []
    for cat in categories:
        cves = list(cves_by_cat[cat["id"]].values())
        items.append({
            "id": cat["id"],
            "title": cat["title"],
            "summary": cat["summary"],
            "cve_count": len(cves),
            "kev_count": _kev_count(cves),
            "cwe_ids": sorted(cwes_by_cat[cat["id"]], key=_cwe_num),
            "example_cves": _example_cves(cves),
        })
    items.sort(key=lambda i: (-i["cve_count"], -i["kev_count"], i["id"]))

    unmapped = list(unmapped_cves.values())
    result = {
        "framework": framework,
        "items": items,
        "unmapped": {
            "cve_count": len(unmapped),
            "kev_count": _kev_count(unmapped),
            "example_cves": _example_cves(unmapped),
            "note": "CVEs whose CWEs are not mapped to this framework in the reference set.",
        },
        **_scope_meta(scoped),
    }
    return result


def owasp_workspace(scoped: dict[str, Any]) -> dict[str, Any]:
    result = _category_workspace(
        scoped,
        framework="owasp",
        categories=reference.OWASP_TOP10_2021,
        cwe_to_cats=reference.owasp_categories_for_cwe,
    )
    result["owasp_version"] = reference.OWASP_VERSION
    return result


def stride_workspace(scoped: dict[str, Any]) -> dict[str, Any]:
    result = _category_workspace(
        scoped,
        framework="stride",
        categories=reference.STRIDE_CATEGORIES,
        cwe_to_cats=reference.stride_categories_for_cwe,
    )
    result["mapping"] = "heuristic"
    return result


def capec_workspace(scoped: dict[str, Any]) -> dict[str, Any]:
    """Attack patterns implied by the scope's CWEs (MITRE CWE->CAPEC)."""
    cves_by_capec: dict[str, dict[str, dict[str, Any]]] = {}
    cwes_by_capec: dict[str, set[str]] = {}
    unmapped_cves: dict[str, dict[str, Any]] = {}

    for cve in scoped["rows"]:
        capecs_for_cve: set[str] = set()
        for cwe in cve["cwe_ids"]:
            for capec in reference.capec_for_cwe(cwe):
                capecs_for_cve.add(capec)
                cwes_by_capec.setdefault(capec, set()).add(cwe)
        if capecs_for_cve:
            for capec in capecs_for_cve:
                cves_by_capec.setdefault(capec, {})[cve["cve_id"]] = cve
        elif cve["cwe_ids"]:
            unmapped_cves[cve["cve_id"]] = cve

    items = [
        {
            "id": capec,
            "capec_id": capec,
            "name": reference.capec_name(capec),
            "cve_count": len(cves),
            "kev_count": _kev_count(list(cves.values())),
            "cwe_ids": sorted(cwes_by_capec.get(capec, set()), key=_cwe_num),
            "example_cves": _example_cves(list(cves.values())),
        }
        for capec, cves in cves_by_capec.items()
    ]
    items.sort(key=lambda i: (-i["cve_count"], -i["kev_count"], _capec_num(i["id"])))

    unmapped = list(unmapped_cves.values())
    return {
        "framework": "capec",
        "items": items,
        "unmapped": {
            "cve_count": len(unmapped),
            "kev_count": _kev_count(unmapped),
            "example_cves": _example_cves(unmapped),
            "note": "CVEs whose CWEs have no CWE->CAPEC mapping in the reference set.",
        },
        **_scope_meta(scoped),
    }


def _cwe_num(cwe_id: str) -> int:
    try:
        return int(cwe_id.split("-")[1])
    except (IndexError, ValueError):
        return 0


def _capec_num(capec_id: str) -> int:
    try:
        return int(capec_id.split("-")[1])
    except (IndexError, ValueError):
        return 0


def _scope_meta(scoped: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": scoped["scope"],
        "terms": scoped.get("terms") or [],
        "total_in_scope": scoped["total_in_scope"],
        "sample_size": scoped["sample_size"],
        "cve_with_cwe": scoped["cve_with_cwe"],
        "truncated": scoped["sample_size"] < scoped["total_in_scope"],
        # Passed through so the UI can explain an empty result honestly (e.g.
        # scope=stack with no stack set) rather than looking like "no threats".
        "unavailable": scoped.get("unavailable", False),
        "reason": scoped.get("reason"),
    }
