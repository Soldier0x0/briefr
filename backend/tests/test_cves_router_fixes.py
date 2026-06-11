"""Regression tests for the PR #96 review fixes in routers/cves.py."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import init_db
from routers.cves import _sort_by_stack_relevance


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


def test_sort_by_stack_relevance_noop_without_stack():
    cves = [{"cve_id": "CVE-2024-0001", "affected_products": None}]
    assert _sort_by_stack_relevance(cves, []) is cves


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
