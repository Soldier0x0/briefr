"""Evidence-composed detection pack (DC-1).

Retrieves CVE-grounded community rules, Nuclei/context artifacts, and YARA
observables. No LLM. Template Sigma/SIEM emission is DC-2+.
"""

from __future__ import annotations

from typing import Any

from database import read_cve_exploits_from_db
from detection.class_router import resolve_detection_class
from detection.context import get_detection_context
from detection.rule_sources import find_elastic_rules, find_sigma_rules
from detection.yara_generator import find_yara_rules_for_cve

__all__ = ["compose_detection_evidence"]


def _ensure_list(val: Any) -> list[Any]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val] if val.strip() else []
    return [val] if val is not None else []


def _normalize_artifacts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "paths": _ensure_list(item.get("paths")),
                "params": _ensure_list(item.get("params")),
                "keywords": _ensure_list(item.get("keywords")),
                "method": str(item.get("method") or ""),
                "provenance": str(
                    item.get("provenance")
                    or item.get("provider")
                    or "unknown"
                ),
            }
        )
    return out


def _nuclei_urls(exploits: list[dict[str, Any]] | None) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for exp in exploits or []:
        if not isinstance(exp, dict):
            continue
        if str(exp.get("source") or "").lower() != "nuclei":
            continue
        url = str(exp.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _primary_source(
    *,
    community_count: int,
    artifact_count: int,
    nuclei_count: int,
    yara_count: int,
) -> str:
    if community_count > 0:
        return "community"
    if artifact_count > 0 or nuclei_count > 0:
        return "nuclei_artifacts"
    if yara_count > 0:
        return "yara"
    return "none"


async def compose_detection_evidence(
    db,
    *,
    cve_id: str,
    technique_ids: list[str] | None = None,
    cwe_ids: list[str] | None = None,
    product: str = "",
    github_token: str = "",
    include_community: bool = True,
) -> dict[str, Any]:
    """Build a deterministic evidence pack for Detect / Forge consumers."""
    cve_key = (cve_id or "").strip().upper()
    techniques = [str(t).strip() for t in (technique_ids or []) if str(t).strip()]
    cwes = [str(c).strip() for c in (cwe_ids or []) if str(c).strip()]

    sigma_rules: list[dict] = []
    elastic_rules: list[dict] = []
    if include_community:
        sigma_rules = await find_sigma_rules(db, cve_key, techniques, github_token)
        elastic_rules = await find_elastic_rules(db, techniques, github_token)

    detection_context = await get_detection_context(db, cve_key)
    artifacts = _normalize_artifacts(
        detection_context.get("artifacts")
        if isinstance(detection_context, dict)
        else []
    )

    exploits = await read_cve_exploits_from_db(db, cve_key, max_age_hours=24 * 365) or []
    nuclei_urls = _nuclei_urls(exploits)
    yara_rules = await find_yara_rules_for_cve(db, cve_key)

    detection_class = None
    if isinstance(detection_context, dict) and detection_context.get("class"):
        detection_class = detection_context.get("class")
    else:
        first_technique = techniques[0] if techniques else ""
        detection_class = resolve_detection_class(first_technique, cwes)

    community_count = len(sigma_rules) + len(elastic_rules)
    artifact_count = len(artifacts)
    nuclei_count = len(nuclei_urls)
    yara_count = len(yara_rules)

    return {
        "cve_id": cve_key,
        "technique_ids": techniques,
        "detection_class": detection_class,
        "community": {
            "sigma_rules": sigma_rules,
            "elastic_rules": elastic_rules,
            "has_community_rules": community_count > 0,
        },
        "artifacts": artifacts,
        "observables": {
            "nuclei_urls": nuclei_urls,
            "yara_rules": yara_rules,
        },
        "detection_context": detection_context,
        "evidence_summary": {
            "community_count": community_count,
            "artifact_count": artifact_count,
            "nuclei_count": nuclei_count,
            "primary_source": _primary_source(
                community_count=community_count,
                artifact_count=artifact_count,
                nuclei_count=nuclei_count,
                yara_count=yara_count,
            ),
        },
        "product": str(product or "").strip()
        or (
            str(detection_context.get("product") or "").strip()
            if isinstance(detection_context, dict)
            else ""
        ),
    }
