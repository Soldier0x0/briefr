"""Enrichment confirmation from cached IOC lookups (Correlation v2 Phase 2)."""

from __future__ import annotations

import os
from typing import Any

from correlation.config import get_correlation_confirm_enabled


def confirmations_enabled() -> bool:
    return get_correlation_confirm_enabled()


def _parse_confirmations(cached: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    gn = cached.get("greynoise") or {}
    classification = (gn.get("classification") or "").strip().lower()
    if classification:
        out["greynoise"] = classification

    if cached.get("malwarebazaar_sentence") or cached.get("malwarebazaar"):
        out["malwarebazaar"] = True

    uh = cached.get("urlhaus") or {}
    if uh.get("url_status") == "online" or cached.get("urlhaus_sentence"):
        out["urlhaus_active"] = True

    return out


async def confirmations_for_iocs_batch(
    db, ioc_values: list[str]
) -> dict[str, dict[str, Any]]:
    """
    Read ioc_cache for all distinct IOC values in one query (instead of one
    query per (peer, ioc) edge). Returns {ioc_value: confirmations}, where
    each confirmations dict has keys: greynoise, malwarebazaar, urlhaus_active.
    """
    if not confirmations_enabled() or not ioc_values:
        return {}

    from database import get_ioc_cache_batch

    cached_by_value = await get_ioc_cache_batch(db, ioc_values)
    return {
        value: _parse_confirmations(cached)
        for value, cached in cached_by_value.items()
    }


def confirmation_receipt(confirmations: dict[str, Any]) -> dict | None:
    if not confirmations:
        return None
    parts = []
    if confirmations.get("greynoise"):
        parts.append(f"GreyNoise: {confirmations['greynoise']}")
    if confirmations.get("malwarebazaar"):
        parts.append("MalwareBazaar: sample seen")
    if confirmations.get("urlhaus_active"):
        parts.append("URLhaus: active URL")
    if not parts:
        return None
    return {"type": "enrichment_confirmation", "summary": "; ".join(parts)}
