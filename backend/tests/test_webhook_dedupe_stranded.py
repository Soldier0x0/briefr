"""IDEM-D — sweep crash-stranded webhook dedupe claims.

A claim is committed before delivery and cleared on failure, so a claim with no
successful delivery-log row is one a crashed worker stranded. The sweep removes
only those, bounded to the delivery-log retention window so a legitimately-sent
claim is never removed (which would cause a spurious re-alert).

SQLite via temp DB_PATH; no live server.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from tests.conftest import run_db_test

from db.cache_retention import purge_stranded_webhook_dedupe


def _fmt(dt: datetime) -> str:
    return dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


async def _insert_claim(db, dest, event, key, recorded_at):
    await db.execute(
        "INSERT INTO webhook_destination_dedupe (destination_id, event_type, dedupe_key, recorded_at)"
        " VALUES (?, ?, ?, ?)",
        (dest, event, key, recorded_at),
    )


async def _insert_delivery(db, dest, event, key, status):
    await db.execute(
        "INSERT INTO webhook_delivery_log (destination_id, event_type, dedupe_key, status, error)"
        " VALUES (?, ?, ?, ?, ?)",
        (dest, event, key, status, None),
    )


def test_sweep_removes_only_stranded_claims(tmp_path):
    db_file = str(tmp_path / "dedupe.db")
    os.environ["DB_PATH"] = db_file

    async def run():
        import database as db_module

        db_module.DB_PATH = db_file
        await db_module.init_db()

        now = datetime.now(timezone.utc)
        stranded = _fmt(now - timedelta(hours=6))     # old, no delivery → sweep
        sent = _fmt(now - timedelta(hours=6))         # old, but delivered → keep
        midflight = _fmt(now - timedelta(minutes=5))  # inside grace → keep
        ancient = _fmt(now - timedelta(days=45))      # beyond log retention → keep

        db = await db_module.get_db()
        try:
            await _insert_claim(db, "d1", "kev_alert", "CVE-1:kev", stranded)
            await _insert_claim(db, "d1", "kev_alert", "CVE-2:kev", sent)
            await _insert_delivery(db, "d1", "kev_alert", "CVE-2:kev", "ok")
            await _insert_claim(db, "d1", "kev_alert", "CVE-3:kev", midflight)
            await _insert_claim(db, "d1", "kev_alert", "CVE-4:kev", ancient)
            await db.commit()
        finally:
            await db.close()

        db = await db_module.get_db()
        try:
            deleted = await purge_stranded_webhook_dedupe(db)
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT dedupe_key FROM webhook_destination_dedupe ORDER BY dedupe_key"
            )
        finally:
            await db.close()

        assert deleted == 1
        remaining = {dict(r)["dedupe_key"] for r in rows}
        assert remaining == {"CVE-2:kev", "CVE-3:kev", "CVE-4:kev"}

    run_db_test(run())
