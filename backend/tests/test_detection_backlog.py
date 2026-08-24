"""Tests for KEV-driven detection backlog (V1.5 Theme 3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import get_db, init_db
from detection.backlog import process_new_kev_backlog, upsert_gap_items_for_cves
from tests.conftest import run_db_test

GAP_TID = "T1566"
COMMUNITY_TID = "T1190"


@pytest.fixture
def backlog_client(tmp_path, monkeypatch):
    db_path = tmp_path / "backlog.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_STACK_TERMS", "nginx")

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await db.executemany(
                "INSERT INTO mitre_techniques (technique_id, name, tactic, url) VALUES (?, ?, ?, ?)",
                [
                    (GAP_TID, "Phishing", "Initial Access", "https://attack.mitre.org/techniques/T1566/"),
                    (
                        COMMUNITY_TID,
                        "Exploit Public-Facing Application",
                        "Initial Access",
                        "https://attack.mitre.org/techniques/T1190/",
                    ),
                ],
            )
            await db.executemany(
                """
                INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "CVE-2024-2001",
                        "nginx path traversal in reverse proxy module",
                        '["nginx:nginx"]',
                        GAP_TID,
                        "HIGH",
                        8.1,
                        0.4,
                        1,
                        "2024-06-01T00:00:00",
                    ),
                    (
                        "CVE-2024-2002",
                        "nginx HTTP request smuggling",
                        '["nginx:nginx"]',
                        COMMUNITY_TID,
                        "CRITICAL",
                        9.8,
                        0.9,
                        1,
                        "2024-06-02T00:00:00",
                    ),
                ],
            )
            await db.executemany(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
                [
                    ("CVE-2024-2001", GAP_TID),
                    ("CVE-2024-2002", COMMUNITY_TID),
                ],
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_gap_kev_creates_backlog_item(backlog_client):
    created = run_db_test(process_new_kev_backlog(["CVE-2024-2001", "CVE-2024-2002"]))
    assert len(created) == 1
    assert created[0]["cve_id"] == "CVE-2024-2001"

    resp = backlog_client.get("/api/detection-backlog?stack=nginx")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["technique_id"] == GAP_TID
    assert items[0]["priority"] == "critical"


def test_dismiss_backlog_item(backlog_client):
    run_db_test(process_new_kev_backlog(["CVE-2024-2001"]))
    resp = backlog_client.get("/api/detection-backlog?stack=nginx")
    item_id = resp.json()["items"][0]["id"]

    dismiss = backlog_client.post(f"/api/detection-backlog/{item_id}/dismiss")
    assert dismiss.status_code == 200
    assert dismiss.json()["item"]["status"] == "dismissed"

    open_resp = backlog_client.get("/api/detection-backlog?stack=nginx")
    assert open_resp.json()["meta"]["count"] == 0


def test_dismiss_missing_returns_404(backlog_client):
    resp = backlog_client.post("/api/detection-backlog/99999/dismiss")
    assert resp.status_code == 404


def test_new_backlog_item_does_not_notify(backlog_client):
    """Coverage gaps stay in Forge Backlog — no analyst bell or webhook."""
    from db.user_notifications import list_notifications

    async def seed_analyst() -> None:
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO users (id, username, password_hash, role, is_active) "
                "VALUES (2, 'analyst-1', 'hash', 'analyst', 1)"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed_analyst())

    created = run_db_test(process_new_kev_backlog(["CVE-2024-2001", "CVE-2024-2002"]))
    assert len(created) == 1

    async def read_notifications():
        db = await get_db()
        try:
            return await list_notifications(db, user_id=2, scope="analyst")
        finally:
            await db.close()

    notifications = run_db_test(read_notifications())
    assert notifications == []


def test_upsert_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "backlog_unit.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO mitre_techniques (technique_id, name, tactic, url) VALUES (?, ?, ?, ?)",
                (GAP_TID, "Phishing", "Initial Access", "https://attack.mitre.org/techniques/T1566/"),
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2001",
                    "nginx path traversal",
                    '["nginx:nginx"]',
                    GAP_TID,
                    "HIGH",
                    8.1,
                    0.4,
                    1,
                    "2024-06-01T00:00:00",
                ),
            )
            await db.execute(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
                ("CVE-2024-2001", GAP_TID),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    async def upsert_twice() -> tuple[int, int]:
        db = await get_db()
        try:
            row = (await db.execute_fetchall(
                "SELECT cve_id, is_kev, cvss_score, epss_score FROM cves WHERE cve_id = ?",
                ("CVE-2024-2001",),
            ))[0]
            payload = dict(row)
            first = await upsert_gap_items_for_cves(db, [payload], stack_terms="nginx")
            second = await upsert_gap_items_for_cves(db, [payload], stack_terms="nginx")
            await db.commit()
            return len(first), len(second)
        finally:
            await db.close()

    first_count, second_count = run_db_test(upsert_twice())
    assert first_count == 1
    assert second_count == 0
