"""
Fetch and normalize cybersecurity news RSS feeds for the Case Studies tab.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

from database import get_feed_cache, set_feed_cache
from feeds.incident_sources import INCIDENT_RSS_SOURCES
from resilient_client import resilient_get

logger = logging.getLogger(__name__)

RSS_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TECHNIQUE_RE = re.compile(r"\b(T\d{4}(?:\.\d{3})?|AML\.T\d{4}(?:\.\d{3})?)\b", re.I)

TAG_HINTS = [
    "Okta", "nginx", "Kubernetes", "TensorFlow", "PyTorch", "AWS", "Azure",
    "Google", "Microsoft", "Cisco", "Fortinet", "Palo Alto", "VMware",
    "Exchange", "Active Directory", "Linux", "Windows", "Docker", "Jenkins",
    "GitHub", "GitLab", "CrowdStrike", "SentinelOne", "Splunk", "Elastic",
    "MongoDB", "PostgreSQL", "Redis", "Apache", "IIS", "OpenSSL", "Java",
    "Python", "Node.js", "React", "Spring", "Confluence", "Jira", "Citrix",
]

CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

CACHE_HOURS = 0.5  # 30 minutes per source

# Editorial/promotional RSS items that are not security news (matched against title).
EXCLUDED_NEWS_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"name that toon", re.I),
]


def _is_relevant_news_item(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    title = item.get("title")
    if not isinstance(title, str):
        title = ""
    return not any(pattern.search(title) for pattern in EXCLUDED_NEWS_TITLE_PATTERNS)


def _filter_news_items(items: list[dict] | None) -> list[dict]:
    if not isinstance(items, list):
        return []
    return [item for item in items if _is_relevant_news_item(item)]


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    return html.unescape(re.sub(r"\s+", " ", cleaned)).strip()


def _truncate(text: str, max_len: int = 280) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _parse_date(raw: str | None) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _extract_meta(title: str, description: str) -> tuple[list[str], list[str]]:
    text = f"{title} {description}"
    techniques = sorted({m.group(0).upper() for m in TECHNIQUE_RE.finditer(text)})
    tags: list[str] = []
    lower = text.lower()
    for hint in TAG_HINTS:
        if hint.lower() in lower:
            tags.append(hint)
    return techniques, tags


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return (node.text or "").strip() or "".join(node.itertext()).strip()


def _item_link(item: ET.Element) -> str:
    link = item.find("link")
    if link is not None:
        href = link.get("href")
        if href:
            return href.strip()
        if link.text:
            return link.text.strip()
    guid = item.find("guid")
    if guid is not None and guid.text:
        text = guid.text.strip()
        if text.startswith("http"):
            return text
    id_node = item.find("id")
    if id_node is not None and id_node.text:
        return id_node.text.strip()
    return ""


def _item_description(item: ET.Element) -> str:
    for path in (
        "description",
        "summary",
        "content",
    ):
        node = item.find(path)
        if node is not None and _node_text(node):
            return _strip_html(_node_text(node))
    encoded = item.find("content:encoded", CONTENT_NS)
    if encoded is not None:
        return _strip_html(_node_text(encoded))
    return ""


def parse_rss_xml(xml_text: str, source: dict) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        preview = (xml_text or "").lstrip()[:80].replace("\n", " ")
        raise ValueError(
            f"RSS parse failed for {source.get('label', source.get('id', 'feed'))}: "
            f"{exc} (response starts with: {preview!r})"
        ) from exc
    nodes = root.findall(".//item") or root.findall(".//entry")
    cards: list[dict] = []

    for item in nodes:
        title = _strip_html(_node_text(item.find("title")))
        url = _item_link(item)
        if not title or not url:
            continue
        description = _item_description(item) or title
        pub_raw = None
        for tag in ("pubDate", "published", "updated", "dc:date"):
            node = item.find(tag)
            if node is not None and _node_text(node):
                pub_raw = _node_text(node)
                break
        published_at = _parse_date(pub_raw)
        techniques, tags = _extract_meta(title, description)
        card = {
            "id": url,
            "source": source["label"],
            "sourceId": source["id"],
            "title": title,
            "description": _truncate(description),
            "publishedAt": published_at,
            "url": url,
            "techniques": techniques,
            "tags": tags,
            "kind": "news",
        }
        if _is_relevant_news_item(card):
            cards.append(card)
    return cards


def _source_feed_urls(source: dict[str, str]) -> list[str]:
    urls = [source["url"]]
    fallback = source.get("fallback_url")
    if fallback and fallback not in urls:
        urls.append(fallback)
    return urls


async def _fetch_rss_bytes(url: str, source_id: str = "rss") -> bytes:
    # SOURCE: direct RSS/Atom feed URL (server-side; avoids browser CSP limits)
    response = await resilient_get(
        f"rss:{source_id}",
        url,
        timeout=30.0,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": RSS_BROWSER_UA,
        },
    )
    raw = response.content
    _assert_rss_bytes(raw, source_id)
    return raw


async def _fetch_rss_source_bytes(source: dict[str, str]) -> bytes:
    """Fetch RSS for a source, trying optional fallback_url after primary failure."""
    source_id = source["id"]
    urls = _source_feed_urls(source)

    for i, url in enumerate(urls):
        try:
            return await _fetch_rss_bytes(url, source_id)
        except Exception as exc:
            if i + 1 < len(urls):
                logger.info(
                    "RSS fetch for %s failed at %s (%s), trying fallback",
                    source_id,
                    url,
                    exc,
                )
                continue
            raise


def _assert_rss_bytes(raw: bytes, source_id: str) -> None:
    stripped = raw.lstrip()
    if not stripped:
        raise ValueError(f"RSS fetch for {source_id}: empty response")
    head = stripped[:256].lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        raise ValueError(
            f"RSS fetch for {source_id}: upstream returned HTML instead of XML "
            "(often bot protection or a challenge page)"
        )
    if stripped[:1] not in (b"<", b"\xef"):
        preview = stripped[:80].decode("utf-8", errors="replace")
        raise ValueError(
            f"RSS fetch for {source_id}: response does not look like XML "
            f"(starts with: {preview!r})"
        )


def rss_cache_key(source_id: str) -> str:
    return f"incident_rss:{source_id}"


def _rss_cache_stale(cached_at: str | None) -> bool:
    if not cached_at:
        return True
    try:
        cached = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except ValueError:
        try:
            cached = datetime.strptime(cached_at, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return True
    if cached.tzinfo is None:
        cached = cached.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - cached
    return age > timedelta(hours=CACHE_HOURS)


async def get_rss_sources_status(db) -> list[dict[str, Any]]:
    """Per-RSS-source cache metadata for admin incident feed health."""
    sources: list[dict[str, Any]] = []
    for source in INCIDENT_RSS_SOURCES:
        row = await db.execute_fetchall(
            "SELECT cached_at, result FROM feed_cache WHERE cache_key = ?",
            (rss_cache_key(source["id"]),),
        )
        item_count = 0
        cached_at = None
        if row:
            cached_at = row[0]["cached_at"]
            try:
                payload = json.loads(row[0]["result"])
                if isinstance(payload.get("items"), list):
                    item_count = len(_filter_news_items(payload["items"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        sources.append(
            {
                "id": source["id"],
                "label": source["label"],
                "kind": "rss",
                "item_count": item_count,
                "cached_at": cached_at,
                "stale": _rss_cache_stale(cached_at),
            }
        )
    return sources


async def fetch_rss_source(db, source: dict, *, force: bool = False) -> list[dict]:
    cache_key = rss_cache_key(source["id"])
    if not force:
        cached = await get_feed_cache(db, cache_key, max_age_hours=CACHE_HOURS)
        if cached is not None and isinstance(cached.get("items"), list):
            return _filter_news_items(cached["items"])

    raw = await _fetch_rss_source_bytes(source)
    items = parse_rss_xml(raw.decode("utf-8", errors="replace"), source)
    await set_feed_cache(db, cache_key, {"items": items})
    return items


async def fetch_all_incident_news(db) -> tuple[list[dict], list[dict]]:
    cards: list[dict] = []
    errors: list[dict] = []

    for source in INCIDENT_RSS_SOURCES:
        try:
            items = await fetch_rss_source(db, source)
            cards.extend(items)
        except Exception as exc:
            logger.warning("RSS fetch failed for %s: %s", source["label"], exc)
            errors.append(
                {
                    "source": source["label"],
                    "message": str(exc) or "Failed to load feed",
                }
            )

    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)
    return cards, errors


async def fetch_all_incident_news_parallel(db) -> tuple[list[dict], list[dict]]:
    """Scheduler-job variant: network fetches run concurrently via
    asyncio.gather while cache reads/writes stay sequential on the single
    SQLite connection. Never use on the request path."""
    cards: list[dict] = []
    errors: list[dict] = []
    to_fetch: list[dict] = []

    for source in INCIDENT_RSS_SOURCES:
        cache_key = rss_cache_key(source["id"])
        cached = await get_feed_cache(db, cache_key, max_age_hours=CACHE_HOURS)
        if cached is not None and isinstance(cached.get("items"), list):
            cards.extend(_filter_news_items(cached["items"]))
        else:
            to_fetch.append(source)

    results = await asyncio.gather(
        *(_fetch_rss_source_bytes(source) for source in to_fetch),
        return_exceptions=True,
    )

    for source, result in zip(to_fetch, results):
        if isinstance(result, BaseException):
            logger.warning("RSS fetch failed for %s: %s", source["label"], result)
            errors.append(
                {
                    "source": source["label"],
                    "message": str(result) or "Failed to load feed",
                }
            )
            continue
        try:
            items = parse_rss_xml(result.decode("utf-8", errors="replace"), source)
        except Exception as exc:
            logger.warning("RSS parse failed for %s: %s", source["label"], exc)
            errors.append(
                {
                    "source": source["label"],
                    "message": str(exc) or "Failed to parse feed",
                }
            )
            continue
        cards.extend(items)
        try:
            await set_feed_cache(db, rss_cache_key(source["id"]), {"items": items})
        except Exception as exc:
            # Cache write contention (e.g. bootstrap ingest) must not drop
            # successfully parsed items; the next cycle will persist them.
            logger.warning("RSS cache write failed for %s: %s", source["label"], exc)

    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)
    return cards, errors
