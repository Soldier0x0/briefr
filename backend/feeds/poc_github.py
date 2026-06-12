"""PoC-in-GitHub index sync (nomi-sec/PoC-in-GitHub).

Repo pull with commit watermark; merges exploit rows and sets has_poc additively.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from database import get_sync_state_value, merge_cve_exploits, set_sync_state_value
from feeds.exploit_common import SOURCE_POC_GITHUB, cve_year, exploit_card
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

POC_GITHUB_COMMIT_KEY = "poc_github_commit"
POC_GITHUB_REPO = "nomi-sec/PoC-in-GitHub"
POC_GITHUB_API = f"https://api.github.com/repos/{POC_GITHUB_REPO}"
POC_GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/nomi-sec/PoC-in-GitHub/master"
)

THROTTLE_SECONDS = float(os.environ.get("POC_GITHUB_THROTTLE_SECONDS", "0.5"))


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_poc_github_json(cve_id: str, payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        return []
    cards: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        url = (item.get("html_url") or "").strip()
        if not url:
            continue
        title = (item.get("full_name") or item.get("name") or f"{cve_id} PoC").strip()
        published = (
            item.get("pushed_at")
            or item.get("updated_at")
            or item.get("created_at")
            or ""
        )
        cards.append(
            exploit_card(
                title=title,
                exploit_type="poc",
                source=SOURCE_POC_GITHUB,
                url=url,
                published_date=str(published),
            )
        )
    return cards


def _cve_from_repo_path(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if not name.lower().endswith(".json"):
        return None
    cve_id = name[:-5].upper()
    if cve_id.startswith("CVE-"):
        return cve_id
    return None


async def _fetch_json(url: str, *, timeout: float = 30.0) -> Any | None:
    try:
        response = await resilient_get(
            "poc_github",
            url,
            headers=_github_headers(),
            timeout=timeout,
        )
        await record_api_call("poc_github", 1)
        return response.json()
    except CircuitOpenError:
        logger.warning("PoC-in-GitHub circuit open — skipping %s", url)
        return None
    except httpx.HTTPStatusError as exc:
        await record_api_call("poc_github", 1)
        if exc.response.status_code != 404:
            logger.warning("PoC-in-GitHub HTTP %s for %s", exc.response.status_code, url)
        return None
    except httpx.HTTPError as exc:
        logger.error("PoC-in-GitHub request failed for %s: %s", url, exc)
        return None
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("PoC-in-GitHub parse failed for %s: %s", url, exc)
        return None


async def _latest_commit_sha() -> str | None:
    data = await _fetch_json(f"{POC_GITHUB_API}/commits/master")
    if isinstance(data, dict) and data.get("sha"):
        return str(data["sha"])
    if isinstance(data, list) and data:
        sha = data[0].get("sha")
        return str(sha) if sha else None
    return None


def parse_github_compare_files(data: dict) -> list[str]:
    """Extract CVE JSON paths from a GitHub compare API response.

    Changed files are listed at the response root in ``files``, not inside
    individual ``commits`` entries.
    """
    paths: list[str] = []
    for entry in data.get("files") or []:
        if not isinstance(entry, dict):
            continue
        filename = str(entry.get("filename") or "")
        if _cve_from_repo_path(filename):
            paths.append(filename)
    return sorted(set(paths))


async def _changed_cve_paths(old_sha: str, new_sha: str) -> list[str]:
    data = await _fetch_json(f"{POC_GITHUB_API}/compare/{old_sha}...{new_sha}")
    if not isinstance(data, dict):
        return []
    return parse_github_compare_files(data)


async def _list_year_cve_paths(year: str, needed: set[str]) -> list[str]:
    if not needed:
        return []
    data = await _fetch_json(f"{POC_GITHUB_API}/contents/{year}")
    if not isinstance(data, list):
        return []
    paths: list[str] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        cve_id = _cve_from_repo_path(name)
        if cve_id and cve_id in needed:
            paths.append(f"{year}/{name}")
    return paths


async def _apply_paths(
    db,
    paths: list[str],
    known_cve_ids: set[str],
) -> tuple[int, set[str]]:
    rows_inserted = 0
    touched: set[str] = set()
    for path in paths:
        cve_id = _cve_from_repo_path(path)
        if not cve_id or cve_id not in known_cve_ids:
            continue
        payload = await _fetch_json(f"{POC_GITHUB_RAW_BASE}/{path}")
        cards = parse_poc_github_json(cve_id, payload)
        if not cards:
            continue
        rows_inserted += await merge_cve_exploits(db, cve_id, cards)
        touched.add(cve_id)
        if THROTTLE_SECONDS > 0:
            await asyncio.sleep(THROTTLE_SECONDS)
    return rows_inserted, touched


async def sync_poc_github(db, known_cve_ids: set[str]) -> dict[str, int]:
    """Sync PoC-in-GitHub index; returns stats for logging."""
    stats = {"cves": 0, "rows": 0, "skipped": 0}
    if os.environ.get("POC_GITHUB_SYNC_ENABLED", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        stats["skipped"] = 1
        return stats

    new_sha = await _latest_commit_sha()
    if not new_sha:
        return stats

    old_sha = await get_sync_state_value(db, POC_GITHUB_COMMIT_KEY)
    if old_sha == new_sha:
        stats["skipped"] = 1
        return stats

    if old_sha:
        paths = await _changed_cve_paths(old_sha, new_sha)
    else:
        years: dict[str, set[str]] = {}
        for cve_id in known_cve_ids:
            year = cve_year(cve_id)
            if year:
                years.setdefault(year, set()).add(cve_id)
        paths = []
        for year, needed in sorted(years.items()):
            paths.extend(await _list_year_cve_paths(year, needed))
            if THROTTLE_SECONDS > 0:
                await asyncio.sleep(THROTTLE_SECONDS)

    rows, touched = await _apply_paths(db, paths, known_cve_ids)
    await set_sync_state_value(db, POC_GITHUB_COMMIT_KEY, new_sha)
    stats["rows"] = rows
    stats["cves"] = len(touched)
    stats["touched"] = sorted(touched)
    return stats
