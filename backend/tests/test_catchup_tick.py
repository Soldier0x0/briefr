from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catchup_mode as cm
import scheduler


def setup_function():
    cm.reset_catchup_for_tests()


def teardown_function():
    cm.reset_catchup_for_tests()


def test_catchup_tick_skips_when_inactive(monkeypatch):
    called = {"embeddings": 0, "precompute": 0}

    async def embeddings():
        called["embeddings"] += 1
        return True

    async def precompute():
        called["precompute"] += 1
        return {"precompute_snapshots": 1}

    monkeypatch.setattr("scheduler.run_embeddings_sync", embeddings)
    monkeypatch.setattr("scheduler.run_correlation_precompute_tick", precompute)
    monkeypatch.setattr("scheduler.get_correlation_precompute_enabled", lambda: True)

    assert asyncio.run(scheduler.run_catchup_tick()) is True
    assert called == {"embeddings": 0, "precompute": 0}


def test_catchup_tick_active_invokes_embeddings(monkeypatch):
    cm.start_catchup(duration_hours=1)
    called = {"embeddings": 0}

    async def embeddings():
        called["embeddings"] += 1
        return True

    monkeypatch.setattr("scheduler.run_embeddings_sync", embeddings)
    monkeypatch.setattr("scheduler.get_correlation_precompute_enabled", lambda: False)

    assert asyncio.run(scheduler.run_catchup_tick()) is True
    assert called["embeddings"] == 1


def test_catchup_tick_skips_in_wind_down(monkeypatch):
    cm.start_catchup(duration_hours=1)
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) + timedelta(seconds=60))
    called = {"embeddings": 0}

    async def embeddings():
        called["embeddings"] += 1
        return True

    monkeypatch.setattr("scheduler.run_embeddings_sync", embeddings)
    monkeypatch.setattr("scheduler.get_correlation_precompute_enabled", lambda: False)

    assert asyncio.run(scheduler.run_catchup_tick()) is True
    assert called["embeddings"] == 0


def test_catchup_tick_runs_precompute_slice_when_enabled(monkeypatch):
    cm.start_catchup(duration_hours=1)
    called = {"precompute": 0}

    async def embeddings():
        return True

    async def precompute():
        called["precompute"] += 1
        return {"precompute_snapshots": 2}

    monkeypatch.setattr("scheduler.run_embeddings_sync", embeddings)
    monkeypatch.setattr("scheduler.run_correlation_precompute_tick", precompute)
    monkeypatch.setattr("scheduler.get_correlation_precompute_enabled", lambda: True)

    assert asyncio.run(scheduler.run_catchup_tick()) is True
    assert called["precompute"] == 1
