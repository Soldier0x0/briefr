import asyncio
import csv
import gzip
import logging
from typing import Any

import httpx

from feeds.file_identity import parse_epss_score_date, sha256_bytes
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

EPSS_API_URL = "https://api.first.org/data/v1/epss"
EPSS_CSV_URL = "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz"
BATCH_SIZE = 100

# Backfill constants — 100 CVEs per request, 2 s between batches ≈ 30 req/min
BACKFILL_BATCH_SIZE = 100
BACKFILL_THROTTLE_SECONDS = 2.0


async def download_epss_csv_gz() -> tuple[bytes, str] | tuple[None, None]:
    """Download EPSS current CSV gzip. Returns (raw_gz, sha256) or (None, None)."""
    try:
        response = await resilient_get(
            "epss_bulk",
            EPSS_CSV_URL,
            timeout=120.0,
            queue_operation="cve_ingest",
            queue_context_type="task",
            queue_context_id="epss_bulk_sync",
        )
        raw = response.content
    except CircuitOpenError:
        logger.warning("EPSS bulk circuit open — skipping CSV download")
        return None, None
    except httpx.HTTPError as exc:
        logger.error("EPSS bulk CSV download failed: %s", exc)
        return None, None
    except Exception as exc:
        logger.error("EPSS bulk CSV download unexpected error: %s", exc)
        return None, None
    await record_api_call("epss", 1)
    return raw, sha256_bytes(raw)


def parse_epss_csv_gz(raw_gz: bytes, needed: set[str] | None = None) -> tuple[dict[str, dict], str | None]:
    """Gunzip + parse EPSS CSV. Returns (scores, score_date)."""
    raw = gzip.decompress(raw_gz)
    text = raw.decode("utf-8", errors="replace")
    score_date = parse_epss_score_date(text)
    scores: dict[str, dict] = {}
    reader = csv.DictReader(
        (line for line in text.splitlines() if line and not line.startswith("#")),
    )
    for row in reader:
        cve_id = (row.get("cve") or "").upper()
        if needed is not None and cve_id not in needed:
            continue
        parsed = _parse_epss_fields(row.get("epss"), row.get("percentile"))
        if parsed is not None:
            scores[cve_id] = parsed
    return scores, score_date


def _parse_epss_fields(epss_val: object, percentile_val: object) -> dict | None:
    if epss_val is None or epss_val == "":
        return None
    try:
        score = float(epss_val)
    except (ValueError, TypeError):
        return None
    percentile = None
    if percentile_val is not None and percentile_val != "":
        try:
            percentile = float(percentile_val)
        except (ValueError, TypeError):
            percentile = None
    return {"score": score, "percentile": percentile}


async def _fetch_batch_api(cve_ids: list) -> dict[str, dict]:
    cve_param = ",".join(cve_ids)
    try:
        response = await resilient_get(
            "epss",
            EPSS_API_URL,
            params={"cve": cve_param},
            timeout=30.0,
            queue_operation="cve_lookup",
            queue_context_type="cve",
            queue_context_id=cve_ids[0].upper(),
        )
        data = response.json()
    except CircuitOpenError:
        logger.warning("EPSS circuit open — skipping batch of %d CVEs", len(cve_ids))
        return {}
    except httpx.HTTPStatusError as exc:
        logger.error(
            "EPSS HTTP error %s for batch of %d CVEs",
            exc.response.status_code,
            len(cve_ids),
        )
        return {}
    except httpx.HTTPError as exc:
        logger.error("EPSS request error for batch of %d CVEs: %s", len(cve_ids), exc)
        return {}
    except Exception as exc:
        logger.error("EPSS unexpected error: %s", exc)
        return {}

    scores: dict[str, dict] = {}
    for item in data.get("data", []):
        cve_id = item.get("cve", "")
        parsed = _parse_epss_fields(item.get("epss"), item.get("percentile"))
        if cve_id and parsed is not None:
            scores[cve_id.upper()] = parsed
    return scores


