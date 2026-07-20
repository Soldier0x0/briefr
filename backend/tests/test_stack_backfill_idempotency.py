"""Regression tests for stack-backfill idempotency (IDEM-A / IDEM-B).

IDEM-A — ``claim_run_running`` is the atomic single-winner gate that stops a
duplicate resume / retry from double-running one ``run_id``. IDEM-B — the
Procrastinate defer carries a per-run ``queueing_lock`` (asserted structurally,
since a live queue is not available in the default SQLite suite).

All DB work is on in-memory-style SQLite via a temp DB_PATH — no live server.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.conftest import run_db_test

from db.stack_backfill import claim_run_running, create_run, get_run, update_run


def _setup_db(tmp_path):
    db_file = str(tmp_path / "backfill_idem.db")
    os.environ["DB_PATH"] = db_file
    return db_file


async def _make_run(db_module) -> int:
    db = await db_module.get_db()
    try:
        run_id = await create_run(
            db,
            user_id=1,
            products=[{"product_key": "::nginx", "vendor": "", "product": "nginx", "version": ""}],
            eta={"eta_low_seconds": 1, "eta_high_seconds": 2},
        )
        await db.commit()
        return run_id
    finally:
        await db.close()


def test_claim_is_single_winner_then_blocks_duplicates(tmp_path):
    db_file = _setup_db(tmp_path)

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()
        run_id = await _make_run(db_module)

        # First claim wins and moves the run into 'running'.
        db = await db_module.get_db()
        try:
            assert await claim_run_running(db, run_id) is True
            await db.commit()
        finally:
            await db.close()

        row = await _run_row(db_module, run_id)
        assert row["status"] == "running"

        # A second claim while the run is freshly running loses — no double-run.
        db = await db_module.get_db()
        try:
            assert await claim_run_running(db, run_id) is False
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())


def test_stale_running_run_is_reclaimable(tmp_path):
    db_file = _setup_db(tmp_path)

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()
        run_id = await _make_run(db_module)

        db = await db_module.get_db()
        try:
            assert await claim_run_running(db, run_id) is True
            await db.commit()
        finally:
            await db.close()

        # Simulate a crashed worker: push the heartbeat far into the past.
        # update_run() always stamps updated_at=now, so set it with a direct
        # dialect-aware UPDATE instead.
        from db.config import is_postgres

        old = datetime.now(timezone.utc) - timedelta(hours=2)
        db = await db_module.get_db()
        try:
            if is_postgres():
                await db.execute(
                    "UPDATE stack_backfill_runs SET updated_at = $2 WHERE id = $1",
                    (run_id, old),
                )
            else:
                await db.execute(
                    "UPDATE stack_backfill_runs SET updated_at = ? WHERE id = ?",
                    (old.replace(tzinfo=None).isoformat(sep=" "), run_id),
                )
            await db.commit()
        finally:
            await db.close()

        # A stale 'running' run can be reclaimed so it is not stuck forever.
        db = await db_module.get_db()
        try:
            assert await claim_run_running(db, run_id) is True
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())


def test_terminal_run_is_never_reclaimed(tmp_path):
    db_file = _setup_db(tmp_path)

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()
        run_id = await _make_run(db_module)

        db = await db_module.get_db()
        try:
            await update_run(db, run_id, status="completed")
            await db.commit()
        finally:
            await db.close()

        db = await db_module.get_db()
        try:
            assert await claim_run_running(db, run_id) is False
            await db.commit()
        finally:
            await db.close()

        row = await _run_row(db_module, run_id)
        assert row["status"] == "completed"

    run_db_test(run())


def test_rate_limited_run_schedules_durable_resume(tmp_path, monkeypatch):
    db_file = _setup_db(tmp_path)
    configured = []
    deferred = []

    class FakeDeferrer:
        async def defer_async(self, **kwargs):
            deferred.append(kwargs)
            return 123

    class FakeTask:
        def configure(self, **kwargs):
            configured.append(kwargs)
            return FakeDeferrer()

    async def fake_page(*_args, **_kwargs):
        return [], 0, "rate_limited"

    async def fake_open_app():
        return object()

    async def run():
        import database as db_module
        import services.stack_backfill_worker as worker

        db_module.DB_PATH = db_file
        await db_module.init_db()
        run_id = await _make_run(db_module)

        monkeypatch.setattr(worker, "fetch_cves_keyword_page", fake_page)
        monkeypatch.setattr(worker, "is_procrastinate_enabled", lambda: True, raising=False)
        monkeypatch.setattr(worker, "open_app", fake_open_app, raising=False)
        monkeypatch.setattr(worker, "_get_stack_backfill_task", lambda: FakeTask(), raising=False)

        result = await worker.process_stack_backfill_run(run_id)

        row = await _run_row(db_module, run_id)
        assert result == {"ok": True, "status": "deferred", "resume_scheduled": True}
        assert row["status"] == "deferred"
        assert row["progress_message"] == "Rate limited — durable resume queued."
        assert configured == [
            {
                "queueing_lock": f"stack_backfill:{run_id}",
                "schedule_in": {"seconds": 180},
            }
        ]
        assert deferred == [{"run_id": run_id}]

    run_db_test(run())


async def _run_row(db_module, run_id: int) -> dict:
    db = await db_module.get_db()
    try:
        return await get_run(db, run_id)
    finally:
        await db.close()


def test_defer_uses_per_run_queueing_lock():
    """IDEM-B: the Procrastinate defer path configures a per-run queueing_lock
    and treats AlreadyEnqueued as an idempotent no-op (structural gate)."""
    src = Path(__file__).resolve().parents[1] / "routers" / "stack_catalog.py"
    text = src.read_text(encoding="utf-8")
    assert 'queueing_lock=f"stack_backfill:{run_id}"' in text
    assert "AlreadyEnqueued" in text
