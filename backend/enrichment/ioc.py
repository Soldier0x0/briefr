# PRIVACY NOTE:
# IOC lookup values are sent to VirusTotal, AbuseIPDB, and (for IPs) GreyNoise;
# file hashes may be sent to MalwareBazaar; domains/URLs to URLhaus.
# These are third-party services with their own privacy policies.
# We do NOT log the IOC values or associate them with any user.
# The ioc_cache table stores the IOC value and result for 6 hours
# to reduce API calls. This cache is local to your server only.
# Users are informed of this in the UI and in the Privacy Policy.

import logging
import re
from urllib.parse import urlparse

import httpx

from tracking import record_api_call

logger = logging.getLogger(__name__)

VT_BASE_URL = "https://www.virustotal.com/api/v3"
ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"

_DOMAIN_LABEL_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
)

_ERROR_RESULT_TEMPLATE = {
    "value": "",
    "type": "",
    "malicious_votes": 0,
    "total_votes": 0,
    "tags": [],
    "last_seen": None,
    "country": None,
    "abuse_score": None,
    "vt_link": None,
    "error": None,
}


def normalize_ioc_value(value: str, ioc_type: str) -> str:
    """Normalize user input before cache keys and upstream API calls."""
    v = (value or "").strip()
    if not v:
        return v
    if ioc_type == "domain":
        if "://" in v or v.startswith("//"):
            try:
                parsed = urlparse(v if "://" in v else f"https:{v}")
                host = parsed.hostname
                if host:
                    v = host
            except ValueError:
                pass
        else:
            v = v.split("/")[0].split("?")[0].split("#")[0]
        v = v.rstrip(".").lower()
    elif ioc_type == "hash":
        v = v.lower()
    return v


def _error_result(value: str, ioc_type: str, error_msg: str) -> dict:
    result = dict(_ERROR_RESULT_TEMPLATE)
    result["value"] = value
    result["type"] = ioc_type
    result["error"] = error_msg
    return result


async def _lookup_vt_ip(client: httpx.AsyncClient, ip: str, api_key: str) -> dict:
    try:
        response = await client.get(
            f"{VT_BASE_URL}/ip_addresses/{ip}",
            headers={"x-apikey": api_key},
            timeout=30.0,
        )
        if response.status_code == 404:
            return {}
        if response.status_code in (403, 401):
            logger.warning("VirusTotal auth error for IP %s: %d", ip, response.status_code)
            return {}
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit for IP lookup")
            return {}
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("VT IP lookup HTTP error for %s: %s", ip, exc)
        return {}
    except httpx.RequestError as exc:
        logger.error("VT IP lookup request error for %s: %s", ip, exc)
        return {}


async def _lookup_abuseipdb(client: httpx.AsyncClient, ip: str, api_key: str) -> dict:
    try:
        response = await client.get(
            ABUSEIPDB_URL,
            params={"ipAddress": ip, "maxAgeInDays": 90},
            headers={"Key": api_key, "Accept": "application/json"},
            timeout=30.0,
        )
        if response.status_code in (404, 422):
            return {}
        if response.status_code in (403, 401):
            logger.warning("AbuseIPDB auth error: %d", response.status_code)
            return {}
        if response.status_code == 429:
            logger.warning("AbuseIPDB rate limit hit")
            return {}
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("AbuseIPDB HTTP error for %s: %s", ip, exc)
        return {}
    except httpx.RequestError as exc:
        logger.error("AbuseIPDB request error for %s: %s", ip, exc)
        return {}


async def _lookup_vt_hash(client: httpx.AsyncClient, file_hash: str, api_key: str) -> dict:
    try:
        response = await client.get(
            f"{VT_BASE_URL}/files/{file_hash}",
            headers={"x-apikey": api_key},
            timeout=30.0,
        )
        if response.status_code == 404:
            return {}
        if response.status_code in (403, 401):
            logger.warning("VirusTotal auth error for hash %s: %d", file_hash, response.status_code)
            return {}
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit for hash lookup")
            return {}
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("VT hash lookup HTTP error for %s: %s", file_hash, exc)
        return {}
    except httpx.RequestError as exc:
        logger.error("VT hash lookup request error for %s: %s", file_hash, exc)
        return {}


