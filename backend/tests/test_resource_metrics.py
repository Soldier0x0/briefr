"""RB-1: resource metrics collector, storage, retention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import resource_collector as collector_mod
from db.resource_metrics import purge_old_resource_metrics
from database import get_db, init_db
from metrics.request_counter import read_and_reset_request_count, reset_for_tests
from resource_collector import _cpu_pct_from_times, _pg_derived_rates, _rate_per_sec
from tests.conftest import run_db_test


def test_cpu_pct_from_times_uses_elapsed_wall_clock():
    import psutil

    prev = {1: (1.0, 0.5)}
    curr = {1: (2.0, 1.0)}
    pct = _cpu_pct_from_times(curr, prev, 60.0)
    cpus = psutil.cpu_count() or 1
    expected = min(100.0, (1.5 / 60.0) / cpus * 100.0)
    assert pct == expected


def test_rate_per_sec_first_sample_is_none():
    assert _rate_per_sec(100, None, 60.0) is None


def test_rate_per_sec_computes_delta_over_elapsed():
    assert _rate_per_sec(1100, 1000, 10.0) == 10.0


def test_rate_per_sec_negative_delta_returns_none():
    assert _rate_per_sec(50, 100, 10.0) is None


def test_pg_derived_rates_first_sample_is_none_tuple():
    curr = {
        "xact_commit": 10,
        "xact_rollback": 1,
        "blks_read": 100,
        "blks_hit": 900,
        "db_size_bytes": 1_000_000,
    }
    assert _pg_derived_rates(curr, None, 60.0) == (None, None, None)


def test_pg_derived_rates_cache_hit_from_deltas():
    prev = {
        "xact_commit": 100,
        "xact_rollback": 5,
        "blks_read": 200,
        "blks_hit": 800,
        "db_size_bytes": 1_000_000,
    }
    curr = {
        "xact_commit": 160,
        "xact_rollback": 10,
        "blks_read": 260,
        "blks_hit": 940,
        "db_size_bytes": 1_050_000,
    }
    xact_per_min, blks_read_per_min, cache_hit = _pg_derived_rates(curr, prev, 60.0)
    assert xact_per_min == 65.0
    assert blks_read_per_min == 60.0
    assert cache_hit == 70.0


def test_request_counter_read_and_reset():
    reset_for_tests()
    from metrics.request_counter import increment_request_count

    increment_request_count()
    increment_request_count()
    assert read_and_reset_request_count() == 2
    assert read_and_reset_request_count() == 0


def test_collect_and_store_sample_records_two_rows():
    collector_mod.reset_collector_state_for_tests()
    reset_for_tests()

    async def _run():
        await init_db()
        db = await get_db()
        try:
            first = await collector_mod.collect_and_store_sample(db)
            await db.commit()
            assert first["briefr_rss_bytes"] is not None

            second = await collector_mod.collect_and_store_sample(db)
            await db.commit()
            assert second["briefr_rss_bytes"] is not None

            rows = await db.execute_fetchall(
                "SELECT COUNT(*) AS n FROM resource_metrics"
            )
            assert rows[0]["n"] == 2
        finally:
            await db.close()

    run_db_test(_run())


def test_purge_old_resource_metrics():
    async def _run():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO resource_metrics (ts, briefr_rss_bytes, req_count)
                VALUES (?, ?, ?)
                """,
                ("2000-01-01T00:00:00+00:00", 1000, 1),
            )
            await db.execute(
                """
                INSERT INTO resource_metrics (ts, briefr_rss_bytes, req_count)
                VALUES (?, ?, ?)
                """,
                ("2099-01-01T00:00:00+00:00", 2000, 2),
            )
            await db.commit()
            deleted = await purge_old_resource_metrics(db, retention_days=30)
            await db.commit()
            assert deleted >= 1
            rows = await db.execute_fetchall("SELECT ts FROM resource_metrics")
            assert len(rows) == 1
            assert str(rows[0]["ts"]).startswith("2099")
        finally:
            await db.close()

    run_db_test(_run())


def test_admin_job_run_map_includes_resource_metrics_sample():
    from routers.admin import _JOB_RUN_MAP

    assert "resource_metrics_sample" in _JOB_RUN_MAP


def test_scheduler_lock_registered():
    import scheduler_locks

    assert "resource_metrics_sample" in scheduler_locks._LOCKS


def test_downsample_series_caps_points():
    from db.resource_metrics import downsample_series

    rows = [{"ts": f"2026-01-01T00:{i:02d}:00+00:00", "briefr_cpu_pct": float(i)} for i in range(1000)]
    out = downsample_series(rows, max_points=100)
    assert len(out) == 100
    assert out[0]["briefr_cpu_pct"] is not None


def test_summarize_metric_peak_timestamp():
    from db.resource_metrics import summarize_metric

    rows = [
        {"ts": "2026-01-01T00:00:00+00:00", "briefr_cpu_pct": 1.0},
        {"ts": "2026-01-01T01:00:00+00:00", "briefr_cpu_pct": 9.0},
        {"ts": "2026-01-01T02:00:00+00:00", "briefr_cpu_pct": 3.0},
    ]
    summary = summarize_metric(rows, "briefr_cpu_pct")
    assert summary["peak"] == 9.0
    assert summary["peak_at"] == "2026-01-01T01:00:00+00:00"
    assert summary["low"] == 1.0


def test_fetch_resource_metrics_rows_is_not_downsampled():
    from db.resource_metrics import fetch_resource_metrics_rows

    async def _run():
        await init_db()
        db = await get_db()
        try:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO resource_metrics (ts, briefr_rss_bytes, req_count) VALUES (?, ?, ?)",
                (now, 111, 2),
            )
            await db.commit()
            rows = await fetch_resource_metrics_rows(db, "1d")
            assert len(rows) == 1
            assert rows[0]["briefr_rss_bytes"] == 111
            assert rows[0]["req_count"] == 2
        finally:
            await db.close()

    run_db_test(_run())


def test_fetch_resources_response_empty():
    async def _run():
        from db.resource_metrics import fetch_resources_response

        await init_db()
        db = await get_db()
        try:
            data = await fetch_resources_response(db, "7d")
            assert data["window"] == "7d"
            assert data["sample_count"] == 0
            assert data["degraded"]["code"] == "empty"
            assert data["series"] == []
        finally:
            await db.close()

    run_db_test(_run())
