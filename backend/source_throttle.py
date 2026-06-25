"""Per-source asyncio pacing before outbound HTTP requests."""

from __future__ import annotations

import asyncio
import time

from source_rate_limits import get_min_interval

_last_call: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(source: str) -> asyncio.Lock:
    lock = _locks.get(source)
    if lock is None:
        lock = asyncio.Lock()
        _locks[source] = lock
    return lock


async def throttle_before_request(source: str) -> None:
    """Sleep if needed so consecutive calls to *source* respect min interval."""
    interval = get_min_interval(source)
    if interval <= 0:
        return
    async with _lock_for(source):
        now = time.monotonic()
        last = _last_call.get(source, 0.0)
        wait = interval - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[source] = time.monotonic()


def reset_throttle_state() -> None:
    """Test helper — clear pacing state."""
    _last_call.clear()
    _locks.clear()
