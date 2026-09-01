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

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import get_db
from security_architecture import merge

COMMUNITY_TID = "T1190"

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_live.db"

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

def _cpe(product: str, **overrides):
    return {"vendor": "", "product": product, **overrides}

async def _seed_coro(self_stack_term="fastapi"):
    """Seed a technique + a KEV CVE whose structured CPE matches a real
    self-stack term (fastapi ships in requirements.txt -- see
    corpus/self_stack.yaml) so self-stack merge queries have something to
    match without needing to monkeypatch the corpus."""

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
            INSERT INTO cves (cve_id, description, affected_products, cpe_matches,
                              severity, cvss_score, epss_score, is_kev, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CVE-2024-9999",
                f"Remote code execution in {self_stack_term} request handling.",
                "[]", json.dumps([_cpe(self_stack_term)]),
                "CRITICAL", 9.8, 0.9, 1, "2024-01-01T00:00:00",
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
    under Postgres. Same fix as tests/test_forge.py's `run_db_test(seed())` placed *before*
    `TestClient(app)` opens; `portal.call` is the equivalent for seeding
    *after* the client is already open, which every test in this file
    needs (fixture seeding alone isn't enough -- some tests insert more
    rows mid-test)."""
    client.portal.call(_seed_coro, self_stack_term)

async def _insert_cve_coro(
    cve_id,
    description,
    cpe_matches,
    affected_products="[]",
    severity="CRITICAL",
    is_kev=1,
    published="2024-01-01T00:00:00",
):

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO cves (cve_id, description, affected_products, cpe_matches,
                              severity, cvss_score, epss_score, is_kev, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cve_id, description, affected_products, json.dumps(cpe_matches),
                severity, 9.8, 0.9, is_kev, published,
            ),
        )
        await db.commit()
    finally:
        await db.close()

async def _insert_cves_coro(rows):
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
                    row.get("affected_products", "[]"),
                    json.dumps(row["cpe_matches"]),
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

async def _self_stack_risk_rows_coro(corpus):

    db = await get_db()
    try:
        return await merge.self_stack_risk_rows(db, corpus)
    finally:
        await db.close()

def _insert_cve(
    client,
    cve_id,
    *,
    description,
    cpe_matches,
    affected_products="[]",
    severity="CRITICAL",
    is_kev=1,
    published="2024-01-01T00:00:00",
):
    client.portal.call(
        _insert_cve_coro,
        cve_id,
        description,
        cpe_matches,
        affected_products,
        severity,
        is_kev,
        published,
    )

def _self_stack_risk_rows(client, corpus):
    return client.portal.call(_self_stack_risk_rows_coro, corpus)

def _insert_cves(client, rows):
    client.portal.call(_insert_cves_coro, rows)

# ── MITRE (wraps routers.forge.build_coverage_map) ─────────────────────

def test_mitre_matches_forge_coverage_output(client):
    _seed(client)
    mitre_res = client.get("/api/security-architecture/mitre")
    forge_res = client.get("/api/forge/coverage")
    assert mitre_res.status_code == 200
    assert forge_res.status_code == 200
    mitre_body = mitre_res.json()
    forge_body = forge_res.json()
    # build_coverage_map stamps generated_at per invocation — two sequential
    # HTTP calls can land on different seconds under CI load. Parity is the
    # technique rows and non-timestamp meta, not the wall-clock stamp.
    assert mitre_body["techniques"] == forge_body["techniques"]
    mitre_meta = {k: v for k, v in mitre_body["meta"].items() if k != "generated_at"}
    forge_meta = {k: v for k, v in forge_body["meta"].items() if k != "generated_at"}
    assert mitre_meta == forge_meta
    assert mitre_body["meta"]["generated_at"]
    assert forge_body["meta"]["generated_at"]

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

def test_postgres_required_control_defaults_active_when_unset(client, monkeypatch):
    """BRIEFR_REQUIRE_POSTGRES is enforced by default: settings.py defaults
    settings.briefr_require_postgres to True, so an unset env var must read
    as ACTIVE (flipped from opt-in default-False behavior on PR #494)."""
    res = client.get("/api/security-architecture/section/controls")
    body = res.json()
    control = next(i for i in body["items"] if i["id"] == "postgres-required-in-production")
    assert control["active"] is True
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    res = client.get("/api/security-architecture/section/controls")
    body = res.json()
    control = next(i for i in body["items"] if i["id"] == "postgres-required-in-production")
    assert control["active"] is False

def test_rate_limiting_control_reflects_real_toggle(client, monkeypatch):
    """Gemini review on PR #494: the rate-limiting control had no live_flag,
    so it always read ACTIVE even with RATE_LIMIT_ENABLED=0 (rate_limit
    .py::_enforce returns immediately in that case -- a real posture gap
    the control must not paper over)."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    res = client.get("/api/security-architecture/section/controls")
    body = res.json()
    control = next(i for i in body["items"] if i["id"] == "rate-limiting")
    assert control["active"] is False

# ── Risks: live self-stack rows (spec §4.5) ─────────────────────────────

def test_curveball_does_not_match_pypi_cryptography(client):
    corpus = {
        "self_stack": {
            "terms": [
                {"term": "cryptography", "ecosystem": "pypi", "version": "41.0.0"},
            ],
        },
    }
    _insert_cve(
        client,
        "CVE-2020-0601",
        description="Windows CryptoAPI certificate spoofing sometimes called CurveBall; cryptography teams tracked it.",
        cpe_matches=[_cpe("cryptoapi", vendor="microsoft", version="10")],
    )

    rows = _self_stack_risk_rows(client, corpus)

    assert rows == []

def test_product_version_match_is_strong(client):
    corpus = {
        "self_stack": {
            "terms": [
                {"term": "react", "ecosystem": "npm", "version": "18.2.0"},
            ],
        },
    }
    _insert_cve(
        client,
        "CVE-2024-2001",
        description="Structured product metadata only.",
        cpe_matches=[
            _cpe(
                "react",
                version_start_including="18.0.0",
                version_end_excluding="18.3.0",
            ),
        ],
    )

    rows = _self_stack_risk_rows(client, corpus)

    assert len(rows) == 1
    assert rows[0]["cve_id"] == "CVE-2024-2001"
    assert rows[0]["match_score"] == 100
    assert rows[0]["match_basis"] == "product+version"

def test_product_only_match_is_weaker_labeled(client):
    corpus = {
        "self_stack": {
            "terms": [
                {"term": "fastapi", "ecosystem": "pypi", "version": None},
            ],
        },
    }
    _insert_cve(
        client,
        "CVE-2024-2002",
        description="Structured product metadata only.",
        cpe_matches=[_cpe("fastapi")],
    )

    rows = _self_stack_risk_rows(client, corpus)

    assert len(rows) == 1
    assert rows[0]["cve_id"] == "CVE-2024-2002"
    assert rows[0]["match_score"] == 55
    assert rows[0]["match_basis"] == "product-only"

def test_self_stack_prefilter_finds_older_matching_kev_after_many_newer_nonmatches(client):
    corpus = {
        "self_stack": {
            "terms": [
                {"term": "fastapi", "ecosystem": "pypi", "version": None},
            ],
        },
    }
    newer_nonmatches = [
        {
            "cve_id": f"CVE-2025-{i:04d}",
            "description": "Newer urgent row with structured metadata for another product.",
            "cpe_matches": [_cpe(f"unrelated-{i}")],
            "published": f"2025-02-{(i % 28) + 1:02d}T00:00:00",
        }
        for i in range(501)
    ]
    older_match = {
        "cve_id": "CVE-2020-4242",
        "description": "Older KEV row; recall must come from structured product fields.",
        "cpe_matches": [_cpe("fastapi")],
        "published": "2020-01-01T00:00:00",
    }
    _insert_cves(client, [*newer_nonmatches, older_match])

    rows = _self_stack_risk_rows(client, corpus)

    assert [row["cve_id"] for row in rows] == ["CVE-2020-4242"]

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

    async def _insert_high_severity_kev():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products, cpe_matches,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-8888",
                    "Remote code execution in fastapi routing.",
                    "[]", json.dumps([_cpe("fastapi")]),
                    "HIGH", 7.5, 0.4, 1, "2024-02-01T00:00:00",
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

def test_resolve_control_active_unset_opt_out_flag_defaults_active(monkeypatch):
    """Most *_ENABLED flags are opt-out (default True when unset) --
    RATE_LIMIT_ENABLED matches settings.rate_limit_enabled: bool = True."""
    monkeypatch.delenv("SOME_OPT_OUT_FLAG", raising=False)
    assert merge.resolve_control_active({"live_flag": "SOME_OPT_OUT_FLAG"}) is True

def test_resolve_control_active_unset_opt_in_flag_defaults_inactive(monkeypatch):
    """An opt-in flag (default False when unset) must not be reported
    active just because merge.py's blanket 'missing env var = enabled'
    assumption doesn't hold for it -- the corpus record says so explicitly
    via live_flag_default_when_unset: false (Codex review, PR #494)."""
    monkeypatch.delenv("SOME_OPT_IN_FLAG", raising=False)
    control = {"live_flag": "SOME_OPT_IN_FLAG", "live_flag_default_when_unset": False}
    assert merge.resolve_control_active(control) is False
    monkeypatch.setenv("SOME_OPT_IN_FLAG", "1")
    assert merge.resolve_control_active(control) is True

def test_self_stack_terms_reads_generated_layer():
    corpus = {"self_stack": {"terms": [{"term": "fastapi"}, {"term": "react"}]}}
    assert merge.self_stack_terms(corpus) == ["fastapi", "react"]

def test_self_stack_terms_empty_when_layer_missing():
    assert merge.self_stack_terms({}) == []
