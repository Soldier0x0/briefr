"""RSS ↔ CVE reverse lookup from the incident feed snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test


def test_get_related_news_for_cve_returns_matching_cards(monkeypatch):
    from feeds import case_study_feed

    async def fake_snapshot():
        return {
            "news": [
                {
                    "sourceId": "cisa-news",
                    "source": "CISA Advisories",
                    "title": "Alert for CVE-2026-11111",
                    "description": "Details",
                    "url": "https://example.com/a",
                    "publishedAt": "2026-07-01T00:00:00+00:00",
                    "kind": "news",
                    "cve_ids": ["CVE-2026-11111"],
                },
                {
                    "sourceId": "hackernews",
                    "source": "The Hacker News",
                    "title": "Unrelated ransomware story",
                    "description": "No identifiers",
                    "url": "https://example.com/b",
                    "publishedAt": "2026-07-02T00:00:00+00:00",
                    "kind": "news",
                    "cve_ids": [],
                },
            ],
            "atlas": [],
            "generated_at": "2026-07-16T00:00:00+00:00",
        }

    monkeypatch.setattr(case_study_feed, "_read_snapshot", fake_snapshot)
    hits = run_db_test(case_study_feed.get_related_news_for_cve("cve-2026-11111"))
    assert len(hits) == 1
    assert hits[0]["title"] == "Alert for CVE-2026-11111"
    assert hits[0]["url"] == "https://example.com/a"


def test_ensure_news_cve_ids_backfills_stale_cards():
    from feeds.case_study_feed import _ensure_news_cve_ids

    card = {
        "sourceId": "krebs",
        "kind": "news",
        "title": "Patch for CVE-2026-22222 shipped",
        "description": "Also CVE-2026-33333",
    }
    out = _ensure_news_cve_ids(card)
    assert out["cve_ids"] == ["CVE-2026-22222", "CVE-2026-33333"]
