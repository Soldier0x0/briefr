"""Operator notification center."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_build_operator_notifications_includes_audit(tmp_path, monkeypatch):
    from database import get_db, init_db, write_audit_log
    from monitoring.notifications import build_operator_notifications

    db_path = tmp_path / "notif.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    from settings import settings

    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    asyncio.run(init_db())

    async def run() -> dict:
        db = await get_db()
        try:
            await write_audit_log(db, "admin", "config.apply", "GROQ_API_KEY")
            await db.commit()
            return await build_operator_notifications(db, limit=10)
        finally:
            await db.close()

    payload = asyncio.run(run())
    assert payload["counts"]["audit"] >= 1
    assert any(evt["type"] == "audit" for evt in payload["events"])
