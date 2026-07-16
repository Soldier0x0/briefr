"""Chunked CVE presence checks — avoid full-table scans during KEV cross-fetch."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import filter_cve_ids_present, get_db, init_db, missing_cve_ids, upsert_cve
from tests.conftest import run_db_test


def test_missing_cve_ids_uses_chunked_lookup(tmp_path, monkeypatch):
    db_path = tmp_path / "missing_cve.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-0001",
                    "description": "test",
                    "published": "2024-01-01",
                },
            )
            await db.commit()
            present = await filter_cve_ids_present(
                db,
                ["CVE-2024-0001", "CVE-2024-9999", "cve-2024-0001"],
            )
            assert present == {"CVE-2024-0001"}
            missing = await missing_cve_ids(
                db,
                ["CVE-2024-0001", "CVE-2024-9999", "CVE-2024-8888"],
            )
            assert missing == ["CVE-2024-9999", "CVE-2024-8888"]
        finally:
            await db.close()

    run_db_test(_run())
