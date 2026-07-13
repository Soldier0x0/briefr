"""OTX pulse IOC ingest — observed_at from indicator created timestamp."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.otx import fetch_pulse_iocs


def test_fetch_pulse_iocs_captures_indicator_created(monkeypatch):
    async def _fake_otx_get(url, api_key, **kwargs):
        return {
            "results": [
                {
                    "type": "domain",
                    "indicator": "evil.example",
                    "description": "C2",
                    "created": "2024-03-01T08:30:00.000Z",
                },
                {
                    "indicator_type": "IPv4",
                    "content": "203.0.113.9",
                    "title": "beacon",
                },
            ]
        }

    monkeypatch.setattr("feeds.otx._otx_get", _fake_otx_get)

    rows = asyncio.run(fetch_pulse_iocs("pulse-abc", "fake-key"))
    assert len(rows) == 2
    assert rows[0]["observed_at"] == "2024-03-01T08:30:00.000Z"
    assert rows[1]["observed_at"] is None
