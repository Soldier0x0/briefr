"""Per-source minimum request intervals for outbound API calls.

BRIEFR paces outbound HTTP to stay within provider rate limits. OTX with an
API key allows ~10,000 requests/hour; we target ~7,200/hour (2 req/sec) to
leave headroom for bursts and other jobs.
"""

from __future__ import annotations

import os

# source_id -> minimum seconds between consecutive requests
_SOURCE_MIN_INTERVAL: dict[str, float] = {
    "otx": 0.5,
    "github": 0.12,
    "nvd": 0.6,
    "groq": float(os.environ.get("GROQ_MIN_REQUEST_INTERVAL_SECONDS", "2")),
}


def get_min_interval(source: str) -> float:
    """Seconds to wait after the previous request to the same source."""
    return max(0.0, float(_SOURCE_MIN_INTERVAL.get(source, 0.0)))


def get_otx_hourly_limit() -> int:
    """OTX authenticated tier: 10,000 requests/hour."""
    return max(1, int(os.environ.get("OTX_HOURLY_LIMIT", "10000")))
