"""Tests for advisory LLM quota snapshots."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.quota import get_quota_snapshot, quota_warnings, record_quota_snapshot


class _Headers:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


def test_record_and_read_quota_snapshot():
    record_quota_snapshot(
        "groq",
        _Headers({
            "x-ratelimit-remaining-requests": "42",
            "x-ratelimit-reset-requests": "1m",
        }),
    )
    snap = get_quota_snapshot("groq")
    assert snap is not None
    assert snap["remaining_requests"] == "42"


def test_quota_warnings_low_remaining():
    record_quota_snapshot(
        "gemini",
        _Headers({"x-ratelimit-remaining-requests": "2"}),
    )
    warnings = quota_warnings()
    assert any("gemini" in w for w in warnings)
