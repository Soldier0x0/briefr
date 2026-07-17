"""In-process Procrastinate worker lifecycle (single-box default)."""

from __future__ import annotations

import asyncio
import logging

from task_registry import register_background_task

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def start_inprocess_worker() -> bool:
    """Start a background worker when Procrastinate is enabled. Returns True if started."""
    global _worker_task
    from jobs.app import is_procrastinate_enabled, open_app

    if not is_procrastinate_enabled():
        return False
    app = await open_app()
    if app is None:
        return False
    if _worker_task is not None and not _worker_task.done():
        return True

    async def _run() -> None:
        logger.info("Procrastinate in-process worker starting (queue=briefr)")
        try:
            await app.run_worker_async(queues=["briefr"], concurrency=1, wait=True)
        except asyncio.CancelledError:
            logger.info("Procrastinate worker cancelled")
            raise
        except Exception:
            logger.exception("Procrastinate worker exited with error")

    _worker_task = register_background_task(asyncio.create_task(_run(), name="procrastinate-worker"))
    return True


async def stop_inprocess_worker() -> None:
    global _worker_task
    from jobs.app import close_app

    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):
            pass
    _worker_task = None
    await close_app()
