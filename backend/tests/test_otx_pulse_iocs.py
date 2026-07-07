"""Concurrent OTX pulse IOC storage must not raise duplicate-key errors."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database
from database import get_db, init_db, store_otx_pulse_iocs


def test_concurrent_store_otx_pulse_iocs_is_idempotent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "otx_ioc.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    run_db_test(init_db())

    pulse_id = "pulse-concurrent-test"
    iocs = [
        {"ioc_type": "domain", "ioc_value": "example.com", "description": "a"},
        {"ioc_type": "IPv4", "ioc_value": "203.0.113.1", "description": "b"},
    ]

    async def store_once() -> None:
        db = await get_db()
        try:
            await store_otx_pulse_iocs(db, pulse_id, iocs)
            await db.commit()
        finally:
            await db.close()

    async def run_concurrent() -> list[dict]:
        await asyncio.gather(*(store_once() for _ in range(8)))
        db = await get_db()
        try:
            return await db.execute_fetchall(
                """
                SELECT ioc_type, ioc_value
                FROM otx_pulse_iocs
                WHERE pulse_id = ?
                ORDER BY ioc_type, ioc_value
                """,
                (pulse_id,),
            )
        finally:
            await db.close()

    rows = run_db_test(run_concurrent())
    assert len(rows) == 2
    values = {(row["ioc_type"], row["ioc_value"]) for row in rows}
    assert ("DOMAIN", "example.com") in values
    assert ("IP", "203.0.113.1") in values


def test_replace_otx_pulse_iocs_removes_stale_rows(tmp_path, monkeypatch):
    db_path = str(tmp_path / "otx_ioc_replace.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    run_db_test(init_db())

    pulse_id = "pulse-replace-test"

    async def run() -> list[dict]:
        db = await get_db()
        try:
            await store_otx_pulse_iocs(
                db,
                pulse_id,
                [
                    {"ioc_type": "domain", "ioc_value": "keep.example", "description": ""},
                    {"ioc_type": "domain", "ioc_value": "drop.example", "description": ""},
                ],
            )
            await db.commit()
            await store_otx_pulse_iocs(
                db,
                pulse_id,
                [{"ioc_type": "domain", "ioc_value": "keep.example", "description": "updated"}],
            )
            await db.commit()
            return await db.execute_fetchall(
                "SELECT ioc_value, description FROM otx_pulse_iocs WHERE pulse_id = ?",
                (pulse_id,),
            )
        finally:
            await db.close()

    rows = run_db_test(run())
    assert len(rows) == 1
    assert rows[0]["ioc_value"] == "keep.example"
    assert rows[0]["description"] == "updated"
