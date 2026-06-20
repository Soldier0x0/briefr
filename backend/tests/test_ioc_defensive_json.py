"""Defensive JSON parsing for quota-billed IOC enrichment APIs."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enrichment import ioc


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_quota_safe_get_rejects_non_dict_json(monkeypatch):
    monkeypatch.setattr(
        ioc,
        "resilient_get",
        AsyncMock(return_value=_FakeResponse(["not", "a", "dict"])),
    )

    result = asyncio.run(
        ioc._quota_safe_get(
            "virustotal",
            "https://example.test/ip",
            headers={},
            label="ip 1.2.3.4",
        )
    )
    assert result == {}
