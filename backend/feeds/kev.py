import logging

import httpx

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
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Fetching CISA KEV catalog from %s", KEV_URL)
            response = await client.get(KEV_URL, timeout=60.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("KEV HTTP error %s: %s", exc.response.status_code, exc)
            return []
        except httpx.RequestError as exc:
            logger.error("KEV request error: %s", exc)
            return []
        except Exception as exc:
            logger.error("KEV unexpected error: %s", exc)
            return []

    results = parse_kev_catalog(data)
    await record_api_call("kev", 1)
    logger.info("KEV fetch complete: %d entries retrieved", len(results))
    return results
