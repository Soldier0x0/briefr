"""DetectionContext scaffold (Sprint D2).

Static CVE envelope cached in ``feed_cache`` for scheduler-built detection
metadata. No LLM on this path — D4 adds artifact injection later.
"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from db.cache import get_feed_cache, set_feed_cache
from db.timeutil import utcnow_str
from detection.class_router import (
    CWE_CLASS_SLUGS,
    TECHNIQUE_CLASS_SLUGS,
    normalize_cwe_ids,
    resolve_detection_class,
)

DETECTION_CTX_PREFIX = "detection_ctx:"
DETECTION_CTX_CACHE_HOURS = 168.0

# Re-export maps for tests and callers that imported from context (D2).
__all__ = [
    "CWE_CLASS_SLUGS",
    "TECHNIQUE_CLASS_SLUGS",
    "resolve_detection_class",
]


def detection_context_cache_key(cve_id: str) -> str:
    return f"{DETECTION_CTX_PREFIX}{cve_id.upper()}"


def _parse_cwe_ids(raw: Any) -> list[str]:
    return normalize_cwe_ids(raw)


def _first_product(affected_products: Any) -> str:
    if not affected_products:
        return ""
    try:
        products = (
            json.loads(affected_products)
            if isinstance(affected_products, str)
            else affected_products
        )
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(products, list) or not products:
        return ""
    first = str(products[0]).strip()
    if not first:
        return ""
    # Stored as "vendor:product" — product half makes the better title.
    return first.split(":")[-1].replace("_", " ").strip()


def build_detection_context(
    *,
    cve_id: str,
    cwe_ids: list[str] | None = None,
    technique_id: str = "",
    affected_products: Any = None,
    generated_at: str | None = None,
) -> dict:
    """Build a static DetectionContext envelope (no LLM)."""
    normalized_cwes = normalize_cwe_ids(cwe_ids)
    product = _first_product(affected_products)
    return {
        "cwe_ids": normalized_cwes,
        "product": product,
        "class": resolve_detection_class(technique_id, normalized_cwes),
        "artifacts": [],
        "model": "",
        "provider": "briefr",
        "generated_at": generated_at or utcnow_str(),
    }


def merge_detection_inputs(
    *,
    product: str = "",
    cwe_ids: list[str] | None = None,
    technique_id: str = "",
    detection_context: dict | None = None,
) -> tuple[str, list[str], str]:
    """Apply cached DetectionContext to rule-generation inputs."""
    ctx = detection_context or {}
    effective_cwe_ids = list(cwe_ids or ctx.get("cwe_ids") or [])
    effective_product = (product or ctx.get("product") or "").strip()
    effective_technique = (technique_id or "").strip()
    return effective_product, effective_cwe_ids, effective_technique


async def get_detection_context(
    db: aiosqlite.Connection,
    cve_id: str,
) -> dict | None:
    return await get_feed_cache(
        db,
        detection_context_cache_key(cve_id),
        DETECTION_CTX_CACHE_HOURS,
    )


async def set_detection_context(
    db: aiosqlite.Connection,
    cve_id: str,
    context: dict,
) -> None:
    await set_feed_cache(db, detection_context_cache_key(cve_id), context)
