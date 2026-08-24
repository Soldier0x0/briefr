"""Build operator stack assets and match CVEs without description LIKE."""

from __future__ import annotations

import json
from typing import Any

from matching.cpe import score_cve_for_assets
from preferences.validate import sanitize_profile


def terms_to_assets(stack_terms: str) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for raw in (stack_terms or "").split(","):
        product = raw.strip()
        if not product:
            continue
        assets.append({"product": product, "vendor": "", "version": ""})
    return assets


def assets_to_terms(assets: list[dict[str, str]]) -> list[str]:
    terms: list[str] = []
    for asset in assets:
        product = (asset.get("product") or "").strip()
        if product and product not in terms:
            terms.append(product)
    return terms


def profile_to_assets(profile: dict[str, Any] | None) -> list[dict[str, str]]:
    clean = sanitize_profile(profile) if profile else None
    if not clean:
        return []
    assets: list[dict[str, str]] = []
    for row in clean.get("operatingSystems") or []:
        product = (row.get("product") or "").strip()
        if not product:
            continue
        assets.append({
            "product": product,
            "vendor": (row.get("vendor") or "").strip(),
            "version": (row.get("version") or "").strip(),
        })
    for row in clean.get("applications") or []:
        product = (row.get("cpeProduct") or row.get("product") or "").strip()
        if not product:
            continue
        assets.append({
            "product": product,
            "vendor": (row.get("vendor") or "").strip(),
            "version": (row.get("version") or "").strip(),
        })
    return assets


def _parse_json_list(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []
    return []


def _affected_to_cpes(affected_products: Any) -> list[dict[str, str]]:
    cpes: list[dict[str, str]] = []
    for item in _parse_json_list(affected_products):
        text = str(item or "").strip()
        if not text:
            continue
        if ":" in text:
            vendor, product = text.split(":", 1)
        else:
            vendor, product = "", text
        cpes.append({
            "vendor": vendor.strip(),
            "product": product.strip(),
            "version": "*",
        })
    return cpes


def cve_matches_assets(
    cpe_matches: Any,
    affected_products: Any,
    assets: list[dict[str, str]],
) -> bool:
    if not assets:
        return False
    parsed_cpes = [c for c in _parse_json_list(cpe_matches) if isinstance(c, dict)]
    if score_cve_for_assets(parsed_cpes, assets) > 0:
        return True
    return score_cve_for_assets(_affected_to_cpes(affected_products), assets) > 0
