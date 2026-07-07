"""Regression test (PR #95 review): on a cached IOC hit, the feed_cache
writes made by on-demand OTX/GreyNoise enrichment must be committed —
otherwise they roll back on connection close and every cached hit
re-spends API quota."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database
from routers import ioc as ioc_router


def test_cached_hit_commits_enrichment_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "ioc.db"))
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    monkeypatch.delenv("GREYNOISE_API_KEY", raising=False)

    async def fake_lookup_otx_for_ioc(db, value, ioc_type, api_key):
        result = {"pulse_count": 0, "pulses": []}
        await database.set_feed_cache(
            db, f"otx:ioc:{ioc_type}:{value.lower()}", result
        )
        return result

    monkeypatch.setattr(ioc_router, "lookup_otx_for_ioc", fake_lookup_otx_for_ioc)

    async def _run():
        await database.init_db()

        db = await database.get_db()
        try:
            await database.set_ioc_cache(db, "8.8.8.8", "ip", {"verdict": "clean"})
            await db.commit()
        finally:
            await db.close()

        body = ioc_router.IocLookupRequest(value="8.8.8.8", type="ip")
        result = await ioc_router.ioc_lookup(body)
        assert result["cached"] is True

        # Fresh connection: the enrichment write must have been committed.
        db = await database.get_db()
        try:
            return await database.get_feed_cache(
                db, "otx:ioc:ip:8.8.8.8", max_age_hours=1
            )
        finally:
            await db.close()

    persisted = run_db_test(_run())
    assert persisted == {"pulse_count": 0, "pulses": []}
