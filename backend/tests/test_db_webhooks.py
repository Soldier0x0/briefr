"""Postgres-native webhooks module (Post-B Phase 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.webhooks as webhooks_mod
from db.config import is_postgres
from db.webhooks import (
    clear_webhook_alert,
    list_webhook_delivery_log,
    record_webhook_alert,
    record_webhook_delivery,
    was_webhook_alert_sent,
)
from database import get_db, init_db
from tests.conftest import run_db_test


def test_webhooks_sql_uses_native_placeholders():
    if is_postgres():
        assert "$1" in webhooks_mod._INSERT_ALERT_PG
        assert "$2" in webhooks_mod._INSERT_ALERT_PG
        assert "ON CONFLICT (alert_type, target)" in webhooks_mod._INSERT_ALERT_PG
        assert "$5" in webhooks_mod._INSERT_DELIVERY_PG
    else:
        assert "INSERT OR IGNORE" in webhooks_mod._INSERT_ALERT_SQLITE
        assert "?" in webhooks_mod._INSERT_DELIVERY_SQLITE


def test_webhook_alert_dedupe_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "webhooks_native.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await was_webhook_alert_sent(db, "kev_alert", "discord:1") is False
            await record_webhook_alert(db, "kev_alert", "discord:1")
            await db.commit()
            assert await was_webhook_alert_sent(db, "kev_alert", "discord:1") is True
            assert await was_webhook_alert_sent(db, "kev_stack", "discord:1") is True

            await record_webhook_alert(db, "kev_alert", "discord:1")
            await db.commit()

            await clear_webhook_alert(db, "kev_stack", "discord:1")
            await db.commit()
            assert await was_webhook_alert_sent(db, "kev_alert", "discord:1") is False
        finally:
            await db.close()

    run_db_test(_run())


def test_webhook_delivery_log_list(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "webhooks_delivery.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await record_webhook_delivery(
                db,
                destination_id="env:discord",
                event_type="kev_alert",
                dedupe_key="CVE-2024-1",
                status="ok",
                error=None,
            )
            await record_webhook_delivery(
                db,
                destination_id="env:discord",
                event_type="backup_failure",
                dedupe_key=None,
                status="error",
                error="timeout",
            )
            await db.commit()

            rows, total = await list_webhook_delivery_log(db)
            assert total == 2
            assert len(rows) == 2

            filtered, filtered_total = await list_webhook_delivery_log(
                db, event_type="kev_stack", limit=10
            )
            assert filtered_total == 1
            assert filtered[0]["event_type"] == "kev_alert"
            assert filtered[0]["dedupe_key"] == "CVE-2024-1"
        finally:
            await db.close()

    run_db_test(_run())
