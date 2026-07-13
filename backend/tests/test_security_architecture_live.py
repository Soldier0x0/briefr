"""TM-3: Security Architecture live sections -- MITRE ATT&CK, Threat
Scenarios wrap, Controls active flags, Self-exposure merge (spec §4.5, §8).

Verifies:
- GET /api/security-architecture/mitre matches routers.forge.build_coverage_map
  output shape (same query, not a reimplementation).
- GET /api/security-architecture/threat-scenarios matches
  /api/threat-model/scenarios output for the same stack, and self_stack=true
  swaps in the generated self-stack terms instead.
- /section/controls rows carry a live `active` flag resolved from live_flag.
- /section/risks includes live-derived self-stack rows with a visible
  matched term, filterable by ?origin=live, and excluded from ?stale=true.
- security_architecture.merge's pure helpers (resolve_control_active,
  self_stack_terms) in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from security_architecture import merge

COMMUNITY_TID = "T1190"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_live.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


async def _seed_coro(self_stack_term="fastapi"):
    """Seed a technique + a KEV CVE whose description matches a real
    self-stack term (fastapi ships in requirements.txt -- see
    corpus/self_stack.yaml) so self-stack merge queries have something to
    match without needing to monkeypatch the corpus."""
    from database import get_db

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO mitre_techniques (technique_id, name, tactic, url) "
            "VALUES (?, ?, ?, ?)",
            (COMMUNITY_TID, "Exploit Public-Facing Application", "Initial Access",
             "https://attack.mitre.org/techniques/T1190/"),
        )
        await db.execute(
            """
            INSERT INTO cves (cve_id, description, affected_products,
                              severity, cvss_score, epss_score, is_kev, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CVE-2024-9999",
                f"Remote code execution in {self_stack_term} request handling.",
                "[]", "CRITICAL", 9.8, 0.9, 1, "2024-01-01T00:00:00",
            ),
        )
        await db.execute(
            "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES (?, ?)",
            ("CVE-2024-9999", COMMUNITY_TID),
        )
        await db.commit()
    finally:
        await db.close()


def _seed(client, self_stack_term="fastapi"):
    """Run the seed coroutine on the TestClient's own event loop via its
    anyio portal, not a bare `asyncio.run()` -- the app lifespan already
    opened the Postgres connection pool on that loop, and asyncpg's Pool
    binds release/reset futures to the loop that created it. A second
    `asyncio.run()` spins up an unrelated loop and blows up with
    'attached to a different loop' / 'another operation is in progress'
    under Postgres (SQLite's aiosqlite tolerates it, which is why this
    only surfaces in the dual-DB run -- CLAUDE.md danger zone 1). Same fix
    as tests/test_forge.py's `run_db_test(seed())` placed *before*
    `TestClient(app)` opens; `portal.call` is the equivalent for seeding
    *after* the client is already open, which every test in this file
    needs (fixture seeding alone isn't enough -- some tests insert more
    rows mid-test)."""
    client.portal.call(_seed_coro, self_stack_term)


# ── MITRE (wraps routers.forge.build_coverage_map) ─────────────────────

def test_mitre_matches_forge_coverage_output(client):
    _seed(client)
    mitre_res = client.get("/api/security-architecture/mitre")
    forge_res = client.get("/api/forge/coverage")
    assert mitre_res.status_code == 200
    assert mitre_res.json() == forge_res.json()


def test_mitre_stack_filter_narrows_results(client):
    _seed(client)
    all_res = client.get("/api/security-architecture/mitre").json()
    narrowed = client.get("/api/security-architecture/mitre?stack=nonexistent-product-xyz").json()
    assert all_res["meta"]["technique_total"] >= narrowed["meta"]["technique_total"]


# ── Threat scenarios (wraps threat_model.scenarios.build_threat_scenarios) ─

def test_threat_scenarios_matches_forge_parity_endpoint(client):
    _seed(client)
    sa_res = client.get("/api/security-architecture/threat-scenarios?stack=fastapi")
    tm_res = client.get("/api/threat-model/scenarios?stack=fastapi")
    assert sa_res.status_code == 200
    sa_body = sa_res.json()
    tm_body = tm_res.json()
    assert sa_body["scenarios"] == tm_body["scenarios"]
    assert sa_body["meta"]["catalog"] == "stack"


def test_threat_scenarios_self_stack_toggle_ignores_stack_param(client):
    _seed(client, self_stack_term="fastapi")
    res = client.get("/api/security-architecture/threat-scenarios?self_stack=true&stack=irrelevant")
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["catalog"] == "self-stack"
    # Self-stack terms come from the generated corpus, not the ignored `stack` param.
    assert "irrelevant" not in body["meta"]["stack_terms"]
    assert any(t["technique_id"] == COMMUNITY_TID for t in body["scenarios"])


