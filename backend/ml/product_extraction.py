"""LLM product extraction for NVD-unanalyzed CVEs - env-gated (V1.3).

Many fresh CVEs carry no CPE data for hours or days. When
``LLM_PRODUCT_EXTRACTION_ENABLED=1`` AND at least one LLM provider API key is
set, a scheduler job extracts ``{vendor, product, version_range}`` from the
description text and fills ``affected_products`` - ONLY while that field is
empty - marking ``affected_products_source='llm'`` so the data stays
distinguishable. Official CPE data supersedes LLM output on the next NVD upsert
(the upsert SQL clears the marker whenever a non-empty official product list
arrives).

Scheduler-side only, never on the request path. Disabled by default; the
tool is fully functional without it. Completed extractions (including empty
ones) are negative-cached in ``feed_cache`` so quota is never burned twice
on the same CVE within the retry window; errors are not cached and retry on
the next run.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import logging
import os
import re

import aiosqlite

from ai.llm_router import LLMCompletion, any_llm_provider_configured, chat_completion_task
from ai.llm_payload import has_substantive_source_text
from database import (
    get_cves_for_llm_product_extraction,
    set_feed_cache,
    set_llm_affected_products,
)

logger = logging.getLogger(__name__)

# Negative-cache window: a CVE whose extraction completed (even with zero
# products) is not retried for this long. Successful writes leave the
# candidate pool permanently because affected_products is no longer empty.
# Errored attempts are not cached at all and retry on the next run.
RETRY_HOURS = 168.0
MAX_PRODUCTS_PER_CVE = 10

SYSTEM_PROMPT = (
    "You are a vulnerability analyst. Extract the affected software from a "
    "CVE description. Respond with valid JSON only (no markdown fences)."
)

USER_PROMPT_TEMPLATE = """Extract every affected vendor/product pair from this CVE description.

Rules:
- vendor and product must be lowercase CPE-style tokens (spaces become underscores,
  e.g. "Palo Alto Networks PAN-OS" -> vendor "paloaltonetworks", product "pan-os").
- If the vendor is unknown, use the product name as the vendor.
- version_range is a short human-readable string ("< 2.4.1", "1.0 - 1.9", "all"); use "" if unknown.
- Only include software actually described as vulnerable. If none can be determined,
  return an empty list.

Respond with JSON only:
{{"products": [{{"vendor": "...", "product": "...", "version_range": "..."}}]}}

