"""LLM product extraction for NVD-unanalyzed CVEs — env-gated (V1.3).

Many fresh CVEs carry no CPE data for hours or days. When
``LLM_PRODUCT_EXTRACTION_ENABLED=1`` AND ``GROQ_API_KEY`` is set, a scheduler
job extracts ``{vendor, product, version_range}`` from the description text
and fills ``affected_products`` — ONLY while that field is empty — marking
``affected_products_source='llm'`` so the data stays distinguishable.
Official CPE data supersedes LLM output on the next NVD upsert (the upsert
SQL clears the marker whenever a non-empty official product list arrives).

Scheduler-side only, never on the request path. Disabled by default; the
tool is fully functional without it. Attempts (including empty extractions)
are negative-cached in ``feed_cache`` so quota is never burned twice on the
same CVE within the retry window.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

import aiosqlite

from database import (
    get_cves_for_llm_product_extraction,
    set_feed_cache,
    set_llm_affected_products,
)
from resilient_client import CircuitOpenError, resilient_request

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Negative-cache window: a CVE attempted (even unsuccessfully) is not retried
# for this long. Successful writes leave the candidate pool permanently
# because affected_products is no longer empty.
RETRY_HOURS = 168.0
THROTTLE_SECONDS = 2.0
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
    return flag in ("1", "true", "yes") and bool(
        os.environ.get("GROQ_API_KEY", "").strip()
    )


def get_extraction_max_per_run() -> int:
    return int(os.environ.get("LLM_PRODUCT_EXTRACTION_MAX_PER_RUN", "25"))


def _normalize_token(value: str) -> str:
    token = re.sub(r"\s+", "_", (value or "").strip().lower())
    return re.sub(r"[^a-z0-9._:\-]", "", token)


def parse_products_payload(content: str) -> list[dict]:
    """Parse the model response into validated {vendor, product, version_range}
    dicts. Returns [] for anything malformed — never raises."""
    text = (content or "").strip()
    if not text:
        return []
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    items = data.get("products") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

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


async def extract_products_via_groq(description: str, api_key: str) -> list[dict]:
    """One Groq call → validated product dicts. retries=0: never burn quota
    on automatic retries (same policy as VT/AbuseIPDB/GreyNoise)."""
    response = await resilient_request(
        "groq",
        "POST",
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        description=(description or "")[:3000]
                    ),
                },
            ],
            "max_tokens": 500,
            "temperature": 0.0,
        },
        timeout=60.0,
        retries=0,
    )
    content = (
        response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    return parse_products_payload(content)


async def run_llm_product_extraction(db: aiosqlite.Connection) -> dict:
    """Scheduler job body: extract products for NVD-unanalyzed CVEs.

    Caller is responsible for the enabled() gate and the job lock. Every
    attempt is recorded in feed_cache (key ``llm_products:<cve_id>``) so the
    candidate query skips it for RETRY_HOURS; successful writes set
    affected_products_source='llm'.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    stats = {"candidates": 0, "extracted": 0, "written": 0, "errors": 0}

    candidates = await get_cves_for_llm_product_extraction(
        db, limit=get_extraction_max_per_run(), retry_hours=RETRY_HOURS
    )
    stats["candidates"] = len(candidates)
    if not candidates:
        return stats

    for index, candidate in enumerate(candidates):
        cve_id = candidate["cve_id"]
        try:
            products = await extract_products_via_groq(
                candidate["description"], api_key
            )
        except CircuitOpenError:
            logger.warning(
                "LLM product extraction: Groq circuit open — aborting run "
                "(%d/%d candidates processed)",
                index,
                len(candidates),
            )
            break
        except Exception as exc:
            stats["errors"] += 1
            logger.error("LLM product extraction failed for %s: %s", cve_id, exc)
            await set_feed_cache(
                db,
                f"llm_products:{cve_id.upper()}",
                {"products": [], "model": GROQ_MODEL, "written": False, "error": str(exc)[:200]},
            )
            await db.commit()
            continue

        written = False
        keys = products_to_affected_keys(products)
        if keys:
            stats["extracted"] += 1
            written = await set_llm_affected_products(db, cve_id, keys)
            if written:
                stats["written"] += 1
        await set_feed_cache(
            db,
            f"llm_products:{cve_id.upper()}",
            {"products": products, "model": GROQ_MODEL, "written": written},
        )
        await db.commit()

        if index + 1 < len(candidates):
            await asyncio.sleep(THROTTLE_SECONDS)

    return stats
