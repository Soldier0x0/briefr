"""DetectionContext scaffold (Sprint D2).

Static CVE envelope cached in ``feed_cache`` for scheduler-built detection
metadata. No LLM on this path — D4 adds artifact injection later.
"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from db.cache import get_feed_cache, set_feed_cache
from db.dialect import utcnow_str
from detection.sigma_generator import _normalize_cwe_id, _resolve_template

DETECTION_CTX_PREFIX = "detection_ctx:"
DETECTION_CTX_CACHE_HOURS = 168.0

# CWE → stable class slug (shared by D3 unified router later).
CWE_CLASS_SLUGS: dict[str, str] = {
    "CWE-22": "path_traversal",
    "CWE-23": "path_traversal",
    "CWE-35": "path_traversal",
    "CWE-78": "cmd_injection",
    "CWE-89": "sqli",
    "CWE-79": "xss",
    "CWE-502": "deserialization",
    "CWE-94": "code_injection",
    "CWE-95": "code_injection",
    "CWE-434": "unsafe_upload",
    "CWE-918": "ssrf",
    "CWE-611": "xxe",
    "CWE-287": "auth_bypass",
    "CWE-288": "auth_bypass",
    "CWE-306": "auth_bypass",
    "CWE-416": "memory_corruption",
    "CWE-787": "memory_corruption",
    "CWE-119": "memory_corruption",
    "CWE-122": "memory_corruption",
    "CWE-798": "default_credentials",
}

TECHNIQUE_CLASS_SLUGS: dict[str, str] = {
    "T1190": "web_exploit",
    "T1133": "remote_access",
    "T1059": "script_execution",
    "T1203": "client_execution",
    "T1068": "privilege_escalation",
    "T1055": "process_injection",
    "T1027": "obfuscation",
    "T1036": "masquerading",
    "T1110": "brute_force",
    "T1003": "credential_dumping",
    "T1021": "lateral_movement",
    "T1570": "lateral_transfer",
    "T1071": "c2_application",
    "T1095": "c2_non_application",
}


def detection_context_cache_key(cve_id: str) -> str:
    return f"{DETECTION_CTX_PREFIX}{cve_id.upper()}"


def _parse_cwe_ids(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        normalized = _normalize_cwe_id(str(item))
        if normalized:
            out.append(normalized)
    return out


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


def resolve_detection_class(
    technique_id: str,
    cwe_ids: list[str] | None,
) -> str:
    """Map ATT&CK technique or CWE to a stable detection class slug."""
    prefix = (technique_id or "").strip().upper()[:5]
    if prefix in TECHNIQUE_CLASS_SLUGS:
        return TECHNIQUE_CLASS_SLUGS[prefix]

    for raw in cwe_ids or []:
        cwe_id = _normalize_cwe_id(str(raw))
        slug = CWE_CLASS_SLUGS.get(cwe_id)
        if slug:
            return slug

    _, basis, _ = _resolve_template(technique_id, cwe_ids)
    if basis == "generic":
        return "generic"
    return "generic"


def build_detection_context(
    *,
    cve_id: str,
    cwe_ids: list[str] | None = None,
    technique_id: str = "",
    affected_products: Any = None,
    generated_at: str | None = None,
) -> dict:
    """Build a static DetectionContext envelope (no LLM)."""
    normalized_cwes = [_normalize_cwe_id(c) for c in (cwe_ids or []) if _normalize_cwe_id(c)]
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
