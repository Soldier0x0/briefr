import logging

import httpx

from feeds.errors import FeedFetchError
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def parse_kev_catalog(data: dict) -> list[dict]:
    """Normalize CISA KEV catalog entries, keeping triage-relevant fields."""
    if not isinstance(data, dict):
        return []
    vulnerabilities = data.get("vulnerabilities", [])
    if not isinstance(vulnerabilities, list):
        return []
    results = []
    for entry in vulnerabilities:
        if not isinstance(entry, dict):
            continue
        cwes = entry.get("cwes") or []
        if not isinstance(cwes, list):
            cwes = []
        results.append(
            {
                "cveID": entry.get("cveID", ""),
                "vendorProject": entry.get("vendorProject", ""),
                "product": entry.get("product", ""),
                "vulnerabilityName": entry.get("vulnerabilityName", ""),
                "shortDescription": entry.get("shortDescription", ""),
                "requiredAction": entry.get("requiredAction", ""),
                "dueDate": entry.get("dueDate", ""),
                "dateAdded": entry.get("dateAdded", ""),
                "knownRansomwareCampaignUse": entry.get(
                    "knownRansomwareCampaignUse", ""
                ),
                "cwes": [str(c).strip() for c in cwes if str(c).strip()],
            }
        )
    return results


async def fetch_kev() -> list[dict]:
    try:
        logger.info("Fetching CISA KEV catalog from %s", KEV_URL)
        response = await resilient_get(
            "kev",
            KEV_URL,
            timeout=60.0,
            queue_operation="cve_ingest",
            queue_context_type="task",
            queue_context_id="kev_sync",
        )
        data = response.json()
    except CircuitOpenError as exc:
        logger.warning("KEV circuit open — skipping catalog fetch")
        raise FeedFetchError("KEV circuit open") from exc
    except httpx.HTTPStatusError as exc:
        logger.error("KEV HTTP error %s: %s", exc.response.status_code, exc)
        raise FeedFetchError(f"KEV HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.error("KEV request error: %s", exc)
        raise FeedFetchError("KEV request failed") from exc
    except Exception as exc:
        logger.error("KEV unexpected error: %s", exc)
        raise FeedFetchError("KEV fetch failed") from exc

    results = parse_kev_catalog(data)
    if not results:
        raise FeedFetchError("KEV catalog parsed empty")
    await record_api_call("kev", 1)
    logger.info("KEV fetch complete: %d entries retrieved", len(results))
    return results
