"""API call audit trail admin endpoints (Phase D)."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]


def _configure_metering_db(monkeypatch, tmp_path):
    monkeypatch.setenv("API_CALL_EVENTS_ENABLED", "1")
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    return tmp_path


async def _seed_api_call_events():
    from database import get_db
    from db.api_metering import insert_api_call_event

    now = datetime.now(timezone.utc)
    rows = [
        {
            "source": "greynoise",
            "method": "GET",
            "url": "https://api.greynoise.io/v3/community/8.8.8.8",
            "status_code": 200,
            "ok": True,
            "latency_ms": 42,
            "actor_type": "user",
            "actor_id": "pytest-user",
            "request_id": "req-gn-user",
            "ts": now - timedelta(hours=1),
        },
        {
            "source": "greynoise",
            "method": "GET",
            "url": "https://api.greynoise.io/v3/community/1.1.1.1",
            "status_code": 200,
            "ok": True,
            "latency_ms": 55,
            "actor_type": "job",
            "job_id": "ioc_retro_match",
            "run_id": "run-gn-job",
            "ts": now - timedelta(hours=2),
        },
        {
            "source": "nvd",
            "method": "GET",
            "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
            "status_code": 200,
            "ok": True,
            "latency_ms": 120,
            "actor_type": "job",
            "job_id": "nvd_incremental_sync",
            "ts": now - timedelta(hours=3),
        },
        {
            "source": "nvd",
            "method": "GET",
            "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
            "status_code": 503,
            "ok": False,
            "latency_ms": 900,
            "actor_type": "job",
            "job_id": "nvd_incremental_sync",
            "ts": now - timedelta(days=40),
        },
    ]

    db = await get_db()
    try:
        try:
            await db.execute("DELETE FROM api_call_events")
        except Exception:
            pass
        for row in rows:
            await insert_api_call_event(
                db,
                source=row["source"],
                method=row["method"],
                url=row["url"],
                status_code=row["status_code"],
                ok=row["ok"],
                latency_ms=row["latency_ms"],
                actor_type=row.get("actor_type"),
                actor_id=row.get("actor_id"),
                job_id=row.get("job_id"),
                run_id=row.get("run_id"),
                request_id=row.get("request_id"),
                ts=row["ts"],
            )
        await db.commit()
    finally:
        await db.close()


@pytest.fixture
def audit_client(tmp_path, monkeypatch, auth_token):
    _configure_metering_db(monkeypatch, tmp_path)
    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        asyncio.run(_seed_api_call_events())
        yield client


def test_api_usage_events_returns_seeded_rows(audit_client):
    res = audit_client.get("/api/admin/api-usage/events?hours=24")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 2
    assert len(body["events"]) >= 2
    event = body["events"][0]
    assert {"ts", "source", "method", "host", "path_template", "status", "latency_ms"} <= set(event)
    assert event["source"] in {"greynoise", "nvd"}


def test_api_usage_events_filters_source_and_actor(audit_client):
    res = audit_client.get(
        "/api/admin/api-usage/events?hours=24&source=greynoise&actor_type=user"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["events"][0]["source"] == "greynoise"
    assert body["events"][0]["actor_type"] == "user"
    assert body["events"][0]["request_id"] == "req-gn-user"


def test_api_usage_events_greynoise_actor_breakdown(audit_client):
    res = audit_client.get("/api/admin/api-usage/events?hours=24&source=greynoise")
    assert res.status_code == 200
    body = res.json()
    breakdown = {row["actor_type"]: row["calls"] for row in body["actor_breakdown"]}
    assert breakdown.get("user") == 1
    assert breakdown.get("job") == 1


def test_api_usage_events_respects_limit_offset(audit_client):
    res = audit_client.get("/api/admin/api-usage/events?hours=24&limit=1&offset=0")
    assert res.status_code == 200
    body = res.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["events"]) == 1
    assert body["total"] >= 2


def test_api_usage_events_export_csv_headers_and_rows(audit_client):
    res = audit_client.get("/api/admin/api-usage/events/export?hours=24&source=greynoise")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("text/csv")
    assert "attachment" in res.headers.get("content-disposition", "")

    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    assert reader.fieldnames == [
        "ts",
        "source",
        "method",
        "host",
        "path_template",
        "status_code",
        "latency_ms",
        "actor_type",
        "actor_id",
        "job_id",
        "run_id",
        "request_id",
    ]
    assert len(rows) == 2
    assert all(row["source"] == "greynoise" for row in rows)
    assert {row["actor_type"] for row in rows} == {"user", "job"}


def test_api_usage_events_export_excludes_rows_outside_window(audit_client):
    res = audit_client.get("/api/admin/api-usage/events/export?hours=24&source=nvd")
    assert res.status_code == 200
    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["status_code"] == "200"
