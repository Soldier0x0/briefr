"""
Detection rule source discovery.

Priority: SigmaHQ community rules → Elastic detection-rules → optional BRIEFR
template (only when no community hit and not generic — see composer).
All results cached 24 hours per CVE via feed_cache table.
GitHub token is optional but recommended (env: GITHUB_TOKEN).
Gracefully returns empty lists if the API is unavailable or rate-limited.

SigmaHQ rules are under Detection Rule License (DRL) 1.1 — commercial use is
allowed with author attribution retained on the rule and on match output.
"""

from __future__ import annotations

import logging
import os
import re

import httpx

from resilient_client import resilient_get

logger = logging.getLogger(__name__)

SIGMA_REPO = "SigmaHQ/sigma"
ELASTIC_REPO = "elastic/detection-rules"
GITHUB_SEARCH_URL = "https://api.github.com/search/code"
GITHUB_RAW = "https://raw.githubusercontent.com"
CACHE_HOURS = 24
MAX_CONTENT_FETCHES = 5  # limit raw content fetches to respect rate limits

SIGMA_LICENSE_ID = "DRL-1.1"
SIGMA_LICENSE_URL = (
    "https://github.com/SigmaHQ/Detection-Rule-License/blob/main/"
    "LICENSE.Detection.Rules.md"
)

_CVE_ID_RE = re.compile(r"CVE-(\d{4})-(\d{4,})", re.IGNORECASE)
_CVE_TAG_RE = re.compile(r"cve\.(\d{4})\.(\d{4,})", re.IGNORECASE)
_MATCH_RANK = {
    "cve_exact": 0,
    "cve_search": 1,
    "technique_related": 2,
}


# ── GitHub helpers ────────────────────────────────────────

def _gh_headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    tok = (token or "").strip() or os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


