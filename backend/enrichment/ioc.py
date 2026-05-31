import logging

import httpx

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


async def lookup_ioc(
    value: str,
    ioc_type: str,
    vt_key: str,
    abuse_key: str,
) -> dict:
    if ioc_type not in ("ip", "hash", "domain"):
        return _error_result(value, ioc_type, f"Unknown IOC type: {ioc_type}")

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
    }

    async with httpx.AsyncClient() as client:
        if ioc_type == "ip":
            vt_data = {}
            abuse_data = {}

            if vt_key:
                vt_data = await _lookup_vt_ip(client, value, vt_key)
            if abuse_key:
                abuse_data = await _lookup_abuseipdb(client, value, abuse_key)

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                attrs = vt_data.get("data", {}).get("attributes", {})
                result["country"] = attrs.get("country")
                result["vt_link"] = f"https://www.virustotal.com/gui/ip-address/{value}"

            if abuse_data:
                abuse_attrs = abuse_data.get("data", {})
                result["abuse_score"] = abuse_attrs.get("abuseConfidenceScore")
                if not result["country"]:
                    result["country"] = abuse_attrs.get("countryCode")

        elif ioc_type == "hash":
            vt_data = {}
            if vt_key:
                vt_data = await _lookup_vt_hash(client, value, vt_key)

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                result["vt_link"] = f"https://www.virustotal.com/gui/file/{value}"
            else:
                result["error"] = "Hash not found in VirusTotal"

        elif ioc_type == "domain":
            vt_data = {}
            if vt_key:
                vt_data = await _lookup_vt_domain(client, value, vt_key)

            if vt_data:
                malicious, total, tags, last_seen = _parse_vt_stats(vt_data)
                result["malicious_votes"] = malicious
                result["total_votes"] = total
                result["tags"] = tags
                result["last_seen"] = last_seen
                attrs = vt_data.get("data", {}).get("attributes", {})
                result["country"] = attrs.get("country")
                result["vt_link"] = f"https://www.virustotal.com/gui/domain/{value}"
            else:
                result["error"] = "Domain not found in VirusTotal"

    return result
