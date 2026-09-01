"""C-Evolve-2: member_of_campaign + campaign_lifecycle on list/export API."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db
import pytest

from database import init_db

async def _seed_campaign_cve(db, cve_id: str) -> None:
    await db.execute(
        """
        INSERT INTO cves (
            cve_id, description, severity, published, modified, is_kev, has_poc
        ) VALUES (?, 'Campaign member test', 'HIGH', datetime('now'), datetime('now'), 0, 0)
        """,
        (cve_id,),
    )

async def _seed_campaign(db, campaign_id: str, cve_id: str, lifecycle: str) -> None:
    await db.execute(
        """
        INSERT INTO correlation_campaigns (
            campaign_id, primary_pulse_id, label, confidence,
            member_count, lifecycle, campaign_version, computed_at
        ) VALUES (?, 'pulse-test', 'Test campaign', 'medium', 1, ?, '2.0.0', datetime('now'))
        """,
        (campaign_id, lifecycle),
    )
    await db.execute(
        """
        INSERT INTO correlation_campaign_members (campaign_id, cve_id, role)
        VALUES (?, ?, 'member')
        """,
        (campaign_id, cve_id),
    )

@pytest.mark.parametrize("lifecycle", ["active", "emerging", "declining", "stale"])
def test_list_cves_campaign_marker(tmp_path, monkeypatch, lifecycle):
    asyncio.run(init_db())

    cve_id = f"CVE-2026-CAMP-{lifecycle.upper()}"

    async def seed() -> None:
        db = await get_db()
        try:
            await _seed_campaign_cve(db, cve_id)
            await _seed_campaign(db, f"camp_{lifecycle}", cve_id, lifecycle)
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get(f"/api/cves?search={cve_id}")

    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["cve_id"] == cve_id
    assert row["member_of_campaign"] is True
    assert row["campaign_lifecycle"] == lifecycle

def test_list_cves_no_campaign_marker(tmp_path, monkeypatch):
    asyncio.run(init_db())

    cve_id = "CVE-2026-NOCAMP"

    async def seed() -> None:
        db = await get_db()
        try:
            await _seed_campaign_cve(db, cve_id)
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get(f"/api/cves?search={cve_id}")

    assert res.status_code == 200
    row = res.json()["data"][0]
    assert row["member_of_campaign"] is False
    assert "campaign_lifecycle" not in row

def test_export_includes_campaign_marker(tmp_path, monkeypatch):
    asyncio.run(init_db())

    cve_id = "CVE-2026-EXPORT-CAMP"

    async def seed() -> None:
        db = await get_db()
        try:
            await _seed_campaign_cve(db, cve_id)
            await _seed_campaign(db, "camp_export", cve_id, "active")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get(f"/api/cves/export?search={cve_id}")

    assert res.status_code == 200
    row = res.json()["data"][0]
    assert row["member_of_campaign"] is True
    assert row["campaign_lifecycle"] == "active"
