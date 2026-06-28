"""Tests for incident/news RSS parsing and relevance filters."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds import incident_news
from feeds.incident_news import _assert_rss_bytes, _filter_news_items, parse_rss_xml
from feeds.incident_sources import INCIDENT_RSS_SOURCES


def test_parse_rss_xml_excludes_name_that_toon_contest():
    source = {"id": "darkreading", "label": "Dark Reading"}
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Name That Toon Contest</title>
          <link>https://www.darkreading.com/contest/toon</link>
          <description>Weekly cartoon caption contest.</description>
          <pubDate>Mon, 08 Jun 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Critical RCE Patched in Popular VPN</title>
          <link>https://www.darkreading.com/vulnerabilities/rce</link>
          <description>Vendor issued emergency patch.</description>
          <pubDate>Mon, 08 Jun 2026 11:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    cards = parse_rss_xml(xml, source)
    titles = [card["title"] for card in cards]

    assert "Name That Toon Contest" not in titles
    assert "Critical RCE Patched in Popular VPN" in titles


def test_filter_news_items_applies_to_cached_rows():
    items = [
        {"title": "Name That Toon Contest - June", "kind": "news"},
        {"title": "New ransomware campaign targets hospitals", "kind": "news"},
    ]
    filtered = _filter_news_items(items)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "New ransomware campaign targets hospitals"


def test_filter_news_items_handles_malformed_cache():
    items = [
        None,
        "not a dict",
        {"title": 123, "kind": "news"},
        {"title": "Name That Toon Contest - June", "kind": "news"},
        {"title": "New ransomware campaign targets hospitals", "kind": "news"},
    ]
    filtered = _filter_news_items(items)
    assert len(filtered) == 2
    assert filtered[0]["title"] == 123
    assert filtered[1]["title"] == "New ransomware campaign targets hospitals"


def test_filter_news_items_returns_empty_for_non_list():
    assert _filter_news_items(None) == []
    assert _filter_news_items("not a list") == []


def test_assert_rss_bytes_rejects_html_challenge_page():
    html = b"<!doctype html><html><head><title>Challenge</title></head></html>"
    try:
        _assert_rss_bytes(html, "krebs")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "HTML instead of XML" in str(exc)


def test_assert_rss_bytes_accepts_xml_payload():
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    _assert_rss_bytes(xml, "hackernews")


def test_krebs_source_has_direct_feed_fallback():
    krebs = next(s for s in INCIDENT_RSS_SOURCES if s["id"] == "krebs")
    assert krebs["url"] == "https://feeds.feedburner.com/KrebsOnSecurity"
    assert krebs["fallback_url"] == "https://krebsonsecurity.com/feed/"


def test_fetch_rss_source_bytes_falls_back_when_primary_fails(monkeypatch):
    source = {
        "id": "krebs",
        "label": "Krebs on Security",
        "url": "https://feeds.feedburner.com/KrebsOnSecurity",
        "fallback_url": "https://krebsonsecurity.com/feed/",
    }
    calls: list[str] = []

    async def fake_fetch(url: str, source_id: str = "rss") -> bytes:
        calls.append(url)
        if "feedburner" in url:
            raise ValueError("RSS fetch for krebs: upstream returned HTML instead of XML")
        return b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'

    monkeypatch.setattr(incident_news, "_fetch_rss_bytes", fake_fetch)

    async def run() -> None:
        raw = await incident_news._fetch_rss_source_bytes(source)
        assert b"<rss" in raw
        assert calls == [
            "https://feeds.feedburner.com/KrebsOnSecurity",
            "https://krebsonsecurity.com/feed/",
        ]

    asyncio.run(run())


def test_fetch_rss_source_bytes_raises_when_all_urls_fail(monkeypatch):
    source = {
        "id": "krebs",
        "label": "Krebs on Security",
        "url": "https://feeds.feedburner.com/KrebsOnSecurity",
        "fallback_url": "https://krebsonsecurity.com/feed/",
    }

    async def always_fail(url: str, source_id: str = "rss") -> bytes:
        raise ValueError(f"failed: {url}")

    monkeypatch.setattr(incident_news, "_fetch_rss_bytes", always_fail)

    async def run() -> None:
        try:
            await incident_news._fetch_rss_source_bytes(source)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "krebsonsecurity.com/feed/" in str(exc)

    asyncio.run(run())
