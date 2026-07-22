"""Self-stack live risk cap honesty tests (Program D Task 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from security_architecture import merge

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_self_stack_risk.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _cpe(product: str, **overrides):
    return {"vendor": "", "product": product, **overrides}


async def _insert_cves_coro(rows):
    from database import get_db

    db = await get_db()
    try:
        for row in rows:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products, cpe_matches,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["cve_id"],
                    row["description"],
                    row["affected_products"],
                    row["cpe_matches"],
                    row.get("severity", "CRITICAL"),
                    9.8,
                    0.9,
                    row.get("is_kev", 1),
                    row["published"],
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def _self_stack_rows_with_stats_coro(corpus):
    from database import get_db

    db = await get_db()
    try:
        return await merge.self_stack_risk_rows_with_stats(db, corpus)
    finally:
        await db.close()


def _insert_cves(client, rows):
    client.portal.call(_insert_cves_coro, rows)


def _self_stack_rows_with_stats(client, corpus):
    return client.portal.call(_self_stack_rows_with_stats_coro, corpus)


def _cap_honesty_rows():
    scored_rows = [
        {
            "cve_id": f"CVE-2026-1{i:03d}",
            "description": "Structured CPE row that should score.",
            "affected_products": "[]",
            "cpe_matches": json.dumps([_cpe("fastapi")]),
            "published": f"2026-01-{(i % 28) + 1:02d}T00:00:00",
        }
        for i in range(90)
    ]
    candidate_non_scored = [
        {
            "cve_id": f"CVE-2026-2{i:03d}",
            "description": "Token prefilter candidate that should not score.",
            "affected_products": json.dumps(["fastapi package text"]),
            "cpe_matches": "[]",
            "published": f"2026-02-{(i % 28) + 1:02d}T00:00:00",
        }
        for i in range(15)
    ]
    return [*scored_rows, *candidate_non_scored]


def test_self_stack_risk_rows_reports_cap_stats(client):
    corpus = {"self_stack": {"terms": [{"term": "fastapi"}]}}
    _insert_cves(client, _cap_honesty_rows())

    rows, stats = _self_stack_rows_with_stats(client, corpus)

    assert stats["cap"] == 50
    assert stats["admitted"] == len(rows) == 50
    assert stats["candidate_rows"] >= stats["scored_matches"] > stats["admitted"]


def test_risks_section_reports_live_self_stack_cap_honesty(client):
    _insert_cves(client, _cap_honesty_rows())

    response = client.get("/api/security-architecture/section/risks?origin=live")

    assert response.status_code == 200
    payload = response.json()
    stats = payload["live_self_stack"]
    assert stats["cap"] == 50
    assert stats["admitted"] == len(payload["items"])
    assert stats["candidate_rows"] >= stats["scored_matches"] > stats["admitted"]
