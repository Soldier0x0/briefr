"""Local boosters (no OTX required) and stack gating — Correlation v2 Phase 3 subset."""

from __future__ import annotations

from typing import Any


async def stack_terms_list(db: Any) -> list[str]:
    """Admin My Stack product terms (after env migrate-once). Not live env."""
    from matching.stack_assets import assets_to_terms
    from preferences.repo import get_operator_stack_assets

    assets = await get_operator_stack_assets(db)
    return [t.strip().lower() for t in assets_to_terms(assets) if t.strip()]


def cve_matches_stack(
    cve_id: str,
    description: str,
    affected_products: list | str,
    terms: list[str],
) -> bool:
    """Mirrors routers.cves._stack_match_clause, evaluated in Python on an
    already-fetched row instead of a second SQL round trip."""
    if not terms:
        return False
    cve_upper = (cve_id or "").upper()
    if isinstance(affected_products, list):
        products_blob = " ".join(str(p) for p in affected_products).lower()
    else:
        products_blob = (affected_products or "").lower()
    desc_lower = (description or "").lower()
    for term in terms:
        if term.upper() == cve_upper:
            return True
        if term in desc_lower or term in products_blob:
            return True
    return False


async def kev_exploit_boosters(db, member_cve_ids: list[str], anchor: str) -> dict[str, list[str]]:
    """KEV/exploit signal among campaign peers (excludes the anchor CVE itself)."""
    others = sorted({m for m in member_cve_ids if m and m != anchor})
    if not others:
        return {"kev": [], "exploit": []}
    placeholders = ",".join("?" * len(others))
    rows = await db.execute_fetchall(
        f"SELECT cve_id, is_kev, has_poc FROM cves WHERE cve_id IN ({placeholders})",
        tuple(others),
    )
    kev = sorted(r["cve_id"] for r in rows if r["is_kev"])
    exploit = sorted(r["cve_id"] for r in rows if r["has_poc"] and not r["is_kev"])
    return {"kev": kev, "exploit": exploit}
