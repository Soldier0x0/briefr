"""Phase 2: URLhaus bulk catalog feed — parse + fetch."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.errors import FeedFetchError
from feeds.urlhaus import URLHAUS_RECENT_API, fetch_urlhaus_iocs, parse_urlhaus_entry

SAMPLE_ENTRY = {
    "id": "223622",
    "urlhaus_reference": "https://urlhaus.abuse.ch/url/223622/",
    "url": "http://45.61.49.78/razor/r4z0r.mips",
    "url_status": "offline",
    "host": "45.61.49.78",
    "date_added": "2024-08-10 09:02:05 UTC",
    "threat": "malware_download",
    "reporter": "zbetcheckin",
    "larted": "true",
    "tags": ["elf", "mirai"],
}


def test_parse_urlhaus_entry_keeps_full_url_and_host():
    row = parse_urlhaus_entry(SAMPLE_ENTRY)
    assert row is not None
    assert row["ioc_id"] == "223622"
    assert row["ioc_type"] == "url"
    assert row["ioc_value"] == "http://45.61.49.78/razor/r4z0r.mips"
    assert row["host_ioc"] == "45.61.49.78"
    assert row["raw_ioc"] == "http://45.61.49.78/razor/r4z0r.mips"
    assert row["threat_type"] == "malware_download"
    assert "mirai" in row["malware"]
    assert row["first_seen"] == "2024-08-10 09:02:05 UTC"


def test_parse_urlhaus_entry_extracts_domain_host():
    entry = {
        "id": "99",
        "url": "https://evil.example.com/path/a.exe?q=1",
        "date_added": "2024-08-10 09:02:05 UTC",
        "threat": "malware_download",
        "tags": ["emotet"],
    }
    row = parse_urlhaus_entry(entry)
    assert row is not None
    assert row["host_ioc"] == "evil.example.com"
    assert row["ioc_value"] == "https://evil.example.com/path/a.exe?q=1"


def test_parse_urlhaus_entry_drops_www_from_host_ioc():
    """URL→DOMAIN joins use the DOMAIN-canonical host (which strips a leading
    ``www.``), so host_ioc must too — otherwise a URL on www.evil.example
    silently misses a DOMAIN edge for evil.example."""
    row = parse_urlhaus_entry(
        {
            "id": "100",
            "url": "http://www.evil.example/razor/payload.bin",
            "date_added": "2024-08-10 09:02:05 UTC",
            "threat": "malware_download",
            "tags": ["emotet"],
        }
    )
    assert row is not None
    assert row["host_ioc"] == "evil.example"
    assert row["ioc_value"] == "http://www.evil.example/razor/payload.bin"


def test_parse_urlhaus_entry_skips_invalid():
    assert parse_urlhaus_entry({}) is None
    assert parse_urlhaus_entry({"id": "1"}) is None
    assert parse_urlhaus_entry({"id": "2", "url": "   "}) is None
    assert parse_urlhaus_entry({"id": "3", "url": "http:///"}) is None


class _FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_fetch_urlhaus_iocs_parses_payload(monkeypatch):
    calls = []

    async def fake_request(source, method, url, **kwargs):
        calls.append((source, method, url))
        return _FakeResponse(
            200,
            {"query_status": "ok", "urls": [SAMPLE_ENTRY, {"id": "bad"}]},
        )

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr("feeds.urlhaus.resilient_request", fake_request)
    monkeypatch.setattr("feeds.urlhaus.record_api_call", fake_record)

    rows = asyncio.run(fetch_urlhaus_iocs("test-key"))
    assert len(rows) == 1
    assert rows[0]["ioc_id"] == "223622"
    assert calls == [("urlhaus", "GET", URLHAUS_RECENT_API)]


def test_fetch_urlhaus_iocs_handles_bad_status(monkeypatch):
    async def fake_request(*args, **kwargs):
        return _FakeResponse(429, {})

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr("feeds.urlhaus.resilient_request", fake_request)
    monkeypatch.setattr("feeds.urlhaus.record_api_call", fake_record)

    with pytest.raises(FeedFetchError, match="HTTP 429"):
        asyncio.run(fetch_urlhaus_iocs("test-key"))


def test_fetch_urlhaus_iocs_handles_non_list_urls(monkeypatch):
    async def fake_request(*args, **kwargs):
        return _FakeResponse(200, {"query_status": "ok", "urls": "not-a-list"})

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr("feeds.urlhaus.resilient_request", fake_request)
    monkeypatch.setattr("feeds.urlhaus.record_api_call", fake_record)

    assert asyncio.run(fetch_urlhaus_iocs("test-key")) == []


def test_fetch_urlhaus_iocs_skips_non_dict_entries(monkeypatch):
    async def fake_request(*args, **kwargs):
        return _FakeResponse(
            200,
            {"query_status": "ok", "urls": [SAMPLE_ENTRY, "not-a-dict", None, {"id": "bad"}]},
        )

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr("feeds.urlhaus.resilient_request", fake_request)
    monkeypatch.setattr("feeds.urlhaus.record_api_call", fake_record)

    rows = asyncio.run(fetch_urlhaus_iocs("test-key"))
    assert len(rows) == 1
    assert rows[0]["ioc_id"] == "223622"


def test_fetch_urlhaus_iocs_requires_key(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("should not call upstream without a key")

    monkeypatch.setattr("feeds.urlhaus.resilient_request", fail_if_called)

    assert asyncio.run(fetch_urlhaus_iocs("")) == []
