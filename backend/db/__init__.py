"""Database backend — PostgreSQL + pgvector only."""

from db.config import (
    database_backend,
    get_database_url,
    is_postgres,
    is_sqlite,
    resolve_database_url,
)
from db.connection import PoolExhaustedError, close_pool, get_connection, get_pool_stats, init_pool
from db.types import DbConnection

__all__ = [
    "DbConnection",
    "PoolExhaustedError",
    "close_pool",
    "database_backend",
    "get_connection",
    "get_database_url",
    "get_pool_stats",
    "init_pool",
    "is_postgres",
    "is_sqlite",
    "resolve_database_url",
]
