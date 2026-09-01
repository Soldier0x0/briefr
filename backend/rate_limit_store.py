"""Optional shared rate-limit bucket state (Track I Phase 3b).

When ``BRIEFR_RATE_LIMIT_STORE=db``, token buckets persist in ``sync_state``
so multiple uvicorn workers share limits. Default remains in-memory (single
worker) for zero-config tests and dev.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

_STORE_PREFIX = "rate_limit:"


def shared_store_enabled() -> bool:
    return os.environ.get("BRIEFR_RATE_LIMIT_STORE", "").strip().lower() in (
        "db",
        "1",
        "true",
        "yes",
    )


def _state_key(bucket_name: str, client_key: str) -> str:
    return f"{_STORE_PREFIX}{bucket_name}:{client_key}"


def _sqlite_path() -> str:
    from settings import settings

    return settings.db_path


def _postgres_dsn() -> str | None:
    from db.config import resolve_database_url

    url = resolve_database_url()
    if url and url.startswith("postgresql"):
        return url
    return None


def _load_sqlite(key: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(_sqlite_path(), timeout=5.0)
    try:
        row = conn.execute(
            "SELECT value FROM sync_state WHERE key = ?",
            (key,),
        ).fetchone()
        if not row or not row[0]:
            return None
        data = json.loads(row[0])
        return data if isinstance(data, dict) else None
    finally:
        conn.close()


def _save_sqlite(key: str, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(_sqlite_path(), timeout=5.0)
    try:
        conn.execute(
            """
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(payload)),
        )
        conn.commit()
    finally:
        conn.close()


def _load_postgres(key: str) -> dict[str, Any] | None:
    import psycopg

    dsn = _postgres_dsn()
    if not dsn:
        return None
    with psycopg.connect(
        dsn,
        connect_timeout=5,
        options="-c search_path=app,intel,public",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM sync_state WHERE key = %s", (key,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            data = json.loads(row[0])
            return data if isinstance(data, dict) else None


def _save_postgres(key: str, payload: dict[str, Any]) -> None:
    import psycopg

    dsn = _postgres_dsn()
    if not dsn:
        return
    with psycopg.connect(
        dsn,
        connect_timeout=5,
        options="-c search_path=app,intel,public",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_state (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW()
                """,
                (key, json.dumps(payload)),
            )
        conn.commit()


def _load_state(key: str) -> dict[str, Any] | None:
    if _postgres_dsn():
        return _load_postgres(key)
    return _load_sqlite(key)


def _save_state(key: str, payload: dict[str, Any]) -> None:
    if _postgres_dsn():
        _save_postgres(key, payload)
    else:
        _save_sqlite(key, payload)


def shared_acquire(
    bucket_name: str,
    client_key: str,
    *,
    rate_per_minute: int,
    now: float | None = None,
) -> float:
    """Try to take one token from the shared store. Returns retry_after seconds."""
    if now is None:
        now = time.monotonic()
    rate = max(1, int(rate_per_minute))
    capacity = float(rate)
    refill_per_second = rate / 60.0
    state_key = _state_key(bucket_name, client_key)

    stored = _load_state(state_key) or {}
    tokens = float(stored.get("tokens", capacity))
    last = float(stored.get("last", now))
    hits = int(stored.get("hits", 0)) + 1

    tokens = min(capacity, tokens + (now - last) * refill_per_second)
    if tokens >= 1.0:
        tokens -= 1.0
        _save_state(
            state_key,
            {"tokens": tokens, "last": now, "hits": hits},
        )
        return 0.0

    _save_state(state_key, {"tokens": tokens, "last": now, "hits": hits})
    return (1.0 - tokens) / refill_per_second
