"""Q1 Procrastinate foundation — flag-off safety + Postgres defer/worker."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark_pg = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    # Force SQLite TestClient path even when the shell has DATABASE_URL=postgresql.
    db_path = tmp_path / "q1_admin.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from jobs.app import reset_app_for_tests
    from main import app

    reset_app_for_tests()
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_procrastinate_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PROCRASTINATE_ENABLED", raising=False)
    from jobs.app import get_app, is_procrastinate_enabled, reset_app_for_tests

    reset_app_for_tests()
    assert is_procrastinate_enabled() is False
    assert get_app() is None


def test_outbound_context_sets_and_clears():
    from jobs.context import get_outbound_context, outbound_context

    assert get_outbound_context()["actor_type"] is None
    with outbound_context(actor_type="job", job_id="nvd_sync", run_id="r1"):
        ctx = get_outbound_context()
        assert ctx["actor_type"] == "job"
        assert ctx["job_id"] == "nvd_sync"
        assert ctx["run_id"] == "r1"
    assert get_outbound_context()["actor_type"] is None


def test_admin_outbound_jobs_when_disabled(admin_client):
    res = admin_client.get("/api/admin/jobs/outbound")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False
    assert body["jobs"] == []


@pytest.mark.postgres_migrations
@pytestmark_pg
@pytest.mark.asyncio
async def test_health_ping_defer_and_worker(monkeypatch):
    """Defer health_ping and run worker until the job succeeds (Postgres)."""
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "1")
    from database import get_db, run_postgres_migrations
    from db.connection import close_pool, init_pool
    from jobs.app import close_app, open_app, reset_app_for_tests
    from jobs.tasks import health_ping

    await run_postgres_migrations()
    await init_pool()
    reset_app_for_tests()
    app = await open_app()
    assert app is not None

    try:
        await health_ping.defer_async(note="q1-smoke")
        await app.run_worker_async(queues=["briefr"], concurrency=1, wait=False)
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT status::text AS status FROM procrastinate_jobs "
                "WHERE task_name = $1 ORDER BY id DESC LIMIT 1",
                ("jobs:health_ping",),
            )
        finally:
            await db.close()
        assert rows, "expected a procrastinate job row"
        status = rows[0]["status"]
        assert status == "succeeded", status
    finally:
        await close_app()
        reset_app_for_tests()
        await close_pool()
