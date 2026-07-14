# PRIVACY NOTE:
# IOC lookup values are sent to VirusTotal, AbuseIPDB, and (for IPs) GreyNoise;
# file hashes may be sent to MalwareBazaar; domains/URLs to URLhaus.
# These are third-party services with their own privacy policies.
# We do NOT log the IOC values or associate them with any user.
# The ioc_cache table stores the IOC value and result for 6 hours
# to reduce API calls. This cache is local to your server only.
# Users are informed of this in the UI and in the Privacy Policy.

import json
import logging
from urllib.parse import urlparse

import httpx

from enrichment.domain_validation import is_valid_domain
from resilient_client import CircuitOpenError, resilient_get
from tracking import has_quota, record_api_call

logger = logging.getLogger(__name__)

VT_BASE_URL = "https://www.virustotal.com/api/v3"
ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"

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
            bare = v.split("/")[0].split("?")[0].split("#")[0]
            try:
                parsed = urlparse(f"http://{bare}")
                v = parsed.hostname or bare.split(":")[0] if ":" in bare else bare
            except ValueError:
                v = bare.split(":")[0] if ":" in bare else bare
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


async def _quota_safe_get(
    source: str,
    url: str,
    *,
    headers: dict,
    params: dict | None = None,
    label: str = "",
    not_found_status: tuple[int, ...] = (404,),
    queue_operation: str = "observable_lookup",
    queue_context_type: str | None = "observable",
    queue_context_id: str | None = None,
) -> dict:
    """GET through the resilient client with retries=0 — IOC enrichment APIs
    are quota-billed (VT 500/day, AbuseIPDB 1000/day), so a failed call must
    never be retried automatically. Circuit breaker still applies."""
    try:
        response = await resilient_get(
            source,
            url,
            headers=headers,
            params=params,
            timeout=30.0,
            retries=0,
            queue_operation=queue_operation,
            queue_context_type=queue_context_type,
            queue_context_id=queue_context_id or label,
        )
        data = response.json()
        return data if isinstance(data, dict) else {}
    except CircuitOpenError:
        logger.warning("%s circuit open — skipping lookup %s", source, label)
        return {}
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in not_found_status:
            return {}
        if status in (401, 403):
            logger.warning("%s auth error for %s: %d", source, label, status)
        elif status == 429:
            logger.warning("%s rate limit hit (%s)", source, label)
        else:
            logger.error("%s HTTP %d for %s", source, status, label)
        return {}
    except httpx.HTTPError as exc:
        logger.error("%s request error for %s: %s", source, label, exc)
        return {}
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("%s parse error for %s: %s", source, label, exc)
        return {}


async def _lookup_vt_ip(ip: str, api_key: str) -> dict:
    return await _quota_safe_get(
        "virustotal",
        f"{VT_BASE_URL}/ip_addresses/{ip}",
        headers={"x-apikey": api_key},
        label=f"ip {ip}",
        queue_operation="observable_lookup",
        queue_context_type="ip",
        queue_context_id=ip,
    )


async def _lookup_abuseipdb(ip: str, api_key: str) -> dict:
    return await _quota_safe_get(
        "abuseipdb",
        ABUSEIPDB_URL,
        params={"ipAddress": ip, "maxAgeInDays": 90},
        headers={"Key": api_key, "Accept": "application/json"},
        label=f"ip {ip}",
        not_found_status=(404, 422),
        queue_operation="ip_lookup",
        queue_context_type="ip",
        queue_context_id=ip,
    )


async def _lookup_vt_hash(file_hash: str, api_key: str) -> dict:
    return await _quota_safe_get(
        "virustotal",
        f"{VT_BASE_URL}/files/{file_hash}",
        headers={"x-apikey": api_key},
        label=f"hash {file_hash}",
        queue_operation="observable_lookup",
        queue_context_type="hash",
        queue_context_id=file_hash,
    )


async def _lookup_vt_domain(domain: str, api_key: str) -> dict:
    return await _quota_safe_get(
        "virustotal",
        f"{VT_BASE_URL}/domains/{domain}",
        headers={"x-apikey": api_key},
        label=f"domain {domain}",
        queue_operation="observable_lookup",
        queue_context_type="domain",
        queue_context_id=domain,
    )


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
    otx_key: str = "",
) -> dict:
    if ioc_type not in ("ip", "hash", "domain"):
        return _error_result(value, ioc_type, f"Unknown IOC type: {ioc_type}")

    value = normalize_ioc_value(value, ioc_type)
    if ioc_type == "domain" and value and not is_valid_domain(value):
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
        "otx": None,
        "otx_sentence": None,
        "vt_engines": [],
        "vt_stats": None,
        "vt_network": None,
        "abuseipdb": None,
        "abuseipdb_link": None,
        "sources_missing": [],
    }

    if ioc_type == "ip":
        vt_data = {}
        abuse_data = {}
        missing: list[str] = []

        if vt_key and await has_quota("virustotal"):
            vt_data = await _lookup_vt_ip(value, vt_key)
            await record_api_call("virustotal", 1)
        else:
            missing.append("virustotal")
        if abuse_key and await has_quota("abuseipdb"):
            abuse_data = await _lookup_abuseipdb(value, abuse_key)
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

        if include_greynoise and greynoise_key and db is not None and await has_quota("greynoise"):
            from feeds.extended import greynoise_for_ip
            from templates.intelligence import greynoise_sentence

            gn = await greynoise_for_ip(db, value, greynoise_key)
            result["greynoise"] = gn
            result["greynoise_sentence"] = greynoise_sentence(gn)

    elif ioc_type == "hash":
        vt_data = {}
        if vt_key and await has_quota("virustotal"):
            vt_data = await _lookup_vt_hash(value, vt_key)
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

        from feeds.extended import lookup_malwarebazaar
        from templates.intelligence import malwarebazaar_sentence

        if db is not None:
            mb = await lookup_malwarebazaar(db, value, abusech_key or None)
        else:
            from feeds.extended import fetch_malwarebazaar_hash

            mb = await fetch_malwarebazaar_hash(value, abusech_key or None)
        result["malwarebazaar"] = mb
        result["malwarebazaar_sentence"] = malwarebazaar_sentence(mb)

    elif ioc_type == "domain":
        vt_data = {}
        if vt_key and await has_quota("virustotal"):
            vt_data = await _lookup_vt_domain(value, vt_key)
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
            from feeds.extended import lookup_urlhaus
            from templates.intelligence import urlhaus_sentence

            if db is not None:
                uh = await lookup_urlhaus(db, value, "domain", abusech_key or None)
            else:
                from feeds.extended import fetch_urlhaus_indicator

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

    if otx_key and db is not None:
        from feeds.otx import lookup_otx_for_ioc
        from templates.intelligence import otx_sentence

        otx = await lookup_otx_for_ioc(db, value, ioc_type, otx_key)
        result["otx"] = otx
        result["otx_sentence"] = otx_sentence(otx)

    return result
