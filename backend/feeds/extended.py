"""
Extended threat-intelligence feeds — each answers a question existing sources do not.

Sploitus: public exploit listings per CVE (not covered by NVD reference tags alone).
GreyNoise: internet-wide scanning context for IPs (not VT/AbuseIPDB).
MalwareBazaar: malware family for file hashes (not VT classification).
URLhaus: URL/domain malware hosting (not VT domain stats).
CIRCL CVE-Search: supplemental references, CAPEC, vendor advisories.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote, urljoin

import httpx

from tracking import record_api_call

logger = logging.getLogger(__name__)

SPLOITUS_SEARCH_URL = "https://sploitus.com/search"
GREYNOISE_COMMUNITY_URL = "https://api.greynoise.io/v3/community"
MALWAREBazaar_URL = "https://mb-api.abuse.ch/api/v1/"
URLHAUS_URL_API = "https://urlhaus-api.abuse.ch/v1/url/"
URLHAUS_HOST_API = "https://urlhaus-api.abuse.ch/v1/host/"
CIRCL_CVE_URL = "https://cve.circl.lu/api/cve"

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

WEAPONISED_HINTS = (
    "metasploit",
    "exploitdb",
    "exploit-db",
    "weaponized",
    "weaponised",
    "in-the-wild",
)


def abusech_headers(auth_key: str | None) -> dict[str, str]:
    """Single Auth-Key from https://auth.abuse.ch/ works for MalwareBazaar and URLhaus."""
    if not auth_key or not auth_key.strip():
        return {}
    return {"Auth-Key": auth_key.strip()}


def extract_ipv4_from_cve(description: str | None, source_urls: list | None) -> list[str]:
    """IPv4 addresses mentioned in CVE text or reference URLs (max 5)."""
    found: set[str] = set()
    for text in [description or "", *(source_urls or [])]:
        for ip in IPV4_RE.findall(text):
            if not ip.startswith(("0.", "127.", "255.")):
                found.add(ip)
    return sorted(found)[:5]


def _normalize_exploit_type(raw_type: str, title: str, source: str) -> str:
    blob = f"{raw_type} {title} {source}".lower()
    if "metasploit" in blob:
        return "metasploit"
    if any(h in blob for h in WEAPONISED_HINTS):
        return "weaponised"
    if "poc" in blob or "proof" in blob or "github" in blob:
        return "poc"
    return "poc"


def _sploitus_exploit_url(item: dict) -> str:
    href = (item.get("href") or "").strip()
    if href:
        if href.startswith("http"):
            return href
        return urljoin("https://sploitus.com", href)
    exploit_id = item.get("id") or ""
    if exploit_id:
        return f"https://sploitus.com/exploit?id={quote(exploit_id)}"
    return ""


async def fetch_sploitus_exploits(cve_id: str, limit: int = 25) -> list[dict]:
    """Search Sploitus for public exploits linked to a CVE."""
    query = cve_id.upper()
    payload = {
        "query": query,
        "type": "exploits",
        "sort": "default",
        "title": False,
        "offset": 0,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://sploitus.com",
        "Referer": f"https://sploitus.com/?query={quote(query)}",
        "User-Agent": CHROME_UA,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SPLOITUS_SEARCH_URL,
                json=payload,
                headers=headers,
            )
        await record_api_call("sploitus", 1)

        if response.status_code in (422, 499, 429):
            logger.warning("Sploitus rate limit or rejection for %s: %s", query, response.status_code)
            return []
        if response.status_code != 200:
            logger.warning("Sploitus HTTP %s for %s", response.status_code, query)
            return []

        data = response.json()
        items = data.get("exploits") or []
        out: list[dict] = []
        for item in items[:limit]:
            title = (item.get("title") or "Untitled exploit").strip()
            source = (item.get("type") or item.get("language") or "unknown").strip()
            exploit_type = _normalize_exploit_type(
                item.get("type") or "",
                title,
                source,
            )
            url = _sploitus_exploit_url(item)
            out.append(
                {
                    "title": title,
                    "type": exploit_type,
                    "source": source,
                    "url": url,
                    "published_date": (item.get("published") or "").strip(),
                }
            )
        return out
    except httpx.HTTPError as exc:
        logger.error("Sploitus request failed for %s: %s", query, exc)
        return []
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Sploitus parse failed for %s: %s", query, exc)
        return []


