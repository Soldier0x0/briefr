import asyncio
import csv
import gzip
import logging

import httpx

from tracking import record_api_call

logger = logging.getLogger(__name__)

EPSS_API_URL = "https://api.first.org/data/v1/epss"
EPSS_CSV_URL = "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz"
BATCH_SIZE = 100


async def _fetch_batch_api(client: httpx.AsyncClient, cve_ids: list) -> dict[str, float]:
    cve_param = ",".join(cve_ids)
    try:
        response = await client.get(
            EPSS_API_URL,
            params={"cve": cve_param},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "EPSS HTTP error %s for batch of %d CVEs",
            exc.response.status_code,
            len(cve_ids),
        )
        return {}
    except httpx.RequestError as exc:
        logger.error("EPSS request error for batch of %d CVEs: %s", len(cve_ids), exc)
        return {}
    except Exception as exc:
        logger.error("EPSS unexpected error: %s", exc)
        return {}

    scores: dict[str, float] = {}
    for item in data.get("data", []):
        cve_id = item.get("cve", "")
        epss_val = item.get("epss")
        if cve_id and epss_val is not None:
            try:
                scores[cve_id.upper()] = float(epss_val)
            except (ValueError, TypeError):
                pass
    return scores


async def fetch_epss_bulk(cve_ids: set[str]) -> dict[str, float]:
    """Load scores from the daily EPSS CSV for the given CVE IDs."""
    if not cve_ids:
        return {}

    needed = {c.upper() for c in cve_ids}
    scores: dict[str, float] = {}

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(EPSS_CSV_URL, timeout=120.0)
            response.raise_for_status()
            raw = gzip.decompress(response.content)
    except httpx.HTTPError as exc:
        logger.error("EPSS bulk CSV download failed: %s", exc)
        return {}
    except Exception as exc:
        logger.error("EPSS bulk CSV parse failed: %s", exc)
        return {}

    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(
        (line for line in text.splitlines() if line and not line.startswith("#")),
    )

    for row in reader:
        cve_id = (row.get("cve") or "").upper()
        if cve_id not in needed:
            continue
        epss_val = row.get("epss")
        if epss_val is None or epss_val == "":
            continue
        try:
            scores[cve_id] = float(epss_val)
        except (ValueError, TypeError):
            continue

    await record_api_call("epss", 1)
    logger.info(
        "EPSS bulk CSV: matched %d/%d CVEs from feed",
        len(scores),
        len(needed),
    )
    return scores


async def fetch_epss_api(cve_ids: list) -> dict[str, float]:
    """Fallback: per-batch API when bulk CSV is unavailable."""
    if not cve_ids:
        return {}

    logger.info("Fetching EPSS via API for %d CVEs", len(cve_ids))
    all_scores: dict[str, float] = {}
    batches = [cve_ids[i : i + BATCH_SIZE] for i in range(0, len(cve_ids), BATCH_SIZE)]

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for idx, batch in enumerate(batches):
            batch_scores = await _fetch_batch_api(client, batch)
            all_scores.update(batch_scores)
            if idx < len(batches) - 1:
                await asyncio.sleep(1)

    await record_api_call("epss", len(batches))
    logger.info(
        "EPSS API fetch complete: %d scores (%d requests)",
        len(all_scores),
        len(batches),
    )
    return all_scores


async def fetch_epss(cve_ids: list) -> dict[str, float]:
    """Prefer bulk CSV; fall back to API batches for any still missing."""
    if not cve_ids:
        return {}

    unique = list({c.upper() for c in cve_ids})
    scores = await fetch_epss_bulk(set(unique))

    missing = [c for c in unique if c not in scores]
    if missing:
        logger.info("EPSS bulk missed %d CVEs — using API fallback", len(missing))
        api_scores = await fetch_epss_api(missing)
        scores.update(api_scores)

    return scores