async def _github_search(
    query: str,
    token: str = "",
    *,
    cve_id: str | None = None,
    context_type: str | None = None,
    context_id: str | None = None,
) -> list[dict]:
    """Search GitHub code. Returns items list or [] on hard errors.

    QA-F1: unauthenticated GitHub code search is rate-limited to 10 req/min
    and was the root cause of a 15-30s hang (then a false frontend timeout)
    on the DETECT tab's first, uncached view of any CVE. find_sigma_rules
    and find_elastic_rules run sequentially by design (routers/cves.py —
    they share one asyncpg connection, which Postgres does not allow
    concurrent queries on), so this is not fixable by parallelizing; skip
    the doomed call outright when no token is configured, same honest
    early-exit pattern as GreyNoise/OTX "not configured" elsewhere.
    """
    if not ((token or "").strip() or os.environ.get("GITHUB_TOKEN", "").strip()):
        return []
    q_context_type = "cve" if cve_id else context_type
    q_context_id = cve_id or context_id
    try:
        resp = await resilient_get(
            "github",
            GITHUB_SEARCH_URL,
            params={"q": query, "per_page": "10"},
            headers=_gh_headers(token),
            timeout=15.0,
            retries=0,
            queue_operation="detection_rule_search" if q_context_id else "exploit_search",
            queue_context_type=q_context_type,
            queue_context_id=q_context_id,
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


async def _fetch_raw(url: str, token: str = "", *, cve_id: str | None = None) -> str | None:
    """Fetch raw file content from GitHub. Returns None on error."""
    try:
        resp = await resilient_get(
            "github",
            url,
            headers=_gh_headers(token),
            timeout=10.0,
            retries=0,
            queue_operation="repository_lookup",
            queue_context_type="cve" if cve_id else None,
            queue_context_id=cve_id,
        )
        return resp.text
    except Exception as exc:
        logger.warning("Raw fetch error (%s): %s", url, exc)
        return None


def _raw_url(repo: str, path: str, branch: str = "main") -> str:
    return f"{GITHUB_RAW}/{repo}/{branch}/{path}"


# ── Sigma (SigmaHQ) metadata extraction ──────────────────

def _normalize_cve_id(value: str) -> str:
    text = (value or "").strip().upper()
    match = _CVE_ID_RE.search(text)
    if not match:
        return ""
    return f"CVE-{match.group(1)}-{match.group(2)}"


def _cve_ids_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for match in _CVE_ID_RE.finditer(text or ""):
        found.add(f"CVE-{match.group(1)}-{match.group(2)}")
    for match in _CVE_TAG_RE.finditer(text or ""):
        found.add(f"CVE-{match.group(1)}-{match.group(2)}")
    return found


def _sigma_mentions_cve(cve_id: str, path: str, content: str | None) -> bool:
    """True when path or rule body explicitly references this CVE."""
    target = _normalize_cve_id(cve_id)
    if not target:
        return False
    haystacks = [path or ""]
    if content:
        haystacks.append(content)
    for hay in haystacks:
        if target in _cve_ids_in_text(hay):
            return True
        # Path slugs often use cve_2021_44228 / CVE-2021-44228
        slug = target.lower().replace("-", "_")
        if slug in hay.lower().replace("-", "_"):
            return True
    return False


def _sigma_meta(content: str) -> dict[str, str]:
    """Quick regex extraction of title, status, and author from Sigma YAML."""
    title = ""
    status = "experimental"
    author = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not title and stripped.startswith("title:"):
            title = stripped[6:].strip().strip("'\"")
        if stripped.startswith("status:"):
            status = stripped[7:].strip().strip("'\"") or status
        if not author and stripped.startswith("author:"):
            author = stripped[7:].strip().strip("'\"")
        if title and author and status not in ("experimental",):
            break
    return {"title": title, "status": status, "author": author}


def _sigma_status_from_path(path: str) -> str:
    """Infer Sigma rule status from its repository path."""
    p = path.lower()
    if "/stable/" in p or p.startswith("rules/") and "/deprecated/" not in p:
        return "stable"
    if "/test/" in p:
        return "test"
    return "experimental"


def _classify_sigma_match(
    cve_id: str,
    path: str,
    content: str | None,
    *,
    search_mode: str,
) -> str:
    """
    Label how strongly a SigmaHQ hit relates to the CVE.

    - cve_exact: path or rule body references this CVE
    - cve_search: found via CVE GitHub search but body not yet confirming
    - technique_related: ATT&CK technique fallback (related class, not CVE-specific)
    """
    if search_mode == "technique":
        if content is not None and _sigma_mentions_cve(cve_id, path, content):
            return "cve_exact"
        return "technique_related"
    if _sigma_mentions_cve(cve_id, path, content):
        return "cve_exact"
    return "cve_search"


def _apply_sigma_provenance(
    rule: dict,
    *,
    cve_id: str,
    search_mode: str,
    content: str | None = None,
) -> None:
    """Attach match basis + DRL attribution fields (mutates rule)."""
    path = str(rule.get("path") or "")
    body = content if content is not None else rule.get("content")
    body_str = body if isinstance(body, str) else None
    match_basis = _classify_sigma_match(
        cve_id, path, body_str, search_mode=search_mode
    )
    rule["match_basis"] = match_basis
    rule["license"] = SIGMA_LICENSE_ID
    rule["license_url"] = SIGMA_LICENSE_URL
    if body_str:
        meta = _sigma_meta(body_str)
        if meta.get("author"):
            rule["author"] = meta["author"]
    author = str(rule.get("author") or "").strip()
    rule["attribution"] = (
        f"SigmaHQ · {author}" if author else "SigmaHQ (DRL-1.1 — retain author credit)"
    )


def _rank_sigma_rules(rules: list[dict]) -> list[dict]:
    """Prefer CVE-exact hits over search/technique-related."""
    return sorted(
        rules,
        key=lambda r: (
            _MATCH_RANK.get(str(r.get("match_basis") or ""), 9),
            str(r.get("title") or r.get("path") or ""),
        ),
    )


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

    Each rule includes ``match_basis`` (cve_exact | cve_search | technique_related)
    and DRL-1.1 attribution fields. CVE-exact hits are ranked first.
    """
    from database import get_feed_cache, set_feed_cache

    cache_key = f"sigma:{cve_id.upper()}"
    cached = await get_feed_cache(db, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached.get("rules", [])

    rules: list[dict] = []
    seen_paths: set[str] = set()
    search_mode_by_path: dict[str, str] = {}

    # Search by CVE ID first
    items = await _github_search(f"{cve_id}+repo:{SIGMA_REPO}", github_token, cve_id=cve_id)
    for item in items:
        path = item.get("path", "")
        if not path.endswith(".yml") or path in seen_paths:
            continue
        seen_paths.add(path)
        search_mode_by_path[path] = "cve"
        raw_url = _raw_url(SIGMA_REPO, path)
        html_url = item.get("html_url", f"https://github.com/{SIGMA_REPO}/blob/main/{path}")
        rule = {
            "title": item.get("name", path).replace(".yml", "").replace("_", " ").title(),
            "status": _sigma_status_from_path(path),
            "source": "SigmaHQ",
            "download_url": raw_url,
            "html_url": html_url,
            "path": path,
        }
        _apply_sigma_provenance(rule, cve_id=cve_id, search_mode="cve", content=None)
        rules.append(rule)

    # If no CVE match, search by technique IDs (up to 3)
    if not rules:
        for tid in technique_ids[:3]:
            if not tid:
                continue
            tech_items = await _github_search(
                f"{tid}+repo:{SIGMA_REPO}",
                github_token,
                cve_id=cve_id,
            )
            for item in tech_items[:5]:
                path = item.get("path", "")
                if not path.endswith(".yml") or path in seen_paths:
                    continue
                seen_paths.add(path)
                search_mode_by_path[path] = "technique"
                raw_url = _raw_url(SIGMA_REPO, path)
                html_url = item.get("html_url", f"https://github.com/{SIGMA_REPO}/blob/main/{path}")
                rule = {
                    "title": item.get("name", path).replace(".yml", "").replace("_", " ").title(),
                    "status": _sigma_status_from_path(path),
                    "source": "SigmaHQ",
                    "download_url": raw_url,
                    "html_url": html_url,
                    "path": path,
                }
                _apply_sigma_provenance(
                    rule, cve_id=cve_id, search_mode="technique", content=None
                )
                rules.append(rule)
            if rules:
                break

    # Enrich first N rules with parsed title/status/author from actual content
    enriched: list[dict] = []
    fetched = 0
    for rule in rules:
        mode = search_mode_by_path.get(str(rule.get("path") or ""), "cve")
        if fetched < MAX_CONTENT_FETCHES:
            content = await _fetch_raw(rule["download_url"], github_token, cve_id=cve_id)
            fetched += 1
            if content:
                rule["content"] = content
                meta = _sigma_meta(content)
                if meta["title"]:
                    rule["title"] = meta["title"]
                rule["status"] = meta["status"] or rule["status"]
                if meta.get("author"):
                    rule["author"] = meta["author"]
                _apply_sigma_provenance(
                    rule, cve_id=cve_id, search_mode=mode, content=content
                )
            else:
                _apply_sigma_provenance(
                    rule, cve_id=cve_id, search_mode=mode, content=None
                )
        else:
            _apply_sigma_provenance(rule, cve_id=cve_id, search_mode=mode, content=None)
        enriched.append(rule)

    ranked = _rank_sigma_rules(enriched)
    await set_feed_cache(db, cache_key, {"rules": ranked})
    return ranked


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
        items = await _github_search(
            f"{tid}+repo:{ELASTIC_REPO}",
            github_token,
            context_type="observable",
            context_id=tid,
        )
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