async def fetch_greynoise_ip(ip: str, api_key: str) -> dict | None:
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{GREYNOISE_COMMUNITY_URL}/{ip}",
                headers={
                    "key": api_key,
                    "Accept": "application/json",
                },
            )
        await record_api_call("greynoise", 1)

        if response.status_code == 404:
            return {
                "ip": ip,
                "classification": "unknown",
                "name": "No GreyNoise record",
                "link": f"https://viz.greynoise.io/ip/{ip}",
                "noise": False,
            }
        if response.status_code in (401, 403):
            logger.warning("GreyNoise auth error for %s", ip)
            return None
        if response.status_code == 429:
            logger.warning("GreyNoise rate limit")
            return None
        response.raise_for_status()
        data = response.json()
        return {
            "ip": data.get("ip", ip),
            "classification": (data.get("classification") or "unknown").lower(),
            "name": data.get("name") or "",
            "link": data.get("link") or f"https://viz.greynoise.io/ip/{ip}",
            "noise": bool(data.get("noise")),
            "riot": bool(data.get("riot")),
        }
    except httpx.HTTPError as exc:
        logger.error("GreyNoise lookup failed for %s: %s", ip, exc)
        return None


async def fetch_malwarebazaar_hash(
    file_hash: str, abusech_auth_key: str | None = None
) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                MALWAREBazaar_URL,
                data={"query": "get_info", "hash": file_hash.lower()},
                headers=abusech_headers(abusech_auth_key),
            )
        await record_api_call("malwarebazaar", 1)

        if response.status_code in (401, 403):
            logger.warning("MalwareBazaar auth rejected — check ABUSECH_AUTH_KEY")
            return None
        if response.status_code != 200:
            return None
        data = response.json()
        status = (data.get("query_status") or "").lower()
        if status in ("unknown_auth_key", "no_auth_key"):
            logger.warning("MalwareBazaar requires ABUSECH_AUTH_KEY")
            return None
        if status != "ok":
            return None
        entry = data.get("data")
        if isinstance(entry, list):
            entry = entry[0] if entry else {}
        if not isinstance(entry, dict):
            entry = data

        tags_raw = entry.get("tags") or []
        if isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = [str(t) for t in tags_raw if t]

        yara = entry.get("yara_rules") or entry.get("yara") or []
        if isinstance(yara, dict):
            yara = list(yara.keys())

        return {
            "malware_family": entry.get("signature") or entry.get("malware") or "",
            "first_seen": entry.get("first_seen") or entry.get("first_seen_utc") or "",
            "tags": tags[:20],
            "yara_rules": [str(y) for y in yara][:10] if yara else [],
            "file_name": entry.get("file_name") or "",
        }
    except httpx.HTTPError as exc:
        logger.error("MalwareBazaar lookup failed: %s", exc)
        return None


async def fetch_urlhaus_indicator(
    value: str,
    ioc_type: str,
    abusech_auth_key: str | None = None,
) -> dict | None:
    """Lookup URLhaus for a URL or domain/host."""
    headers = abusech_headers(abusech_auth_key)
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            if ioc_type == "domain":
                payload = {"host": value.lower()}
                if abusech_auth_key:
                    payload["auth_key"] = abusech_auth_key.strip()
                response = await client.post(
                    URLHAUS_HOST_API,
                    json=payload,
                    headers=headers,
                )
            else:
                url = value if value.startswith(("http://", "https://")) else f"http://{value}"
                form = {"url": url}
                if abusech_auth_key:
                    form["auth_key"] = abusech_auth_key.strip()
                response = await client.post(
                    URLHAUS_URL_API,
                    data=form,
                    headers=headers,
                )
        await record_api_call("urlhaus", 1)

        if response.status_code in (401, 403):
            logger.warning("URLhaus auth rejected — check ABUSECH_AUTH_KEY")
            return None
        if response.status_code != 200:
            return None
        data = response.json()
        status = (data.get("query_status") or "").lower()
        if status in ("unknown_auth_key", "no_auth_key"):
            logger.warning("URLhaus requires ABUSECH_AUTH_KEY")
            return None
        if status in ("no_results", "invalid_host", "invalid_url"):
            return None
        if status not in ("ok", "ok_host"):
            return None

        threat = data.get("threat") or data.get("threat_type") or ""
        tags_raw = data.get("tags") or []
        if isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = [str(t) for t in tags_raw if t]

        return {
            "threat_type": threat,
            "tags": tags[:15],
            "reporter": data.get("reporter") or "",
            "url_status": data.get("url_status") or data.get("blacklists", ""),
            "reference": data.get("urlhaus_reference") or data.get("urlhaus_link") or "",
        }
    except httpx.HTTPError as exc:
        logger.error("URLhaus lookup failed: %s", exc)
        return None


