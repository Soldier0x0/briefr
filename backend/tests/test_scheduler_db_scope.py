"""Scheduler background jobs should not hold DB pool slots during HTTP/sleep."""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
import ml.product_extraction as pex
from database import init_db
from feeds.otx import run_otx_nightly_correlation
from ml.product_extraction import run_llm_product_extraction


def test_llm_extraction_releases_db_during_groq(tmp_path, monkeypatch):
    """Without a passed connection, Groq runs while no pool slot is held."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "llm_scope.db"))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    held: list[bool] = []

    real_get_db = database.get_db

    async def tracking_get_db():
        conn = await real_get_db()
        held.append(True)

        real_close = conn.close

        async def tracking_close():
            held.pop()
            await real_close()

        conn.close = tracking_close  # type: ignore[method-assign]
        return conn

    monkeypatch.setattr(database, "get_db", tracking_get_db)

    async def fake_extract(description: str, api_key: str) -> list[dict]:
        assert held == [], "Groq call must not run while a connection is held"
        return [{"vendor": "acme", "product": "widget", "version_range": ""}]

    monkeypatch.setattr(pex, "extract_products_via_groq", fake_extract)

    async def run():
        await init_db()
        conn = await database.get_db()
        try:
            await conn.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0099', 'RCE in acme widget', ?, '[]', '[]')",
                (date.today().isoformat(),),
            )
            await conn.commit()
        finally:
            await conn.close()

        return await run_llm_product_extraction()

    stats = asyncio.run(run())
    assert stats["candidates"] == 1
    assert stats["written"] == 1
    assert held == []


def test_otx_nightly_correlation_owns_db_for_cve_list(tmp_path, monkeypatch):
    """CVE list load and per-CVE writes use short-lived connections."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "otx_scope.db"))

    acquires = {"n": 0}
    real_get_db = database.get_db

    async def counting_get_db():
        acquires["n"] += 1
        return await real_get_db()

    monkeypatch.setattr(database, "get_db", counting_get_db)

    async def fake_pulses(cve_id: str, api_key: str) -> list[dict]:
        return [{"id": f"pulse-{cve_id}", "name": "test"}]

    import feeds.otx as otx_mod

    monkeypatch.setattr(otx_mod, "fetch_cve_pulses", fake_pulses)

    async def run():
        await init_db()
        conn = await database.get_db()
        try:
            today = date.today().isoformat()
            await conn.execute(
                "INSERT INTO cves (cve_id, description, published, is_kev, has_poc) "
                "VALUES ('CVE-2024-0100', 'test', ?, 1, 0)",
                (today,),
            )
            await conn.commit()
        finally:
            await conn.close()

        acquires["n"] = 0
        return await run_otx_nightly_correlation(None, "otx-test-key")

    stats = asyncio.run(run())
    assert stats["cves"] == 1
    assert stats["pulses"] == 1
    # One for CVE list + one for the pulse write.
    assert acquires["n"] == 2
