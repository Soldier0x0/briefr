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

from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)


async def _otx_get(
    url: str,
    api_key: str,
    *,
    operation: str = "pulse_lookup",
    context_type: str | None = None,
    context_id: str | None = None,
) -> dict | None:
    """GET via the resilient client; returns None on 404, circuit-open or failure."""
    from tracking import has_quota

    if not await has_quota("otx"):
        logger.warning("OTX hourly quota exhausted — skipping %s", url)
        return None
    try:
        response = await resilient_get(
            "otx",
            url,
            headers=_otx_headers(api_key),
            timeout=30.0,
            queue_operation=operation,
            queue_context_type=context_type,
            queue_context_id=context_id,
        )
        await record_api_call("otx", 1)
        data = response.json()
        return data if isinstance(data, dict) else None
    except CircuitOpenError:
        logger.warning("OTX circuit open — skipping %s", url)
        return None
    except httpx.HTTPStatusError as exc:
        await record_api_call("otx", 1)
        if exc.response.status_code != 404:
            logger.warning("OTX HTTP %s for %s", exc.response.status_code, url)
        return None
    except httpx.HTTPError as exc:
        logger.warning("OTX request failed for %s: %s", url, exc)
        return None
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("OTX parse failed for %s: %s", url, exc)
        return None

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




def _normalize_malware_families(value) -> list[str]:
    if isinstance(value, str):
        return [m.strip() for m in value.split(",") if m.strip()]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("name") or item.get("family") or item.get("id") or ""
            if str(label).strip():
                out.append(str(label).strip())
    return out


def _normalize_adversary(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        return str(value.get("name") or value.get("id") or "").strip()
    return str(value).strip() if value else ""



def _normalize_pulse(raw: dict) -> dict:
    malware = _normalize_malware_families(
        raw.get("malware_families") or raw.get("malware_family") or []
    )

    tags = _parse_json_list(raw.get("tags"))
    adversary = _normalize_adversary(
        raw.get("adversary")
        or raw.get("actor")
        or raw.get("threat_actor")
        or ""
    )

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


async def fetch_cve_pulses(cve_id: str, api_key: str) -> list[dict] | None:
    """Fetch OTX pulses referencing a CVE.

    Returns None when the upstream request fails (HTTP 5xx, circuit open, etc.)
    so callers can distinguish outage from a legitimate empty pulse list.
    """
    if not api_key or not cve_id:
        return []

    url = f"{OTX_BASE}/indicators/cve/{cve_id.upper()}/general"
    data = await _otx_get(
        url,
        api_key,
        operation="pulse_lookup",
        context_type="cve",
        context_id=cve_id.upper(),
    )
    if data is None:
        return None

    pulse_info = data.get("pulse_info") or {}
    raw_pulses = pulse_info.get("pulses") or []
    pulse_count = int(pulse_info.get("count") or 0)
    pulses: list[dict] = []
    for raw in raw_pulses:
        if not isinstance(raw, dict):
            continue
        try:
            pulses.append(_normalize_pulse(raw))
        except Exception as exc:
            logger.warning("OTX pulse normalize failed for %s: %s", cve_id, exc)
    if pulse_count > 0 and not pulses:
        logger.error(
            "OTX returned count=%s but parsed 0 pulses for %s — check pulse schema",
            pulse_count,
            cve_id,
        )
    return pulses


async def fetch_pulse_iocs(pulse_id: str, api_key: str) -> list[dict]:
    """Fetch IOCs contained in an OTX pulse."""
    if not api_key or not pulse_id:
        return []

    url = f"{OTX_BASE}/pulses/{pulse_id}/indicators"
    data = await _otx_get(
        url,
        api_key,
        operation="indicator_lookup",
        context_type="task",
        context_id=pulse_id,
    )
    if data is None:
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
            "observed_at": str(row.get("created") or row.get("created_date") or "").strip() or None,
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
    data = await _otx_get(
        url,
        api_key,
        operation="indicator_lookup",
        context_type="observable",
        context_id=ioc_value,
    )
    if data is None:
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
    if pulses is None:
        stale = await read_otx_cve_pulses(db, key, max_age_hours=None)
        if stale:
            logger.warning(
                "OTX upstream unavailable for %s — serving %s stale pulse(s)",
                key,
                len(stale),
            )
            return stale
        return []

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
    from correlation.ioc_graph import related_cves_for_ioc
    from database import get_feed_cache, set_feed_cache

    if not api_key:
        result = await lookup_ioc_in_otx(ioc_value, ioc_type, "")
    else:
        cache_key = f"otx:ioc:{ioc_type}:{ioc_value.lower()}"
        cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
        if cached is not None:
            result = cached
        else:
            result = await lookup_ioc_in_otx(ioc_value, ioc_type, api_key)
            await set_feed_cache(db, cache_key, result)

    db_related = await related_cves_for_ioc(db, ioc_type, ioc_value)
    if db_related:
        merged = sorted(set(result.get("related_cves") or []) | set(db_related))
        result = {**result, "related_cves": merged, "related_cves_source": "correlation_tables"}
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


async def run_otx_nightly_correlation(db, api_key: str, progress_cb=None) -> dict:
    """Pre-warm OTX pulse cache for prioritized CVEs."""
    from database import get_db, get_prioritized_cve_ids_for_otx, store_otx_cve_pulses

    if not api_key:
        return {"cves": 0, "pulses": 0}

    passed_db = db
    own_db = passed_db is None
    if own_db:
        db = await get_db()
    try:
        cve_ids = await get_prioritized_cve_ids_for_otx(db)
    finally:
        if own_db:
            await db.close()
    total_pulses = 0
    for index, cve_id in enumerate(cve_ids):
        if progress_cb:
            progress_cb(f"Fetching OTX threat intelligence pulses: {cve_id} ({index + 1}/{len(cve_ids)})…")
        try:
            pulses = await fetch_cve_pulses(cve_id, api_key)
            if pulses is None or not pulses:
                continue
            write_db = await get_db() if own_db else passed_db
            try:
                await store_otx_cve_pulses(write_db, cve_id, pulses)
                await write_db.commit()
                total_pulses += len(pulses)
            finally:
                if own_db:
                    await write_db.close()
        except Exception as exc:
            logger.warning("OTX nightly skip %s: %s", cve_id, exc)

    return {"cves": len(cve_ids), "pulses": total_pulses}