# ── Controls: live active flag ──────────────────────────────────────────

def test_controls_section_rows_carry_live_active_flag(client):
    res = client.get("/api/security-architecture/section/controls")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] > 0
    assert all("active" in item for item in body["items"])
    # Structural controls (no live_flag) always read active.
    jwt = next(i for i in body["items"] if i["id"] == "jwt-session-auth")
    assert jwt["active"] is True


def test_controls_active_flag_respects_env_override(client, monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "0")
    res = client.get("/api/security-architecture/section/controls")
    body = res.json()
    backup = next(i for i in body["items"] if i["id"] == "backup-encryption")
    assert backup["active"] is False


# ── Risks: live self-stack rows (spec §4.5) ─────────────────────────────

def test_risks_section_includes_live_self_stack_row_with_matched_term(client):
    _seed(client, self_stack_term="fastapi")
    res = client.get("/api/security-architecture/section/risks")
    assert res.status_code == 200
    body = res.json()
    live_rows = [r for r in body["items"] if r.get("origin") == "live"]
    assert live_rows, "expected at least one live self-stack risk row"
    row = live_rows[0]
    assert row["matched_term"]
    assert row["cve_id"] == "CVE-2024-9999"
    assert row["is_kev"] is True


def test_risks_section_live_row_reports_real_severity_not_invented(client):
    """A KEV CVE isn't necessarily severity=CRITICAL -- the live row must
    report the DB's actual severity, not synthesize one. Inventing
    'critical' here would violate the central principle (spec v2 note 3:
    no opinion rendered as measurement)."""
    from database import get_db

    async def _insert_high_severity_kev():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-8888",
                    "Remote code execution in fastapi routing.",
                    "[]", "HIGH", 7.5, 0.4, 1, "2024-02-01T00:00:00",
                ),
            )
            await db.commit()
        finally:
            await db.close()

    client.portal.call(_insert_high_severity_kev)

    res = client.get("/api/security-architecture/section/risks?origin=live")
    body = res.json()
    row = next(r for r in body["items"] if r["cve_id"] == "CVE-2024-8888")
    assert row["severity"] == "high"
    assert row["is_kev"] is True


def test_risks_section_origin_filter_isolates_live_rows(client):
    _seed(client, self_stack_term="fastapi")
    res = client.get("/api/security-architecture/section/risks?origin=live")
    body = res.json()
    assert body["count"] > 0
    assert all(r["origin"] == "live" for r in body["items"])


def test_risks_stale_filter_excludes_live_rows(client):
    """Live rows have no review_date -- they can never be 'stale' the way a
    curated judgment call can; stale filtering must not error or include them."""
    _seed(client, self_stack_term="fastapi")
    res = client.get("/api/security-architecture/section/risks?stale=true")
    assert res.status_code == 200
    assert all(r.get("origin") != "live" for r in res.json()["items"])


def test_overview_self_cve_exposure_tile_reflects_live_kev_hit(client):
    _seed(client, self_stack_term="fastapi")
    res = client.get("/api/security-architecture/overview")
    body = res.json()
    tile = next(t for t in body["tiles"] if t["id"] == "self_cve_exposure")
    assert tile["value"] > 0
    assert tile["section"] == "risks"
    assert tile["filter"] == {"origin": "live"}
    assert body["self_exposure"]["kev_count"] > 0


def test_overview_mitre_detection_coverage_tile_is_a_visible_ratio(client):
    _seed(client)
    res = client.get("/api/security-architecture/overview")
    tile = next(t for t in res.json()["tiles"] if t["id"] == "mitre_detection_coverage")
    assert "/" in tile["value"]
    assert tile["section"] == "mitre_attack"


# ── merge.py pure helpers ────────────────────────────────────────────────

def test_resolve_control_active_structural_control_always_active():
    assert merge.resolve_control_active({"id": "x"}) is True


def test_resolve_control_active_respects_falsy_env_values(monkeypatch):
    monkeypatch.setenv("SOME_FLAG", "off")
    assert merge.resolve_control_active({"live_flag": "SOME_FLAG"}) is False
    monkeypatch.setenv("SOME_FLAG", "1")
    assert merge.resolve_control_active({"live_flag": "SOME_FLAG"}) is True


def test_self_stack_terms_reads_generated_layer():
    corpus = {"self_stack": {"terms": [{"term": "fastapi"}, {"term": "react"}]}}
    assert merge.self_stack_terms(corpus) == ["fastapi", "react"]


def test_self_stack_terms_empty_when_layer_missing():
    assert merge.self_stack_terms({}) == []
