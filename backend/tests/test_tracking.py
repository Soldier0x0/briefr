"""Tests for API usage tracking and SQLite write batching."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import pytest

from database import get_db, init_db
import tracking


@pytest.fixture(autouse=True)
def reset_tracking_buffers():
    tracking._API_USAGE_LOCK = asyncio.Lock()
    tracking._API_USAGE_WRITE_LOCK = asyncio.Lock()
    tracking._api_usage_pending.clear()
    if tracking._api_usage_flush_task and not tracking._api_usage_flush_task.done():
        tracking._api_usage_flush_task.cancel()
    tracking._api_usage_flush_task = None
    yield
    tracking._API_USAGE_LOCK = asyncio.Lock()
    tracking._API_USAGE_WRITE_LOCK = asyncio.Lock()
    tracking._api_usage_pending.clear()
    if tracking._api_usage_flush_task and not tracking._api_usage_flush_task.done():
        tracking._api_usage_flush_task.cancel()
    tracking._api_usage_flush_task = None


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "tracking.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setattr("database.DB_PATH", str(path))
    run_db_test(init_db())
    return path


async def _usage_count(service: str) -> int:
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT count FROM api_usage WHERE service = ?",
            (service,),
        )
        return row[0][0] if row else 0
    finally:
        await db.close()


def test_record_api_call_batches_writes(db_path):
    async def _run():
        await tracking.record_api_call("circl", 3)
        await tracking.record_api_call("sploitus", 2)
        await tracking.record_api_call("circl", 1)
        await tracking.flush_api_usage_pending()
        assert await _usage_count("circl") == 4
        assert await _usage_count("sploitus") == 2

    run_db_test(_run())


def test_record_api_call_schedules_background_flush(db_path, monkeypatch):
    monkeypatch.setattr(tracking, "_API_USAGE_FLUSH_DELAY_SECONDS", 0.05)

    async def _run():
        await tracking.record_api_call("circl", 1)
        await asyncio.sleep(0.15)
        assert await _usage_count("circl") == 1

    run_db_test(_run())


def test_get_usage_stats_uses_configured_db(db_path):
    async def _run():
        await tracking.record_api_call("nvd", 2)
        await tracking.flush_api_usage_pending()
        stats = await tracking.get_usage_stats()
        nvd = next(item for item in stats if item["service"] == "nvd")
        assert nvd["today"]["used"] == 2

    run_db_test(_run())