async def fetch_epss_bulk(cve_ids: set[str]) -> dict[str, dict]:
    """Load scores from the daily EPSS CSV for the given CVE IDs."""
    if not cve_ids:
        return {}

    needed = {c.upper() for c in cve_ids}
    raw_gz, _sha = await download_epss_csv_gz()
    if not raw_gz:
        return {}
    try:
        scores, _score_date = parse_epss_csv_gz(raw_gz, needed)
    except Exception as exc:
        logger.error("EPSS bulk CSV parse failed: %s", exc)
        return {}

    logger.info(
        "EPSS bulk CSV: matched %d/%d CVEs from feed",
        len(scores),
        len(needed),
    )
    return scores


async def fetch_epss_bulk_with_identity(
    cve_ids: list[str] | set[str],
) -> dict[str, Any]:
    """Download EPSS CSV and return scores + file identity metadata (Q5).

    Returns ``{scores, sha256, score_date, skipped, raw_gz}``. Callers that
    already applied this sha256 may short-circuit before calling this (after
    download hash check) via ``download_epss_csv_gz`` + ``identity_matches``.
    """
    unique = {c.upper() for c in cve_ids}
    raw_gz, digest = await download_epss_csv_gz()
    if not raw_gz or not digest:
        return {
            "scores": {},
            "sha256": None,
            "score_date": None,
            "skipped": False,
            "raw_gz": None,
        }
    try:
        scores, score_date = parse_epss_csv_gz(raw_gz, unique)
    except Exception as exc:
        logger.error("EPSS bulk CSV parse failed: %s", exc)
        return {
            "scores": {},
            "sha256": digest,
            "score_date": None,
            "skipped": False,
            "raw_gz": None,
        }
    return {
        "scores": scores,
        "sha256": digest,
        "score_date": score_date,
        "skipped": False,
        "raw_gz": raw_gz,
    }


async def fetch_epss_api(cve_ids: list) -> dict[str, dict]:
    """Fallback: per-batch API when bulk CSV is unavailable."""
    if not cve_ids:
        return {}

    logger.info("Fetching EPSS via API for %d CVEs", len(cve_ids))
    all_scores: dict[str, dict] = {}
    batches = [cve_ids[i : i + BATCH_SIZE] for i in range(0, len(cve_ids), BATCH_SIZE)]

    for idx, batch in enumerate(batches):
        batch_scores = await _fetch_batch_api(batch)
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


async def fetch_epss(cve_ids: list) -> dict[str, dict]:
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


async def fetch_epss_time_series_batch(cve_ids: list[str]) -> list[dict]:
    """Fetch EPSS daily history for up to BACKFILL_BATCH_SIZE CVEs via FIRST API.

    Uses ``scope=time-series`` which returns one entry per (CVE, date) pair for
    all available dates (≤30 days).  Returns a list of
    ``{"cve_id": str, "score": float, "date": str}`` dicts.
    """
    if not cve_ids:
        return []

    cve_param = ",".join(cve_ids)
    try:
        response = await resilient_get(
            "epss",
            EPSS_API_URL,
            params={"cve": cve_param, "scope": "time-series"},
            timeout=30.0,
            queue_operation="cve_lookup",
            queue_context_type="cve",
            queue_context_id=cve_ids[0].upper(),
        )
        data = response.json()
    except CircuitOpenError:
        logger.warning(
            "EPSS circuit open — skipping time-series batch of %d CVEs", len(cve_ids)
        )
        return []
    except httpx.HTTPStatusError as exc:
        logger.error(
            "EPSS time-series HTTP %s for batch of %d CVEs",
            exc.response.status_code,
            len(cve_ids),
        )
        return []
    except httpx.HTTPError as exc:
        logger.error(
            "EPSS time-series request error for batch of %d CVEs: %s", len(cve_ids), exc
        )
        return []
    except Exception as exc:
        logger.error("EPSS time-series unexpected error: %s", exc)
        return []

    if not isinstance(data, dict):
        logger.error("EPSS time-series API returned non-dict JSON; skipping batch of %d CVEs", len(cve_ids))
        return []

    rows: list[dict] = []
    for item in data.get("data", []):
        cve_id = (item.get("cve") or "").upper()
        epss_val = item.get("epss")
        date_str = item.get("date") or ""
        if not cve_id or epss_val is None or not date_str:
            continue
        try:
            score = float(epss_val)
        except (ValueError, TypeError):
            continue
        rows.append({"cve_id": cve_id, "score": score, "date": date_str})

    await record_api_call("epss", 1)
    return rows
