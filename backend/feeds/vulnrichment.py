"""CISA Vulnrichment — SSVC / CVSS / CWE / CPE for NVD-unanalyzed CVEs.

Snapshot-style sync (no watermark): each run lists the repo tree and enriches
CVE rows that still lack official NVD analysis fields. CISA ADP data is
superseded when NVD later fills cvss_score / severity / cwe_ids.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

from feeds.cve_record_v5 import (
    cve_id_from_repo_path,
    merge_additive_cve_fields,
    parse_vulnrichment_record,
    vulnrichment_repo_path,
)
from feeds.github_helpers import GITHUB_API, github_headers, raw_repo_url
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

REPO_OWNER = "cisagov"
REPO_NAME = "vulnrichment"
DEFAULT_BRANCH = "develop"
DEFAULT_INTERVAL_HOURS = 6
FETCH_CONCURRENCY = 8
FETCH_DELAY_SECONDS = 0.15


def get_vulnrichment_sync_interval_hours() -> int:
    return int(os.environ.get("VULNRICHMENT_SYNC_INTERVAL_HOURS", str(DEFAULT_INTERVAL_HOURS)))


def get_vulnrichment_branch() -> str:
    return os.environ.get("VULNRICHMENT_BRANCH", DEFAULT_BRANCH).strip() or DEFAULT_BRANCH


async def _vulnrichment_get(
    url: str,
    *,
    operation: str = "cve_ingest",
    context_type: str | None = "task",
    context_id: str | None = "vulnrichment_sync",
    timeout: float = 60.0,
    params: dict | None = None,
) -> httpx.Response:
    return await resilient_get(
        "vulnrichment",
        url,
        headers=github_headers(),
        timeout=timeout,
        params=params,
        queue_operation=operation,
        queue_context_type=context_type,
        queue_context_id=context_id,
    )


async def _fetch_repo_tree(branch: str) -> list[str]:
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{branch}"
    try:
        response = await _vulnrichment_get(
            url,
            params={"recursive": "1"},
            timeout=120.0,
        )
        data = response.json()
    except CircuitOpenError:
        logger.warning("Vulnrichment circuit open — skipping tree fetch")
        return []
    except httpx.HTTPError as exc:
        logger.error("Vulnrichment tree fetch failed: %s", exc)
        return []

    await record_api_call("vulnrichment", 1)
    if data.get("truncated"):
        logger.warning("Vulnrichment git tree truncated — some paths may be skipped")

    paths: list[str] = []
    for item in data.get("tree") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or ""
        if path.endswith(".json") and cve_id_from_repo_path(path):
            paths.append(path)
    return paths


async def _fetch_record(path: str, branch: str) -> dict | None:
    url = raw_repo_url(REPO_OWNER, REPO_NAME, branch, path)
    cve_id = cve_id_from_repo_path(path)
    try:
        response = await _vulnrichment_get(
            url,
            operation="cve_lookup",
            context_type="cve" if cve_id else "task",
            context_id=cve_id or path[:48],
            timeout=45.0,
        )
        record = response.json()
    except CircuitOpenError:
        return None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            logger.debug("Vulnrichment HTTP %s for %s", exc.response.status_code, path)
        return None
    except httpx.HTTPError:
        return None
    except (json.JSONDecodeError, ValueError):
        return None

    await record_api_call("vulnrichment", 1)
    if not isinstance(record, dict):
        return None
    return parse_vulnrichment_record(record)


async def fetch_vulnrichment_enrichments(
    target_cve_ids: set[str] | None = None,
) -> list[dict]:
    """Return parsed enrichment dicts from the current vulnrichment snapshot."""
    branch = get_vulnrichment_branch()
    tree_paths = await _fetch_repo_tree(branch)
    if not tree_paths:
        return []

    if target_cve_ids:
        wanted = {c.upper() for c in target_cve_ids}
        tree_paths = [
            path
            for path in tree_paths
            if (cve_id_from_repo_path(path) or "") in wanted
        ]

    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    results: list[dict] = []

    async def _one(path: str) -> None:
        async with semaphore:
            parsed = await _fetch_record(path, branch)
            if parsed:
                results.append(parsed)
            await asyncio.sleep(FETCH_DELAY_SECONDS)

    await asyncio.gather(*(_one(path) for path in tree_paths))
    logger.info(
        "Vulnrichment snapshot parsed %d/%d JSON files (branch=%s)",
        len(results),
        len(tree_paths),
        branch,
    )
    return results


async def fetch_vulnrichment_for_cve(cve_id: str) -> dict | None:
    """Fetch a single CVE enrichment by constructed repo path (tests / targeted use)."""
    path = vulnrichment_repo_path(cve_id)
    if not path:
        return None
    return await _fetch_record(path, get_vulnrichment_branch())


def preview_merge(existing: dict, incoming: dict) -> dict | None:
    """Test helper exposing additive merge rules."""
    return merge_additive_cve_fields(existing, incoming)
