import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from db.api_metering import window_api_call_digest
from tests.conftest import run_db_test


def test_window_api_call_digest_allows_720_hours(tmp_path, monkeypatch):
    from db.config import is_postgres

    if is_postgres():
        return
    db_path = tmp_path / "metering_digest.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            digest = await window_api_call_digest(db, hours=720, recent_limit=10)
            assert digest["hours"] == 720
            assert digest["total"] == 0
            assert digest["recent"] == []
            assert digest["by_source"] == []
        finally:
            await db.close()

    run_db_test(_run())
