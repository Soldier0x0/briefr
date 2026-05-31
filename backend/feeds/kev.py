import logging

import httpx

logger = logging.getLogger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


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

    vulnerabilities = data.get("vulnerabilities", [])
    results = []

    for entry in vulnerabilities:
        results.append(
            {
                "cveID": entry.get("cveID", ""),
                "product": entry.get("product", ""),
                "shortDescription": entry.get("shortDescription", ""),
                "requiredAction": entry.get("requiredAction", ""),
                "dueDate": entry.get("dueDate", ""),
            }
        )

    logger.info("KEV fetch complete: %d entries retrieved", len(results))
    return results
