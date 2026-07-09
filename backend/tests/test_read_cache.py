"""Tests for in-process read TTL cache (Track I5)."""

import asyncio

from read_cache import clear_read_cache, cached_read


def test_cached_read_hits_within_ttl():
    clear_read_cache()
    calls = 0

    async def build():
        nonlocal calls
        calls += 1
        return {"n": calls}

    async def run():
        first = await cached_read("k", 60.0, build)
        second = await cached_read("k", 60.0, build)
        return first, second

    first, second = asyncio.run(run())
    assert first == {"n": 1}
    assert second == {"n": 1}
    assert calls == 1
