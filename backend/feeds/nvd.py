import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from enrichment.cve import extract_mitre_technique, has_public_poc
from api_queue import (
    apply_rate_limit_headers,
    await_api_slot,
    release_api_slot,
)
from resilient_client import (
    get_pooled_client,
    record_source_failure,
    record_source_success,
)
from tracking import record_api_call

logger = logging.getLogger(__name__)

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
RESULTS_PER_PAGE = 2000
RATE_LIMIT_WAIT = 35


def _extract_english_description(descriptions: list) -> str:
    for d in descriptions:
        if d.get("lang") == "en":
            return d.get("value", "")
    return descriptions[0].get("value", "") if descriptions else ""


def _extract_cvss_v3(metrics: dict) -> tuple[float | None, str]:
    for key in ("cvssMetricV31", "cvssMetricV30"):
        items = metrics.get(key, [])
        if items:
            data = items[0].get("cvssData", {})
            score = data.get("baseScore")
            severity = data.get("baseSeverity", "UNKNOWN").upper()
            return score, severity
    return None, "UNKNOWN"


def _extract_affected_products(configurations: list) -> list:
    products = set()
    for config in configurations:
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                cpe = match.get("criteria", "")
                parts = cpe.split(":")
                if len(parts) >= 5:
                    vendor = parts[3]
                    product = parts[4]
                    if vendor and product and vendor != "*" and product != "*":
                        products.add(f"{vendor}:{product}")
    return list(products)


def _extract_cpe_matches(configurations: list) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for config in configurations:
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                cpe = match.get("criteria", "")
                parts = cpe.split(":")
                if len(parts) < 5:
                    continue
                vendor = parts[3]
                product = parts[4]
                cpe_version = parts[5] if len(parts) > 5 else None
                if not vendor or not product or vendor in ("*", "-") or product in ("*", "-"):
                    continue
                key = (
                    vendor,
                    product,
                    cpe_version,
                    match.get("versionStartIncluding"),
                    match.get("versionStartExcluding"),
                    match.get("versionEndIncluding"),
                    match.get("versionEndExcluding"),
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    {
                        "vendor": vendor,
                        "product": product,
                        "version": cpe_version,
                        "version_start_including": match.get("versionStartIncluding"),
                        "version_start_excluding": match.get("versionStartExcluding"),
                        "version_end_including": match.get("versionEndIncluding"),
                        "version_end_excluding": match.get("versionEndExcluding"),
                    }
                )
    return matches


def _extract_cwe_ids(weaknesses: list) -> list:
    cwes = set()
    for weakness in weaknesses:
        for desc in weakness.get("description", []):
            value = desc.get("value", "")
            if value.startswith("CWE-"):
                cwes.add(value)
    return list(cwes)


def _extract_reference_urls(references: list) -> list:
    urls = []
    for ref in references:
        url = ref.get("url", "")
        if url:
            urls.append(url)
    return urls[:20]


def _has_patch(references: list) -> bool:
    patch_tags = {"Patch", "Vendor Advisory", "Mitigation"}
    for ref in references:
        tags = set(ref.get("tags", []))
        if tags & patch_tags:
            return True
    return False


def _is_nvd_cve_rejected(cve_data: dict) -> bool:
    status = cve_data.get("vulnStatus")
    return isinstance(status, str) and status.strip().upper() == "REJECTED"


def _nvd_rejected_cve_id(item: dict) -> str | None:
    cve_data = item.get("cve", {})
    if not isinstance(cve_data, dict) or not _is_nvd_cve_rejected(cve_data):
        return None
    cve_id = cve_data.get("id")
    if isinstance(cve_id, str) and cve_id.strip():
        return cve_id.strip().upper()
    return None


def _parse_cve_item(item: dict) -> dict | None:
    cve_data = item.get("cve", {})
    if not isinstance(cve_data, dict) or _is_nvd_cve_rejected(cve_data):
        return None
    cve_id = cve_data.get("id", "")
    descriptions = cve_data.get("descriptions", [])
    description = _extract_english_description(descriptions)
    metrics = cve_data.get("metrics", {})
    cvss_score, severity = _extract_cvss_v3(metrics)
    configurations = cve_data.get("configurations", [])
    affected_products = _extract_affected_products(configurations)
    cpe_matches = _extract_cpe_matches(configurations)
    weaknesses = cve_data.get("weaknesses", [])
    cwe_ids = _extract_cwe_ids(weaknesses)
    references = cve_data.get("references", [])
    source_urls = _extract_reference_urls(references)
    patch_available = _has_patch(references)
    published = cve_data.get("published", "")
    modified = cve_data.get("lastModified", "")

    return {
        "cve_id": cve_id,
        "description": description,
        "cvss_score": cvss_score,
        "severity": severity,
        "published": published,
        "modified": modified,
        "affected_products": affected_products,
        "cpe_matches": cpe_matches,
        "mitre_technique": extract_mitre_technique(references),
        "summary": None,
        "is_kev": False,
        "epss_score": None,
        "has_poc": has_public_poc(references),
        "patch_available": patch_available,
        "source_urls": source_urls,
        "cwe_ids": cwe_ids,
    }


