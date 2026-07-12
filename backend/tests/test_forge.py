"""Forge MVP (Beta V1.3 Theme 3) — coverage map, hunt-packs API, CVE→pack linkage.

Verifies:
- hunt_packs schema lands via the idempotent migration list (fresh + re-run)
- GET /api/forge/coverage statuses (yours / community / gap), counts, stack filter
- POST /api/hunt-packs/generate persists the CVE→pack link idempotently
- GET /api/hunt-packs/{technique_id} returns technique, packs, baseline, linked CVEs
- Input validation mirrors the sibling CVE endpoints (CVE- prefix, T-prefix)
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from database import get_db, init_db
from routers.forge import _coverage_status, _derive_priority, _first_product
from tests.conftest import run_db_test

# PRAGMA table_info/index_list below are SQLite-only introspection — a
# genuine dialect gap (Postgres uses information_schema/pg_catalog), not a
# fixture-pattern issue. Portable rewrite is Post-B scope, not this PR's.
_requires_sqlite = pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="asserts schema via SQLite PRAGMA table_info/index_list",
)

# T1190 is in the bundled template library ("community"); T1566 (Phishing)
# is not — it must surface as a "gap".
COMMUNITY_TID = "T1190"
GAP_TID = "T1566"


@pytest.fixture
def forge_client(tmp_path, monkeypatch):
    db_path = tmp_path / "forge.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await db.executemany(
                "INSERT INTO mitre_techniques (technique_id, name, tactic, url) "
                "VALUES (?, ?, ?, ?)",
                [
                    (COMMUNITY_TID, "Exploit Public-Facing Application",
                     "Initial Access", "https://attack.mitre.org/techniques/T1190/"),
                    (GAP_TID, "Phishing",
                     "Initial Access", "https://attack.mitre.org/techniques/T1566/"),
                ],
            )
            await db.executemany(
                """
                INSERT INTO cves (cve_id, description, affected_products,
                                  mitre_technique, severity, cvss_score,
                                  epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("CVE-2021-44228",
                     "Apache Log4j2 JNDI features allow remote code execution.",
                     '["apache:log4j"]', COMMUNITY_TID, "CRITICAL", 10.0, 0.97, 1,
                     "2021-12-10T00:00:00"),
                    ("CVE-2024-1111",
                     "Phishing-delivered macro in office suite.",
                     '["vendorx:office_suite"]', GAP_TID, "MEDIUM", 6.5, 0.02, 0,
                     "2024-02-01T00:00:00"),
                    ("CVE-2024-2222",
                     "No technique linked to this one.",
                     "[]", None, "LOW", 3.1, 0.01, 0,
                     "2024-03-01T00:00:00"),
                ],
            )
            await db.executemany(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
                [
                    ("CVE-2021-44228", COMMUNITY_TID),
                    ("CVE-2024-1111", GAP_TID),
                ],
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        yield client, db_path


# ── Schema / migration ────────────────────────────────────

@_requires_sqlite
def test_hunt_packs_schema_and_idempotent_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "schema.db"
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def run_twice():
        await init_db()
        await init_db()  # forward-only migration list must be re-runnable

    run_db_test(run_twice())

    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(hunt_packs)")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(hunt_packs)")}
    finally:
        conn.close()

    assert cols == {
        "id", "technique_id", "cve_id", "title", "priority", "sigma_yaml",
        "siem_queries", "log_patterns", "notes", "created_at", "updated_at",
    }
    assert "idx_hunt_packs_technique" in indexes
    assert "idx_hunt_packs_cve" in indexes


# ── Pure helpers ──────────────────────────────────────────

def test_coverage_status_precedence():
    assert _coverage_status(1, GAP_TID) == "yours"          # packs beat everything
    assert _coverage_status(0, COMMUNITY_TID) == "community"
    assert _coverage_status(0, "T1190.003") == "community"  # sub-technique inherits
    assert _coverage_status(0, GAP_TID) == "gap"


def test_derive_priority_tiers():
    assert _derive_priority(1, 5.0, 0.01) == "critical"  # KEV trumps scores
    assert _derive_priority(0, 9.8, 0.01) == "high"
    assert _derive_priority(0, 5.0, 0.6) == "high"
    assert _derive_priority(0, 7.5, 0.01) == "medium"
    assert _derive_priority(0, 3.1, None) == "low"
    assert _derive_priority(None, None, None) == "low"


def test_first_product_parses_vendor_product():
    assert _first_product('["apache:log4j"]') == "log4j"
    assert _first_product('["plain_product"]') == "plain product"
    assert _first_product("[]") == ""
    assert _first_product(None) == ""
    assert _first_product("{not json") == ""


# ── Coverage map ──────────────────────────────────────────

