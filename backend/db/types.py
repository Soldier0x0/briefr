"""Shared database connection types."""

from __future__ import annotations

from typing import Any, Protocol


class ExecuteResult(Protocol):
    rowcount: int


class DbConnection(Protocol):
    async def execute(self, sql: str, params: tuple | list = ()) -> Any: ...

    async def execute_fetchall(self, sql: str, params: tuple | list = ()) -> list[Any]: ...

    async def executescript(self, sql: str) -> None: ...

    async def commit(self) -> None: ...

    async def close(self) -> None: ...
