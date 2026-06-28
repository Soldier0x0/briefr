"""Tests for incident/news RSS parsing and relevance filters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.incident_news import _assert_rss_bytes, _filter_news_items, parse_rss_xml


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
