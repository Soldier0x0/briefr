"""Product clustering and formatting for the daily brief MARKET section."""

from __future__ import annotations

import json
from typing import Any

UNANALYZED_LABEL = "unanalyzed"
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


def primary_product(cpe_matches, affected_products) -> str:
    for match in _parse_list(cpe_matches):
        if isinstance(match, dict):
            product = _product_key(match.get("product"))
            if product:
                return product

    for affected in _parse_list(affected_products):
        product = _product_key(affected)
        if product:
            return product.split(":", 1)[-1] or UNANALYZED_LABEL

    return UNANALYZED_LABEL


def cluster_weight(c, h, m, l) -> int:
    return c * 10 + h * 3 + m + l * 0


def cluster_published(rows: list[dict]) -> dict:
    severity_totals = {severity: 0 for severity in _SEVERITIES}
    clusters: dict[str, dict[str, int]] = {}

    for row in rows:
        severity = str(row.get("severity") or "").strip().lower()
        if severity not in severity_totals:
            severity = "medium"
        severity_totals[severity] += 1

        key = primary_product(row.get("cpe_matches"), row.get("affected_products"))
        cluster = clusters.setdefault(
            key,
            {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        cluster["total"] += 1
        cluster[severity] += 1

    display_labels = {key: key.replace("_", " ") for key in clusters}
    label_counts: dict[str, int] = {}
    for label in display_labels.values():
        label_counts[label] = label_counts.get(label, 0) + 1

    products = []
    for key, counts in clusters.items():
        display_label = display_labels[key]
        label = key if label_counts[display_label] > 1 else display_label
        products.append({"label": label, **counts})

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

    return {
        "published": len(rows),
        **severity_totals,
        "products": products[:_PRODUCT_LIMIT],
        "omitted_products": max(0, len(products) - _PRODUCT_LIMIT),
    }


def format_market_section(market: dict) -> list[str]:
    if market["published"] == 0:
        return []

    lines = [
        "// MARKET",
        (
            f"Published: {market['published']}  ·  "
            f"C {market['critical']} · H {market['high']} · "
            f"M {market['medium']} · L {market['low']}"
        ),
    ]
    for product in market["products"]:
        lines.append(
            f"• {product['label']}  {product['total']}  "
            f"(C {product['critical']} · H {product['high']} · "
            f"M {product['medium']} · L {product['low']})"
        )
    if market["omitted_products"]:
        lines.append(f"+{market['omitted_products']} products in BRIEFR.")
    return lines
