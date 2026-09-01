"""FR1 — per-section intel provenance derivation."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db
import pytest

from database import init_db
from intel.provenance import (
    derive_correlation_provenance,
    derive_detection_provenance,
    derive_exploit_provenance,
)
from resilient_client import record_source_failure, reset_feed_health

@pytest.fixture(autouse=True)
def _clean_feed_health():
    reset_feed_health()
    yield
    reset_feed_health()

def test_exploit_provenance_checked_from_cache(tmp_path, monkeypatch):
    asyncio.run(init_db())

    async def seed() -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO feed_cache (cache_key, result, cached_at)
                VALUES ('sploitus:CVE-2026-PROV', '{"exploits": []}', '2026-07-09 12:00:00')
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    async def run():

        db = await get_db()
        try:
            return await derive_exploit_provenance(db, "CVE-2026-PROV")
        finally:
            await db.close()

    result = asyncio.run(run())
    assert result["status"] == "checked"
    assert "Sploitus" in result["source"]

def test_exploit_provenance_source_unavailable_on_circuit(tmp_path, monkeypatch):
    asyncio.run(init_db())
    for _ in range(3):
        record_source_failure("sploitus", "HTTP 503")

    async def run():

        db = await get_db()
        try:
            return await derive_exploit_provenance(db, "CVE-2026-DOWN")
        finally:
            await db.close()

    result = asyncio.run(run())
    assert result["status"] == "source_unavailable"
    assert result["source"] == "Sploitus"

def test_correlation_provenance_not_configured():
    result = derive_correlation_provenance(
        {"otx_status": "not_configured", "computed_at": "2026-07-09T12:00:00Z"},
        otx_configured=False,
    )
    assert result["status"] == "source_unavailable"
    assert "OTX" in result["source"]

def test_correlation_provenance_checked():
    result = derive_correlation_provenance(
        {"otx_status": "ok", "computed_at": "2026-07-09T12:00:00Z"},
        otx_configured=True,
    )
    assert result["status"] == "checked"
    assert result["as_of"] == "2026-07-09T12:00:00Z"

def test_detection_provenance_checked_after_cache(tmp_path, monkeypatch):
    asyncio.run(init_db())

    async def seed() -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO feed_cache (cache_key, result, cached_at)
                VALUES ('sigma:CVE-2026-DET', '{"rules": []}', '2026-07-09 11:00:00')
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    async def run():

        db = await get_db()
        try:
            return await derive_detection_provenance(
                db, "CVE-2026-DET", technique_ids=["T1190"]
            )
        finally:
            await db.close()

    result = asyncio.run(run())
    assert result["status"] == "checked"
    assert "SigmaHQ" in result["source"]

def test_detail_includes_exploit_provenance(tmp_path, monkeypatch):
    asyncio.run(init_db())

    async def seed() -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, published, is_kev, has_poc)
                VALUES ('CVE-2026-DETAIL', 'Test', 'HIGH', datetime('now'), 0, 0)
                """
            )
            await db.execute(
                """
                INSERT INTO feed_cache (cache_key, result, cached_at)
                VALUES ('sploitus:CVE-2026-DETAIL', '{"exploits": []}', '2026-07-09 10:00:00')
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves/CVE-2026-DETAIL")

    assert res.status_code == 200
    body = res.json()
    assert "exploit_provenance" in body
    assert body["exploit_provenance"]["status"] == "checked"
