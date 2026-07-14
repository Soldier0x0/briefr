"""ThreatFox read-time corroboration for OTX IOC edges (CORR-PR-10)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from correlation.ioc_normalize import normalize_ioc, normalize_ioc_type

# ThreatFox mirror stores lowercase ip/hash/domain (feeds/threatfox.py).
_MIRROR_TYPES = {
    "IP": "ip",
    "DOMAIN": "domain",
    "HASH": "hash",
    "URL": "domain",
}


def mirror_type_for_otx(ioc_type: str) -> str | None:
    return _MIRROR_TYPES.get(normalize_ioc_type(ioc_type))


def corroboration_receipt(ioc_id: str) -> str:
    return f"threatfox:{ioc_id}"


def ioc_edge_key(ioc_type: str, ioc_value: str) -> tuple[str, str] | None:
    """Canonical OTX edge key used for ThreatFox mirror joins."""
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    return canon_type, canon_value.lower()


def _threatfox_lookup_pair(ioc_type: str, ioc_value: str) -> tuple[str, str] | None:
    tf_type = mirror_type_for_otx(ioc_type)
    if not tf_type:
        return None
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    if tf_type == "domain" and canon_type == "URL":
        parsed = urlparse(canon_value if "://" in canon_value else f"http://{canon_value}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            return None
        return tf_type, host
    return tf_type, canon_value.lower()


def _is_postgres(db) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _ioc_key(ioc_type: str, ioc_value: str) -> tuple[str, str] | None:
    return ioc_edge_key(ioc_type, ioc_value)


async def batch_threatfox_hits(
    db, iocs: list[tuple[str, str]]
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """
    Map canonical (OTX ioc_type, lowercased value) -> ThreatFox mirror rows.
    Join is on mirror type + case-insensitive value.
    """
    if not iocs:
        return {}

    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for ioc_type, ioc_value in iocs:
        key = _ioc_key(ioc_type, ioc_value)
        if key is None:
            continue
        pair = _threatfox_lookup_pair(ioc_type, ioc_value)
        if pair is None:
            continue
        lookup[key] = pair

    if not lookup:
        return {}

    pg = _is_postgres(db)
    clauses: list[str] = []
    params: list[Any] = []
    for idx, (tf_type, value_lower) in enumerate(lookup.values()):
        if pg:
            base = idx * 2
            clauses.append(f"(ioc_type = ${base + 1} AND ioc_value = ${base + 2})")
        else:
            clauses.append("(ioc_type = ? AND ioc_value = ?)")
        params.extend([tf_type, value_lower])

    rows = await db.execute_fetchall(
        f"""
        SELECT ioc_id, ioc_type, ioc_value, malware, threat_type,
               confidence_level, first_seen
        FROM threatfox_iocs
        WHERE {" OR ".join(clauses)}
        """,
        tuple(params),
    )

    hits: dict[tuple[str, str], list[dict[str, Any]]] = {}
    reverse: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for key, (tf_type, value_lower) in lookup.items():
        reverse.setdefault((tf_type, value_lower), []).append(key)
    for row in rows:
        tf_type = (row["ioc_type"] or "").strip().lower()
        value_lower = (row["ioc_value"] or "").strip().lower()
        keys = reverse.get((tf_type, value_lower))
        if not keys:
            continue
        for key in keys:
            hits.setdefault(key, []).append(dict(row))
    return hits
