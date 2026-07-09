"""In-process TTL cache for hot read endpoints (Track I5).

No Redis — dict + monotonic clock. Tests call ``clear_read_cache()`` between cases.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_store: dict[str, tuple[float, Any]] = {}
DEFAULT_TTL_SECONDS = 45.0


async def cached_read(
    key: str,
    ttl: float,
    build: Callable[[], Awaitable[T]],
) -> T:
    """Return cached value when fresh; otherwise await ``build()`` and store."""
    now = time.monotonic()
    hit = _store.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = await build()
    _store[key] = (now, value)
    return value


def clear_read_cache() -> None:
    """Clear all entries (tests only)."""
    _store.clear()
