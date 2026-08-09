"""Source-agnostic mirror corroboration driven by the catalog source registry.

Generalizes the ThreatFox-hardcoded read path (`threatfox_corroboration.py`):
`batch_source_evidence` maps canonical OTX edge keys -> matching mirror rows
across every source registered in `sources.registry`, one registry iteration
with no per-source branches.
"""

from __future__ import annotations

from typing import Any

from correlation.ioc_normalize import _url_host, normalize_ioc
from sources.registry import CATALOG_SOURCES, SourceDescriptor


def corroboration_receipt(source_key: str, ref_id: str) -> str:
    """Receipt identifier for one mirror row: ``<source_key>:<ref_id>``."""
    return f"{source_key}:{ref_id}"


def ioc_edge_key(ioc_type: str, ioc_value: str) -> tuple[str, str] | None:
    """Canonical OTX edge key used for mirror joins."""
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    return canon_type, canon_value.lower()


def _mirror_lookup_pair(
    desc: SourceDescriptor, ioc_type: str, ioc_value: str
) -> tuple[tuple[str, str], str] | None:
    """Return ((join_column, mirror_type), value) or None.

    ``join_column`` is ``host_ioc`` when a DOMAIN edge must match a URL row's
    derived host (extracted once at ingest, plan §3.4), and ``ioc_value`` for
    verbatim matches. URL rows therefore corroborate both DOMAIN edges (via
    host) and URL edges (via the stored full URL).
    """
    mirror_type = desc.canonical_type(ioc_type)
    if not mirror_type:
        return None
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    if mirror_type == "url" and canon_type == "DOMAIN":
        return ("host_ioc", "url"), canon_value.lower()
    if mirror_type == "url" and canon_type == "URL":
        return ("ioc_value", "url"), canon_value.lower()
    if mirror_type == "domain" and canon_type == "URL":
        host = _url_host(canon_value)
        if not host:
            return None
        return ("ioc_value", "domain"), host
    return ("ioc_value", mirror_type), canon_value.lower()


def _mirror_clauses(
    lookup: dict[tuple[str, str], tuple[tuple[str, str], str]]
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for (join_column, mirror_type), value in lookup.values():
        if join_column not in ("host_ioc", "ioc_value"):
            raise ValueError(f"unexpected mirror join column: {join_column!r}")
        clauses.append(f"(ioc_type = ? AND LOWER({join_column}) = ?)")
        params.extend([mirror_type, value])
    return " OR ".join(clauses), params


async def batch_source_evidence(
    db, iocs: list[tuple[str, str]]
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """
    Map canonical (OTX ioc_type, lowercased value) -> mirror rows across all
    catalog sources. Each returned row carries `source` and `ref_id` so
    callers can build receipts via corroboration_receipt(source, ref_id).
    """
    if not iocs:
        return {}

    edge_keys: dict[tuple[str, str], tuple[str, str]] = {}
    for ioc_type, ioc_value in iocs:
        key = ioc_edge_key(ioc_type, ioc_value)
        if key is None:
            continue
        edge_keys[key] = (ioc_type, ioc_value)

    if not edge_keys:
        return {}

    hits: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for desc in CATALOG_SOURCES:
        lookup: dict[tuple[str, str], tuple[tuple[str, str], str]] = {}
        for key, (ioc_type, ioc_value) in edge_keys.items():
            pair = _mirror_lookup_pair(desc, ioc_type, ioc_value)
            if pair is not None:
                lookup[key] = pair
        if not lookup:
            continue

        clauses, params = _mirror_clauses(lookup)
        rows = await db.execute_fetchall(
            f"""
            SELECT source, ref_id, ioc_type, ioc_value, host_ioc, malware,
                   threat_type, confidence_level, first_seen
            FROM ti_mirror_iocs
            WHERE source = ? AND ({clauses})
            """,
            (desc.source_key, *params),
        )

        reverse: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
        for key, ((join_column, mirror_type), value) in lookup.items():
            reverse.setdefault((join_column, mirror_type, value), []).append(key)
        for row in rows:
            mirror_type = (row["ioc_type"] or "").strip().lower()
            candidates: list[tuple[str, str, str]] = []
            if mirror_type == "url":
                host_lower = (row["host_ioc"] or "").strip().lower()
                value_lower = (row["ioc_value"] or "").strip().lower()
                if host_lower:
                    candidates.append(("host_ioc", "url", host_lower))
                if value_lower:
                    candidates.append(("ioc_value", "url", value_lower))
            else:
                candidates.append(
                    ("ioc_value", mirror_type, (row["ioc_value"] or "").strip().lower())
                )
            matched_keys: set[tuple[str, str]] = set()
            for candidate in candidates:
                matched_keys.update(reverse.get(candidate, []))
            for key in matched_keys:
                hits.setdefault(key, []).append(dict(row))
    return hits