def _is_valid_api_key(key: str | None) -> bool:
    if not key:
        return False
    stripped = key.strip()
    if len(stripped) < 32:
        return False
    if "placeholder" in stripped.lower() or stripped.startswith("your_"):
        return False
    return True


def _nvd_request_headers(api_key: str | None, *, key_rejected: bool = False) -> dict[str, str]:
    """NVD API 2.0 requires the key in the request header, not the query string."""
    if _is_valid_api_key(api_key) and not key_rejected:
        return {"apiKey": api_key.strip()}
    return {}


async def _fetch_page(
    client: httpx.AsyncClient,
    params: dict,
    api_key: str | None,
    _key_rejected: bool = False,
) -> dict:
    request_params = dict(params)
    headers = _nvd_request_headers(api_key, key_rejected=_key_rejected)
    use_key = bool(headers)

    while True:
        slot_id = await await_api_slot(
            "nvd",
            operation="cve_ingest",
            context_type="task",
            context_id="nvd_sync",
        )
        try:
            response = await client.get(
                NVD_BASE_URL,
                params=request_params,
                headers=headers,
                timeout=60.0,
            )
            if response.status_code == 429:
                apply_rate_limit_headers("nvd", response.headers)
                logger.warning("NVD rate limited (429) — waiting in queue before retry")
                continue
            if response.status_code == 404 and use_key:
                nvd_msg = response.headers.get("message", "")
                logger.warning(
                    "NVD returned 404 with API key (%s) — key may be invalid or not activated. "
                    "Retrying without key (anonymous rate limits apply).",
                    nvd_msg or "no message header",
                )
                return await _fetch_page(client, params, api_key, _key_rejected=True)
            response.raise_for_status()
            apply_rate_limit_headers("nvd", response.headers)
            record_source_success("nvd")
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                apply_rate_limit_headers("nvd", exc.response.headers)
                logger.warning("NVD rate limited — waiting in queue before retry")
                continue
            logger.error("NVD HTTP error: %s", exc)
            record_source_failure("nvd", f"HTTP {exc.response.status_code}")
            raise
        except httpx.RequestError as exc:
            logger.error("NVD request error: %s", exc)
            record_source_failure("nvd", f"{type(exc).__name__}: {exc}")
            raise
        finally:
            release_api_slot("nvd", slot_id)


def _format_nvd_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _parse_nvd_datetime(value: str) -> datetime | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        logger.warning("Could not parse NVD datetime: %r", value)
        return None


async def _fetch_cves_paginated(
    client: httpx.AsyncClient,
    base_params: dict,
    api_key: str | None,
    *,
    log_label: str,
) -> tuple[list[dict], list[str]]:
    all_cves: list[dict] = []
    rejected_ids: list[str] = []
    pages_fetched = 0

    def _consume_page(vulnerabilities: list) -> None:
        for item in vulnerabilities:
            rejected = _nvd_rejected_cve_id(item)
            if rejected:
                rejected_ids.append(rejected)
                continue
            parsed = _parse_cve_item(item)
            if parsed:
                all_cves.append(parsed)

    first_page = await _fetch_page(client, base_params, api_key)
    pages_fetched += 1
    total_results = first_page.get("totalResults", 0)
    vulnerabilities = first_page.get("vulnerabilities", [])

    _consume_page(vulnerabilities)

    logger.info("NVD %s: fetched %d/%d CVEs (page 1)", log_label, len(all_cves), total_results)

    start_index = RESULTS_PER_PAGE
    while start_index < total_results:
        page_params = dict(base_params)
        page_params["startIndex"] = start_index

        await asyncio.sleep(6)

        page_data = await _fetch_page(client, page_params, api_key)
        pages_fetched += 1
        page_vulns = page_data.get("vulnerabilities", [])

        if not page_vulns:
            break

        _consume_page(page_vulns)

        logger.info(
            "NVD %s: fetched %d/%d CVEs (startIndex=%d)",
            log_label,
            len(all_cves),
            total_results,
            start_index,
        )

        start_index += RESULTS_PER_PAGE

    await record_api_call("nvd", pages_fetched)
    if rejected_ids:
        logger.info(
            "NVD %s: skipped %d Rejected CVE(s)",
            log_label,
            len(rejected_ids),
        )
    logger.info(
        "NVD %s complete: %d CVEs retrieved (%d API requests)",
        log_label,
        len(all_cves),
        pages_fetched,
    )
    return all_cves, rejected_ids


