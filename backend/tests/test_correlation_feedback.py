"""CORR-PR-12: analyst correlation feedback persistence and API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.config import is_postgres
from db.correlation import (
    delete_correlation_feedback,
    insert_correlation_feedback,
    list_correlation_feedback,
)
from database import get_db, init_db, write_audit_log
from tests.conftest import run_db_test

CVE_A = "CVE-2024-5001"
CAMP_ID = "camp-feedback-1"


def test_correlation_feedback_db_round_trip_and_uniqueness(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "correlation_feedback.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            row = await insert_correlation_feedback(
                db,
                CVE_A,
                scope="campaign_id",
                scope_key=CAMP_ID,
                verdict="confirm",
                reason="looks legit",
                created_by="analyst@example.com",
            )
            await db.commit()
            assert row["cve_id"] == CVE_A
            assert row["verdict"] == "confirm"

            listed = await list_correlation_feedback(db, CVE_A)
            assert len(listed) == 1
            assert listed[0]["scope_key"] == CAMP_ID

            updated = await insert_correlation_feedback(
                db,
                CVE_A,
                scope="campaign_id",
                scope_key=CAMP_ID,
                verdict="confirm",
                reason="still legit",
                created_by="analyst2@example.com",
            )
            await db.commit()
            assert updated["reason"] == "still legit"
            assert len(await list_correlation_feedback(db, CVE_A)) == 1

            deleted = await delete_correlation_feedback(
                db, CVE_A, "campaign_id", CAMP_ID, "confirm"
            )
            await db.commit()
            assert deleted is True
            assert await list_correlation_feedback(db, CVE_A) == []
        finally:
            await db.close()

    run_db_test(_run())


def test_correlation_feedback_api_round_trip_and_audit(tmp_path, monkeypatch):
    db_path = tmp_path / "corr_feedback_router.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                (CVE_A, "Feedback test", "2024-01-01"),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        post = client.post(
            f"/api/cves/{CVE_A}/correlation/feedback",
            json={
                "scope": "campaign_id",
                "key": {"campaign_id": CAMP_ID},
                "verdict": "confirm",
                "reason": "validated link",
                "created_by": "tester@example.com",
            },
        )
        assert post.status_code == 200
        body = post.json()
        assert body["ok"] is True
        assert body["feedback"]["verdict"] == "confirm"
        assert body["feedback"]["scope_key"] == CAMP_ID

        listed = client.get(f"/api/cves/{CVE_A}/correlation/feedback")
        assert listed.status_code == 200
        assert len(listed.json()["feedback"]) == 1

        dup = client.post(
            f"/api/cves/{CVE_A}/correlation/feedback",
            json={
                "scope": "campaign_id",
                "key": {"campaign_id": CAMP_ID},
                "verdict": "confirm",
                "reason": "updated note",
                "created_by": "tester@example.com",
            },
        )
        assert dup.status_code == 200
        assert dup.json()["feedback"]["reason"] == "updated note"
        assert len(client.get(f"/api/cves/{CVE_A}/correlation/feedback").json()["feedback"]) == 1

        deleted = client.delete(
            f"/api/cves/{CVE_A}/correlation/feedback"
            f"?scope=campaign_id&verdict=confirm&campaign_id={CAMP_ID}"
        )
        assert deleted.status_code == 200
        assert client.get(f"/api/cves/{CVE_A}/correlation/feedback").json()["feedback"] == []

    async def check_audit():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT actor, action, target FROM audit_log ORDER BY id"
            )
            assert len(rows) >= 2
            assert rows[-2]["action"] == "correlation.feedback.confirm"
            assert CAMP_ID in rows[-2]["target"]
            assert rows[-1]["action"] == "correlation.feedback.delete"
        finally:
            await db.close()

    run_db_test(check_audit())