CVE description:
{description}
"""


def llm_product_extraction_enabled() -> bool:
    flag = os.environ.get("LLM_PRODUCT_EXTRACTION_ENABLED", "0").strip().lower()
    return flag in ("1", "true", "yes") and any_llm_provider_configured()


def get_extraction_max_per_run() -> int:
    try:
        return int(os.environ.get("LLM_PRODUCT_EXTRACTION_MAX_PER_RUN", "10"))
    except ValueError:
        return 10


def _normalize_token(value: str) -> str:
    token = re.sub(r"\s+", "_", (value or "").strip().lower())
    return re.sub(r"[^a-z0-9._:\-]", "", token)


def _json_candidates(text: str):
    """Yield progressively more forgiving JSON extraction candidates.

    LLMs occasionally wrap the payload in markdown fences or prepend
    conversational text ("Here is the JSON: ..."). Try the raw text first,
    then the content of a fenced block anywhere in the response, then the
    outermost {...} / [...] span. A non-greedy fence-with-braces regex would
    truncate nested JSON at the first '}', so spans are located by index.
    """
    yield text
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        yield fence.group(1)
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start != -1 and end > start:
            yield text[start : end + 1]


def _extract_items(text: str) -> list:
    """First candidate that parses AND carries a products list wins - a
    candidate that merely parses (e.g. a sub-object grabbed by the brace-span
    fallback) must not stop the search."""
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        items = data.get("products") if isinstance(data, dict) else data
        if isinstance(items, list):
            return items
    return []


def parse_products_payload(content: str) -> list[dict]:
    """Parse the model response into validated {vendor, product, version_range}
    dicts. Returns [] for anything malformed - never raises."""
    text = (content or "").strip()
    if not text:
        return []
    items = _extract_items(text)

    products: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        product = _normalize_token(str(item.get("product") or ""))
        vendor = _normalize_token(str(item.get("vendor") or "")) or product
        if not product:
            continue
        key = f"{vendor}:{product}"
        if key in seen:
            continue
        seen.add(key)
        products.append(
            {
                "vendor": vendor,
                "product": product,
                "version_range": str(item.get("version_range") or "").strip()[:100],
            }
        )
        if len(products) >= MAX_PRODUCTS_PER_CVE:
            break
    return products


def products_to_affected_keys(products: list[dict]) -> list[str]:
    """Convert structured extractions to the existing affected_products
    format ("vendor:product" strings) used by stack matching."""
    return [f"{p['vendor']}:{p['product']}" for p in products if p.get("product")]


async def extract_products_via_llm(description: str) -> tuple[list[dict], LLMCompletion] | None:
    """One router call -> validated product dicts with provider provenance."""
    if not has_substantive_source_text(description):
        logger.info("Skipping LLM product extraction — empty CVE description")
        return None
    completion = await chat_completion_task(
        "product_extraction",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    description=(description or "")[:3000]
                ),
            },
        ],
        max_tokens=500,
        temperature=0.0,
        timeout=60.0,
    )
    if not completion:
        return None
    return parse_products_payload(completion.content), completion


async def run_llm_product_extraction(db: aiosqlite.Connection | None = None, progress_cb=None) -> dict:
    """Scheduler job body: extract products for NVD-unanalyzed CVEs.

    Caller is responsible for the enabled() gate and the job lock. Every
    *completed* extraction (including ones that found no products) is
    recorded in feed_cache (key ``llm_products:<cve_id>``) so the candidate
    query skips it for RETRY_HOURS; successful writes set
    affected_products_source='llm'. Errors are never cached - transient
    failures retry on the next run.

    When ``db`` is omitted, pool connections are held only for short read/write
    scopes - LLM HTTP and throttle sleeps run without a connection.
    """
    from database import get_db

    stats = {"candidates": 0, "extracted": 0, "written": 0, "errors": 0}

    async def _load_candidates(conn):
        return await get_cves_for_llm_product_extraction(
            conn, limit=get_extraction_max_per_run(), retry_hours=RETRY_HOURS
        )

    if db is not None:
        candidates = await _load_candidates(db)
    else:
        conn = await get_db()
        try:
            candidates = await _load_candidates(conn)
        finally:
            await conn.close()

    stats["candidates"] = len(candidates)
    if not candidates:
        return stats

    for index, candidate in enumerate(candidates):
        cve_id = candidate["cve_id"]
        if progress_cb:
            progress_cb(f"Processing CVE {index + 1} of {stats['candidates']}...")

        try:
            description = (candidate.get("description") or "").strip()
            if not has_substantive_source_text(description):
                logger.info(
                    "Skipping LLM product extraction for %s — no description text",
                    cve_id,
                )
                async def _cache_skip(conn, _cve_id=cve_id):
                    await set_feed_cache(
                        conn,
                        f"llm_products:{_cve_id.upper()}",
                        {
                            "products": [],
                            "provider": None,
                            "model": None,
                            "written": False,
                            "skipped": "empty_description",
                        },
                    )
                    await conn.commit()

                if db is not None:
                    await _cache_skip(db)
                else:
                    conn = await get_db()
                    try:
                        await _cache_skip(conn)
                    finally:
                        await conn.close()
                continue

            result = await extract_products_via_llm(description)
        except Exception as exc:
            stats["errors"] += 1
            logger.error("LLM product extraction failed for %s: %s", cve_id, exc)
            continue

        if result is None:
            stats["errors"] += 1
            logger.warning(
                "LLM product extraction: all providers failed for %s (%d/%d)",
                cve_id,
                index + 1,
                len(candidates),
            )
            continue

        products, completion = result
        written = False
        keys = products_to_affected_keys(products)

        async def _persist(
            conn,
            _cve_id=cve_id,
            _keys=keys,
            _products=products,
            _completion=completion,
        ):
            nonlocal written
            if _keys:
                stats["extracted"] += 1
                written = await set_llm_affected_products(conn, _cve_id, _keys)
                if written:
                    stats["written"] += 1
            await set_feed_cache(
                conn,
                f"llm_products:{_cve_id.upper()}",
                {
                    "products": _products,
                    "provider": _completion.provider,
                    "model": _completion.model,
                    "written": written,
                },
            )
            await conn.commit()

        if db is not None:
            await _persist(db)
        else:
            conn = await get_db()
            try:
                await _persist(conn)
            finally:
                await conn.close()

    return stats
