"""Build the malicious-domain-candidates blocklist.

Pipeline (deliberately layered, never one giant SQL):
  1. evidence retrieval      -> db/blocklist.py (mirror + OTX, read-only)
  2. canonicalization        -> correlation/ioc_normalize (reused)
  3. infrastructure class.   -> blocklist/classify
  4. corroboration control   -> correlation/source_evidence (host-level
                                suppression for classified shared hosts)
  5. confidence              -> correlation/confidence (existing, reused)
  6. deterministic dedup     -> by canonical domain
  7. candidate construction  -> this module
  8. serialization           -> blocklist/serialize
  9. API                     -> routers/threat_intel

Semantics (locked):
- Catalog sources (ThreatFox/URLhaus) back a candidate unconditionally.
- OTX is corroboration-only: an OTX-only domain never exports on its own and
  must be corroborated by a catalog source (checked through the same
  batch_source_evidence path) with BRIEFR confidence >= medium.
- Exact IOC evidence is never deleted or rewritten; classification only
  controls host-level corroboration and export eligibility.
"""

from __future__ import annotations

from typing import Any

from blocklist.classify import (
    canonical_host,
    classify_host,
    is_excluded_from_export,
)
from blocklist.infra_seed import (
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
)
from correlation.confidence import confidence_for_ioc_edge
from correlation.ioc_normalize import _url_host, normalize_ioc_type
from correlation.source_evidence import batch_source_evidence, corroboration_receipt
from db.blocklist import (
    fetch_catalog_evidence,
    fetch_infra_classifications,
    fetch_otx_candidates,
)
from db.timeutil import utcnow_str
from db.types import DbConnection

_LEVEL_INDEX = {"low": 0, "medium": 1, "high": 2}

_MIN_OTX_CONFIDENCE = "medium"


def _candidate_domain_for_row(row: dict[str, Any]) -> str:
    """Canonical domain candidate for a catalog mirror row.

    ThreatFox rows are stored as ioc_type='domain' (URLs downcast at ingest,
    raw_ioc keeps the URL); URLhaus rows are ioc_type='url' and the domain
    lives in host_ioc. Reuses the persisted host semantics — no new parser.
    """
    ioc_type = (row.get("ioc_type") or "").strip().lower()
    if ioc_type == "url":
        host = (row.get("host_ioc") or "").strip()
        if not host:
            host = _url_host(row.get("ioc_value") or "")
        return canonical_host(host)
    return canonical_host(row.get("ioc_value") or "")


def _otx_domain_for_row(row: dict[str, Any]) -> str:
    """Canonical domain candidate for an OTX pulse IOC row.

    DOMAIN/HOSTNAME rows keep the canonical value in ioc_value; URL rows carry
    the derived host in host_ioc (raw_ioc holds the exact upstream URL).
    """
    ioc_type = normalize_ioc_type(row.get("ioc_type") or "")
    if ioc_type == "URL":
        host = (row.get("host_ioc") or "").strip()
        if not host:
            host = _url_host(row.get("ioc_value") or "")
        return canonical_host(host)
    return canonical_host(row.get("ioc_value") or "")


def _first(list_values: list[str | None]) -> str:
    for v in list_values:
        if v:
            return str(v)
    return ""


def _evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": row.get("source") or ("otx" if row.get("pulse_id") else ""),
        "ref_id": row.get("ref_id") or "",
        "ioc_type": row.get("ioc_type") or "",
        "ioc_value": row.get("ioc_value") or "",
        "raw_ioc": row.get("raw_ioc") or "",
        "host_ioc": row.get("host_ioc") or "",
        "malware": row.get("malware") or "",
        "threat_type": row.get("threat_type") or "",
        "confidence_level": int(row.get("confidence_level") or 0),
        "first_seen": row.get("first_seen") or row.get("observed_at") or "",
        "fetched_at": row.get("fetched_at") or "",
        "pulse_id": row.get("pulse_id") or "",
        "description": row.get("description") or "",
    }


def _catalog_receipts(rows: list[dict[str, Any]]) -> list[str]:
    receipts: list[str] = []
    seen: set[str] = set()
    for row in rows:
        receipt = corroboration_receipt(row.get("source") or "", row.get("ref_id") or "")
        if receipt and receipt not in seen:
            seen.add(receipt)
            receipts.append(receipt)
    return receipts


def _upstream_confidence(rows: list[dict[str, Any]]) -> int:
    return max([int(r.get("confidence_level") or 0) for r in rows] or [0])


def _upstream_level(confidence_level: int) -> str:
    """Deterministic BRIEFR-style level derived from upstream confidence_level
    (used only when no OTX corroboration is present — catalog exports run on
    the upstream number per the locked semantics)."""
    if confidence_level >= 80:
        return "high"
    if confidence_level >= 50:
        return "medium"
    return "low"


