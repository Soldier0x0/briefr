"""Evidence-composed detection pack (DC-1) + emission (DC-2).

Retrieves CVE-grounded community rules, Nuclei/context artifacts, and YARA
observables, then emits Sigma/SIEM/YARA from that pack. No LLM.
"""

from __future__ import annotations

from typing import Any

from database import read_cve_exploits_from_db
from detection.class_router import resolve_detection_class
from detection.context import get_detection_context
from detection.rule_sources import find_elastic_rules, find_sigma_rules
from detection.siem_queries import get_siem_queries
from detection.sigma_generator import generate_sigma_rule_bundle
from detection.yara_generator import find_yara_rules_for_cve
from ttl_constants import HOURS_PER_YEAR

__all__ = ["compose_detection_evidence", "emit_composed_detection"]


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

    exploits = await read_cve_exploits_from_db(db, cve_key, max_age_hours=HOURS_PER_YEAR) or []
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


def _compose_basis(evidence: dict[str, Any]) -> str:
    primary = str(
        (evidence.get("evidence_summary") or {}).get("primary_source") or "none"
    ).strip()
    if primary in ("", "none"):
        return "template_fallback"
    return primary


def _context_for_emit(evidence: dict[str, Any]) -> dict[str, Any] | None:
    artifacts = evidence.get("artifacts") or []
    ctx = evidence.get("detection_context")
    if isinstance(ctx, dict):
        merged = dict(ctx)
        if artifacts:
            merged["artifacts"] = artifacts
        return merged
    if not artifacts and not evidence.get("detection_class"):
        return None
    return {
        "class": evidence.get("detection_class"),
        "artifacts": artifacts,
        "product": evidence.get("product") or "",
    }


def _artifact_tokens(artifacts: list[Any]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        for key in ("paths", "keywords"):
            for raw in _ensure_list(art.get(key)):
                token = str(raw or "").strip()
                if not token:
                    continue
                low = token.lower()
                if low in seen:
                    continue
                seen.add(low)
                tokens.append(token)
                if len(tokens) >= 8:
                    return tokens
    return tokens


def _inject_artifacts_into_siem(
    siem: dict[str, Any], artifacts: list[Any]
) -> dict[str, Any]:
    """Inject evidence tokens into SIEM queries without breaking dialect syntax.

    Elastic/Splunk tolerate trailing OR clauses. Sentinel gets a Kusto
    ``has_any`` pipe. QRadar AQL is left untouched (naive suffixes break
    ``LAST`` / ``WHERE`` clauses).
    """
    tokens = _artifact_tokens(artifacts)
    if not tokens:
        return siem
    quoted = ", ".join(f'"{t}"' for t in tokens)
    space_quoted = " ".join(f'"{t}"' for t in tokens)
    out = dict(siem)

    elastic = out.get("elastic_kql")
    if isinstance(elastic, dict) and isinstance(elastic.get("query"), str):
        out["elastic_kql"] = {
            **elastic,
            "query": f'{elastic["query"]} or url.path:({quoted})',
        }

    splunk = out.get("splunk_spl")
    if isinstance(splunk, dict) and isinstance(splunk.get("query"), str):
        out["splunk_spl"] = {
            **splunk,
            "query": f'{splunk["query"]} OR ({space_quoted})',
        }

    sentinel = out.get("sentinel_kql")
    if isinstance(sentinel, dict) and isinstance(sentinel.get("query"), str):
        out["sentinel_kql"] = {
            **sentinel,
            "query": (
                f'{sentinel["query"].rstrip()}\n'
                f'| where * has_any ({quoted})'
            ),
        }

    return out


def emit_composed_detection(
    evidence: dict[str, Any],
    *,
    description: str = "",
    cwe_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Emit Sigma + SIEM + YARA from a DC-1 evidence pack (no LLM).

    Community SigmaHQ/Elastic rules are primary. BRIEFR template YAML is only
    emitted when there is no community hit *and* the template is class-mapped
    (CWE / ATT&CK) — never the generic keyword dump.
    """
    cve_id = str(evidence.get("cve_id") or "").strip().upper()
    techniques = [
        str(t).strip()
        for t in (evidence.get("technique_ids") or [])
        if str(t).strip()
    ]
    first_technique = techniques[0] if techniques else ""
    product = str(evidence.get("product") or "").strip() or "Affected Product"
    detection_context = _context_for_emit(evidence)
    artifacts = evidence.get("artifacts") or []
    compose_basis = _compose_basis(evidence)
    has_community = bool(
        (evidence.get("community") or {}).get("has_community_rules")
    )

    generated_sigma, generated_sigma_meta = generate_sigma_rule_bundle(
        cve_id=cve_id or "CVE-UNKNOWN",
        technique_id=first_technique,
        product=product,
        description=description,
        cwe_ids=cwe_ids,
        detection_context=detection_context,
    )
    meta = dict(generated_sigma_meta or {})
    meta["compose_basis"] = compose_basis

    briefr_basis = str(meta.get("briefr_basis") or "generic").lower()
    # Community-first: real SigmaHQ/Elastic beats BRIEFR templates.
    # Generic keyword dumps are refused — empty is more honest than noisy YAML.
    if has_community:
        generated_sigma = None
        meta["suppressed"] = "community_primary"
    elif briefr_basis == "generic":
        generated_sigma = None
        meta["suppressed"] = "generic_refused"

    siem_queries = get_siem_queries(
        technique_id=first_technique,
        cve_id=cve_id,
        product=product if product != "Affected Product" else "",
        cwe_ids=cwe_ids,
        detection_context=detection_context,
    )
    siem_queries = _inject_artifacts_into_siem(siem_queries, artifacts)

    yara_rules = list((evidence.get("observables") or {}).get("yara_rules") or [])

    return {
        "generated_sigma": generated_sigma,
        "generated_sigma_meta": meta,
        "siem_queries": siem_queries,
        "yara_rules": yara_rules,
        "compose_basis": compose_basis,
    }
