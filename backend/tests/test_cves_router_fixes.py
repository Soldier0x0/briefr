"""Regression tests for the PR #96 review fixes in routers/cves.py."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db
from routers.cves import _row_to_cve_dict, _sort_by_stack_relevance


def test_sort_by_stack_relevance_handles_null_affected_products():
    """A NULL affected_products column reaches the sorter as an explicit
    None value — it must not raise and must rank below a matching CVE."""
    cves = [
        {"cve_id": "CVE-2024-0001", "affected_products": None, "description": None, "summary": None},
        {
            "cve_id": "CVE-2024-0002",
            "affected_products": ["nginx:nginx"],
            "description": "Buffer overflow in nginx.",
            "summary": "",
        },
    ]
    ranked = _sort_by_stack_relevance(cves, ["nginx"])
    assert [c["cve_id"] for c in ranked] == ["CVE-2024-0002", "CVE-2024-0001"]


def test_row_to_cve_dict_normalizes_list_fields():
    """NULL/'' list columns must surface as [] — API_REFERENCE.md documents
    affected_products/source_urls/cwe_ids as arrays, never null."""
    row = {
        "cve_id": "CVE-2024-0001",
        "affected_products": None,
        "source_urls": "",
        "cwe_ids": '["CWE-79"]',
    }
    d = _row_to_cve_dict(row)
    assert d["affected_products"] == []
    assert d["source_urls"] == []
    assert d["cwe_ids"] == ["CWE-79"]


def test_row_to_cve_dict_unparseable_strings_still_become_empty_lists():
    """Pre-existing behavior kept: garbage/whitespace JSON strings -> []."""
    row = {
        "cve_id": "CVE-2024-0002",
        "affected_products": "{not json",
        "source_urls": "   ",
        "cwe_ids": None,
    }
    d = _row_to_cve_dict(row)
    assert d["affected_products"] == []
    assert d["source_urls"] == []
    assert d["cwe_ids"] == []


def test_sort_by_stack_relevance_noop_without_stack():
    cves = [{"cve_id": "CVE-2024-0001", "affected_products": None}]
    assert _sort_by_stack_relevance(cves, []) is cves


def test_stats_single_query_matches_legacy_counts(tmp_path, monkeypatch):
    """/api/stats was rewritten from five COUNT(*) scans to one conditional
    aggregation — counts must match, including empty-table and NULL columns
    (SUM(CASE ...) is NULL on an empty table and must surface as 0)."""
    db_path = tmp_path / "stats.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        body = client.get("/api/stats").json()
        assert body == {
            "critical": 0,
            "high": 0,
            "kev_count": 0,
            "patched": 0,
            "last_24h": 0,
            "ai_ml_alerts": 0,
        }

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await db.executemany(
                """
                INSERT INTO cves (
                    cve_id, description, severity, is_kev, patch_available, published
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("CVE-2024-0001", "a", "CRITICAL", 1, 0, "2099-01-01T00:00:00"),
                    ("CVE-2024-0002", "b", "HIGH", 0, 1, "2020-01-01T00:00:00"),
                    ("CVE-2024-0003", "c", None, None, None, None),
                ],
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    with TestClient(app) as client:
        body = client.get("/api/stats").json()
        assert body["critical"] == 1
        assert body["high"] == 1
        assert body["kev_count"] == 1
        assert body["patched"] == 1
        assert body["last_24h"] == 1


def test_intel_endpoints_reject_malformed_cve_id(tmp_path, monkeypatch):
    """momentum/detection/correlation validate the CVE- prefix like their
    sibling detail endpoints (detection used to spend GitHub quota on junk)."""
    db_path = tmp_path / "intel.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        for path in (
            "/api/cves/not-a-cve/momentum",
            "/api/cves/not-a-cve/detection",
            "/api/cves/not-a-cve/correlation",
        ):
            res = client.get(path)
            assert res.status_code == 400, path
            assert res.json()["detail"] == "Invalid CVE ID format"

        # Well-formed IDs still pass validation and answer 200.
        res = client.get("/api/cves/CVE-2024-0001/momentum")
        assert res.status_code == 200


def test_correlation_endpoint_serializes_priority_and_suppress_round_trip(tmp_path, monkeypatch):
    """The /correlation response must carry the new `priority` field through
    HTTP JSON serialization, and the suppress/unsuppress endpoints must
    actually remove a campaign from a subsequent GET (dismissed_by included)."""
    db_path = tmp_path / "corr_router.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    async def seed() -> None:
        import database
        from correlation.campaigns import build_campaigns_from_pulses

        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
                VALUES
                    ('CVE-2024-7001', 'Alpha', '2024-01-01', 0, 0, 0.1),
                    ('CVE-2024-7002', 'Beta', '2024-01-02', 0, 0, 0.2)
                """
            )
            pulses = [
                {
                    "pulse_id": "pulse-router-1",
                    "pulse_name": "Router test pulse",
                    "author": "analyst",
                    "created_date": "2024-01-10",
                    "adversary": "APT-ROUTER",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await database.replace_otx_cve_pulses(db, "CVE-2024-7001", pulses)
            await database.replace_otx_cve_pulses(db, "CVE-2024-7002", pulses)
            await db.commit()
            await build_campaigns_from_pulses(db)
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves/CVE-2024-7001/correlation")
        assert res.status_code == 200
        body = res.json()
        assert len(body["campaigns"]) == 1
        campaign_id = body["campaigns"][0]["campaign_id"]
        assert body["priority"]["score"] > 0
        assert body["priority"]["components"][0]["signal"] == "campaign"

        sup = client.post(
            f"/api/cves/CVE-2024-7001/correlation/suppress",
            json={
                "scope": "campaign_id",
                "key": {"campaign_id": campaign_id},
                "reason": "test dismiss",
                "dismissed_by": "tester@example.com",
            },
        )
        assert sup.status_code == 200
        assert sup.json()["suppression"]["dismissed_by"] == "tester@example.com"

        res2 = client.get("/api/cves/CVE-2024-7001/correlation")
        assert res2.json()["campaigns"] == []

        unsup = client.delete(
            f"/api/cves/CVE-2024-7001/correlation/suppress"
            f"?scope=campaign_id&campaign_id={campaign_id}"
        )
        assert unsup.status_code == 200

        res3 = client.get("/api/cves/CVE-2024-7001/correlation")
        assert len(res3.json()["campaigns"]) == 1
