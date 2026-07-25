"""PR-P3 / IDX-001: idx_cves_modified exists after bootstrap."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from database import get_db, init_db
from db.config import is_postgres
from tests.conftest import run_db_test


def test_idx_cves_modified_migration_file_exists():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "022_idx_cves_modified.py"
    )
    assert migration.is_file()
    text = migration.read_text(encoding="utf-8")
    assert "idx_cves_modified" in text
    assert "cves(modified)" in text


@pytest.mark.skipif(is_postgres(), reason="sqlite_master is SQLite-only")
def test_init_db_creates_idx_cves_modified(tmp_path, monkeypatch):
    db_path = tmp_path / "idx_modified.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'cves'"
            )
            names = {row["name"] for row in rows}
            assert "idx_cves_modified" in names
        finally:
            await db.close()

    run_db_test(_run())
