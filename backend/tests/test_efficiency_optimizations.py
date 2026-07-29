"""Phase C efficiency optimizations — safe defaults preserved."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from tests.conftest import run_db_test


def test_api_call_events_batch_disabled_inserts_immediately(tmp_path, monkeypatch):
    db_path = tmp_path / "batch.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("API_CALL_EVENTS_BATCH_MS", "0")

    async def _run():
        from db.api_metering import (
            flush_api_call_event_buffer,
            queue_api_call_event,
            reset_api_call_event_buffer_for_tests,
        )

        reset_api_call_event_buffer_for_tests()
        await init_db()
        buffered = await queue_api_call_event(
            source="test",
            method="GET",
            url="https://example.com/cve",
            status_code=200,
            ok=True,
            latency_ms=12,
        )
        assert buffered is False
        flushed = await flush_api_call_event_buffer()
        assert flushed == 0

    run_db_test(_run())


def test_api_call_events_batch_buffers_until_flush(tmp_path, monkeypatch):
    db_path = tmp_path / "batch_flush.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("API_CALL_EVENTS_BATCH_MS", "50")

    async def _run():
        from db.api_metering import (
            flush_api_call_event_buffer,
            queue_api_call_event,
            reset_api_call_event_buffer_for_tests,
        )

        reset_api_call_event_buffer_for_tests()
        await init_db()
        buffered = await queue_api_call_event(
            source="test",
            method="GET",
            url="https://example.com/a",
            status_code=200,
            ok=True,
            latency_ms=5,
        )
        assert buffered is True
        count = await flush_api_call_event_buffer()
        assert count == 1
        db = await get_db()
        try:
            rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM api_call_events")
            assert int(rows[0]["cnt"]) == 1
        finally:
            await db.close()

    run_db_test(_run())


def test_ssvc_feed_cache_retention_is_one_week():
    from db.cache_retention import FEED_CACHE_PREFIX_RETENTION

    ssvc = next(hours for prefix, hours in FEED_CACHE_PREFIX_RETENTION if prefix == "ssvc:")
    assert ssvc == 168


def test_resource_metrics_retention_reads_env(monkeypatch):
    from db.resource_metrics import get_resource_metrics_retention_days

    monkeypatch.setenv("RESOURCE_METRICS_RETENTION_DAYS", "14")
    assert get_resource_metrics_retention_days() == 14


def test_embeddings_skip_queue_depth_default_high(monkeypatch):
    from ml.embeddings import get_embeddings_ingest_skip_queue_depth

    monkeypatch.delenv("EMBEDDINGS_INGEST_SKIP_QUEUE_DEPTH", raising=False)
    assert get_embeddings_ingest_skip_queue_depth() >= 1000
