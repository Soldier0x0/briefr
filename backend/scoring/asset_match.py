"""Asset profile matching for Risk Score v1.1b (mirrors frontend graduation table)."""

from __future__ import annotations

from typing import Any, Optional

DEFAULT_ASSET_UNKNOWN = 0.5


def _profile_product_name(item: Any) -> str:
    """Safe string for profile product fields (guards non-str / None)."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("product") or item.get("cpeProduct") or "").strip()
    return ""


def profile_to_match_assets(profile: Optional[dict]) -> list[dict[str, str]]:
    """Flatten an asset profile to CPE-match asset rows."""
    if not profile:
        return []
    assets: list[dict[str, str]] = []
    for os_item in profile.get("operatingSystems") or []:
        if not isinstance(os_item, dict) or not str(os_item.get("product") or "").strip():
            continue
        assets.append(
            {
                "product": str(os_item.get("product") or "").strip(),
                "version": str(os_item.get("version") or "").strip(),
                "vendor": str(os_item.get("vendor") or "").strip(),
            }
        )
    for app in profile.get("applications") or []:
        if not isinstance(app, dict) or not str(
            app.get("product") or app.get("cpeProduct") or ""
        ).strip():
            continue
        assets.append(
            {
                "product": str(app.get("cpeProduct") or app.get("product") or "").strip(),
                "version": str(app.get("version") or "").strip(),
                "vendor": str(app.get("vendor") or "").strip(),
            }
        )
    for ai in profile.get("aiSystems") or []:
        name = _profile_product_name(ai)
        if not name:
            continue
        assets.append({"product": name, "version": "", "vendor": ""})
    return assets


def asset_score_from_backend(match_score: Optional[int]) -> tuple[float, str]:
    score = int(match_score or 0)
    if score >= 100:
        return 1.0, "Your asset directly affected (exact CPE version match)"
    if score >= 55:
        return 0.55, "Your asset found in affected products (CPE product match)"
    if score > 0:
        return score / 100.0, "Partial match to your asset profile"
    return 0.0, "No matching assets in your profile"


def _affected_products(cve: dict) -> list[str]:
    products = cve.get("affected_products") or []
    if isinstance(products, str):
        return [products.lower()]
    return [str(p).lower() for p in products if p]


def asset_match_info(cve: dict, profile: Optional[dict]) -> tuple[float, str]:
    """Graduated fuzzy asset match (tiers 1–9)."""
    if not profile:
        return DEFAULT_ASSET_UNKNOWN, ""

    affected = _affected_products(cve)
    desc_blob = f"{cve.get('description') or ''} {cve.get('summary') or ''}".lower()

    apps = profile.get("applications") or []
    oses = profile.get("operatingSystems") or []
    ais = profile.get("aiSystems") or []

    best_score = 0.0
    best_tier = "no match"
    best_label: Optional[str] = None

    for app in apps:
        if not isinstance(app, dict):
            continue
        vendor = str(app.get("vendor") or "").lower().strip()
        cpe_product = str(app.get("cpeProduct") or "").lower().strip()
        display_name = str(app.get("product") or "").strip()
        version = str(app.get("version") or "").strip()

        for prod in affected:
            parts = prod.split(":")
            aff_vendor = (parts[0] if parts else "").strip()
            aff_product = (parts[1] if len(parts) > 1 else prod).strip()

            vendor_match = bool(
                vendor
                and (
                    vendor == aff_vendor
                    or aff_vendor in vendor
                    or vendor in aff_vendor
                )
            )
            product_match = bool(
                cpe_product
                and (
                    cpe_product == aff_product
                    or aff_product in cpe_product
                    or cpe_product in aff_product
                )
            )

            if vendor_match and product_match:
                if version:
                    if best_score < 1.0:
                        best_score = 1.0
                        best_tier = "exact CPE match"
                        best_label = f"{display_name} {version}".strip()
                elif best_score < 0.9:
                    best_score = 0.9
                    best_tier = "CPE product match"
                    best_label = display_name or cpe_product
            elif product_match and not vendor_match and best_score < 0.75:
                best_score = 0.75
                best_tier = "product match"
                best_label = display_name or cpe_product
            elif vendor_match and not product_match and best_score < 0.65:
                best_score = 0.65
                best_tier = "vendor match"
                best_label = vendor

        if best_score < 0.45:
            needle = display_name.lower()
            if (needle and needle in desc_blob) or (
                cpe_product and cpe_product in desc_blob
            ):
                best_score = 0.45
                best_tier = "description mention"
                best_label = display_name or cpe_product

    for os_item in oses:
        if not isinstance(os_item, dict):
            continue
        os_prod = str(os_item.get("product") or "").lower().strip()
        os_version = str(os_item.get("version") or "").strip()
        os_display = str(os_item.get("product") or "").strip()

        for prod in affected:
            aff_product = (prod.split(":")[1] if ":" in prod else prod).strip()
            if os_prod and (
                aff_product in os_prod
                or os_prod in aff_product
                or os_prod in prod
            ):
                if best_score < 0.8:
                    best_score = 0.8
                    best_tier = "OS match"
                    best_label = os_display + (f" {os_version}" if os_version else "")

        if best_score < 0.45 and os_prod and os_prod in desc_blob:
            best_score = 0.45
            best_tier = "description mention"
            best_label = os_display

    for ai in ais:
        ai_name = _profile_product_name(ai)
        if not ai_name:
            continue
        ai_lower = ai_name.lower()

        for prod in affected:
            aff_product = (prod.split(":")[1] if ":" in prod else prod).strip()
            if ai_lower and (
                aff_product in ai_lower
                or ai_lower in aff_product
                or ai_lower in prod
            ):
                if best_score < 0.55:
                    best_score = 0.55
                    best_tier = "AI system match"
                    best_label = ai_name

        if best_score < 0.35 and ai_lower and ai_lower in desc_blob:
            best_score = 0.35
            best_tier = "AI system reference"
            best_label = ai_name

    match_type_map = {
        "exact CPE match": lambda lbl: f"{lbl} directly affected (exact CPE match)",
        "CPE product match": lambda lbl: f"{lbl} found in affected products (CPE product match)",
        "product match": lambda lbl: f"{lbl} found in affected products (product match)",
        "vendor match": lambda lbl: f"{lbl} vendor matched in affected products",
        "OS match": lambda lbl: f"{lbl} found in affected products (OS match)",
        "AI system match": lambda lbl: f"{lbl} AI/ML system in affected products",
        "AI system reference": lambda lbl: f"{lbl} referenced in vulnerability description",
        "description mention": lambda lbl: f"{lbl} mentioned in vulnerability description",
    }
    if best_tier in match_type_map and best_label:
        match_type = match_type_map[best_tier](best_label)
    else:
        match_type = "No matching assets in your profile"

    return best_score, match_type


def resolve_asset_component(
    cve: dict,
    profile: Optional[dict],
    backend_match_score: Optional[int],
) -> tuple[float, str]:
    """CPE backend match first, fuzzy graduation fallback when CPE score is zero."""
    if profile:
        cpe_score, cpe_label = asset_score_from_backend(backend_match_score)
        asset_score = cpe_score
        asset_match_type = cpe_label
        if cpe_score == 0.0:
            fuzzy_score, fuzzy_type = asset_match_info(cve, profile)
            if fuzzy_score > asset_score:
                asset_score = fuzzy_score
                asset_match_type = fuzzy_type
        return asset_score, asset_match_type

    score, match_type = asset_match_info(cve, profile)
    return score, match_type or ""


def cpe_match_score_for_cve(cve: dict, assets: list[dict]) -> int:
    """Score one CVE row against analyst assets using stored CPE matches."""
    if not assets:
        return 0
    from matching.cpe import score_cve_for_assets

    cpe_matches = cve.get("cpe_matches") or []
    if isinstance(cpe_matches, str):
        import json

        try:
            cpe_matches = json.loads(cpe_matches)
        except (json.JSONDecodeError, TypeError):
            cpe_matches = []
    if not cpe_matches:
        for entry in _affected_products(cve):
            if ":" in entry:
                vendor, product = entry.split(":", 1)
                cpe_matches.append({"vendor": vendor, "product": product})
    return score_cve_for_assets(cpe_matches, assets)
