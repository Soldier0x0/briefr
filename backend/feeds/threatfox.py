"""ThreatFox bulk IOC ingest (abuse.ch Auth-Key)."""

from __future__ import annotations

import ipaddress
import logging
import os
from typing import Any

from correlation.ioc_normalize import _url_host, normalize_ioc
from feeds.extended import abusech_headers
from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

THREATFOX_API_URL = "https://threatfox-api.abuse.ch/api/v1/"


def _lookup_type_from_threatfox(ioc_type: str) -> str | None:
    t = (ioc_type or "").strip().lower()
    if t in ("ip:port", "ip"):
        return "ip"
    if t == "domain":
        return "domain"
    if t in ("md5_hash", "sha256_hash", "sha1_hash", "hash"):
        return "hash"
    if t == "url":
        return "domain"
    return None


def _extract_match_value(raw_ioc: str, threatfox_type: str, lookup_type: str) -> str | None:
    raw = (raw_ioc or "").strip()
    if not raw:
        return None

    if lookup_type == "ip":
        host = raw.split(":")[0] if ":" in raw and threatfox_type == "ip:port" else raw
        try:
            return str(ipaddress.ip_address(host.strip()))
        except ValueError:
            return None

    if lookup_type == "domain" and threatfox_type == "url":
        try:
            host = _url_host(raw)
            return host or None
        except ValueError:
            return None

    normalized = normalize_ioc(
        {"ip": "IP", "hash": "HASH", "domain": "DOMAIN"}.get(lookup_type, lookup_type.upper()),
        raw,
    )
    if normalized is None:
        return None
    _canon_type, canon_value, _meta = normalized
    return canon_value


def parse_threatfox_ioc(entry: dict[str, Any]) -> dict[str, str] | None:
    ioc_id = str(entry.get("id") or "").strip()
    raw_ioc = (entry.get("ioc") or "").strip()
    tf_type = (entry.get("ioc_type") or "").strip()
    if not ioc_id or not raw_ioc:
        return None

    lookup_type = _lookup_type_from_threatfox(tf_type)
    if not lookup_type:
        return None

    match_value = _extract_match_value(raw_ioc, tf_type, lookup_type)
    if not match_value:
        return None

    return {
        "ioc_id": ioc_id,
        "ioc_type": lookup_type,
        "ioc_value": match_value,
        "raw_ioc": raw_ioc,
        "malware": (entry.get("malware_printable") or entry.get("malware") or "").strip(),
        "threat_type": (entry.get("threat_type") or "").strip(),
        "confidence_level": str(entry.get("confidence_level") or 0),
        "first_seen": (entry.get("first_seen") or "").strip(),
    }


async def fetch_threatfox_iocs(auth_key: str, *, days: int = 7) -> list[dict[str, str]]:
    """Fetch recent ThreatFox IOCs (max 7 days per API)."""
    key = (auth_key or "").strip()
    if not key:
        return []

    days = max(1, min(int(days), 7))
    headers = {
        **abusech_headers(key),
        "Content-Type": "application/json",
    }
    payload = {"query": "get_iocs", "days": days}

    try:
        response = await resilient_request(
            "threatfox",
            "POST",
            THREATFOX_API_URL,
            headers=headers,
            json=payload,
            timeout=120.0,
            queue_operation="threat_intel_sync",
            queue_context_type="task",
            queue_context_id="threatfox_sync",
        )
        await record_api_call("threatfox", 1)
    except CircuitOpenError:
        logger.warning("ThreatFox circuit open — skipping sync")
        return []
    except Exception as exc:
        logger.error("ThreatFox fetch failed: %s", exc)
        return []

    if response.status_code != 200:
        logger.warning("ThreatFox HTTP %s", response.status_code)
        return []

    body = response.json()
    if body.get("query_status") != "ok":
        logger.warning("ThreatFox query_status: %s", body.get("query_status"))
        return []

    parsed: list[dict[str, str]] = []
    for entry in body.get("data") or []:
        row = parse_threatfox_ioc(entry)
        if row:
            parsed.append(row)
    return parsed


def threatfox_sync_days() -> int:
    raw = os.environ.get("THREATFOX_SYNC_DAYS", "7").strip()
    try:
        return max(1, min(int(raw), 7))
    except ValueError:
        return 7
