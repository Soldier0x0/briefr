"""Postgres connection wrapper behavior (no live Postgres required)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import PostgresConnection


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
