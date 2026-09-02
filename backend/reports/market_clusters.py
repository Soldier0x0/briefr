"""Product clustering and formatting for the daily brief products section."""

from __future__ import annotations

import json
from typing import Any

from db.software_catalog import display_name_for

UNANALYZED_LABEL = "unanalyzed"
UNMAPPED_DISPLAY = "Unmapped"
_SEVERITIES = ("critical", "high", "medium", "low")
_PRODUCT_LIMIT = 8


def _parse_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _product_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _primary_vendor_product(cpe_matches, affected_products) -> tuple[str, str]:
    for match in _parse_list(cpe_matches):
        if isinstance(match, dict):
            product = _product_key(match.get("product"))
            vendor = _product_key(match.get("vendor"))
            if product:
                return vendor, product

    for affected in _parse_list(affected_products):
        raw = _product_key(affected)
        if not raw:
            continue
        if ":" in raw:
            vendor, product = raw.split(":", 1)
            return vendor, product or UNANALYZED_LABEL
        return "", raw

    return "", UNANALYZED_LABEL


def primary_product(cpe_matches, affected_products) -> str:
    _vendor, product = _primary_vendor_product(cpe_matches, affected_products)
    return product


def cluster_weight(c, h, m, l) -> int:
    return c * 100 + h * 3 + m + l * 0


def _raw_key_label(key: str) -> str:
    if key == UNANALYZED_LABEL:
        return UNMAPPED_DISPLAY
    return key.replace("_", " ")


def product_display_label(
    vendor: str,
    product: str,
    *,
    catalog_titles: dict[tuple[str, str], str] | None = None,
) -> str:
    """Catalog title, else display_name_for(vendor, product), else raw key.

    Never invents a vendor that is not on the cluster or in the catalog title.
    """
    key = (product or "").strip().lower()
    vend = (vendor or "").strip().lower()
    if not key or key == UNANALYZED_LABEL:
        return UNMAPPED_DISPLAY
    titles = catalog_titles or {}
    if vend:
        catalog = (titles.get((vend, key)) or "").strip()
        if catalog:
            return catalog
        return display_name_for(vend, key)
    return _raw_key_label(key)


def is_unmapped_product(product: dict) -> bool:
    label = str(product.get("label") or "")
    key = str(product.get("product") or "")
    return label in {UNMAPPED_DISPLAY, UNANALYZED_LABEL} or key == UNANALYZED_LABEL


def unmapped_coverage(market: dict) -> dict[str, int]:
    published = int(market.get("published") or 0)
    unmapped = int(market.get("unmapped") or 0)
    if unmapped == 0:
        for product in market.get("products") or []:
            if is_unmapped_product(product):
                unmapped += int(product.get("total") or 0)
    named = max(0, published - unmapped)
    return {"published": published, "unmapped": unmapped, "named": named}


def cluster_published(
    rows: list[dict],
    *,
    catalog_titles: dict[tuple[str, str], str] | None = None,
) -> dict:
    severity_totals = {severity: 0 for severity in _SEVERITIES}
    clusters: dict[str, dict[str, int]] = {}
    cluster_vendors: dict[str, str] = {}

    for row in rows:
        severity = str(row.get("severity") or "").strip().lower()
        if severity not in severity_totals:
            severity = "medium"
        severity_totals[severity] += 1

        vendor, key = _primary_vendor_product(
            row.get("cpe_matches"), row.get("affected_products")
        )
        if vendor:
            existing = cluster_vendors.get(key)
            if existing is None:
                cluster_vendors[key] = vendor
            elif existing and existing != vendor:
                cluster_vendors[key] = ""
        cluster = clusters.setdefault(
            key,
            {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        cluster["total"] += 1
        cluster[severity] += 1

    titles = catalog_titles or {}
    resolved: list[tuple[str, str, str, dict[str, int]]] = []
    label_counts: dict[str, int] = {}
    for key, counts in clusters.items():
        vendor = cluster_vendors.get(key, "")
        label = product_display_label(vendor, key, catalog_titles=titles)
        resolved.append((vendor, key, label, counts))
        label_counts[label] = label_counts.get(label, 0) + 1

    products = []
    for vendor, key, label, counts in resolved:
        if key == UNANALYZED_LABEL:
            display = UNMAPPED_DISPLAY
        elif label_counts[label] > 1:
            display = key
        else:
            display = label
        products.append(
            {
                "label": display,
                "vendor": vendor,
                "product": key,
                **counts,
            }
        )

    products.sort(
        key=lambda product: (
            -cluster_weight(
                product["critical"],
                product["high"],
                product["medium"],
                product["low"],
            ),
            -product["total"],
            product["label"],
        )
    )

    unmapped_total = int(clusters.get(UNANALYZED_LABEL, {}).get("total") or 0)
    return {
        "published": len(rows),
        **severity_totals,
        "unmapped": unmapped_total,
        "products": products[:_PRODUCT_LIMIT],
        "omitted_products": max(0, len(products) - _PRODUCT_LIMIT),
    }


def format_market_section(market: dict) -> list[str]:
    if market["published"] == 0:
        return []

    lines = [
        "Products",
        (
            f"Published: {market['published']}  ·  "
            f"Critical: {market['critical']} · High: {market['high']} · "
            f"Medium: {market['medium']} · Low: {market['low']}"
        ),
    ]
    for product in market["products"]:
        lines.append(
            f"• {product['label']}  {product['total']}  "
            f"(Critical {product['critical']} · High {product['high']} · "
            f"Medium {product['medium']} · Low {product['low']})"
        )
    if market["omitted_products"]:
        lines.append(f"+{market['omitted_products']} products in BRIEFR.")
    return lines
