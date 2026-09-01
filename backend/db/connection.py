"""Async PostgreSQL connections via asyncpg pool."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from db.config import postgres_dsn
from db.pg_adapt import prepare_query
from db.errors import reraise_db_exception
from settings import settings

logger = logging.getLogger(__name__)

_pool: Any | None = None


def _pool_loop_matches_running(pool: Any) -> bool:
    """True when *pool* was created on the currently running event loop."""
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        return False
    pool_loop = getattr(pool, "_loop", None)
    if not isinstance(pool_loop, asyncio.AbstractEventLoop):
        return True
    return pool_loop is running and not pool_loop.is_closed()


class PoolExhaustedError(RuntimeError):
    """Raised when asyncpg pool.acquire() exceeds the configured timeout."""


def get_pool_stats() -> dict[str, int] | None:
    """Return asyncpg pool counters."""
    if _pool is None:
        return None
    size = _pool.get_size()
    idle = _pool.get_idle_size()
    return {
        "size": size,
        "idle": idle,
        "in_use": max(0, size - idle),
        "min": _pool.get_min_size(),
        "max": _pool.get_max_size(),
    }


@dataclass
class _ExecuteResult:
    rowcount: int


class PostgresConnection:
    """asyncpg-backed connection with legacy placeholder translation."""

    def __init__(self, conn: Any, pool: Any) -> None:
        self._conn: Any | None = conn
        self._pool = pool
        self._transaction = None

    async def _ensure_transaction(self) -> None:
        if self._transaction is None:
            self._transaction = self._conn.transaction()
            await self._transaction.start()

    async def execute(self, sql: str, params: tuple | list | dict = ()) -> _ExecuteResult:
        try:
            await self._ensure_transaction()
            adapted, bound = prepare_query(sql, params, backend="postgresql")
            status = await self._conn.execute(adapted, *bound)
            rowcount = 0
            if status:
                parts = status.split()
                if parts and parts[-1].isdigit():
                    rowcount = int(parts[-1])
            return _ExecuteResult(rowcount=rowcount)
        except Exception as exc:
            reraise_db_exception(exc)

    async def execute_fetchall(self, sql: str, params: tuple | list | dict = ()) -> list[Any]:
        try:
            await self._ensure_transaction()
            adapted, bound = prepare_query(sql, params, backend="postgresql")
            records = await self._conn.fetch(adapted, *bound)
            return [dict(record) for record in records]
        except Exception as exc:
            reraise_db_exception(exc)

    async def executemany(
        self, sql: str, params_list: list[tuple | list | dict]
    ) -> _ExecuteResult:
        try:
            await self._ensure_transaction()
            adapted, _ = prepare_query(sql, params_list[0] if params_list else (), backend="postgresql")
            adapted_params = [
                prepare_query(sql, p, backend="postgresql")[1] for p in params_list
            ]
            await self._conn.executemany(adapted, adapted_params)
            return _ExecuteResult(rowcount=len(params_list))
        except Exception as exc:
            reraise_db_exception(exc)

    async def executescript(self, sql: str) -> None:
        raise NotImplementedError(
            "executescript() is not supported — use Alembic migrations"
        )

    async def commit(self) -> None:
        if self._transaction is not None:
            await self._transaction.commit()
            self._transaction = None

    async def rollback(self) -> None:
        if self._transaction is not None:
            try:
                await self._transaction.rollback()
            finally:
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
    """Create the PostgreSQL connection pool."""
    global _pool
    if _pool is not None:
        if _pool_loop_matches_running(_pool):
            return
        # pytest-asyncio (function scope) and run_db_test's asyncio.run() each
        # use distinct loops — drop a pool bound to a closed/other loop.
        _pool = None
    import asyncpg

    dsn = postgres_dsn()
    max_size = max(1, settings.database_pool_size)
    command_timeout = max(1, settings.database_pool_command_timeout_seconds)
    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=max_size,
            command_timeout=command_timeout,
            max_inactive_connection_lifetime=300,
            server_settings={"search_path": "app, intel, public"},
        )
    except Exception as exc:
        logger.error(
            "db/connection.py init_pool(): cannot connect to PostgreSQL at %s — %s",
            dsn.split("@")[-1] if "@" in dsn else dsn,
            exc,
        )
        raise
    logger.info(
        "db/connection.py init_pool(): PostgreSQL pool ready "
        "(max_size=%d, command_timeout=%ds)",
        max_size,
        command_timeout,
    )


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    pool = _pool
    _pool = None
    if not _pool_loop_matches_running(pool):
        return
    try:
        await asyncio.wait_for(pool.close(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning(
            "db/connection.py close_pool(): timed out after 5s — "
            "connections may still be leaked; process exit will reclaim them"
        )


async def get_connection() -> PostgresConnection:
    if _pool is None or not _pool_loop_matches_running(_pool):
        await init_pool()
    acquire_timeout = max(1.0, float(settings.database_pool_acquire_timeout_seconds))
    try:
        raw = await asyncio.wait_for(_pool.acquire(), timeout=acquire_timeout)
    except asyncio.TimeoutError:
        stats = get_pool_stats() or {}
        logger.error(
            "db/connection.py get_connection(): pool acquire timed out after %.1fs — %s",
            acquire_timeout,
            stats,
        )
        raise PoolExhaustedError(
            f"PostgreSQL pool saturated (acquire timed out after {acquire_timeout:.0f}s)"
        ) from None
    return PostgresConnection(raw, _pool)