def test_coverage_map_statuses_and_counts(forge_client):
    client, _ = forge_client
    body = client.get("/api/forge/coverage").json()

    by_tid = {t["technique_id"]: t for t in body["techniques"]}
    assert set(by_tid) == {COMMUNITY_TID, GAP_TID}

    community = by_tid[COMMUNITY_TID]
    assert community["status"] == "community"
    assert community["name"] == "Exploit Public-Facing Application"
    assert community["tactic"] == "Initial Access"
    assert community["cve_count"] == 1
    assert community["kev_count"] == 1
    assert community["max_epss"] == 0.97

    gap = by_tid[GAP_TID]
    assert gap["status"] == "gap"
    assert gap["kev_count"] == 0

    assert body["meta"]["counts"] == {"yours": 0, "community": 1, "gap": 1}
    assert body["meta"]["stack_terms"] == []
    assert body["meta"]["technique_total"] == 2
    assert body["meta"]["generated_at"]


def test_coverage_map_stack_filter_narrows(forge_client):
    client, _ = forge_client
    body = client.get("/api/forge/coverage", params={"stack": "log4j"}).json()

    tids = [t["technique_id"] for t in body["techniques"]]
    assert tids == [COMMUNITY_TID]
    assert body["meta"]["stack_terms"] == ["log4j"]


def test_coverage_map_gap_sorts_before_community_within_tactic(forge_client):
    client, _ = forge_client
    body = client.get("/api/forge/coverage").json()
    tids = [t["technique_id"] for t in body["techniques"]]
    assert tids.index(GAP_TID) < tids.index(COMMUNITY_TID)


# ── Generate (CVE→pack linkage) ───────────────────────────

def test_generate_pack_persists_link_and_is_idempotent(forge_client):
    client, db_path = forge_client

    first = client.post("/api/hunt-packs/generate", json={"cve_id": "CVE-2021-44228"})
    assert first.status_code == 200
    body = first.json()
    assert body["created"] is True
    pack = body["pack"]
    assert pack["technique_id"] == COMMUNITY_TID
    assert pack["cve_id"] == "CVE-2021-44228"
    assert pack["priority"] == "critical"  # KEV
    assert "CVE-2021-44228" in pack["sigma_yaml"]
    assert "attack.t1190" in pack["sigma_yaml"]
    assert set(pack["siem_queries"]) >= {
        "elastic_kql", "splunk_spl", "sentinel_kql", "qradar_aql",
    }
    assert pack["log_patterns"]

    second = client.post("/api/hunt-packs/generate", json={"cve_id": "CVE-2021-44228"})
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["pack"]["id"] == pack["id"]

    # Pack now flips the technique's coverage status to "yours" — pack_count
    # here is the idempotency check (only 1 row, not 2, from the two POSTs
    # above), read through the API rather than a direct DB count: a bare
    # get_db() here would try to share the fixture's already-open pool from
    # a different event loop (Postgres) — same issue as test_auth_setup.py.
    coverage = client.get("/api/forge/coverage").json()
    by_tid = {t["technique_id"]: t for t in coverage["techniques"]}
    assert by_tid[COMMUNITY_TID]["status"] == "yours"
    assert by_tid[COMMUNITY_TID]["pack_count"] == 1
    assert coverage["meta"]["counts"]["yours"] == 1


