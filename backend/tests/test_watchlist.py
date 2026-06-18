"""CVE watchlist — pin / snooze (Beta V1.3 Theme 1).

Verifies:
- watchlist schema via idempotent migration (fresh + re-run)
- GET/POST/DELETE /api/watchlist
- list feed hides active snoozes, floats pins, watchlist_only filter
- additive watchlist_state on list + detail responses
"""

import asyncio
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from database import init_db
from main import app

CVE_A = "CVE-2021-44228"
CVE_B = "CVE-2024-0001"
CVE_C = "CVE-2024-0002"


@pytest.fixture
def watchlist_client(tmp_path, monkeypatch):
    db_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await db.executemany(
                """
                INSERT INTO cves (cve_id, description, severity, cvss_score,
                                  epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (CVE_A, "Log4Shell", "CRITICAL", 10.0, 0.97, 1, "2021-12-10T00:00:00"),
                    (CVE_B, "Older issue", "HIGH", 8.0, 0.5, 0, "2024-01-15T00:00:00"),
                    (CVE_C, "Newer issue", "MEDIUM", 5.0, 0.1, 0, "2024-06-01T00:00:00"),
                ],
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    with TestClient(app) as client:
        yield client, db_path


def _table_columns(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def test_watchlist_schema_idempotent(watchlist_client):
    _client, db_path = watchlist_client
    cols = _table_columns(db_path, "watchlist")
    assert "cve_id" in cols
    assert "state" in cols
    assert "snooze_until" in cols
    assert "created_at" in cols
    asyncio.run(init_db())
    assert _table_columns(db_path, "watchlist") == cols


def test_watchlist_crud(watchlist_client):
    client, _db_path = watchlist_client

    empty = client.get("/api/watchlist")
    assert empty.status_code == 200
    assert empty.json()["count"] == 0

    pin = client.post("/api/watchlist", json={"cve_id": CVE_A, "state": "pin"})
    assert pin.status_code == 200
    assert pin.json()["data"]["state"] == "pin"

    listed = client.get("/api/watchlist")
    assert listed.json()["count"] == 1
    assert listed.json()["data"][0]["cve_id"] == CVE_A

    snooze = client.post(
        "/api/watchlist",
        json={"cve_id": CVE_B, "state": "snooze", "snooze_days": 3},
    )
    assert snooze.status_code == 200
    assert snooze.json()["data"]["state"] == "snooze"
    assert snooze.json()["data"]["snooze_until"]

    replace = client.post("/api/watchlist", json={"cve_id": CVE_A, "state": "snooze"})
    assert replace.json()["data"]["state"] == "snooze"

    deleted = client.delete(f"/api/watchlist/{CVE_A}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    missing = client.delete(f"/api/watchlist/{CVE_A}")
    assert missing.status_code == 404

    bad_cve = client.post("/api/watchlist", json={"cve_id": "CVE-9999-99999", "state": "pin"})
    assert bad_cve.status_code == 404


def test_feed_pin_floats_and_snooze_hidden(watchlist_client):
    client, db_path = watchlist_client

    client.post("/api/watchlist", json={"cve_id": CVE_A, "state": "pin"})
    client.post("/api/watchlist", json={"cve_id": CVE_B, "state": "snooze", "snooze_days": 7})

    feed = client.get("/api/cves?limit=50")
    assert feed.status_code == 200
    ids = [row["cve_id"] for row in feed.json()["data"]]
    assert CVE_B not in ids
    assert ids[0] == CVE_A
    pinned = next(r for r in feed.json()["data"] if r["cve_id"] == CVE_A)
    assert pinned["watchlist_state"] == "pin"

    wl_only = client.get("/api/cves?watchlist_only=true&limit=50")
    wl_ids = [row["cve_id"] for row in wl_only.json()["data"]]
    assert CVE_A in wl_ids
    assert CVE_B in wl_ids
    snoozed = next(r for r in wl_only.json()["data"] if r["cve_id"] == CVE_B)
    assert snoozed["watchlist_state"] == "snooze"


def test_expired_snooze_reappears(watchlist_client):
    client, db_path = watchlist_client

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0)
    past_sql = past.strftime("%Y-%m-%d %H:%M:%S")

    async def insert_expired() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute(
                "INSERT INTO watchlist (cve_id, state, snooze_until) VALUES (?, 'snooze', ?)",
                (CVE_C, past_sql),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(insert_expired())

    feed = client.get("/api/cves?limit=50")
    ids = [row["cve_id"] for row in feed.json()["data"]]
    assert CVE_C in ids

    wl = client.get("/api/watchlist")
    assert CVE_C not in {e["cve_id"] for e in wl.json()["data"]}


def test_detail_includes_watchlist_state(watchlist_client):
    client, _db_path = watchlist_client
    client.post("/api/watchlist", json={"cve_id": CVE_A, "state": "pin"})

    detail = client.get(f"/api/cves/{CVE_A}")
    assert detail.status_code == 200
    assert detail.json()["watchlist_state"] == "pin"

    plain = client.get(f"/api/cves/{CVE_B}")
    assert "watchlist_state" not in plain.json()


def test_clear_all_snoozes(watchlist_client):
    client, _db_path = watchlist_client

    client.post("/api/watchlist", json={"cve_id": CVE_A, "state": "pin"})
    client.post("/api/watchlist", json={"cve_id": CVE_B, "state": "snooze", "snooze_days": 7})

    cleared = client.delete("/api/watchlist/snoozes")
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1

    listed = client.get("/api/watchlist")
    assert listed.json()["count"] == 1
    assert listed.json()["data"][0]["cve_id"] == CVE_A
    assert listed.json()["data"][0]["state"] == "pin"

    feed = client.get("/api/cves?limit=50")
    ids = [row["cve_id"] for row in feed.json()["data"]]
    assert CVE_B in ids
