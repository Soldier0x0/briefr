"""Unit tests for Feodo and PhishTank catalog feed parsers."""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.feodo import _parse_feodo_csv, parse_feodo_row
from feeds.phishtank import fetch_phishtank_iocs, parse_phishtank_row


def test_parse_feodo_row_maps_ip():
    row = parse_feodo_row({
        "first_seen_utc": "2026-01-13 21:41:15",
        "dst_ip": "34.204.119.63",
        "dst_port": "443",
        "c2_status": "online",
        "malware": "QakBot",
    })
    assert row is not None
    assert row["ioc_type"] == "ip"
    assert row["ioc_value"] == "34.204.119.63"
    assert row["ioc_id"] == "34.204.119.63:443"


def test_parse_feodo_csv_skips_comments():
    text = """#
"first_seen_utc","dst_ip","dst_port","c2_status","last_online","malware"
"2026-01-13 21:41:15","1.2.3.4","443","online","2026-03-01","QakBot"
"""
    rows = _parse_feodo_csv(text)
    assert len(rows) == 1
    assert rows[0]["ioc_value"] == "1.2.3.4"


def test_parse_phishtank_row_requires_verified_online():
    assert parse_phishtank_row({
        "phish_id": "1",
        "url": "https://evil.example/phish",
        "verified": "no",
        "online": "yes",
    }) is None
    assert parse_phishtank_row({
        "phish_id": "2",
        "url": "https://evil.example/offline",
        "verified": "yes",
        "online": "no",
    }) is None

    row = parse_phishtank_row({
        "phish_id": "9506592",
        "url": "https://wvc3bayjg.com/Cxpu5t",
        "verified": "yes",
        "online": "yes",
        "verification_time": "2026-08-18T03:12:32+00:00",
        "target": "Apple",
    })
    assert row is not None
    assert row["ioc_type"] == "url"
    assert row["host_ioc"] == "wvc3bayjg.com"
    assert row["threat_type"] == "phishing:Apple"


def test_fetch_phishtank_iocs_kwargs_match_resilient_request(monkeypatch):
    """PhishTank must not pass kwargs resilient_request does not accept."""
    import httpx
    from resilient_client import resilient_request

    seen = {}

    async def fake_request(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        inspect.signature(resilient_request).bind(*args, **kwargs)
        return httpx.Response(
            200,
            text=(
                "phish_id,url,verified,online,verification_time,target\n"
                "9506592,https://wvc3bayjg.com/Cxpu5t,yes,yes,2026-08-18T03:12:32+00:00,Apple\n"
            ),
        )

    async def fake_record(*_args, **_kwargs):
        return None

    monkeypatch.setattr("feeds.phishtank.resilient_request", fake_request)
    monkeypatch.setattr("feeds.phishtank.record_api_call", fake_record)

    rows = asyncio.run(fetch_phishtank_iocs())
    assert len(rows) == 1
    assert "follow_redirects" not in seen["kwargs"]