async def fetch_circl_cve(cve_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(
                f"{CIRCL_CVE_URL}/{cve_id.upper()}",
                headers={"Accept": "application/json"},
            )
        await record_api_call("circl", 1)

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            logger.warning("CIRCL HTTP %s for %s", response.status_code, cve_id)
            return None
        return response.json()
    except httpx.HTTPError as exc:
        logger.error("CIRCL lookup failed for %s: %s", cve_id, exc)
        return None


def merge_circl_into_cve(cve: dict, circl: dict | None) -> dict:
    """Append CIRCL references and CAPEC IDs not already present."""
    if not circl:
        return cve

    existing_urls = {u.lower() for u in (cve.get("source_urls") or []) if isinstance(u, str)}
    extra_refs: list[str] = []

    for ref in circl.get("references") or []:
        if isinstance(ref, str) and ref.strip():
            url = ref.strip()
        elif isinstance(ref, dict):
            url = (ref.get("url") or ref.get("name") or "").strip()
        else:
            continue
        if url and url.lower() not in existing_urls:
            extra_refs.append(url)
            existing_urls.add(url.lower())

    for key in ("refmap", "vulnerable_product"):
        pass

    if extra_refs:
        cve["source_urls"] = list(cve.get("source_urls") or []) + extra_refs

    capec: list[str] = []
    for item in circl.get("capec") or []:
        if isinstance(item, str) and item.upper().startswith("CAPEC-"):
            capec.append(item.upper())
        elif isinstance(item, dict):
            cid = item.get("id") or item.get("name") or ""
            if "CAPEC" in str(cid).upper():
                capec.append(str(cid).upper())

    if capec:
        existing_cwe = set(cve.get("cwe_ids") or [])
        cve["capec_ids"] = sorted(set(capec))
        _ = existing_cwe

    cve["circl"] = {
        "capec_ids": cve.get("capec_ids", []),
        "extra_reference_count": len(extra_refs),
    }
    return cve


async def load_sploitus_exploits_for_cve(db, cve_id: str) -> list[dict]:
    from database import get_cached_cve_exploits, store_cve_exploits

    cached = await get_cached_cve_exploits(db, cve_id)
    if cached is not None:
        return cached
    exploits = await fetch_sploitus_exploits(cve_id)
    await store_cve_exploits(db, cve_id, exploits)
    return exploits


async def greynoise_for_ip(db, ip: str, api_key: str) -> dict | None:
    from database import get_feed_cache, set_feed_cache

    cache_key = f"greynoise:{ip}"
    cached = await get_feed_cache(db, cache_key, max_age_hours=1)
    if cached is not None:
        return cached

    result = await fetch_greynoise_ip(ip, api_key)
    if result is not None:
        await set_feed_cache(db, cache_key, result)
    return result


async def greynoise_scans_for_cve(
    db, description: str | None, source_urls: list | None, api_key: str
) -> list[dict]:
    if not api_key:
        return []
    from templates.intelligence import greynoise_sentence

    scans: list[dict] = []
    for ip in extract_ipv4_from_cve(description, source_urls):
        gn = await greynoise_for_ip(db, ip, api_key)
        if gn:
            gn = dict(gn)
            gn["sentence"] = greynoise_sentence(gn)
            scans.append(gn)
    return scans
