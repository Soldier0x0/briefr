import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

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


def _parse_cve_item(item: dict) -> dict:
    cve_data = item.get("cve", {})
    cve_id = cve_data.get("id", "")
    descriptions = cve_data.get("descriptions", [])
    description = _extract_english_description(descriptions)
    metrics = cve_data.get("metrics", {})
    cvss_score, severity = _extract_cvss_v3(metrics)
    configurations = cve_data.get("configurations", [])
    affected_products = _extract_affected_products(configurations)
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
        "mitre_technique": None,
        "summary": None,
        "is_kev": False,
        "epss_score": 0.0,
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


async def _fetch_page(
    client: httpx.AsyncClient,
    params: dict,
    api_key: str | None,
    _key_rejected: bool = False,
) -> dict:
    request_params = dict(params)
    use_key = _is_valid_api_key(api_key) and not _key_rejected
    if use_key:
        request_params["apiKey"] = api_key

    for attempt in range(5):
        try:
            response = await client.get(NVD_BASE_URL, params=request_params, timeout=60.0)
            if response.status_code == 429:
                wait_time = RATE_LIMIT_WAIT * (attempt + 1)
                logger.warning("NVD rate limited (429). Waiting %d seconds before retry %d.", wait_time, attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            if response.status_code == 404 and use_key:
                logger.warning(
                    "NVD returned 404 with API key — key may not be activated yet. "
                    "Retrying without key (anonymous rate limits apply)."
                )
                return await _fetch_page(client, params, api_key, _key_rejected=True)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                wait_time = RATE_LIMIT_WAIT * (attempt + 1)
                logger.warning("NVD rate limited. Waiting %d seconds.", wait_time)
                await asyncio.sleep(wait_time)
                continue
            logger.error("NVD HTTP error: %s", exc)
            raise
        except httpx.RequestError as exc:
            logger.error("NVD request error: %s", exc)
            if attempt < 4:
                await asyncio.sleep(2 ** attempt)
                continue
            raise

    raise RuntimeError("NVD API failed after maximum retries")


async def fetch_recent_cves(api_key: str | None = None, days_back: int = 7) -> list[dict]:
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days_back)

    pub_start = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    pub_end = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    base_params = {
        "pubStartDate": pub_start,
        "pubEndDate": pub_end,
        "resultsPerPage": RESULTS_PER_PAGE,
        "startIndex": 0,
    }

    all_cves = []

    async with httpx.AsyncClient() as client:
        logger.info("Fetching NVD CVEs from %s to %s", pub_start, pub_end)

        first_page = await _fetch_page(client, base_params, api_key)
        total_results = first_page.get("totalResults", 0)
        vulnerabilities = first_page.get("vulnerabilities", [])

        for item in vulnerabilities:
            all_cves.append(_parse_cve_item(item))

        logger.info("NVD: fetched %d/%d CVEs (page 1)", len(all_cves), total_results)

        start_index = RESULTS_PER_PAGE
        while start_index < total_results:
            page_params = dict(base_params)
            page_params["startIndex"] = start_index

            await asyncio.sleep(6)

            page_data = await _fetch_page(client, page_params, api_key)
            page_vulns = page_data.get("vulnerabilities", [])

            if not page_vulns:
                break

            for item in page_vulns:
                all_cves.append(_parse_cve_item(item))

            logger.info(
                "NVD: fetched %d/%d CVEs (startIndex=%d)",
                len(all_cves),
                total_results,
                start_index,
            )

            start_index += RESULTS_PER_PAGE

    logger.info("NVD fetch complete: %d CVEs retrieved", len(all_cves))
    return all_cves
