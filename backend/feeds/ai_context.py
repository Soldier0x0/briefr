"""
AI/ML CVE context detection and MITRE ATLAS technique hints.
"""

from __future__ import annotations

import json
import re
from typing import Any

from feeds.mitre import AI_ML_KEYWORDS, CVE_TO_ATLAS_HINTS

_AI_REGEXES = [
    re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in AI_ML_KEYWORDS
]


def _haystack_text(cve: dict[str, Any]) -> str:
    parts: list[str] = [cve.get("description") or ""]
    products = cve.get("affected_products") or []
    if isinstance(products, str):
        try:
            products = json.loads(products)
        except (json.JSONDecodeError, TypeError):
            products = [products]
    if isinstance(products, list):
        parts.extend(str(p) for p in products)
    return " ".join(parts).lower()


def matched_ai_keywords(cve: dict[str, Any]) -> list[str]:
    text = _haystack_text(cve)
    found: list[str] = []
    for kw, pattern in zip(AI_ML_KEYWORDS, _AI_REGEXES):
        if pattern.search(text):
            found.append(kw)
    return found


def infer_atlas_technique_ids(cve: dict[str, Any]) -> list[str]:
    text = _haystack_text(cve)
    techniques: list[str] = []
    seen: set[str] = set()
    for hint, tids in CVE_TO_ATLAS_HINTS.items():
        if hint in text:
            for tid in tids:
                tid_up = tid.upper()
                if tid_up not in seen:
                    seen.add(tid_up)
                    techniques.append(tid_up)
    return techniques


def analyze_cve_ai_context(cve: dict[str, Any]) -> tuple[bool, list[str]]:
    keywords = matched_ai_keywords(cve)
    if not keywords:
        return False, []
    return True, infer_atlas_technique_ids(cve)


def cve_matches_declared_frameworks(cve: dict[str, Any], frameworks: list[str]) -> bool:
    if not frameworks:
        return False
    text = _haystack_text(cve)
    for fw in frameworks:
        fw_l = fw.strip().lower()
        if not fw_l:
            continue
        if re.search(rf"\b{re.escape(fw_l)}\b", text, re.IGNORECASE):
            return True
    return False
