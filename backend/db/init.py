"""DB init/bootstrap: get_db, init_db, run_postgres_migrations. Split from database.py (Phase 3).

Postgres-native: runtime fixup SQL is dialect-neutral (no placeholders).
Schema is applied via Alembic in ``run_postgres_migrations``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from db.config import is_postgres as is_postgres  # noqa: F401 — monkeypatch target
from db.connection import get_connection
from db.types import DbConnection

_NORMALIZE_EPSS_SCORES_SQL = (
    "UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0"
)

_CREATE_IDX_CVES_HAS_POC_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_cves_has_poc ON cves(has_poc)"
)

_CREATE_IDX_CVES_MODIFIED_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_cves_modified ON cves(modified)"
)

_ALEMBIC_VERSION_SQL = "SELECT version_num FROM alembic_version LIMIT 1"


async def get_db() -> DbConnection:
    """Return a PostgreSQL connection from the asyncpg pool."""
    return await get_connection()


async def _normalize_epss_scores(db: DbConnection) -> None:
    await db.execute(_NORMALIZE_EPSS_SCORES_SQL)


async def run_postgres_migrations() -> None:
    """Apply Alembic DDL before the asyncpg pool opens (avoids migration lock waits)."""
    import logging

    import asyncpg
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from db.config import postgres_dsn

    log = logging.getLogger(__name__)
    # __file__ is backend/db/init.py — alembic.ini lives in backend/, one
    # level up from this module's own directory (it was backend/database.py
    # before the Phase 3 split, where .parent already pointed at backend/).
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()

    current: str | None = None
    skip_alembic = False
    try:
        conn = await asyncpg.connect(postgres_dsn(), timeout=15)
        try:
            row = await conn.fetchrow(_ALEMBIC_VERSION_SQL)
            current = row["version_num"] if row else None
            skip_alembic = current == head
        except asyncpg.UndefinedTableError:
            current = None
        finally:
            await conn.close()
    except Exception as exc:
        log.warning(
            "database.py run_postgres_migrations(): version check failed (%s) — falling back to Alembic",
            exc,
        )

    if skip_alembic:
        log.info(
            "database.py run_postgres_migrations(): already at head (%s) — skipping Alembic",
            head,
        )
        return

    log.info(
        "database.py run_postgres_migrations(): current=%s head=%s — running Alembic upgrade head",
        current or "(none)",
        head,
    )
    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    except Exception as exc:
        log.error(
            "database.py run_postgres_migrations(): Alembic failed — %s. "
            "Check DATABASE_URL and that Postgres is running.",
            exc,
        )
        raise
    log.info("database.py run_postgres_migrations(): Alembic upgrade head finished")


async def _init_postgres_schema() -> None:
    db = await get_db()
    try:
        await _normalize_epss_scores(db)
        from blocklist.infra_seed import seed_infra_classifications

        await seed_infra_classifications(db)
        await db.commit()
    finally:
        await db.close()


async def init_db() -> None:
    """Apply runtime Postgres fixups. Schema comes from Alembic (session fixture / startup).

    Always uses the Postgres path. Tests that monkeypatch ``is_postgres`` to
    False (legacy SQLite isolation) must still initialize against the live
    PostgreSQL schema rather than SQLite ``executescript`` DDL.
    """
    await _init_postgres_schema()
