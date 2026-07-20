"""Durable Procrastinate coverage for LLM product extraction (Wave 2)."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
import sys

from procrastinate.exceptions import AlreadyEnqueued

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test
from tests.test_job_ownership_registry import _defined_procrastinate_tasks


def test_llm_extraction_task_registered():
    assert "llm_product_extraction" in _defined_procrastinate_tasks()


def test_llm_extraction_task_uses_pool_scoped_job_context(monkeypatch):
    import jobs.tasks as tasks

    calls = []
    contexts = []

    @contextmanager
    def fake_outbound_context(**kwargs):
        contexts.append(kwargs)
        yield

    async def fake_run_llm_product_extraction(db=None, progress_cb=None):
        calls.append({"db": db, "progress_cb": progress_cb})
        return {"candidates": 1, "extracted": 1, "written": 1, "errors": 0}

    monkeypatch.setattr(tasks, "outbound_context", fake_outbound_context)
    monkeypatch.setattr(
        tasks,
        "run_llm_product_extraction",
        fake_run_llm_product_extraction,
    )

    result = asyncio.run(tasks.llm_product_extraction_tick(trigger="unit"))

    assert result == {"candidates": 1, "extracted": 1, "written": 1, "errors": 0}
    assert calls == [{"db": None, "progress_cb": None}]
    assert contexts == [
        {
            "actor_type": "queue",
            "queue_task": "jobs:llm_product_extraction",
            "trigger": "unit",
        }
    ]


def test_llm_extraction_task_redefers_retryable_failure(monkeypatch):
    import jobs.tasks as tasks

    configured = []
    deferred = []
    task = tasks.llm_product_extraction_tick

    class FakeDeferrer:
        async def defer_async(self, **kwargs):
            deferred.append(kwargs)
            return 42

    class FakeTask:
        def configure(self, **kwargs):
            configured.append(kwargs)
            return FakeDeferrer()

    @contextmanager
    def fake_outbound_context(**_kwargs):
        yield

    async def fail_with_timeout(db=None, progress_cb=None):
        raise TimeoutError("Database command timeout")

    monkeypatch.setattr(tasks, "llm_product_extraction_tick", FakeTask())
    monkeypatch.setattr(tasks, "outbound_context", fake_outbound_context)
    monkeypatch.setattr(tasks, "run_llm_product_extraction", fail_with_timeout)

    result = asyncio.run(task(trigger="unit", attempts=1))

    assert result == {
        "ok": False,
        "retry_scheduled": True,
        "attempts": 1,
        "retry_in_seconds": 180,
    }
    assert configured == [
        {
            "queueing_lock": "llm_product_extraction",
            "schedule_in": {"seconds": 180},
        }
    ]
    assert deferred == [{"trigger": "unit", "attempts": 2}]


def test_scheduler_defers_llm_extraction_when_procrastinate_enabled(monkeypatch):
    import scheduler

    configured = []
    deferred = []
    last_runs = []

    class FakeDeferrer:
        async def defer_async(self, **kwargs):
            deferred.append(kwargs)
            return 99

    class FakeTask:
        def configure(self, **kwargs):
            configured.append(kwargs)
            return FakeDeferrer()

    async def fake_open_app():
        return object()

    async def fail_if_inline(*_args, **_kwargs):
        raise AssertionError("scheduler used inline LLM extraction despite durable queue")

    async def fake_write_last_run(job_id, started_at, *, had_error, error_message=""):
        last_runs.append(
            {
                "job_id": job_id,
                "started_at": started_at,
                "had_error": had_error,
                "error_message": error_message,
            }
        )

    monkeypatch.setattr(scheduler, "llm_product_extraction_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "is_procrastinate_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "open_app", fake_open_app)
    monkeypatch.setattr(scheduler, "llm_product_extraction_tick", FakeTask())
    monkeypatch.setattr(scheduler, "run_llm_product_extraction", fail_if_inline)
    monkeypatch.setattr(scheduler, "_write_job_last_run", fake_write_last_run)

    assert run_db_test(scheduler.run_llm_extraction_sync()) is True
    assert configured == [{"queueing_lock": "llm_product_extraction"}]
    assert deferred == [{"trigger": "scheduler"}]
    assert last_runs[0]["job_id"] == "llm_product_extraction"
    assert last_runs[0]["had_error"] is False
    assert last_runs[0]["error_message"] == ""


def test_scheduler_treats_already_enqueued_as_success(monkeypatch):
    import scheduler

    last_runs = []

    class FakeDeferrer:
        async def defer_async(self, **_kwargs):
            raise AlreadyEnqueued()

    class FakeTask:
        def configure(self, **_kwargs):
            return FakeDeferrer()

    async def fake_open_app():
        return object()

    async def fake_write_last_run(job_id, started_at, *, had_error, error_message=""):
        last_runs.append((job_id, had_error, error_message))

    monkeypatch.setattr(scheduler, "llm_product_extraction_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "is_procrastinate_enabled", lambda: True)
    monkeypatch.setattr(scheduler, "open_app", fake_open_app)
    monkeypatch.setattr(scheduler, "llm_product_extraction_tick", FakeTask())
    monkeypatch.setattr(scheduler, "_write_job_last_run", fake_write_last_run)

    assert run_db_test(scheduler.run_llm_extraction_sync()) is True
    assert last_runs == [("llm_product_extraction", False, "")]
