"""In-process HTTP request counter — read-and-reset by the resource collector."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_count = 0


def increment_request_count() -> None:
    global _count
    with _lock:
        _count += 1


def read_and_reset_request_count() -> int:
    global _count
    with _lock:
        value = _count
        _count = 0
        return value


def reset_for_tests() -> None:
    global _count
    with _lock:
        _count = 0
