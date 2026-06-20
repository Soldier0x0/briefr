"""Database backend abstraction (V2.0 foundation).

SQLite remains the default. Set ``DATABASE_URL`` to a ``postgresql://`` DSN to
use PostgreSQL (beta — see ``docs/POSTGRES.md``).
"""

from db.config import (
    database_backend,
    get_database_url,
    is_postgres,
    is_sqlite,
    resolve_database_url,
)
from db.connection import close_pool, get_connection, init_pool
from db.types import DbConnection

__all__ = [
    "DbConnection",
    "close_pool",
    "database_backend",
    "get_connection",
    "get_database_url",
    "init_pool",
    "is_postgres",
    "is_sqlite",
    "resolve_database_url",
]
