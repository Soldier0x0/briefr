"""NVD CPE 2.3 dictionary sync → software_catalog (Q3).

Runs on the scheduler (never the request path). Uses resilient_get("nvd")
so pacing + Q2 metering apply. Full corpus is checkpointed across runs.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from db.software_catalog import (
    categorize_cpe,
    display_name_for,
    parse_cpe23,
    upsert_catalog_rows,
)
from db.sync_state import get_sync_state_value, set_sync_state_value
from feeds.errors import FeedFetchError
from resilient_client import CircuitOpenError, resilient_get

logger = logging.getLogger(__name__)

CPE_API = "https://services.nvd.nist.gov/rest/json/cpes/2.0"
SYNC_START_KEY = "cpe_catalog_start_index"
SYNC_TOTAL_KEY = "cpe_catalog_total_results"
SYNC_LAST_MOD_KEY = "cpe_catalog_last_mod"
SYNC_MODE_KEY = "cpe_catalog_mode"  # full | incremental
SYNC_WINDOW_START_KEY = "cpe_catalog_window_start"
SYNC_WINDOW_END_KEY = "cpe_catalog_window_end"


def cpe_catalog_sync_enabled() -> bool:
    raw = os.environ.get("CPE_CATALOG_SYNC_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _max_pages() -> int:
    try:
        return max(1, min(int(os.environ.get("CPE_CATALOG_MAX_PAGES", "10")), 100))
    except ValueError:
        return 10


def _page_size() -> int:
    try:
        return max(100, min(int(os.environ.get("CPE_CATALOG_PAGE_SIZE", "2000")), 10000))
    except ValueError:
        return 2000


def _nvd_headers() -> dict[str, str]:
    key = (os.environ.get("NVD_API_KEY") or "").strip()
    if key:
        return {"apiKey": key}
    return {}


def _title_from_product(product_obj: dict) -> str | None:
    titles = product_obj.get("titles") or []
    if not isinstance(titles, list):
        return None
    en = None
    for t in titles:
        if not isinstance(t, dict):
            continue
        title = (t.get("title") or "").strip()
        lang = (t.get("lang") or "").lower()
        if not title:
            continue
        if lang.startswith("en"):
            return title
        if en is None:
            en = title
    return en


def normalize_cpe_product(entry: dict) -> dict[str, Any] | None:
    """Map one NVD CPE API product entry → software_catalog row."""
    if not isinstance(entry, dict):
        return None
    cpe = entry.get("cpe") if isinstance(entry.get("cpe"), dict) else entry
    cpe_uri = (cpe.get("cpeName") or cpe.get("cpe23Uri") or "").strip()
    if not cpe_uri:
        return None
    parsed = parse_cpe23(cpe_uri)
    vendor = parsed["vendor"]
    product = parsed["product"]
    version = parsed["version"]
    if vendor in ("", "*", "-") or product in ("", "*", "-"):
        return None
    title = _title_from_product(cpe)
    category = categorize_cpe(part=parsed["part"], vendor=vendor, product=product)
    return {
        "cpe_uri": cpe_uri,
        "vendor": vendor,
        "product": product,
        "version": None if version in ("*", "-") else version,
        "display_name": display_name_for(vendor, product, title),
        "category": category,
        "title": title,
        "versions_json": [version] if version not in ("*", "-", None, "") else [],
    }


async def fetch_cpe_page(
    *,
    start_index: int,
    results_per_page: int,
    last_mod_start: str | None = None,
    last_mod_end: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "startIndex": start_index,
        "resultsPerPage": results_per_page,
    }
    if last_mod_start and last_mod_end:
        params["lastModStartDate"] = last_mod_start
        params["lastModEndDate"] = last_mod_end
    url = f"{CPE_API}?{urlencode(params)}"
    try:
        response = await resilient_get(
            "nvd",
            url,
            headers=_nvd_headers(),
            timeout=60.0,
            queue_operation="cpe_catalog",
            queue_context_type="task",
            queue_context_id="cpe_catalog_sync",
        )
        return response.json()
    except CircuitOpenError as exc:
        raise FeedFetchError("NVD circuit open") from exc
    except httpx.HTTPStatusError as exc:
        raise FeedFetchError(f"NVD CPE HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise FeedFetchError("NVD CPE request failed") from exc


async def sync_cpe_catalog(db, *, progress_cb=None) -> dict[str, Any]:
    """Checkpointed sync. Returns stats dict.

    Incremental windows are sticky in sync_state until fully drained so a
    max_pages stop does not advance the watermark and skip remaining pages.
    """
    page_size = _page_size()
    max_pages = _max_pages()
    mode = (await get_sync_state_value(db, SYNC_MODE_KEY)) or "full"
    start_raw = await get_sync_state_value(db, SYNC_START_KEY)
    start_index = int(start_raw or "0")
    upserted = 0
    pages = 0
    total_results = 0

    last_mod_start = None
    last_mod_end = None
    if mode == "incremental":
        window_start = await get_sync_state_value(db, SYNC_WINDOW_START_KEY)
        window_end = await get_sync_state_value(db, SYNC_WINDOW_END_KEY)
        if window_start and window_end:
            last_mod_start = window_start
            last_mod_end = window_end
            # Resume mid-window from SYNC_START_KEY (already loaded).
        else:
            last = await get_sync_state_value(db, SYNC_LAST_MOD_KEY)
            now = datetime.now(timezone.utc)
            if last:
                last_mod_start = last
            else:
                last_mod_start = (now - timedelta(days=7)).strftime(
                    "%Y-%m-%dT%H:%M:%S.000"
                )
            last_mod_end = now.strftime("%Y-%m-%dT%H:%M:%S.000")
            start_index = 0
            await set_sync_state_value(db, SYNC_WINDOW_START_KEY, last_mod_start)
            await set_sync_state_value(db, SYNC_WINDOW_END_KEY, last_mod_end)
            await set_sync_state_value(db, SYNC_START_KEY, "0")
            await db.commit()

    while pages < max_pages:
        if progress_cb:
            progress_cb(f"Fetching CPE dictionary page startIndex={start_index}…")
        data = await fetch_cpe_page(
            start_index=start_index,
            results_per_page=page_size,
            last_mod_start=last_mod_start,
            last_mod_end=last_mod_end,
        )
        products = data.get("products") or []
        total_results = int(data.get("totalResults") or 0)
        rows = []
        for item in products:
            # API wraps as {"cpe": {...}}
            entry = item.get("cpe") if isinstance(item, dict) and "cpe" in item else item
            row = normalize_cpe_product(entry if isinstance(entry, dict) else {})
            if row:
                rows.append(row)
        n = await upsert_catalog_rows(db, rows)
        upserted += n
        pages += 1
        start_index += int(data.get("resultsPerPage") or page_size)
        await set_sync_state_value(db, SYNC_START_KEY, str(start_index))
        await set_sync_state_value(db, SYNC_TOTAL_KEY, str(total_results))
        await db.commit()

        if start_index >= total_results or not products:
            break

    complete = (
        start_index >= total_results if total_results else (pages > 0 and not products)
    )
    if complete:
        watermark = last_mod_end or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000"
        )
        if mode == "full":
            await set_sync_state_value(db, SYNC_MODE_KEY, "incremental")
        await set_sync_state_value(db, SYNC_START_KEY, "0")
        await set_sync_state_value(db, SYNC_LAST_MOD_KEY, watermark)
        await set_sync_state_value(db, SYNC_WINDOW_START_KEY, "")
        await set_sync_state_value(db, SYNC_WINDOW_END_KEY, "")
        await db.commit()

    stats = {
        "mode": mode,
        "pages": pages,
        "upserted": upserted,
        "start_index": start_index,
        "total_results": total_results,
        "complete": bool(complete),
    }
    logger.info("CPE catalog sync: %s", stats)
    return stats
