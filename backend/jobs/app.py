"""Procrastinate App factory. No-op unless PROCRASTINATE_ENABLED=1 and Postgres."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import procrastinate

_app: "procrastinate.App | None" = None
_opened = False


def is_procrastinate_enabled() -> bool:
    raw = os.environ.get("PROCRASTINATE_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _database_url() -> str | None:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url.startswith("postgres"):
        return None
    return (
        url.replace("postgresql+asyncpg://", "postgresql://", 1)
        .replace("postgres+asyncpg://", "postgresql://", 1)
        .replace("postgres://", "postgresql://", 1)
    )


def get_app(*, create: bool = True) -> "procrastinate.App | None":
    """Return the process-wide App, or None when disabled / not Postgres."""
    global _app
    if not is_procrastinate_enabled():
        return None
    dsn = _database_url()
    if not dsn:
        logger.warning(
            "PROCRASTINATE_ENABLED=1 but DATABASE_URL is not postgresql — durable jobs disabled"
        )
        return None
    if _app is not None:
        return _app
    if not create:
        return None
    import procrastinate

    from jobs.tasks import blueprint

    connector = procrastinate.PsycopgConnector(conninfo=dsn)
    app = procrastinate.App(
        connector=connector,
        worker_defaults={"concurrency": 1, "wait": True},
    )
    app.add_tasks_from(blueprint, namespace="jobs")
    _app = app
    return _app


async def open_app() -> "procrastinate.App | None":
    global _opened
    app = get_app()
    if app is None:
        return None
    if not _opened:
        await app.open_async()
        _opened = True
        logger.info("Procrastinate app opened")
    return app


async def close_app() -> None:
    global _app, _opened
    if _app is not None and _opened:
        try:
            await _app.close_async()
        except Exception:
            logger.exception("Procrastinate close_async failed")
    _opened = False
    _app = None


def reset_app_for_tests() -> None:
    """Test helper — clear process-wide App state."""
    global _app, _opened
    _app = None
    _opened = False
