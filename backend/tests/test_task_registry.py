"""PR-R1: task registry + bounded graceful shutdown."""

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_registry
from task_registry import (
    drain_background_tasks,
    pending_background_tasks,
    register_background_task,
    shutdown_drain_timeout_seconds,
    spawn_background_task,
)


def test_shutdown_drain_timeout_default_and_env(monkeypatch):
    monkeypatch.delenv("SHUTDOWN_DRAIN_TIMEOUT_SECONDS", raising=False)
    assert shutdown_drain_timeout_seconds() == 10.0
    monkeypatch.setenv("SHUTDOWN_DRAIN_TIMEOUT_SECONDS", "3.5")
    assert shutdown_drain_timeout_seconds() == 3.5
    monkeypatch.setenv("SHUTDOWN_DRAIN_TIMEOUT_SECONDS", "not-a-number")
    assert shutdown_drain_timeout_seconds() == 10.0
    monkeypatch.setenv("SHUTDOWN_DRAIN_TIMEOUT_SECONDS", "-5")
    assert shutdown_drain_timeout_seconds() == 0.0


def test_drain_waits_for_registered_tasks():
    async def _run():
        done = []

        async def _work():
            await asyncio.sleep(0.05)
            done.append(True)

        spawn_background_task(_work())
        spawn_background_task(_work())
        assert pending_background_tasks() == 2
        remaining = await drain_background_tasks(timeout=2.0)
        assert remaining == 0
        assert len(done) == 2
        assert pending_background_tasks() == 0

    asyncio.run(_run())


def test_drain_bounded_leaves_stuck_task():
    async def _run():
        stop = asyncio.Event()

        async def _stuck():
            await stop.wait()

        task = spawn_background_task(_stuck())
        start = time.monotonic()
        remaining = await drain_background_tasks(timeout=0.2)
        elapsed = time.monotonic() - start
        assert remaining == 1
        assert elapsed < 2.0
        stop.set()
        await task

    asyncio.run(_run())


def test_register_discards_on_completion():
    async def _run():
        async def _noop():
            return None

        task = register_background_task(asyncio.create_task(_noop()))
        await task
        # done callback runs soon after completion
        await asyncio.sleep(0)
        assert task not in task_registry._tasks

    asyncio.run(_run())


def test_failed_background_task_exception_is_retrieved(caplog):
    async def _run():
        async def _boom():
            raise RuntimeError("boom")

        task = spawn_background_task(_boom())
        await asyncio.wait({task})
        await asyncio.sleep(0)
        assert task not in task_registry._tasks

    with caplog.at_level(logging.ERROR, logger="task_registry"):
        asyncio.run(_run())

    logged = [
        record
        for record in caplog.records
        if record.name == "task_registry"
        and record.exc_info
        and isinstance(record.exc_info[1], RuntimeError)
        and str(record.exc_info[1]) == "boom"
    ]
    assert logged


def test_wait_for_running_jobs_returns_empty_when_idle():
    from scheduler import wait_for_running_jobs

    async def _run():
        assert await wait_for_running_jobs(timeout=0.5) == []

    asyncio.run(_run())


def test_wait_for_running_jobs_reports_stuck_lock():
    import scheduler_locks
    from scheduler import wait_for_running_jobs

    async def _run():
        lock = scheduler_locks.get_lock("kev_metadata_sync")
        await lock.acquire()
        try:
            running = await wait_for_running_jobs(timeout=0.3)
            assert "kev_metadata_sync" in running
        finally:
            lock.release()
        assert await wait_for_running_jobs(timeout=0.3) == []

    asyncio.run(_run())
