"""ThreatFox read-time corroboration for OTX IOC edges (CORR-PR-10)."""

from __future__ import annotations

from typing import Any

from correlation.ioc_normalize import normalize_ioc_type

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


def _is_postgres(db) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _ioc_key(ioc_type: str, ioc_value: str) -> tuple[str, str]:
    return (normalize_ioc_type(ioc_type), (ioc_value or "").strip().lower())


async def batch_threatfox_hits(
    db, iocs: list[tuple[str, str]]
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """
    Map canonical (OTX ioc_type, lowercased value) -> ThreatFox mirror rows.
    Join is on mirror type + case-insensitive value.
    """
    if not iocs:
        return {}

    lookup: dict[tuple[str, str], tuple[str, str, str]] = {}
    for ioc_type, ioc_value in iocs:
        value = (ioc_value or "").strip()
        if not value:
            continue
        tf_type = mirror_type_for_otx(ioc_type)
        if not tf_type:
            continue
        key = _ioc_key(ioc_type, value)
        lookup[key] = (tf_type, value.lower(), normalize_ioc_type(ioc_type))

    if not lookup:
        return {}

    pg = _is_postgres(db)
    clauses: list[str] = []
    params: list[Any] = []
    for idx, (tf_type, value_lower, _) in enumerate(lookup.values()):
        if pg:
            base = idx * 2
            clauses.append(f"(ioc_type = ${base + 1} AND LOWER(ioc_value) = ${base + 2})")
        else:
            clauses.append("(ioc_type = ? AND LOWER(ioc_value) = ?)")
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
    reverse: dict[tuple[str, str], tuple[str, str]] = {
        (tf_type, value_lower): key for key, (tf_type, value_lower, _) in lookup.items()
    }
    for row in rows:
        tf_type = (row["ioc_type"] or "").strip().lower()
        value_lower = (row["ioc_value"] or "").strip().lower()
        key = reverse.get((tf_type, value_lower))
        if not key:
            continue
        hits.setdefault(key, []).append(dict(row))
    return hits
