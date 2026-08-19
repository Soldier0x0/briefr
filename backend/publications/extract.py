"""Deterministic entity extractors for publication ingest (shared with incident RSS cards)."""

from __future__ import annotations

import re

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)
TECHNIQUE_RE = re.compile(
    r"\b(T\d{4}(?:\.\d{3})?|AML\.T\d{4}(?:\.\d{3})?)\b",
    re.I,
)


def extract_cve_ids(*texts: str, max_ids: int | None = None) -> list[str]:
    """Return unique CVE IDs found in text (uppercase, stable order)."""
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in CVE_RE.finditer(str(text)):
            cve_id = match.group(0).upper()
            if cve_id in seen:
                continue
            seen.add(cve_id)
            found.append(cve_id)
            if max_ids is not None and len(found) >= max_ids:
                return found
    return found


def extract_technique_ids(*texts: str) -> list[str]:
    """Return unique ATT&CK / ATLAS technique IDs from text."""
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in TECHNIQUE_RE.finditer(str(text)):
            technique_id = match.group(0).upper()
            if technique_id in seen:
                continue
            seen.add(technique_id)
            found.append(technique_id)
    return found
