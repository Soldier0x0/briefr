import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

EPSS_URL = "https://api.first.org/data/v1/epss"
BATCH_SIZE = 100


async def _fetch_batch(client: httpx.AsyncClient, cve_ids: list) -> dict:
    cve_param = ",".join(cve_ids)
    try:
        response = await client.get(
            EPSS_URL,
            params={"cve": cve_param},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("EPSS HTTP error %s for batch of %d CVEs", exc.response.status_code, len(cve_ids))
        return {}
    except httpx.RequestError as exc:
        logger.error("EPSS request error for batch of %d CVEs: %s", len(cve_ids), exc)
        return {}
    except Exception as exc:
        logger.error("EPSS unexpected error: %s", exc)
        return {}

    scores = {}
    for item in data.get("data", []):
        cve_id = item.get("cve", "")
        epss_val = item.get("epss")
        if cve_id and epss_val is not None:
            try:
                scores[cve_id] = float(epss_val)
            except (ValueError, TypeError):
                pass
    return scores


async def fetch_epss(cve_ids: list) -> dict:
    if not cve_ids:
        return {}

    logger.info("Fetching EPSS scores for %d CVEs", len(cve_ids))
    all_scores = {}

    batches = [cve_ids[i : i + BATCH_SIZE] for i in range(0, len(cve_ids), BATCH_SIZE)]

    async with httpx.AsyncClient() as client:
        for idx, batch in enumerate(batches):
            batch_scores = await _fetch_batch(client, batch)
            all_scores.update(batch_scores)

            if idx < len(batches) - 1:
                await asyncio.sleep(1)

    logger.info("EPSS fetch complete: scores for %d CVEs retrieved", len(all_scores))
    return all_scores
