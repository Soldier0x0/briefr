"""Tests for KEV-on-stack and backup dead-man webhook rules."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from db.config import is_postgres
from tests.conftest import run_db_test

import httpx

import resilient_client
from database import (
    clear_webhook_alert,
    get_db,
    init_db,
    mark_cves_as_kev,
    record_webhook_alert,
    was_webhook_alert_sent,
)
from resilient_client import reset_feed_health
from webhooks.alerts import (
    ALERT_BACKUP_DEADMAN,
    ALERT_KEV_STACK,
    ALERT_WATCHLIST,
    BACKUP_DEADMAN_TARGET,
    check_backup_deadman,
    process_kev_stack_alerts,
    process_watchlist_kev_alerts,
    process_watchlist_monitor_alerts,
    process_watchlist_withdrawn_alerts,
)


def _setup_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "webhooks.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())
    from webhooks.destinations import sync_env_destinations_to_db

    run_db_test(sync_env_destinations_to_db())
    return db_path


def _history_ts(hours_ago: float):
    """Portable detected_at for cve_change_history inserts."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt if is_postgres() else dt.strftime("%Y-%m-%d %H:%M:%S")


def _mock_webhooks(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("BRIEFR_STACK_TERMS", "nginx")
    monkeypatch.setenv("BACKUP_ENABLED", "1")

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    reset_feed_health()
    from webhooks.destinations import sync_env_destinations_to_db

    run_db_test(sync_env_destinations_to_db())
    return calls


async def _seed_cve(db_path: Path, cve_id: str, description: str, is_kev: int = 0):
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO cves (cve_id, description, severity, is_kev)
            VALUES (?, ?, 'HIGH', ?)
            """,
            (cve_id, description, is_kev),
        )
        await db.commit()
    finally:
        await db.close()


def test_kev_stack_alert_sent_once(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-1001", "nginx reverse proxy RCE"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-1001"])
            await db.commit()
        finally:
            await db.close()
        sent = await process_kev_stack_alerts(newly)
        sent_again = await process_kev_stack_alerts(newly)
        return sent, sent_again

    sent, sent_again = run_db_test(run())
    assert sent == 1
    assert sent_again == 0
    assert len(calls) == 1


def test_kev_stack_skips_non_matching(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-1002", "unrelated apache issue"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-1002"])
            await db.commit()
        finally:
            await db.close()
        return await process_kev_stack_alerts(newly)

    assert run_db_test(run()) == 0
    assert calls == []


def test_kev_stack_requires_stack_terms(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    _mock_webhooks(monkeypatch)
    monkeypatch.delenv("BRIEFR_STACK_TERMS", raising=False)
    run_db_test(_seed_cve(db_path, "CVE-2024-1003", "nginx issue"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-1003"])
            await db.commit()
        finally:
            await db.close()
        return await process_kev_stack_alerts(newly)

    assert run_db_test(run()) == 0


def test_backup_deadman_alerts_when_stale(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive = backup_dir / "briefr-20260101T000000Z.tar.gz"
    archive.write_bytes(b"x")
    stale = datetime.now(timezone.utc) - timedelta(hours=20)
    os.utime(archive, (stale.timestamp(), stale.timestamp()))
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("BACKUP_INTERVAL_HOURS", "6")

    async def run():
        first = await check_backup_deadman()
        second = await check_backup_deadman()
        return first, second

    first, second = run_db_test(run())
    assert first is True
    assert second is False
    assert len(calls) == 1


def test_backup_deadman_clears_after_fresh_backup(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive = backup_dir / "briefr-20260102T000000Z.tar.gz"
    archive.write_bytes(b"x")
    stale = datetime.now(timezone.utc) - timedelta(hours=20)
    os.utime(archive, (stale.timestamp(), stale.timestamp()))
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("BACKUP_INTERVAL_HOURS", "6")

    async def run():
        await check_backup_deadman()
        fresh = datetime.now(timezone.utc) - timedelta(hours=1)
        os.utime(archive, (fresh.timestamp(), fresh.timestamp()))
        res = await check_backup_deadman()
        db = await get_db()
        try:
            was_sent = await was_webhook_alert_sent(
                db, ALERT_BACKUP_DEADMAN, BACKUP_DEADMAN_TARGET
            )
        finally:
            await db.close()
        return res, was_sent

    res, was_sent = run_db_test(run())
    assert res is False
    assert was_sent is False
    assert len(calls) == 1


def test_watchlist_kev_alert_for_pinned_cve(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2001", "nginx issue"))

    async def run():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2001', 'pin')"
            )
            newly = await mark_cves_as_kev(db, ["CVE-2024-2001"])
            await db.commit()
        finally:
            await db.close()
        sent = await process_watchlist_kev_alerts(newly)
        sent_again = await process_watchlist_kev_alerts(newly)
        return sent, sent_again

    sent, sent_again = run_db_test(run())
    assert sent == 1
    assert sent_again == 0
    assert len(calls) == 1


def test_watchlist_kev_alert_skips_unpinned(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2002", "nginx issue"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-2002"])
            await db.commit()
        finally:
            await db.close()
        return await process_watchlist_kev_alerts(newly)

    assert run_db_test(run()) == 0
    assert calls == []


def test_watchlist_monitor_epss_and_poc_alerts(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2003", "pinned target"))

    async def seed_changes():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2003', 'pin')"
            )
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2003",
                    "epss_score",
                    "0.05",
                    "0.20",
                    _history_ts(1),
                    "CVE-2024-2003",
                    "has_poc",
                    "0",
                    "1",
                    _history_ts(0.5),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed_changes())
    sent = run_db_test(process_watchlist_monitor_alerts())
    assert sent == 2
    assert len(calls) == 2
    sent_again = run_db_test(process_watchlist_monitor_alerts())
    assert sent_again == 0


def test_watchlist_monitor_second_epss_jump_alerts(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2004", "pinned epss ladder"))

    async def seed_first_jump():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2004', 'pin')"
            )
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2004",
                    "epss_score",
                    "0.05",
                    "0.20",
                    _history_ts(2),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed_first_jump())
    assert run_db_test(process_watchlist_monitor_alerts()) == 1
    assert len(calls) == 1

    async def seed_second_jump():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2004",
                    "epss_score",
                    "0.20",
                    "0.40",
                    _history_ts(1),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed_second_jump())
    assert run_db_test(process_watchlist_monitor_alerts()) == 1
    assert len(calls) == 2


def test_watchlist_monitor_skips_disabled_epss(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2005", "policy skip"))

    async def seed():
        from watchlist.policy import save_policy

        db = await get_db()
        try:
            await save_policy(db, {"triggers": {"epss": False, "poc": True}})
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2005', 'pin')"
            )
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2005",
                    "epss_score",
                    "0.05",
                    "0.20",
                    _history_ts(1),
                    "CVE-2024-2005",
                    "has_poc",
                    "0",
                    "1",
                    _history_ts(0.5),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    sent = run_db_test(process_watchlist_monitor_alerts())
    assert sent == 1
    assert len(calls) == 1


def test_watchlist_monitor_patch_when_enabled(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2006", "patch target"))

    async def seed():
        from watchlist.policy import save_policy

        db = await get_db()
        try:
            await save_policy(db, {"triggers": {"patch": True}})
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2006', 'pin')"
            )
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-2006",
                    "patch_available",
                    "0",
                    "1",
                    _history_ts(1),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    assert run_db_test(process_watchlist_monitor_alerts()) == 1
    assert len(calls) == 1
    assert run_db_test(process_watchlist_monitor_alerts()) == 0


def test_watchlist_withdrawn_alerts_pinned(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    run_db_test(_seed_cve(db_path, "CVE-2024-2007", "withdrawn pin"))

    async def seed():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO watchlist (cve_id, state) VALUES ('CVE-2024-2007', 'pin')"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    assert run_db_test(process_watchlist_withdrawn_alerts(["CVE-2024-2007"])) == 1
    assert len(calls) == 1
    assert run_db_test(process_watchlist_withdrawn_alerts(["CVE-2024-2007"])) == 0


def test_webhook_alert_log_helpers(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)

    async def run():
        db = await get_db()
        try:
            assert await was_webhook_alert_sent(db, ALERT_KEV_STACK, "CVE-2024-1") is False
            await record_webhook_alert(db, ALERT_KEV_STACK, "CVE-2024-1")
            await db.commit()
            assert await was_webhook_alert_sent(db, ALERT_KEV_STACK, "CVE-2024-1") is True
            await clear_webhook_alert(db, ALERT_KEV_STACK, "CVE-2024-1")
            await db.commit()
            return await was_webhook_alert_sent(db, ALERT_KEV_STACK, "CVE-2024-1")
        finally:
            await db.close()

    assert run_db_test(run()) is False
