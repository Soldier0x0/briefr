"""
AlienVault OTX — campaign correlation via community pulses.

CVE pulses: threat intel collections referencing a vulnerability.
Pulse IOCs: indicators bundled in a pulse (IPs, domains, hashes).
IOC lookup: pulses referencing an indicator + CVE pivot links.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from tracking import record_api_call

logger = logging.getLogger(__name__)

OTX_BASE = "https://otx.alienvault.com/api/v1"
CACHE_HOURS = 6
CVE_TAG_RE = re.compile(r"CVE-\d{4}-\d+", re.I)


def _otx_headers(api_key: str) -> dict[str, str]:
    return {
        "X-OTX-API-KEY": api_key.strip(),
        "Accept": "application/json",
    }


def _parse_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _extract_cves_from_pulse(pulse: dict) -> list[str]:
    found: set[str] = set()
    for tag in pulse.get("tags") or []:
        for match in CVE_TAG_RE.findall(str(tag)):
            found.add(match.upper())
    for ref in pulse.get("references") or []:
        for match in CVE_TAG_RE.findall(str(ref)):
            found.add(match.upper())
    for cve in pulse.get("cves") or []:
        cid = cve if isinstance(cve, str) else (cve.get("id") or cve.get("cve") or "")
        if CVE_TAG_RE.fullmatch(str(cid).strip()):
            found.add(str(cid).strip().upper())
    return sorted(found)



def _author_name(raw: dict) -> str:
    author = raw.get("author_name") or raw.get("author") or ""
    if isinstance(author, dict):
        return str(
            author.get("username")
            or author.get("name")
            or author.get("id")
            or ""
        ).strip()
    return str(author).strip()



def _normalize_pulse(raw: dict) -> dict:
    malware = raw.get("malware_families") or raw.get("malware_family") or []
    if isinstance(malware, str):
        malware = [m.strip() for m in malware.split(",") if m.strip()]

    tags = _parse_json_list(raw.get("tags"))
    adversary = (
        raw.get("adversary")
        or raw.get("actor")
        or raw.get("threat_actor")
        or ""
    )
    if isinstance(adversary, list):
        adversary = adversary[0] if adversary else ""

    return {
        "pulse_id": str(raw.get("id") or raw.get("pulse_id") or ""),
        "pulse_name": (raw.get("name") or "Unnamed pulse").strip(),
        "author": _author_name(raw),
        "created_date": (raw.get("created") or raw.get("created_date") or "").strip(),
        "tags": tags,
        "targeted_countries": _parse_json_list(raw.get("targeted_countries")),
        "adversary": str(adversary).strip() if adversary else "",
        "malware_families": malware,
        "ioc_count": int(
            raw.get("indicator_count")
            or raw.get("ioc_count")
            or raw.get("indicators_count")
            or 0
        ),
    }


async def fetch_cve_pulses(cve_id: str, api_key: str) -> list[dict]:
    """Fetch OTX pulses referencing a CVE."""
    if not api_key or not cve_id:
        return []

    url = f"{OTX_BASE}/indicators/cve/{cve_id.upper()}/general"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_otx_headers(api_key))
        await record_api_call("otx", 1)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("OTX CVE pulse fetch failed for %s: %s", cve_id, exc)
        return []

    pulse_info = data.get("pulse_info") or {}
    raw_pulses = pulse_info.get("pulses") or []
    pulses: list[dict] = []
    for raw in raw_pulses:
        if not isinstance(raw, dict):
            continue
        try:
            pulses.append(_normalize_pulse(raw))
        except Exception as exc:
            logger.warning("OTX pulse normalize failed for %s: %s", cve_id, exc)
    return pulses


async def fetch_pulse_iocs(pulse_id: str, api_key: str) -> list[dict]:
    """Fetch IOCs contained in an OTX pulse."""
    if not api_key or not pulse_id:
        return []

    url = f"{OTX_BASE}/pulses/{pulse_id}/indicators"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_otx_headers(api_key))
        await record_api_call("otx", 1)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("OTX pulse IOC fetch failed for %s: %s", pulse_id, exc)
        return []

    rows = data.get("results") or data.get("indicators") or []
    iocs: list[dict] = []
    for row in rows:
        ioc_type = (row.get("type") or row.get("indicator_type") or "").strip()
        value = (row.get("indicator") or row.get("content") or "").strip()
        if not value:
            continue
        iocs.append({
            "ioc_type": ioc_type,
            "ioc_value": value,
            "description": (row.get("description") or row.get("title") or "").strip(),
        })
    return iocs


def _otx_indicator_path(ioc_type: str, value: str) -> str | None:
    t = ioc_type.lower()
    if t == "ip":
        return f"IPv4/{value}"
    if t == "domain":
        return f"domain/{value.lower()}"
    if t == "hash":
        return f"file/{value.lower()}"
    return None


async def lookup_ioc_in_otx(ioc_value: str, ioc_type: str, api_key: str) -> dict:
    """Lookup an IOC in OTX — pulse count, pulses, geo, and related CVEs."""
    empty = {
        "pulse_count": 0,
        "pulses": [],
        "country": None,
        "asn": None,
        "adversary": None,
        "malware_families": [],
        "related_cves": [],
    }
    if not api_key or not ioc_value:
        return empty

    path = _otx_indicator_path(ioc_type, ioc_value)
    if not path:
        return empty

    url = f"{OTX_BASE}/indicators/{path}/general"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_otx_headers(api_key))
        await record_api_call("otx", 1)
        if response.status_code == 404:
            return empty
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("OTX IOC lookup failed for %s: %s", ioc_value, exc)
        return empty

    pulse_info = data.get("pulse_info") or {}
    raw_pulses = pulse_info.get("pulses") or []
    pulses = []
    related_cves: set[str] = set()
    adversaries: list[str] = []
    families: list[str] = []

    for raw in raw_pulses:
        norm = _normalize_pulse(raw)
        pulses.append({
            "pulse_id": norm["pulse_id"],
            "name": norm["pulse_name"],
            "adversary": norm["adversary"],
            "malware_families": norm["malware_families"],
        })
        if norm["adversary"]:
            adversaries.append(norm["adversary"])
        families.extend(norm["malware_families"])
        related_cves.update(_extract_cves_from_pulse(raw))

    asn = data.get("asn") or data.get("asn_code")
    if isinstance(asn, dict):
        asn = asn.get("asn") or asn.get("number")

    return {
        "pulse_count": int(pulse_info.get("count") or len(pulses)),
        "pulses": pulses[:10],
        "country": data.get("country") or data.get("country_name"),
        "asn": str(asn) if asn else None,
        "adversary": adversaries[0] if adversaries else None,
        "malware_families": list(dict.fromkeys(families))[:8],
        "related_cves": sorted(related_cves),
    }


async def load_otx_pulses_for_cve(
    db, cve_id: str, api_key: str
) -> list[dict]:
    """Return cached OTX pulses for a CVE, refreshing if stale."""
    from database import get_feed_cache, read_otx_cve_pulses, store_otx_cve_pulses

    key = cve_id.upper()
    if not api_key:
        cached = await read_otx_cve_pulses(db, key, max_age_hours=CACHE_HOURS)
        return cached or []

    cache_key = f"otx:cve:{key}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached.get("pulses", [])

    db_rows = await read_otx_cve_pulses(db, key, max_age_hours=CACHE_HOURS)
    if db_rows is not None:
        return db_rows

    pulses = await fetch_cve_pulses(key, api_key)
    await store_otx_cve_pulses(db, key, pulses)
    return pulses


async def load_pulse_iocs(db, pulse_id: str, api_key: str) -> list[dict]:
    """Return cached pulse IOCs, refreshing if stale."""
    from database import get_feed_cache, read_otx_pulse_iocs, store_otx_pulse_iocs

    if not pulse_id:
        return []
    if not api_key:
        cached = await read_otx_pulse_iocs(db, pulse_id, max_age_hours=CACHE_HOURS)
        return cached or []

    cache_key = f"otx:pulse:{pulse_id}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached.get("iocs", [])

    db_rows = await read_otx_pulse_iocs(db, pulse_id, max_age_hours=CACHE_HOURS)
    if db_rows is not None:
        return db_rows

    iocs = await fetch_pulse_iocs(pulse_id, api_key)
    await store_otx_pulse_iocs(db, pulse_id, iocs)
    return iocs


async def lookup_otx_for_ioc(
    db, ioc_value: str, ioc_type: str, api_key: str
) -> dict:
    """Cached OTX IOC enrichment for IOC Lookup."""
    from database import get_feed_cache, set_feed_cache

    if not api_key:
        return await lookup_ioc_in_otx(ioc_value, ioc_type, "")

    cache_key = f"otx:ioc:{ioc_type}:{ioc_value.lower()}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached

    result = await lookup_ioc_in_otx(ioc_value, ioc_type, api_key)
    await set_feed_cache(db, cache_key, result)
    return result


async def top_pulse_ipv4s(
    db, pulse_id: str, api_key: str, limit: int = 3
) -> list[str]:
    """Top IPv4 indicators from a pulse (for Investigate IOCs prefill)."""
    iocs = await load_pulse_iocs(db, pulse_id, api_key)
    ips: list[str] = []
    for row in iocs:
        ioc_t = (row.get("ioc_type") or "").upper()
        val = (row.get("ioc_value") or "").strip()
        if ioc_t in ("IPV4", "IPV6") and val:
            ips.append(val)
        if len(ips) >= limit:
            break
    return ips


async def run_otx_nightly_correlation(db, api_key: str) -> dict:
    """Pre-warm OTX pulse cache for CVEs published in the last 7 days."""
    from database import get_recent_cve_ids_for_otx, store_otx_cve_pulses

    if not api_key:
        return {"cves": 0, "pulses": 0}

    cve_ids = await get_recent_cve_ids_for_otx(db, days=7)
    total_pulses = 0
    for cve_id in cve_ids:
        try:
            pulses = await fetch_cve_pulses(cve_id, api_key)
            await store_otx_cve_pulses(db, cve_id, pulses)
            total_pulses += len(pulses)
        except Exception as exc:
            logger.warning("OTX nightly skip %s: %s", cve_id, exc)

    return {"cves": len(cve_ids), "pulses": total_pulses}
