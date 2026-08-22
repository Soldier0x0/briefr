"""Parse and resolve investigation search queries to entity references."""

from __future__ import annotations

import ipaddress
import re

from correlation.ioc_normalize import normalize_ioc
from db.ioc_digest import ioc_value_digest
from investigations.contracts import EntityRef, GRAPH_ENTITY_TYPES, RESOLVE_ROOT_ENTITY_TYPES

_CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


def is_valid_cve_id(value: str) -> bool:
    """True when ``value`` matches the investigation CVE id pattern."""
    return _CVE_RE.match((value or "").strip()) is not None


def is_valid_technique_id(value: str) -> bool:
    """True when ``value`` matches MITRE technique id pattern (T1234 or T1234.001)."""
    return _TECHNIQUE_RE.match((value or "").strip()) is not None
_TECHNIQUE_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$", re.IGNORECASE)
_CAMPAIGN_ID_RE = re.compile(r"^camp_[0-9a-fA-F]{12}$")
_HEX_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")
_MAX_QUERY_LEN = 512


def _ioc_kind_from_canon_type(canon_type: str) -> str:
    mapping = {
        "IP": "ip",
        "HASH": "hash",
        "DOMAIN": "domain",
        "URL": "url",
    }
    kind = mapping.get((canon_type or "").upper())
    if kind is None:
        raise ValueError(f"unsupported IOC type: {canon_type}")
    return kind


def _guess_ioc_type(value: str) -> str:
    if _HEX_HASH_RE.fullmatch(value):
        return "HASH"
    try:
        ipaddress.ip_address(value)
        return "IP"
    except ValueError:
        pass
    if "://" in value or "/" in value:
        return "URL"
    return "DOMAIN"


def parse_investigation_query(q: str) -> EntityRef:
    """Parse a search string into an EntityRef without existence checks."""
    stripped = (q or "").strip()
    if not stripped:
        raise ValueError("query is empty")
    if len(stripped) > _MAX_QUERY_LEN:
        raise ValueError("query too long")

    if _CVE_RE.match(stripped):
        cve_id = stripped.upper()
        return EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)

    normalized = normalize_ioc(_guess_ioc_type(stripped), stripped)
    if normalized is not None:
        canon_type, canon_value, _meta = normalized
        kind = _ioc_kind_from_canon_type(canon_type)
        entity_id = f"{kind}:{canon_value}"
        return EntityRef(
            entity_type="ioc",
            entity_id=entity_id,
            label=canon_value,
        )

    if _TECHNIQUE_RE.match(stripped):
        technique_id = stripped.upper()
        return EntityRef(
            entity_type="technique",
            entity_id=technique_id,
            label=technique_id,
        )

    campaign_id = stripped
    if stripped.lower().startswith("campaign:"):
        campaign_id = stripped.split(":", 1)[1].strip()
    if _CAMPAIGN_ID_RE.match(campaign_id):
        return EntityRef(
            entity_type="campaign",
            entity_id=campaign_id,
            label=campaign_id,
        )

    raise ValueError("unsupported query")


async def resolve_entity(db, q: str) -> EntityRef | None:
    """Parse and verify the entity exists in local stores."""
    ref = parse_investigation_query(q)
    exists = await _entity_exists(db, ref)
    if not exists:
        return None
    return await _enrich_label(db, ref)


async def _entity_exists(db, ref: EntityRef) -> bool:
    entity_type = ref.entity_type
    entity_id = ref.entity_id

    if entity_type == "cve":
        rows = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?",
            (entity_id.upper(),),
        )
        return bool(rows)

    if entity_type == "ioc":
        return await _ioc_exists(db, entity_id)

    if entity_type == "technique":
        rows = await db.execute_fetchall(
            """
            SELECT 1 FROM mitre_techniques WHERE technique_id = ?
            UNION
            SELECT 1 FROM cve_technique_map WHERE technique_id = ?
            LIMIT 1
            """,
            (entity_id.upper(), entity_id.upper()),
        )
        return bool(rows)

    if entity_type == "campaign":
        rows = await db.execute_fetchall(
            """
            SELECT 1 FROM correlation_campaigns
            WHERE campaign_id = ? AND retracted_at IS NULL
            """,
            (entity_id,),
        )
        return bool(rows)

    return False


async def _ioc_exists(db, entity_id: str) -> bool:
    if ":" not in entity_id:
        return False
    kind, _, value = entity_id.partition(":")
    ioc_type = kind.upper()
    if ioc_type == "IP":
        canon_type = "IP"
    elif ioc_type == "HASH":
        canon_type = "HASH"
    elif ioc_type == "DOMAIN":
        canon_type = "DOMAIN"
    elif ioc_type == "URL":
        canon_type = "URL"
    else:
        return False

    normalized = normalize_ioc(canon_type, value)
    if normalized is None:
        return False
    _canon_type, canon_value, _meta = normalized
    value_digest = ioc_value_digest(canon_value)

    rows = await db.execute_fetchall(
        """
        SELECT 1 FROM otx_pulse_iocs
        WHERE LOWER(ioc_type) = LOWER(?)
          AND (
            ioc_value_digest = ?
            OR (ioc_value_digest = '' AND LOWER(ioc_value) = LOWER(?))
          )
        LIMIT 1
        """,
        (canon_type, value_digest, canon_value),
    )
    if rows:
        return True

    rows = await db.execute_fetchall(
        """
        SELECT 1 FROM ti_mirror_iocs
        WHERE LOWER(ioc_type) = LOWER(?)
          AND (
            ioc_value_digest = ?
            OR (ioc_value_digest = '' AND LOWER(ioc_value) = LOWER(?))
          )
        LIMIT 1
        """,
        (_mirror_ioc_type(canon_type), value_digest, canon_value.lower()),
    )
    return bool(rows)


def _mirror_ioc_type(canon_type: str) -> str:
    match canon_type.upper():
        case "IP":
            return "ip"
        case "HASH":
            return "hash"
        case "DOMAIN":
            return "domain"
        case "URL":
            return "url"
        case other:
            raise ValueError(f"unexpected IOC type: {other}")


async def _enrich_label(db, ref: EntityRef) -> EntityRef:
    if ref.entity_type != "technique":
        return ref

    rows = await db.execute_fetchall(
        "SELECT name FROM mitre_techniques WHERE technique_id = ?",
        (ref.entity_id.upper(),),
    )
    if rows and rows[0]["name"]:
        return EntityRef(
            entity_type=ref.entity_type,
            entity_id=ref.entity_id,
            label=rows[0]["name"],
        )
    return ref


def is_resolve_root_entity_type(entity_type: str) -> bool:
    return entity_type.strip().lower() in RESOLVE_ROOT_ENTITY_TYPES


def is_graph_entity_type(entity_type: str) -> bool:
    return entity_type.strip().lower() in GRAPH_ENTITY_TYPES