async def _lookup_vt_domain(client: httpx.AsyncClient, domain: str, api_key: str) -> dict:
    try:
        response = await client.get(
            f"{VT_BASE_URL}/domains/{domain}",
            headers={"x-apikey": api_key},
            timeout=30.0,
        )
        if response.status_code == 404:
            return {}
        if response.status_code in (403, 401):
            logger.warning("VirusTotal auth error for domain %s: %d", domain, response.status_code)
            return {}
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit for domain lookup")
            return {}
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("VT domain lookup HTTP error for %s: %s", domain, exc)
        return {}
    except httpx.RequestError as exc:
        logger.error("VT domain lookup request error for %s: %s", domain, exc)
        return {}


def _parse_vt_stats(vt_data: dict) -> tuple[int, int, list, str | None]:
    attrs = vt_data.get("data", {}).get("attributes", {})
    stats = attrs.get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    total = sum(stats.values()) if stats else 0
    tags = attrs.get("tags", [])
    last_seen = attrs.get("last_analysis_date")
    if last_seen:
        last_seen = str(last_seen)
    return malicious, total, tags, last_seen


def _parse_vt_engines(vt_data: dict) -> list[dict]:
    attrs = vt_data.get("data", {}).get("attributes", {})
    results = attrs.get("last_analysis_results") or {}
    engines: list[dict] = []
    for name, row in results.items():
        if not isinstance(row, dict):
            continue
        category = (row.get("category") or "undetected").lower()
        engines.append(
            {
                "name": name,
                "category": category,
                "result": row.get("result") or "",
            }
        )
    order = {"malicious": 0, "suspicious": 1, "timeout": 2, "undetected": 3, "harmless": 4}
    engines.sort(key=lambda e: (order.get(e["category"], 9), e["name"].lower()))
    return engines


def _parse_vt_network(vt_data: dict) -> dict:
    attrs = vt_data.get("data", {}).get("attributes", {})
    asn = attrs.get("asn")
    as_owner = attrs.get("as_owner") or attrs.get("network") or ""
    return {
        "asn": f"AS{asn}" if asn else None,
        "as_owner": as_owner or None,
        "network": attrs.get("network"),
    }


def _parse_abuseipdb(abuse_data: dict) -> dict:
    abuse_attrs = abuse_data.get("data") or {}
    return {
        "abuse_score": abuse_attrs.get("abuseConfidenceScore"),
        "country_code": abuse_attrs.get("countryCode"),
        "country_name": abuse_attrs.get("countryName"),
        "isp": abuse_attrs.get("isp"),
        "domain": abuse_attrs.get("domain"),
        "usage_type": abuse_attrs.get("usageType"),
        "total_reports": abuse_attrs.get("totalReports"),
        "num_distinct_users": abuse_attrs.get("numDistinctUsers"),
        "is_whitelisted": abuse_attrs.get("isWhitelisted"),
        "is_tor": abuse_attrs.get("isTor"),
        "last_reported_at": abuse_attrs.get("lastReportedAt"),
    }


