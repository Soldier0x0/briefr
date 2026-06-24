"""Postgres connection wrapper behavior (no live Postgres required)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import PoolExhaustedError, PostgresConnection, get_connection


def test_postgres_close_releases_once_and_is_idempotent():
    raw = MagicMock()
    transaction = AsyncMock()
    raw.transaction.return_value = transaction
    pool = AsyncMock()

    async def _run() -> None:
        conn = PostgresConnection(raw, pool)
        await conn.close()
        await conn.close()
        pool.release.assert_awaited_once_with(raw)

    asyncio.run(_run())


def test_postgres_acquire_timeout_raises_pool_exhausted(monkeypatch):
    import db.connection as conn_mod

    pool = MagicMock()

    async def slow_acquire():
        await asyncio.sleep(60)

    pool.acquire = slow_acquire
    pool.get_size.return_value = 1
    pool.get_idle_size.return_value = 0
    pool.get_min_size.return_value = 1
    pool.get_max_size.return_value = 1
    conn_mod._pool = pool
    monkeypatch.setattr(conn_mod, "is_postgres", lambda: True)
    monkeypatch.setattr(
        "settings.settings.database_pool_acquire_timeout_seconds",
        1,
        raising=False,
    )

    async def _run() -> None:
        with pytest.raises(PoolExhaustedError, match="saturated"):
            await get_connection()

    try:
        asyncio.run(_run())
    finally:
        conn_mod._pool = None


def test_postgres_rollback_clears_failed_transaction():
    raw = MagicMock()
    transaction = AsyncMock()
    raw.transaction.return_value = transaction
    pool = AsyncMock()

    async def _run() -> None:
        conn = PostgresConnection(raw, pool)
        conn._transaction = transaction
        await conn.rollback()
        transaction.rollback.assert_awaited_once()
        assert conn._transaction is None

    asyncio.run(_run())


def test_postgres_close_releases_even_when_rollback_fails():
    raw = MagicMock()
    transaction = AsyncMock()
    transaction.rollback.side_effect = RuntimeError("in progress")
    raw.transaction.return_value = transaction
    pool = AsyncMock()

    async def _run() -> None:
        conn = PostgresConnection(raw, pool)
        conn._transaction = transaction
        await conn.close()
        pool.release.assert_awaited_once_with(raw)

    asyncio.run(_run())
