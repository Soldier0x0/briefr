"""OTX upstream outage must not wipe cached CVE pulses."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
from db.correlation import read_otx_cve_pulses, replace_otx_cve_pulses
from feeds.otx import load_otx_pulses_for_cve
from tests.conftest import run_db_test

CVE = "CVE-2021-44228"
PULSE_ID = "pulse-log4shell-smoke"


def test_load_otx_pulses_serves_stale_on_upstream_failure(tmp_path, monkeypatch):
    db_path = str(tmp_path / "otx_stale.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)

    async def _seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await replace_otx_cve_pulses(
                db,
                CVE,
                [
                    {
                        "pulse_id": PULSE_ID,
                        "pulse_name": "Log4Shell campaign",
                        "author": "tester",
                        "created_date": "2021-12-10",
                        "adversary": "actor",
                        "malware_families": [],
                        "tags": [],
                        "targeted_countries": [],
                        "ioc_count": 1,
                    }
                ],
            )
            # Force a cache miss on the 6h freshness gate while keeping any-age rows.
            await db.execute(
                "UPDATE otx_cve_pulses SET fetched_at = '2020-01-01 00:00:00' WHERE cve_id = ?",
                (CVE,),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())

    async def _fake_fetch(_cve_id: str, _api_key: str):
        return None

    monkeypatch.setattr("feeds.otx.fetch_cve_pulses", _fake_fetch)

    async def _load() -> list[dict]:
        db = await get_db()
        try:
            return await load_otx_pulses_for_cve(db, CVE, "fake-key")
        finally:
            await db.close()

    pulses = run_db_test(_load())
    assert len(pulses) == 1
    assert pulses[0]["pulse_id"] == PULSE_ID

    async def _still_cached() -> list[dict] | None:
        db = await get_db()
        try:
            return await read_otx_cve_pulses(db, CVE, max_age_hours=None)
        finally:
            await db.close()

    cached = run_db_test(_still_cached())
    assert cached is not None
    assert len(cached) == 1


def test_fetch_cve_pulses_returns_none_on_upstream_failure(monkeypatch):
    async def _fake_otx_get(*_args, **_kwargs):
        return None

    monkeypatch.setattr("feeds.otx._otx_get", _fake_otx_get)

    async def _run():
        from feeds.otx import fetch_cve_pulses

        return await fetch_cve_pulses(CVE, "fake-key")

    assert run_db_test(_run()) is None
