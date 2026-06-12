"""Tests for KEV-on-stack and backup dead-man webhook rules."""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
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
    BACKUP_DEADMAN_TARGET,
    check_backup_deadman,
    process_kev_stack_alerts,
)


def _setup_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "webhooks.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    asyncio.run(init_db())
    return db_path


def _mock_webhooks(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    monkeypatch.setenv("BRIEFR_STACK_TERMS", "nginx")
    monkeypatch.setenv("BACKUP_ENABLED", "1")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    reset_feed_health()
    return calls


async def _seed_cve(db_path: Path, cve_id: str, description: str, is_kev: int = 0):
    db = await aiosqlite.connect(db_path)
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
    asyncio.run(_seed_cve(db_path, "CVE-2024-1001", "nginx reverse proxy RCE"))

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

    sent, sent_again = asyncio.run(run())
    assert sent == 1
    assert sent_again == 0
    assert len(calls) == 1


def test_kev_stack_skips_non_matching(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    calls = _mock_webhooks(monkeypatch)
    asyncio.run(_seed_cve(db_path, "CVE-2024-1002", "unrelated apache issue"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-1002"])
            await db.commit()
        finally:
            await db.close()
        return await process_kev_stack_alerts(newly)

    assert asyncio.run(run()) == 0
    assert calls == []


def test_kev_stack_requires_stack_terms(tmp_path, monkeypatch):
    db_path = _setup_db(tmp_path, monkeypatch)
    _mock_webhooks(monkeypatch)
    monkeypatch.delenv("BRIEFR_STACK_TERMS", raising=False)
    asyncio.run(_seed_cve(db_path, "CVE-2024-1003", "nginx issue"))

    async def run():
        db = await get_db()
        try:
            newly = await mark_cves_as_kev(db, ["CVE-2024-1003"])
            await db.commit()
        finally:
            await db.close()
        return await process_kev_stack_alerts(newly)

    assert asyncio.run(run()) == 0


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

    first, second = asyncio.run(run())
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
        db = await get_db()
        try:
            await clear_webhook_alert(db, ALERT_BACKUP_DEADMAN, BACKUP_DEADMAN_TARGET)
            await db.commit()
        finally:
            await db.close()
        return await check_backup_deadman()

    assert asyncio.run(run()) is False
    assert len(calls) == 1


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

    assert asyncio.run(run()) is False
