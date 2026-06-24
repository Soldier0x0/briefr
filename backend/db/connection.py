"""Async database connections for SQLite (default) and PostgreSQL (optional)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import aiosqlite
import os

from db.config import is_postgres, postgres_dsn, resolve_database_url
from db.dialect import adapt_params, prepare_query

logger = logging.getLogger(__name__)

_pool: Any | None = None


@dataclass
class _ExecuteResult:
    rowcount: int


class SqliteConnection:
    """Thin wrapper so callers share the same surface as PostgreSQL."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def execute(self, sql: str, params: tuple | list = ()) -> _ExecuteResult:
        cursor = await self._conn.execute(sql, adapt_params(params))
        return _ExecuteResult(rowcount=cursor.rowcount if cursor.rowcount is not None else 0)

    async def execute_fetchall(self, sql: str, params: tuple | list = ()) -> list[Any]:
        cursor = await self._conn.execute(sql, adapt_params(params))
        rows = await cursor.fetchall()
        return list(rows)

    async def executemany(
        self, sql: str, params_list: list[tuple | list]
    ) -> _ExecuteResult:
        cursor = await self._conn.executemany(
            sql, [adapt_params(p) for p in params_list]
        )
        return _ExecuteResult(rowcount=cursor.rowcount if cursor.rowcount is not None else 0)

    async def executescript(self, sql: str) -> None:
        await self._conn.executescript(sql)

    async def commit(self) -> None:
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()


class PostgresConnection:
    """asyncpg-backed connection with SQLite placeholder translation."""

    def __init__(self, conn: Any, pool: Any) -> None:
        self._conn: Any | None = conn
        self._pool = pool
        self._transaction = None

    async def _ensure_transaction(self) -> None:
        if self._transaction is None:
            self._transaction = self._conn.transaction()
            await self._transaction.start()

    async def execute(self, sql: str, params: tuple | list | dict = ()) -> _ExecuteResult:
        await self._ensure_transaction()
        adapted, bound = prepare_query(sql, params, backend="postgresql")
        status = await self._conn.execute(adapted, *bound)
        rowcount = 0
        if status:
            parts = status.split()
            if parts and parts[-1].isdigit():
                rowcount = int(parts[-1])
        return _ExecuteResult(rowcount=rowcount)

    async def execute_fetchall(self, sql: str, params: tuple | list | dict = ()) -> list[Any]:
        await self._ensure_transaction()
        adapted, bound = prepare_query(sql, params, backend="postgresql")
        records = await self._conn.fetch(adapted, *bound)
        return [dict(record) for record in records]

    async def executemany(
        self, sql: str, params_list: list[tuple | list | dict]
    ) -> _ExecuteResult:
        await self._ensure_transaction()
        adapted, _ = prepare_query(sql, params_list[0] if params_list else (), backend="postgresql")
        adapted_params = [
            prepare_query(sql, p, backend="postgresql")[1] for p in params_list
        ]
        await self._conn.executemany(adapted, adapted_params)
        return _ExecuteResult(rowcount=len(params_list))

    async def executescript(self, sql: str) -> None:
        raise NotImplementedError(
            "executescript() is SQLite-only — use Alembic migrations on PostgreSQL"
        )

    async def commit(self) -> None:
        if self._transaction is not None:
            await self._transaction.commit()
            self._transaction = None

    async def close(self) -> None:
        if self._conn is None:
            return
        try:
            if self._transaction is not None:
                await self._transaction.rollback()
        except Exception as exc:
            logger.warning(
                "PostgresConnection.close(): rollback failed (%s) — releasing anyway",
                exc,
            )
        finally:
            self._transaction = None
            conn, self._conn = self._conn, None
            await self._pool.release(conn)


async def init_pool() -> None:
    """Create the PostgreSQL pool when ``DATABASE_URL`` points at Postgres."""
    global _pool
    if not is_postgres():
        return
    if _pool is not None:
        return
    import asyncpg

    dsn = postgres_dsn()
    max_size = max(1, int(os.environ.get("DATABASE_POOL_SIZE", "10")))
    try:
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=max_size)
    except Exception as exc:
        logger.error(
            "db/connection.py init_pool(): cannot connect to PostgreSQL at %s — %s",
            dsn.split("@")[-1] if "@" in dsn else dsn,
            exc,
        )
        raise
    logger.info("db/connection.py init_pool(): PostgreSQL pool ready (max_size=%d)", max_size)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await asyncio.wait_for(_pool.close(), timeout=5.0)
        except TimeoutError:
            logger.warning(
                "db/connection.py close_pool(): timed out after 5s — "
                "connections may still be leaked; process exit will reclaim them"
            )
        _pool = None


async def get_connection() -> SqliteConnection | PostgresConnection:
    if is_postgres():
        if _pool is None:
            logger.error(
                "db/connection.py get_connection(): PostgreSQL pool is not open. "
                "DATABASE_URL is set but main.py startup did not finish (or the backend is restarting). "
                "Fix: systemctl restart briefr-backend and check journalctl for startup errors."
            )
            raise RuntimeError(
                "PostgreSQL pool is not initialized — call init_pool() during app startup"
            )
        raw = await _pool.acquire()
        return PostgresConnection(raw, _pool)

    # Lazy import (avoids a circular import with database.py) and read the
    # module attribute directly rather than db.config.resolve_database_url():
    # the latter resolves through the Settings singleton, which is frozen at
    # process start and does not observe per-test monkeypatch.setattr /
    # monkeypatch.setenv("DB_PATH", ...) overrides that the existing test
    # suite relies on for per-test database isolation.
    import database

    path = database.DB_PATH
    conn = await aiosqlite.connect(path, timeout=30)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.execute("PRAGMA foreign_keys=ON")
    return SqliteConnection(conn)
