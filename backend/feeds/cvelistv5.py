"""cvelistV5 — CVE JSON 5.x records hours before NVD.

Incremental sync via GitHub compare API; watermark stored in sync_state as
``cvelistv5_head_sha``. Only changed JSON paths are fetched each run.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from feeds.cve_record_v5 import (
    cve_id_from_repo_path,
    cvelistv5_repo_path,
    is_cve_record_rejected,
    parse_cvelistv5_record,
)
from feeds.github_helpers import GITHUB_API, github_headers, raw_repo_url
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

REPO_OWNER = "CVEProject"
REPO_NAME = "cvelistV5"
DEFAULT_BRANCH = "main"
DEFAULT_INTERVAL_MINUTES = 30
DEFAULT_INITIAL_SINCE_DAYS = 7
SYNC_STATE_KEY = "cvelistv5_head_sha"
FETCH_CONCURRENCY = 10
FETCH_DELAY_SECONDS = 0.1


def get_cvelistv5_sync_interval_minutes() -> int:
    return int(
        os.environ.get("CVELISTV5_SYNC_INTERVAL_MINUTES", str(DEFAULT_INTERVAL_MINUTES))
    )


def get_cvelistv5_branch() -> str:
    return os.environ.get("CVELISTV5_BRANCH", DEFAULT_BRANCH).strip() or DEFAULT_BRANCH


def get_cvelistv5_initial_since_days() -> int:
    return int(os.environ.get("CVELISTV5_INITIAL_SINCE_DAYS", str(DEFAULT_INITIAL_SINCE_DAYS)))


async def _cvelistv5_get(
    url: str,
    *,
    operation: str = "cve_ingest",
    context_type: str | None = "task",
    context_id: str | None = "cvelistv5_sync",
    timeout: float = 60.0,
    params: dict | None = None,
) -> httpx.Response:
    return await resilient_get(
        "cvelistv5",
        url,
        headers=github_headers(),
        timeout=timeout,
        params=params,
        queue_operation=operation,
        queue_context_type=context_type,
        queue_context_id=context_id,
    )


async def _fetch_head_sha(branch: str) -> str | None:
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/commits/{branch}"
    try:
        response = await _cvelistv5_get(url)
        data = response.json()
    except CircuitOpenError:
        logger.warning("cvelistV5 circuit open — skipping head lookup")
        return None
    except httpx.HTTPError as exc:
        logger.error("cvelistV5 head lookup failed: %s", exc)
        return None

    await record_api_call("cvelistv5", 1)
    sha = data.get("sha")
    return sha if isinstance(sha, str) and sha else None


async def _fetch_bootstrap_base_sha(branch: str, since_days: int) -> str | None:
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/commits"
    try:
        response = await _cvelistv5_get(
            url,
            params={"sha": branch, "since": since, "per_page": 100},
        )
        commits = response.json()
    except CircuitOpenError:
        return None
    except httpx.HTTPError as exc:
        logger.error("cvelistV5 bootstrap commits failed: %s", exc)
        return None

    await record_api_call("cvelistv5", 1)
    if not isinstance(commits, list) or not commits:
        return None
    oldest = commits[-1]
    if isinstance(oldest, dict):
        sha = oldest.get("sha")
        if isinstance(sha, str) and sha:
            return sha
    return None


def _filter_cve_paths(files: list) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status == "removed":
            continue
        path = item.get("filename") or ""
        if not path.startswith("cves/") or not path.endswith(".json"):
            continue
        if cve_id_from_repo_path(path) and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


async def _compare_commits(base_sha: str, head_sha: str) -> list[str]:
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/compare/{base_sha}...{head_sha}"
    try:
        response = await _cvelistv5_get(url, timeout=120.0)
        data = response.json()
    except CircuitOpenError:
        logger.warning("cvelistV5 circuit open — skipping compare")
        return []
    except httpx.HTTPError as exc:
        logger.error("cvelistV5 compare failed (%s...%s): %s", base_sha[:8], head_sha[:8], exc)
        return []

    await record_api_call("cvelistv5", 1)
    if data.get("status") == "identical":
        return []
    files = data.get("files") or []
    if len(files) >= 300:
        logger.warning(
            "cvelistV5 compare returned %d files (possibly truncated). "
            "Some changes may be missed.",
            len(files),
        )
    return _filter_cve_paths(files)


async def _fetch_record(path: str, branch: str) -> tuple[dict | None, str | None]:
    url = raw_repo_url(REPO_OWNER, REPO_NAME, branch, path)
    cve_id = cve_id_from_repo_path(path)
    try:
        response = await _cvelistv5_get(
            url,
            operation="cve_lookup",
            context_type="cve" if cve_id else "task",
            context_id=cve_id or path[:48],
            timeout=45.0,
        )
        record = response.json()
    except CircuitOpenError:
        return None, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            logger.debug("cvelistV5 HTTP %s for %s", exc.response.status_code, path)
        return None, None
    except httpx.HTTPError:
        return None, None
    except (json.JSONDecodeError, ValueError):
        return None, None

    await record_api_call("cvelistv5", 1)
    if not isinstance(record, dict):
        return None, None
    rejected_id = is_cve_record_rejected(record)
    if rejected_id:
        return None, rejected_id
    return parse_cvelistv5_record(record), None


async def fetch_cvelistv5_delta(
    watermark_sha: str | None,
) -> tuple[list[dict], list[str], str | None, bool]:
    """Return (parsed records, rejected_ids, new_head_sha, watermark_advanced).

    When ``watermark_advanced`` is False the caller must not persist a new SHA
    (transient failure or nothing to do).
    """
    branch = get_cvelistv5_branch()
    head_sha = await _fetch_head_sha(branch)
    if not head_sha:
        return [], [], watermark_sha, False

    if watermark_sha and watermark_sha == head_sha:
        logger.info("cvelistV5 up to date at %s", head_sha[:12])
        return [], [], head_sha, True

    base_sha = watermark_sha
    if not base_sha:
        base_sha = await _fetch_bootstrap_base_sha(branch, get_cvelistv5_initial_since_days())
        if not base_sha:
            logger.info(
                "cvelistV5 bootstrap: no commits in last %d days — seeding watermark %s",
                get_cvelistv5_initial_since_days(),
                head_sha[:12],
            )
            return [], [], head_sha, True

    changed_paths = await _compare_commits(base_sha, head_sha)
    if not changed_paths:
        logger.info("cvelistV5 compare %s...%s: no CVE JSON changes", base_sha[:8], head_sha[:8])
        return [], [], head_sha, True

    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    records: list[dict] = []
    rejected_ids: list[str] = []

    async def _one(path: str) -> None:
        async with semaphore:
            parsed, rejected = await _fetch_record(path, branch)
            if parsed:
                records.append(parsed)
            elif rejected:
                rejected_ids.append(rejected)
            await asyncio.sleep(FETCH_DELAY_SECONDS)

    await asyncio.gather(*(_one(path) for path in changed_paths))
    logger.info(
        "cvelistV5 delta: %d records, %d rejected from %d changed paths (%s...%s)",
        len(records),
        len(rejected_ids),
        len(changed_paths),
        base_sha[:8],
        head_sha[:8],
    )
    return records, rejected_ids, head_sha, True


async def fetch_cvelistv5_for_cve(cve_id: str) -> dict | None:
    path = cvelistv5_repo_path(cve_id)
    if not path:
        return None
    parsed, _rejected = await _fetch_record(path, get_cvelistv5_branch())
    return parsed
