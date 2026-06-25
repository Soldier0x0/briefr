"""
Detection rule source discovery.

Priority: SigmaHQ community rules → Elastic detection-rules → BRIEFR generated.
All results cached 24 hours per CVE via feed_cache table.
GitHub token is optional but recommended (env: GITHUB_TOKEN).
Gracefully returns empty lists if the API is unavailable or rate-limited.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from resilient_client import resilient_get

logger = logging.getLogger(__name__)

SIGMA_REPO = "SigmaHQ/sigma"
ELASTIC_REPO = "elastic/detection-rules"
GITHUB_SEARCH_URL = "https://api.github.com/search/code"
GITHUB_RAW = "https://raw.githubusercontent.com"
CACHE_HOURS = 24
MAX_CONTENT_FETCHES = 5  # limit raw content fetches to respect rate limits


# ── GitHub helpers ────────────────────────────────────────

def _gh_headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    tok = token.strip() or os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


async def _github_search(query: str, token: str = "") -> list[dict]:
    """Search GitHub code. Returns items list or [] on hard errors."""
    try:
        resp = await resilient_get(
            "github",
            GITHUB_SEARCH_URL,
            params={"q": query, "per_page": "10"},
            headers=_gh_headers(token),
            timeout=15.0,
            retries=0,
        )
        return resp.json().get("items", [])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (403, 429):
            logger.warning("GitHub Search rate-limited (query=%r): %d", query, exc.response.status_code)
        else:
            logger.warning("GitHub Search failed (query=%r): %d", query, exc.response.status_code)
        return []
    except Exception as exc:
        logger.warning("GitHub Search error: %s", exc)
        return []


async def _fetch_raw(url: str, token: str = "") -> str | None:
    """Fetch raw file content from GitHub. Returns None on error."""
    try:
        resp = await resilient_get(
            "github",
            url,
            headers=_gh_headers(token),
            timeout=10.0,
            retries=0,
        )
        return resp.text
    except Exception as exc:
        logger.warning("Raw fetch error (%s): %s", url, exc)
        return None


def _raw_url(repo: str, path: str, branch: str = "main") -> str:
    return f"{GITHUB_RAW}/{repo}/{branch}/{path}"


# ── Sigma (SigmaHQ) metadata extraction ──────────────────

def _sigma_meta(content: str) -> dict[str, str]:
    """Quick regex extraction of title and status from Sigma YAML without full parse."""
    title = ""
    status = "experimental"
    for line in content.splitlines():
        if not title and line.startswith("title:"):
            title = line[6:].strip().strip("'\"")
        if not status or status == "experimental":
            if line.startswith("status:"):
                status = line[7:].strip().strip("'\"")
        if title and status not in ("experimental",):
            break
    return {"title": title, "status": status}


def _sigma_status_from_path(path: str) -> str:
    """Infer Sigma rule status from its repository path."""
    p = path.lower()
    if "/stable/" in p or p.startswith("rules/") and "/deprecated/" not in p:
        return "stable"
    if "/test/" in p:
        return "test"
    return "experimental"


# ── Elastic metadata extraction ───────────────────────────

def _elastic_meta(content: str, filename: str) -> dict[str, str]:
    """Extract name and language from Elastic detection rule TOML."""
    name = ""
    language = "kuery"
    rule_type = "query"
    for line in content.splitlines():
        line = line.strip()
        if not name and re.match(r'^name\s*=', line):
            m = re.search(r'=\s*"([^"]+)"', line)
            if m:
                name = m.group(1)
        if re.match(r'^language\s*=', line):
            m = re.search(r'=\s*"([^"]+)"', line)
            if m:
                language = m.group(1)
        if re.match(r'^type\s*=', line):
            m = re.search(r'=\s*"([^"]+)"', line)
            if m:
                rule_type = m.group(1)
    if not name:
        name = filename.replace("_", " ").replace("-", " ").replace(".toml", "").title()
    return {"name": name, "language": language, "rule_type": rule_type}


# ── Level 1 — SigmaHQ search ─────────────────────────────

async def find_sigma_rules(
    db,
    cve_id: str,
    technique_ids: list[str],
    github_token: str = "",
) -> list[dict]:
    """
    Search SigmaHQ for Sigma rules matching a CVE ID or ATT&CK technique IDs.
    Results cached for 24 hours.
    """
    from database import get_feed_cache, set_feed_cache

    cache_key = f"sigma:{cve_id.upper()}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached.get("rules", [])

    rules: list[dict] = []
    seen_paths: set[str] = set()

    # Search by CVE ID first
    items = await _github_search(f"{cve_id}+repo:{SIGMA_REPO}", github_token)
    for item in items:
        path = item.get("path", "")
        if not path.endswith(".yml") or path in seen_paths:
            continue
        seen_paths.add(path)
        raw_url = _raw_url(SIGMA_REPO, path)
        html_url = item.get("html_url", f"https://github.com/{SIGMA_REPO}/blob/main/{path}")
        rules.append({
            "title": item.get("name", path).replace(".yml", "").replace("_", " ").title(),
            "status": _sigma_status_from_path(path),
            "source": "SigmaHQ",
            "download_url": raw_url,
            "html_url": html_url,
            "path": path,
        })

    # If no CVE match, search by technique IDs (up to 3)
    if not rules:
        for tid in technique_ids[:3]:
            if not tid:
                continue
            tech_items = await _github_search(f"{tid}+repo:{SIGMA_REPO}", github_token)
            for item in tech_items[:5]:
                path = item.get("path", "")
                if not path.endswith(".yml") or path in seen_paths:
                    continue
                seen_paths.add(path)
                raw_url = _raw_url(SIGMA_REPO, path)
                html_url = item.get("html_url", f"https://github.com/{SIGMA_REPO}/blob/main/{path}")
                rules.append({
                    "title": item.get("name", path).replace(".yml", "").replace("_", " ").title(),
                    "status": _sigma_status_from_path(path),
                    "source": "SigmaHQ",
                    "download_url": raw_url,
                    "html_url": html_url,
                    "path": path,
                })
            if rules:
                break

    # Enrich first N rules with parsed title/status from actual content
    enriched: list[dict] = []
    fetched = 0
    for rule in rules:
        if fetched < MAX_CONTENT_FETCHES:
            content = await _fetch_raw(rule["download_url"], github_token)
            fetched += 1
            if content:
                rule["content"] = content
                meta = _sigma_meta(content)
                if meta["title"]:
                    rule["title"] = meta["title"]
                rule["status"] = meta["status"] or rule["status"]
        enriched.append(rule)

    await set_feed_cache(db, cache_key, {"rules": enriched})
    return enriched


# ── Level 2 — Elastic detection-rules search ─────────────

async def find_elastic_rules(
    db,
    technique_ids: list[str],
    github_token: str = "",
) -> list[dict]:
    """
    Search elastic/detection-rules for rules matching ATT&CK technique IDs.
    Results cached per technique set for 24 hours.
    """
    from database import get_feed_cache, set_feed_cache

    sorted_tids = sorted(t.upper() for t in technique_ids if t)
    cache_key = f"elastic:{','.join(sorted_tids[:5])}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached.get("rules", [])

    rules: list[dict] = []
    seen_paths: set[str] = set()

    for tid in sorted_tids[:3]:
        items = await _github_search(f"{tid}+repo:{ELASTIC_REPO}", github_token)
        for item in items[:5]:
            path = item.get("path", "")
            if not path.endswith(".toml") or path in seen_paths:
                continue
            seen_paths.add(path)
            raw_url = _raw_url(ELASTIC_REPO, path)
            html_url = item.get("html_url", f"https://github.com/{ELASTIC_REPO}/blob/main/{path}")
            rules.append({
                "name": item.get("name", path).replace(".toml", "").replace("_", " ").title(),
                "rule_type": "query",
                "language": "kuery",
                "source": "Elastic",
                "download_url": raw_url,
                "html_url": html_url,
                "path": path,
            })
        if rules:
            break

    # Enrich first few with real name/language from TOML content
    fetched = 0
    for rule in rules:
        if fetched >= 3:
            break
        content = await _fetch_raw(rule["download_url"], github_token)
        fetched += 1
        if content:
            meta = _elastic_meta(content, rule["path"].split("/")[-1])
            rule["name"] = meta["name"] or rule["name"]
            rule["language"] = meta["language"]
            rule["rule_type"] = meta["rule_type"]

    await set_feed_cache(db, cache_key, {"rules": rules})
    return rules