async def build_blocklist(db: DbConnection) -> dict[str, Any]:
    """Assemble the malicious-domain-candidates export payload.

    Returns a dict with `meta`, `domains` (eligible, one per canonical domain),
    and `excluded` (classified/OTX-unsupported candidates with reasons).
    Deterministic: domains sorted by name, evidence lists stable.
    """
    generated_at = utcnow_str()

    infra_rows = await fetch_infra_classifications(db)
    classification_index: dict[str, dict[str, Any]] = {}
    excluded_hosts: set[str] = set()
    for row in infra_rows:
        host = canonical_host(row.get("host") or "")
        if not host:
            continue
        classification_index[host] = dict(row)
        if int(row.get("enabled") or 0) and (row.get("classification") or "") in (
            LEGITIMATE_DOMAIN,
            SHARED_LEGITIMATE_INFRASTRUCTURE,
            TRUSTED_SERVICE,
        ):
            excluded_hosts.add(host)

    catalog_rows = await fetch_catalog_evidence(db)
    otx_rows = await fetch_otx_candidates(db)

    # ── Deterministic dedup by canonical domain ─────────────────────────────
    catalog_by_domain: dict[str, list[dict[str, Any]]] = {}
    otx_by_domain: dict[str, list[dict[str, Any]]] = {}
    for row in catalog_rows:
        domain = _candidate_domain_for_row(row)
        if not domain or "." not in domain:
            continue
        catalog_by_domain.setdefault(domain, []).append(_evidence_row(row))
    for row in otx_rows:
        domain = _otx_domain_for_row(row)
        if not domain or "." not in domain:
            continue
        otx_by_domain.setdefault(domain, []).append(_evidence_row(row))

    # ── Corroboration control: OTX-only domains need catalog corroboration,
    #    checked through batch_source_evidence with host-level suppression for
    #    classified shared hosts (exact matches always survive). ─────────────
    otx_domain_edges: list[tuple[str, str]] = []
    for domain in sorted(otx_by_domain):
        otx_domain_edges.append(("DOMAIN", domain))
    corroboration_hits = await batch_source_evidence(
        db,
        otx_domain_edges,
        suppress_host_level=frozenset(excluded_hosts),
    )

    domains: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    all_candidate_domains = sorted(set(catalog_by_domain) | set(otx_by_domain))

    for domain in all_candidate_domains:
        catalog_ev = catalog_by_domain.get(domain, [])
        otx_ev = otx_by_domain.get(domain, [])
        classified = classify_host(domain, _index=classification_index)

        evidence = list(catalog_ev) + list(otx_ev)
        sources = sorted({e["source"] for e in evidence if e["source"]})
        malware = sorted({e["malware"] for e in evidence if e["malware"]})
        threat_types = sorted({e["threat_type"] for e in evidence if e["threat_type"]})
        first_seen = min(
            [e["first_seen"] for e in evidence if e["first_seen"]] or [generated_at]
        )
        fetched_at = max(
            [e["fetched_at"] for e in evidence if e["fetched_at"]] or [generated_at]
        )

        # Reason for the entry (inclusion or exclusion).
        if is_excluded_from_export(classified):
            excluded.append(_candidate_record(
                domain,
                eligible=False,
                reason=f"Infrastructure classification: {classified['classification']}",
                classified=classified,
                sources=sources,
                confidence_level=_upstream_confidence(catalog_ev),
                confidence=_upstream_level(_upstream_confidence(catalog_ev)),
                malware=malware,
                threat_type=threat_types,
                first_seen=first_seen,
                fetched_at=fetched_at,
                corroborating_sources=[],
                otx_corroborated=False,
                evidence=evidence,
            ))
            continue

        # Catalog sources back a candidate unconditionally (upstream confidence).
        # OTX-only domains export only when a catalog source corroborates them
        # and BRIEFR confidence >= medium.
        key = ("DOMAIN", domain.lower())
        corroborating_rows = corroboration_hits.get(key, [])
        corroborating_receipts = _catalog_receipts(corroborating_rows)
        corroborating_sources = sorted(
            {receipt.split(":", 1)[0] for receipt in corroborating_receipts if ":" in receipt}
        )
        otx_corroborated = bool(corroborating_rows)

        if catalog_ev:
            # Locked: catalog exports on upstream confidence_level; OTX evidence
            # on the same domain adds corroboration but never blocks export.
            confidence = _upstream_level(_upstream_confidence(catalog_ev))
            factors: list[dict[str, Any]] = []
            confidence_level = _upstream_confidence(catalog_ev)
            if otx_ev and otx_corroborated:
                level, why, factors = confidence_for_ioc_edge(
                    "DOMAIN",
                    corroborated_by=corroborating_receipts,
                    observed_at=_first([e["first_seen"] for e in otx_ev]),
                    ingested_at=fetched_at,
                )
                confidence = level
            domains.append(_candidate_record(
                domain,
                eligible=True,
                reason="Catalog source evidence (ThreatFox/URLhaus)",
                classified=classified,
                sources=sources,
                confidence_level=confidence_level,
                confidence=confidence,
                malware=malware,
                threat_type=threat_types,
                first_seen=first_seen,
                fetched_at=fetched_at,
                corroborating_sources=corroborating_sources if otx_ev else [],
                otx_corroborated=otx_corroborated,
                confidence_factors=factors,
                evidence=evidence,
            ))
            continue

        # OTX-only candidate: requires catalog corroboration + medium confidence.
        if not otx_corroborated:
            excluded.append(_candidate_record(
                domain,
                eligible=False,
                reason="OTX-only candidate without catalog corroboration",
                classified=classified,
                sources=sources,
                confidence_level=0,
                confidence="low",
                malware=malware,
                threat_type=threat_types,
                first_seen=first_seen,
                fetched_at=fetched_at,
                corroborating_sources=[],
                otx_corroborated=False,
                evidence=evidence,
            ))
            continue

        level, why, factors = confidence_for_ioc_edge(
            "DOMAIN",
            corroborated_by=corroborating_receipts,
            observed_at=_first([e["first_seen"] for e in otx_ev]),
            ingested_at=fetched_at,
        )
        if _LEVEL_INDEX.get(level, 0) < _LEVEL_INDEX[_MIN_OTX_CONFIDENCE]:
            excluded.append(_candidate_record(
                domain,
                eligible=False,
                reason=(
                    "OTX-only candidate below BRIEFR medium confidence "
                    f"({level})"
                ),
                classified=classified,
                sources=sources,
                confidence_level=_upstream_confidence(catalog_ev),
                confidence=level,
                malware=malware,
                threat_type=threat_types,
                first_seen=first_seen,
                fetched_at=fetched_at,
                corroborating_sources=corroborating_sources,
                otx_corroborated=True,
                confidence_factors=factors,
                evidence=evidence,
            ))
            continue

        domains.append(_candidate_record(
            domain,
            eligible=True,
            reason="Catalog corroboration of OTX candidate",
            classified=classified,
            sources=sources,
            confidence_level=_upstream_confidence(corroborating_rows),
            confidence=level,
            malware=malware,
            threat_type=threat_types,
            first_seen=first_seen,
            fetched_at=fetched_at,
            corroborating_sources=corroborating_sources,
            otx_corroborated=True,
            confidence_factors=factors,
            evidence=evidence,
        ))

    domains.sort(key=lambda r: r["domain"])
    excluded.sort(key=lambda r: r["domain"])

    return {
        "meta": {
            "generated_at": generated_at,
            "title": "BRIEFR malicious-domain candidates",
            "description": (
                "Domains identified as malicious-domain candidates from "
                "ThreatFox/URLhaus catalog evidence, plus OTX pulse IOCs that "
                "are corroborated by a catalog source. Shared/legitimate "
                "infrastructure hosts (e.g. drive.google.com, t.me) are "
                "excluded — exact-path IOC evidence is never deleted."
            ),
            "criteria": [
                "Catalog sources (ThreatFox domain rows, URLhaus URL hosts) qualify directly.",
                "OTX pulse IOCs qualify only when corroborated by a catalog source.",
                "OTX corroboration requires BRIEFR confidence >= medium.",
                "Infrastructure-classified hosts are excluded from export.",
            ],
            "candidate_count": len(all_candidate_domains),
            "eligible_count": len(domains),
            "excluded_count": len(excluded),
        },
        "domains": domains,
        "excluded": excluded,
    }


def _candidate_record(
    domain: str,
    *,
    eligible: bool,
    reason: str,
    classified: dict[str, Any],
    sources: list[str],
    confidence_level: int,
    confidence: str,
    malware: list[str],
    threat_type: list[str],
    first_seen: str,
    fetched_at: str,
    corroborating_sources: list[str],
    otx_corroborated: bool,
    confidence_factors: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "domain": domain,
        "eligible": eligible,
        "reason": reason,
        "classification": classified["classification"],
        "classification_enabled": bool(classified.get("enabled")),
        "sources": sources,
        "corroborating_sources": corroborating_sources,
        "otx_corroborated": otx_corroborated,
        "evidence": evidence or [],
        "confidence_level": confidence_level,
        "confidence": confidence,
        "confidence_factors": confidence_factors or [],
        "malware": malware,
        "threat_type": threat_type,
        "first_seen": first_seen,
        "fetched_at": fetched_at,
    }
