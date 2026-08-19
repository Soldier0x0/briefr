"""Deterministic infrastructure classification for blocklist eligibility.

Classifies an exact canonical host. There is deliberately NO parent-domain
folding: ``drive.google.com`` stays distinct from ``google.com`` and a
hypothetical ``malicious.example.com`` stays distinct from ``example.com``.
The classification only ever controls host-level corroboration and export
eligibility — it never deletes or rewrites IOC evidence.
"""

from __future__ import annotations

from typing import Any

from blocklist.infra_seed import (
    EXCLUSION_CLASSIFICATIONS,
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
    UNKNOWN,
)
from correlation.ioc_normalize import _normalize_domain


def canonical_host(value: str) -> str:
    """Canonical host form used for classification keys (lowercase, trailing
    dot + leading ``www.`` stripped) — identical to domain-edge canonicalization."""
    return _normalize_domain(value or "")


def _index_classifications(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        host = canonical_host(row.get("host") or "")
        if host:
            index[host] = dict(row)
    return index


def classify_host(
    host: str,
    classifications: list[dict[str, Any]] | None = None,
    _index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return {host, classification, enabled, reason, notes} for an exact host.

    Exact canonical-host match only (no parent-domain folding). A host with no
    row, or whose row is disabled, classifies as UNKNOWN and enabled=0 so it is
    treated as a normal candidate.
    """
    canon = canonical_host(host)
    if not canon:
        return {
            "host": canon,
            "classification": UNKNOWN,
            "enabled": 0,
            "reason": "",
            "notes": "",
        }
    index = _index if _index is not None else _index_classifications(classifications)
    row = index.get(canon)
    if not row:
        return {
            "host": canon,
            "classification": UNKNOWN,
            "enabled": 0,
            "reason": "",
            "notes": "",
        }
    classification = row.get("classification") or UNKNOWN
    if classification not in (LEGITIMATE_DOMAIN, SHARED_LEGITIMATE_INFRASTRUCTURE, TRUSTED_SERVICE, UNKNOWN):
        classification = UNKNOWN
    return {
        "host": canon,
        "classification": classification,
        "enabled": int(row.get("enabled") or 0),
        "reason": row.get("reason") or "",
        "notes": row.get("notes") or "",
    }


def is_excluded_from_export(classified: dict[str, Any]) -> bool:
    """True when a classified host is suppressed from the blocklist export and
    from host-level corroboration (exact IOC evidence stays untouched)."""
    if not classified:
        return False
    if not int(classified.get("enabled") or 0):
        return False
    return classified.get("classification") in EXCLUSION_CLASSIFICATIONS


def is_excluded_from_domain_export(classified: dict[str, Any]) -> bool:
    """Alias for host-level domain suppression (shared/legitimate infra)."""
    return is_excluded_from_export(classified)


def export_eligibility(
    *,
    base_eligible: bool,
    classified: dict[str, Any],
    ioc_type: str,
) -> tuple[bool, bool]:
    """Return (eligible_domain, eligible_url) for one candidate record."""
    if not base_eligible:
        return False, False
    domain_blocked = is_excluded_from_domain_export(classified)
    if domain_blocked and ioc_type == "url":
        return False, True
    if domain_blocked:
        return False, False
    return True, ioc_type == "url"


def is_excluded_classification(classification: str) -> bool:
    return classification in EXCLUSION_CLASSIFICATIONS


def classification_label(classification: str) -> str:
    return {
        LEGITIMATE_DOMAIN: "legitimate_domain",
        SHARED_LEGITIMATE_INFRASTRUCTURE: "shared_legitimate_infrastructure",
        TRUSTED_SERVICE: "trusted_service",
        UNKNOWN: "unknown",
    }.get(classification, "unknown")