def test_generate_pack_validation(forge_client):
    client, _ = forge_client

    res = client.post("/api/hunt-packs/generate", json={"cve_id": "not-a-cve"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid CVE ID format"

    res = client.post("/api/hunt-packs/generate", json={"cve_id": "CVE-1999-9999"})
    assert res.status_code == 404

    # CVE with no technique link → 400 unless technique_id is supplied
    res = client.post("/api/hunt-packs/generate", json={"cve_id": "CVE-2024-2222"})
    assert res.status_code == 400
    assert "technique" in res.json()["detail"].lower()

    res = client.post(
        "/api/hunt-packs/generate",
        json={"cve_id": "CVE-2024-2222", "technique_id": "T1059"},
    )
    assert res.status_code == 200
    assert res.json()["pack"]["technique_id"] == "T1059"

    res = client.post(
        "/api/hunt-packs/generate",
        json={"cve_id": "CVE-2024-2222", "technique_id": "bogus"},
    )
    assert res.status_code == 400


# ── Hunt pack detail ──────────────────────────────────────

def test_hunt_pack_detail_shape(forge_client):
    client, _ = forge_client

    res = client.get(f"/api/hunt-packs/{COMMUNITY_TID}")
    assert res.status_code == 200
    body = res.json()
    assert body["technique"]["technique_id"] == COMMUNITY_TID
    assert body["technique"]["name"] == "Exploit Public-Facing Application"
    assert body["status"] == "community"
    assert body["packs"] == []
    assert body["siem_queries"]["elastic_kql"]["query"]
    assert body["log_patterns"]
    assert [c["cve_id"] for c in body["linked_cves"]] == ["CVE-2021-44228"]
    assert body["linked_cves"][0]["is_kev"] is True

    client.post("/api/hunt-packs/generate", json={"cve_id": "CVE-2021-44228"})
    body = client.get(f"/api/hunt-packs/{COMMUNITY_TID}").json()
    assert body["status"] == "yours"
    assert len(body["packs"]) == 1
    assert body["packs"][0]["cve_id"] == "CVE-2021-44228"


def test_hunt_pack_detail_validation(forge_client):
    client, _ = forge_client

    res = client.get("/api/hunt-packs/not-a-technique")
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid ATT&CK technique ID"

    res = client.get("/api/hunt-packs/T9999")
    assert res.status_code == 404


# ── Library list + delete (FR-1) ──────────────────────────

def test_list_hunt_packs_empty(forge_client):
    client, _ = forge_client
    body = client.get("/api/hunt-packs").json()
    assert body == {"packs": [], "total": 0}


def test_list_hunt_packs_filters_and_pagination(forge_client):
    client, _ = forge_client

    critical = client.post(
        "/api/hunt-packs/generate", json={"cve_id": "CVE-2021-44228"}
    ).json()["pack"]
    low = client.post(
        "/api/hunt-packs/generate",
        json={"cve_id": "CVE-2024-2222", "technique_id": "T1059"},
    ).json()["pack"]

    all_packs = client.get("/api/hunt-packs").json()
    assert all_packs["total"] == 2
    assert {p["id"] for p in all_packs["packs"]} == {critical["id"], low["id"]}

    by_technique = client.get(
        "/api/hunt-packs", params={"technique_id": COMMUNITY_TID}
    ).json()
    assert by_technique["total"] == 1
    assert by_technique["packs"][0]["id"] == critical["id"]

    by_cve = client.get(
        "/api/hunt-packs", params={"cve_id": "cve-2024-2222"}  # case-insensitive
    ).json()
    assert by_cve["total"] == 1
    assert by_cve["packs"][0]["id"] == low["id"]

    by_priority = client.get(
        "/api/hunt-packs", params={"priority": "critical"}
    ).json()
    assert by_priority["total"] == 1
    assert by_priority["packs"][0]["id"] == critical["id"]

    by_query = client.get(
        "/api/hunt-packs", params={"q": "log4j"}
    ).json()
    assert by_query["total"] == 0  # title search, not sigma content

    by_title = client.get(
        "/api/hunt-packs", params={"q": critical["title"][:10].lower()}
    ).json()
    assert by_title["total"] == 1
    assert by_title["packs"][0]["id"] == critical["id"]

    page1 = client.get("/api/hunt-packs", params={"limit": 1, "offset": 0}).json()
    page2 = client.get("/api/hunt-packs", params={"limit": 1, "offset": 1}).json()
    assert page1["total"] == 2 and page2["total"] == 2
    assert len(page1["packs"]) == 1 and len(page2["packs"]) == 1
    assert page1["packs"][0]["id"] != page2["packs"][0]["id"]


def test_list_hunt_packs_invalid_filters(forge_client):
    client, _ = forge_client

    res = client.get("/api/hunt-packs", params={"technique_id": "not-a-technique"})
    assert res.status_code == 400

    res = client.get("/api/hunt-packs", params={"priority": "urgent"})
    assert res.status_code == 400


def test_delete_hunt_pack_via_client(forge_client):
    client, _ = forge_client

    pack = client.post(
        "/api/hunt-packs/generate", json={"cve_id": "CVE-2021-44228"}
    ).json()["pack"]

    res = client.delete(f"/api/hunt-packs/{pack['id']}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    assert client.get("/api/hunt-packs").json() == {"packs": [], "total": 0}


def test_delete_hunt_pack_404_when_missing(forge_client):
    client, _ = forge_client
    res = client.delete("/api/hunt-packs/999999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Hunt pack not found"


def test_delete_hunt_pack_writes_audit_log(tmp_path, monkeypatch):
    """Direct-DB test (no TestClient) so a fresh get_db() call for the
    audit-log assertion doesn't race the app lifespan's pool -- see the
    forge_client fixture's own comment on this same event-loop pitfall."""
    from routers.forge import delete_hunt_pack

    db_path = str(tmp_path / "forge-audit.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)

    async def run():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO hunt_packs (technique_id, cve_id, title) "
                "VALUES (?, ?, ?)",
                ("T1190", "CVE-2021-44228", "Test pack"),
            )
            await db.commit()
            rows = await db.execute_fetchall("SELECT id FROM hunt_packs")
            pack_id = rows[0]["id"]
        finally:
            await db.close()

        result = await delete_hunt_pack(pack_id)
        assert result == {"ok": True}

        db = await get_db()
        try:
            audit_rows = await db.execute_fetchall(
                "SELECT actor, action, target FROM audit_log WHERE action = ?",
                ("hunt_pack_deleted",),
            )
            assert len(audit_rows) == 1
            assert audit_rows[0]["target"] == "T1190/CVE-2021-44228"
        finally:
            await db.close()

    run_db_test(run())
