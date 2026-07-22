"""Tests for cache/overlay retention sweeps (Sprint C3)."""

import asyncio
from datetime import datetime, timedelta, timezone

import database as db_module
from settings import settings


def _force_sqlite(tmp_path, monkeypatch, db_name: str):
    db_path = tmp_path / db_name
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    return db_path


def _utc(days_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_purge_stale_feed_cache_keeps_fresh_ssvc(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "retention.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO feed_cache (cache_key, result, cached_at)
                VALUES (?, ?, ?), (?, ?, ?)
                """,
                (
                    "ssvc:CVE-2024-0001",
                    '{"decisions": {"Exploitation": "active"}}',
                    _utc(200),
                    "greynoise:1.2.3.4",
                    '{"noise": true}',
                    _utc(10),
                ),
            )
            await db.commit()

            deleted = await db_module.purge_stale_feed_cache(db)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT cache_key FROM feed_cache ORDER BY cache_key"
            )
            keys = [row["cache_key"] for row in rows]
            assert deleted >= 1
            assert "ssvc:CVE-2024-0001" in keys
            assert "greynoise:1.2.3.4" not in keys
        finally:
            await db.close()

    asyncio.run(run())


def test_purge_old_ai_operations_uses_started_at(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "ai_ops_retention.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            for op_id, days_ago in (("old-op", 45), ("recent-op", 2)):
                await db_module.insert_ai_operation(
                    db,
                    operation_id=op_id,
                    request_id=None,
                    started_at=_utc(days_ago),
                    latency_ms=10,
                    feature="pdf_summary",
                    task_class="pdf_summary",
                    provider="groq",
                    model="m",
                    success=True,
                )
            await db.commit()

            deleted = await db_module.purge_old_ai_operations(db, retention_days=30)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT operation_id FROM ai_operations ORDER BY operation_id"
            )
            assert deleted == 1
            assert [row["operation_id"] for row in rows] == ["recent-op"]
        finally:
            await db.close()

    asyncio.run(run())


def test_purge_old_webhook_delivery_log_uses_attempted_at(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "webhook_delivery_retention.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO webhook_delivery_log (
                    destination_id, event_type, dedupe_key, status, error, attempted_at
                ) VALUES (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?)
                """,
                (
                    "db:old",
                    "kev_alert",
                    "CVE-2024-1",
                    "ok",
                    None,
                    _utc(45),
                    "db:recent",
                    "kev_alert",
                    "CVE-2024-2",
                    "ok",
                    None,
                    _utc(2),
                ),
            )
            await db.commit()

            deleted = await db_module.purge_old_webhook_delivery_log(db, retention_days=30)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT destination_id FROM webhook_delivery_log ORDER BY destination_id"
            )
            assert deleted == 1
            assert [row["destination_id"] for row in rows] == ["db:recent"]
        finally:
            await db.close()

    asyncio.run(run())


def test_purge_old_audit_log_uses_created_at(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "audit_log_retention.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO audit_log (actor, action, target, created_at)
                VALUES (?, ?, ?, ?), (?, ?, ?, ?)
                """,
                (
                    "admin",
                    "test.old",
                    "t1",
                    _utc(400),
                    "admin",
                    "test.recent",
                    "t2",
                    _utc(10),
                ),
            )
            await db.commit()

            deleted = await db_module.purge_old_audit_log(db, retention_days=365)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT target FROM audit_log ORDER BY target"
            )
            assert deleted == 1
            assert [row["target"] for row in rows] == ["t2"]
        finally:
            await db.close()

    asyncio.run(run())


def test_run_retention_cleanup_includes_operator_tables(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "retention_all.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            stats = await db_module.run_retention_cleanup(db)
            await db.commit()
            for key in (
                "ai_operations",
                "ai_operation_payloads",
                "webhook_delivery_log",
                "audit_log",
            ):
                assert key in stats
        finally:
            await db.close()

    asyncio.run(run())


def test_purge_old_cve_change_history_uses_detected_at(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "change_history.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cve_change_history (
                    cve_id, field_name, old_value, new_value, detected_at
                ) VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-0001",
                    "severity",
                    "LOW",
                    "HIGH",
                    _utc(120),
                    "CVE-2024-0002",
                    "severity",
                    "LOW",
                    "MEDIUM",
                    _utc(1),
                ),
            )
            await db.commit()

            deleted = await db_module.purge_old_cve_change_history(db, retention_days=90)
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT cve_id FROM cve_change_history ORDER BY cve_id"
            )
            assert deleted == 1
            assert [row["cve_id"] for row in rows] == ["CVE-2024-0002"]
        finally:
            await db.close()

    asyncio.run(run())


def test_purge_stale_ioc_cache(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch, "ioc.db")

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
                VALUES (?, ?, ?, ?), (?, ?, ?, ?)
                """,
                (
                    "8.8.8.8",
                    "ip",
                    "{}",
                    _utc(2),
                    "1.1.1.1",
                    "ip",
                    "{}",
                    _utc(0.01),
                ),
            )
            await db.commit()

            deleted = await db_module.purge_stale_ioc_cache(db, retention_hours=24)
            await db.commit()

            rows = await db.execute_fetchall("SELECT value FROM ioc_cache")
            assert deleted == 1
            assert [row["value"] for row in rows] == ["1.1.1.1"]
        finally:
            await db.close()

    asyncio.run(run())