async def fetch_cves_by_last_modified(
    api_key: str | None,
    mod_start: datetime,
    mod_end: datetime,
) -> list[dict]:
    mod_start_str = _format_nvd_datetime(mod_start)
    mod_end_str = _format_nvd_datetime(mod_end)
    base_params = {
        "lastModStartDate": mod_start_str,
        "lastModEndDate": mod_end_str,
        "resultsPerPage": RESULTS_PER_PAGE,
        "startIndex": 0,
    }

    client = get_pooled_client()
    logger.info("Fetching NVD CVEs modified from %s to %s", mod_start_str, mod_end_str)
    return await _fetch_cves_paginated(
        client,
        base_params,
        api_key,
        log_label="incremental",
    )


async def fetch_recent_cves(api_key: str | None = None, days_back: int = 7) -> list[dict]:
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days_back)

    pub_start = _format_nvd_datetime(start_date)
    pub_end = _format_nvd_datetime(now)

    base_params = {
        "pubStartDate": pub_start,
        "pubEndDate": pub_end,
        "resultsPerPage": RESULTS_PER_PAGE,
        "startIndex": 0,
    }

    client = get_pooled_client()
    logger.info("Fetching NVD CVEs published from %s to %s", pub_start, pub_end)
    return await _fetch_cves_paginated(
        client,
        base_params,
        api_key,
        log_label="bootstrap",
    )


async def fetch_nvd_cve_updates(
    api_key: str | None,
    *,
    watermark: str | None,
    days_back: int = 14,
    overlap_minutes: int = 15,
) -> tuple[list[dict], str, bool, list[str]]:
    """
    Fetch CVEs for a refresh cycle.

    Returns (cves, mod_end_iso_for_watermark, used_incremental, rejected_cve_ids).
    """
    now = datetime.now(timezone.utc)
    mod_end_iso = _format_nvd_datetime(now)

    if watermark:
        mod_start = _parse_nvd_datetime(watermark)
        if mod_start is None:
            logger.warning("Invalid NVD watermark %r — using full publish-window sync", watermark)
        else:
            mod_start = mod_start - timedelta(minutes=overlap_minutes)
            if (now - mod_start) > timedelta(days=120):
                mod_start = now - timedelta(days=120)
                logger.warning("NVD watermark older than 120 days — clamping start to %s", mod_start.isoformat())
            cves, rejected = await fetch_cves_by_last_modified(api_key, mod_start, now)
            return cves, mod_end_iso, True, rejected

    logger.info("No NVD watermark — full sync for CVEs published in the last %d days", days_back)
    cves, rejected = await fetch_recent_cves(api_key=api_key, days_back=days_back)
    return cves, mod_end_iso, False, rejected



async def fetch_cve_by_id(cve_id: str, api_key: str | None = None) -> dict | None:
    """Fetch a single CVE by ID from the NVD API."""
    params: dict = {"cveId": cve_id}
    key_rejected = False

    client = get_pooled_client()
    for attempt in range(3):
        headers = _nvd_request_headers(api_key, key_rejected=key_rejected)
        try:
            response = await client.get(
                NVD_BASE_URL,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            if response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_WAIT)
                continue
            if response.status_code == 404 and headers:
                nvd_msg = response.headers.get("message", "")
                logger.warning(
                    "NVD 404 for %s with API key (%s) — retrying anonymously",
                    cve_id,
                    nvd_msg or "no message header",
                )
                key_rejected = True
                continue
            if response.status_code == 404:
                return None
            response.raise_for_status()
            record_source_success("nvd")
            data = response.json()
            vulns = data.get("vulnerabilities", [])
            if not vulns:
                return None
            await record_api_call("nvd", 1)
            return _parse_cve_item(vulns[0])
        except httpx.HTTPStatusError as exc:
            logger.error("NVD HTTP error fetching %s: %s", cve_id, exc)
            record_source_failure("nvd", f"HTTP {exc.response.status_code}")
            return None
        except httpx.RequestError as exc:
            logger.error("NVD request error fetching %s: %s", cve_id, exc)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            record_source_failure("nvd", f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            logger.error("Unexpected error fetching %s: %s", cve_id, exc)
            record_source_failure("nvd", f"{type(exc).__name__}: {exc}")
            return None
    return None
