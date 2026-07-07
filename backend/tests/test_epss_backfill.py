"""Tests for the EPSS 30-day history backfill job (§5.4).

All tests use an in-memory SQLite database and mock HTTP transport — no live
server or real FIRST API calls.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import resilient_client
from database import (
    EPSS_BACKFILL_DONE_KEY,
    get_db,
    get_sync_state_value,
    init_db,
    insert_epss_history_rows,
    set_sync_state_value,
    upsert_cves,
)
from feeds.epss import fetch_epss_time_series_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _install_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)


def _time_series_response(items: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"status": "OK", "data": items})


def _make_items(cve_id: str, dates_scores: list[tuple[str, float]]) -> list[dict]:
    return [
        {"cve": cve_id, "epss": str(score), "percentile": "0.99000", "date": date}
        for date, score in dates_scores
    ]


# ---------------------------------------------------------------------------
# fetch_epss_time_series_batch — unit tests (no DB needed)
# ---------------------------------------------------------------------------

def test_time_series_batch_parses_response(monkeypatch):
    items = _make_items("CVE-2021-44228", [("2024-01-01", 0.975), ("2024-01-02", 0.976)])

    def handler(request):
        assert "scope=time-series" in str(request.url)
        return _time_series_response(items)

    _install_transport(monkeypatch, handler)
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch(["CVE-2021-44228"])
        assert len(rows) == 2
        assert rows[0]["cve_id"] == "CVE-2021-44228"
        assert rows[0]["score"] == pytest.approx(0.975)
        assert rows[0]["date"] == "2024-01-01"

    run_db_test(run())


def test_time_series_batch_normalises_cve_id_to_upper(monkeypatch):
    items = _make_items("CVE-2021-44228", [("2024-01-01", 0.5)])

    def handler(request):
        return _time_series_response(items)

    _install_transport(monkeypatch, handler)
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch(["cve-2021-44228"])
        assert rows[0]["cve_id"] == "CVE-2021-44228"

    run_db_test(run())


def test_time_series_batch_skips_malformed_items(monkeypatch):
    items = [
        {"cve": "CVE-2021-44228", "epss": "not-a-float", "date": "2024-01-01"},
        {"cve": "", "epss": "0.5", "date": "2024-01-02"},
        {"cve": "CVE-2021-44228", "epss": "0.3", "date": ""},
        {"cve": "CVE-2021-44228", "epss": "0.4", "date": "2024-01-03"},
    ]

    def handler(request):
        return _time_series_response(items)

    _install_transport(monkeypatch, handler)
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch(["CVE-2021-44228"])
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(0.4)

    run_db_test(run())


def test_time_series_batch_returns_empty_on_empty_input(monkeypatch):
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch([])
        assert rows == []

    run_db_test(run())


def test_time_series_batch_returns_empty_on_circuit_open(monkeypatch):
    resilient_client.reset_feed_health()
    resilient_client._health["epss"] = {
        "last_success": None,
        "last_failure": None,
        "last_error": "injected",
        "consecutive_failures": 5,
        "circuit_open_until": 9_999_999_999.0,
    }

    async def run():
        rows = await fetch_epss_time_series_batch(["CVE-2021-44228"])
        assert rows == []

    run_db_test(run())
    resilient_client.reset_feed_health()


def test_time_series_batch_returns_empty_on_http_error(monkeypatch):
    def handler(request):
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch(["CVE-2021-44228"])
        assert rows == []

    run_db_test(run())


def test_time_series_batch_returns_empty_on_non_dict_json(monkeypatch):
    """API returns a list or other non-dict JSON — should not raise AttributeError."""
    def handler(request):
        return httpx.Response(200, json=[{"cve": "CVE-2021-44228", "epss": "0.5"}])

    _install_transport(monkeypatch, handler)
    resilient_client.reset_feed_health()

    async def run():
        rows = await fetch_epss_time_series_batch(["CVE-2021-44228"])
        assert rows == []

    run_db_test(run())


# ---------------------------------------------------------------------------
# insert_epss_history_rows — DB unit tests
# ---------------------------------------------------------------------------

def _run_in_tmp_db(coro_fn, tmp_path):
    """Bootstrap a fresh in-memory DB and run ``coro_fn(db)``."""
    import os

    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file

    async def _inner():
        from database import DB_PATH  # noqa: F401 — needed to refresh module state

        # Re-import to pick up the updated DB_PATH.
        import importlib
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            return await coro_fn(db)
        finally:
            await db.close()

    return run_db_test(_inner())


def test_insert_epss_history_rows_inserts_new_rows(tmp_path):
    import os

    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        # Seed a CVE
        db = await db_module.get_db()
        try:
            await db_module.upsert_cves(db, [{"cve_id": "CVE-2021-1234", "severity": "HIGH"}])
            await db.commit()
        finally:
            await db.close()

        db = await db_module.get_db()
        try:
            rows = [
                {"cve_id": "CVE-2021-1234", "score": 0.5, "date": "2024-01-01"},
                {"cve_id": "CVE-2021-1234", "score": 0.6, "date": "2024-01-02"},
            ]
            inserted = await db_module.insert_epss_history_rows(db, rows)
            await db.commit()
            assert inserted == 2

            history = await db.execute_fetchall(
                "SELECT * FROM epss_history WHERE cve_id = 'CVE-2021-1234' ORDER BY recorded_date"
            )
            assert len(history) == 2
            assert history[0]["recorded_date"] == "2024-01-01"
        finally:
            await db.close()

    run_db_test(run())


def test_insert_epss_history_rows_ignores_duplicates(tmp_path):
    import os

    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            row = {"cve_id": "CVE-2021-5678", "score": 0.7, "date": "2024-01-01"}
            await db_module.insert_epss_history_rows(db, [row])
            await db.commit()
            # Insert the same row again — should be ignored
            await db_module.insert_epss_history_rows(db, [row])
            await db.commit()

            history = await db.execute_fetchall(
                "SELECT COUNT(*) as cnt FROM epss_history WHERE cve_id = 'CVE-2021-5678'"
            )
            assert history[0]["cnt"] == 1
        finally:
            await db.close()

    run_db_test(run())


def test_insert_epss_history_rows_empty_input(tmp_path):
    import os

    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            inserted = await db_module.insert_epss_history_rows(db, [])
            assert inserted == 0
        finally:
            await db.close()

    run_db_test(run())


# ---------------------------------------------------------------------------
# sync_state helpers
# ---------------------------------------------------------------------------

def test_get_set_sync_state_value(tmp_path):
    import os

    db_file = str(tmp_path / "sync_state_test.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            val = await db_module.get_sync_state_value(db, "test_key")
            assert val is None

            await db_module.set_sync_state_value(db, "test_key", "hello")
            await db.commit()
            val = await db_module.get_sync_state_value(db, "test_key")
            assert val == "hello"

            # Upsert overwrites
            await db_module.set_sync_state_value(db, "test_key", "world")
            await db.commit()
            val = await db_module.get_sync_state_value(db, "test_key")
            assert val == "world"
        finally:
            await db.close()

    run_db_test(run())


# ---------------------------------------------------------------------------
# run_epss_backfill — integration (mocked HTTP, real in-memory DB)
# ---------------------------------------------------------------------------

def test_backfill_skipped_when_marker_set(tmp_path, monkeypatch):
    """If sync_state has epss_backfill_done=1, the job exits without API calls."""
    import os

    db_file = str(tmp_path / "backfill_skip.db")
    os.environ["DB_PATH"] = db_file

    called = {"n": 0}

    async def fake_fetch(cve_ids):
        called["n"] += 1
        return []

    async def run():
        import database as db_module
        import scheduler as sched_module

        db_module.DB_PATH = db_file
        sched_module._epss_backfill_lock = asyncio.Lock()  # fresh lock per test
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            await db_module.set_sync_state_value(db, db_module.EPSS_BACKFILL_DONE_KEY, "1")
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(sched_module, "fetch_epss_time_series_batch", fake_fetch)
        await sched_module.run_epss_backfill()
        assert called["n"] == 0

    run_db_test(run())


def test_backfill_inserts_history_rows(tmp_path, monkeypatch):
    """Happy path: CVEs in DB, API returns data, rows land in epss_history."""
    import os

    db_file = str(tmp_path / "backfill_happy.db")
    os.environ["DB_PATH"] = db_file

    async def fake_fetch(cve_ids):
        return [
            {"cve_id": cid, "score": 0.1, "date": "2024-01-01"} for cid in cve_ids
        ] + [
            {"cve_id": cid, "score": 0.2, "date": "2024-01-02"} for cid in cve_ids
        ]

    async def run():
        import database as db_module
        import scheduler as sched_module

        db_module.DB_PATH = db_file
        sched_module._epss_backfill_lock = asyncio.Lock()
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            await db_module.upsert_cves(
                db,
                [
                    {"cve_id": "CVE-2021-0001", "severity": "HIGH"},
                    {"cve_id": "CVE-2021-0002", "severity": "MEDIUM"},
                ],
            )
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(sched_module, "fetch_epss_time_series_batch", fake_fetch)
        monkeypatch.setattr(sched_module.asyncio, "sleep", AsyncMock())

        await sched_module.run_epss_backfill()

        db = await db_module.get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT COUNT(*) as cnt FROM epss_history"
            )
            assert rows[0]["cnt"] == 4  # 2 CVEs × 2 dates

            marker = await db_module.get_sync_state_value(db, db_module.EPSS_BACKFILL_DONE_KEY)
            assert marker == "1"
        finally:
            await db.close()

    run_db_test(run())


def test_backfill_is_idempotent(tmp_path, monkeypatch):
    """Running the backfill twice does not duplicate rows (INSERT OR IGNORE)."""
    import os

    db_file = str(tmp_path / "backfill_idem.db")
    os.environ["DB_PATH"] = db_file

    async def fake_fetch(cve_ids):
        return [{"cve_id": cid, "score": 0.5, "date": "2024-01-01"} for cid in cve_ids]

    async def run():
        import database as db_module
        import scheduler as sched_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        db = await db_module.get_db()
        try:
            await db_module.upsert_cves(db, [{"cve_id": "CVE-2021-9999", "severity": "LOW"}])
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(sched_module, "fetch_epss_time_series_batch", fake_fetch)
        monkeypatch.setattr(sched_module.asyncio, "sleep", AsyncMock())

        # First run
        sched_module._epss_backfill_lock = asyncio.Lock()
        await sched_module.run_epss_backfill()

        # Clear marker so we can force a second run (simulate interrupted + restart)
        db = await db_module.get_db()
        try:
            await db.execute(
                "DELETE FROM sync_state WHERE key = ?",
                (db_module.EPSS_BACKFILL_DONE_KEY,),
            )
            await db.commit()
        finally:
            await db.close()

        sched_module._epss_backfill_lock = asyncio.Lock()
        await sched_module.run_epss_backfill()

        db = await db_module.get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT COUNT(*) as cnt FROM epss_history WHERE cve_id = 'CVE-2021-9999'"
            )
            assert rows[0]["cnt"] == 1  # no duplicates
        finally:
            await db.close()

    run_db_test(run())


def test_backfill_sets_marker_after_completion(tmp_path, monkeypatch):
    """Marker must be absent before job starts and present after job completes."""
    import os

    db_file = str(tmp_path / "backfill_marker.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module
        import scheduler as sched_module

        db_module.DB_PATH = db_file
        sched_module._epss_backfill_lock = asyncio.Lock()
        await db_module.init_db()

        # DB with no CVEs — job should still set the marker
        monkeypatch.setattr(sched_module.asyncio, "sleep", AsyncMock())
        await sched_module.run_epss_backfill()

        db = await db_module.get_db()
        try:
            marker = await db_module.get_sync_state_value(db, db_module.EPSS_BACKFILL_DONE_KEY)
            assert marker == "1"
        finally:
            await db.close()

    run_db_test(run())


def test_backfill_skips_concurrent_call(tmp_path, monkeypatch):
    """Second concurrent call is skipped while the first is in progress."""
    import os

    db_file = str(tmp_path / "backfill_conc.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module
        import scheduler as sched_module

        db_module.DB_PATH = db_file
        sched_module._epss_backfill_lock = asyncio.Lock()
        await db_module.init_db()

        # Acquire the lock externally to simulate an in-progress run
        async with sched_module._epss_backfill_lock:
            result = await sched_module.run_epss_backfill()
            assert result is False  # skipped

    run_db_test(run())