async def lookup_ioc(
    value: str,
    ioc_type: str,
    vt_key: str,
    abuse_key: str,
    greynoise_key: str = "",
    abusech_key: str = "",
    db=None,
    *,
    include_greynoise: bool = False,
) -> dict:
    if ioc_type not in ("ip", "hash", "domain"):
        return _error_result(value, ioc_type, f"Unknown IOC type: {ioc_type}")

    value = normalize_ioc_value(value, ioc_type)
    if ioc_type == "domain" and value and not _DOMAIN_LABEL_RE.match(value):
        return _error_result(value, ioc_type, "Invalid domain format")

    result = {
        "value": value,
        "type": ioc_type,
        "malicious_votes": 0,
        "total_votes": 0,
        "tags": [],
        "last_seen": None,
        "country": None,
        "abuse_score": None,
        "vt_link": None,
        "error": None,
        "greynoise": None,
        "malwarebazaar": None,
        "urlhaus": None,
        "greynoise_sentence": None,
        "malwarebazaar_sentence": None,
        "urlhaus_sentence": None,
        "vt_engines": [],
        "vt_stats": None,
        "vt_network": None,
        "abuseipdb": None,
        "abuseipdb_link": None,
        "sources_missing": [],
    }

    async with httpx.AsyncClient() as client:
        if ioc_type == "ip":
            vt_data = {}
            abuse_data = {}
            missing: list[str] = []

            if vt_key:
                vt_data = await _lookup_vt_ip(client, value, vt_key)
                await record_api_call("virustotal", 1)
            else:
                missing.append("virustotal")
            if abuse_key:
                abuse_data = await _lookup_abuseipdb(client, value, abuse_key)
                await record_api_call("abuseipdb", 1)
            else:
                missing.append("abuseipdb")

            result["sources_missing"] = missing
            result["abuseipdb_link"] = f"https://www.abuseipdb.com/check/{value}"

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                attrs = vt_data.get("data", {}).get("attributes", {})
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                result["country"] = attrs.get("country")
                result["vt_link"] = f"https://www.virustotal.com/gui/ip-address/{value}"
                result["vt_engines"] = _parse_vt_engines(vt_data)
                result["vt_stats"] = attrs.get("last_analysis_stats") or {}
                result["vt_network"] = _parse_vt_network(vt_data)
            elif vt_key:
                result["vt_link"] = f"https://www.virustotal.com/gui/ip-address/{value}"

            if abuse_data:
                parsed = _parse_abuseipdb(abuse_data)
                result["abuseipdb"] = parsed
                result["abuse_score"] = parsed.get("abuse_score")
                if not result["country"]:
                    result["country"] = parsed.get("country_code")

            if include_greynoise and greynoise_key and db is not None:
                from feeds.extended import greynoise_for_ip
                from templates.intelligence import greynoise_sentence

                gn = await greynoise_for_ip(db, value, greynoise_key)
                result["greynoise"] = gn
                result["greynoise_sentence"] = greynoise_sentence(gn)

        elif ioc_type == "hash":
            vt_data = {}
            if vt_key:
                vt_data = await _lookup_vt_hash(client, value, vt_key)
                await record_api_call("virustotal", 1)

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                result["vt_link"] = f"https://www.virustotal.com/gui/file/{value}"
            else:
                result["error"] = "Hash not found in VirusTotal"

            from feeds.extended import fetch_malwarebazaar_hash
            from templates.intelligence import malwarebazaar_sentence

            mb = await fetch_malwarebazaar_hash(value, abusech_key or None)
            result["malwarebazaar"] = mb
            result["malwarebazaar_sentence"] = malwarebazaar_sentence(mb)

        elif ioc_type == "domain":
            vt_data = {}
            if vt_key:
                vt_data = await _lookup_vt_domain(client, value, vt_key)
                await record_api_call("virustotal", 1)

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                attrs = vt_data.get("data", {}).get("attributes", {})
                result["country"] = attrs.get("country")
                result["vt_link"] = f"https://www.virustotal.com/gui/domain/{value}"
                result["vt_engines"] = _parse_vt_engines(vt_data)
                result["vt_stats"] = attrs.get("last_analysis_stats") or {}
            elif vt_key:
                result["vt_link"] = f"https://www.virustotal.com/gui/domain/{value}"

            uh = None
            try:
                from feeds.extended import fetch_urlhaus_indicator
                from templates.intelligence import urlhaus_sentence

                uh = await fetch_urlhaus_indicator(value, "domain", abusech_key or None)
                result["urlhaus"] = uh
                result["urlhaus_sentence"] = urlhaus_sentence(uh)
            except Exception as exc:
                logger.error("URLhaus enrichment failed for domain %s: %s", value, exc)
                result["urlhaus_sentence"] = (
                    "URLhaus lookup failed — other sources may still be available."
                )

            if not vt_data and not (uh and uh.get("threat_type")):
                if not vt_key:
                    result["error"] = "VirusTotal API key not configured"
                else:
                    result["error"] = "Domain not found in VirusTotal or URLhaus"

    return result
