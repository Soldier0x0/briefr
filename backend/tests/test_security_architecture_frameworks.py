"""TM-6: analyst framework workspaces (CWE / OWASP / CAPEC / STRIDE) over the
user's own live threat surface (spec §4.5 reframe).

Verifies:
- GET /api/security-architecture/frameworks/{id} projects the live
  `cves.cwe_ids` aggregation four ways, ranked by CVE frequency.
- OWASP/STRIDE/CAPEC counts are distinct-CVE counts with an explicit
  `unmapped` bucket, so the parts reconcile with the whole (no dropped CWEs).
- Scope selector (all / stack / watchlist / kev) narrows the live set via the
  shipping matching path, and `severity=` narrows further.
- `stack` scope with no saved stack and no ?stack override reports itself
  unavailable rather than silently falling back to the whole corpus.
- Pure reference/aggregate helpers in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from security_architecture.frameworks import aggregate, reference, scope


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_frameworks.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


async def _seed_coro():
    """Seed CVEs with known cwe_ids across severities/KEV so every framework
    projection has deterministic, hand-checkable counts."""
    from database import get_db

    db = await get_db()
    try:
        rows = [
            # cve_id, description, severity, is_kev, cwe_ids(JSON)
            ("CVE-2024-0001", "generic", "CRITICAL", 1, '["CWE-79", "CWE-89"]'),
            ("CVE-2023-0002", "generic", "HIGH", 0, '["CWE-89"]'),
            ("CVE-2022-0003", "generic", "MEDIUM", 0, '["CWE-99999"]'),   # unmapped CWE
            ("CVE-2024-0004", "generic", "HIGH", 1, '["CWE-918"]'),        # SSRF
            ("CVE-2024-0005", "flaw in fastapi routing", "HIGH", 0, '["CWE-79"]'),  # stack match
        ]
        for cve_id, desc, sev, kev, cwes in rows:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products, severity,
                                  cvss_score, epss_score, is_kev, published, cwe_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cve_id, desc, "[]", sev, 8.0, 0.5, kev, "2024-01-01T00:00:00", cwes),
            )
        await db.execute(
            "INSERT INTO watchlist (cve_id, state) VALUES (?, ?)", ("CVE-2024-0001", "pin")
        )
        await db.commit()
    finally:
        await db.close()


def _seed(client):
    client.portal.call(_seed_coro)


def _get(client, framework, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/security-architecture/frameworks/{framework}"
    if qs:
        url += f"?{qs}"
    res = client.get(url)
    assert res.status_code == 200, res.text
    return res.json()


# ── CWE ─────────────────────────────────────────────────────────────────

def test_cwe_workspace_ranks_by_cve_frequency(client):
    _seed(client)
    body = _get(client, "cwe")
    ids = [i["id"] for i in body["items"]]
    assert "CWE-89" in ids and "CWE-79" in ids
    # CWE-79 and CWE-89 each appear in 2 CVEs; the single-CVE CWEs rank below
    # them, so the two most-frequent classes lead the list.
    assert set(ids[:2]) == {"CWE-79", "CWE-89"}
    sqli = next(i for i in body["items"] if i["id"] == "CWE-89")
    assert sqli["cve_count"] == 2
    assert sqli["name"] == "SQL Injection"  # human name from reference set
    # Each row ships drill-through evidence.
    assert sqli["example_cves"] and all("cve_id" in e for e in sqli["example_cves"])


def test_cwe_unknown_id_falls_back_to_bare_id_but_still_counts(client):
    _seed(client)
    body = _get(client, "cwe")
    unmapped = next(i for i in body["items"] if i["id"] == "CWE-99999")
    assert unmapped["name"] == "CWE-99999"  # no name, but not dropped
    assert unmapped["cve_count"] == 1


# ── OWASP ───────────────────────────────────────────────────────────────

def test_owasp_rollup_distinct_cves_and_unmapped_bucket(client):
    _seed(client)
    body = _get(client, "owasp")
    assert body["owasp_version"] == "2021"
    a03 = next(i for i in body["items"] if i["id"] == "A03")
    a10 = next(i for i in body["items"] if i["id"] == "A10")
    # CVE-0001 (79,89), CVE-0002 (89), CVE-0005 (79) all map to A03 Injection = 3 distinct.
    assert a03["cve_count"] == 3
    assert a03["kev_count"] == 1            # only CVE-0001 is KEV
    assert a10["cve_count"] == 1            # CVE-0004 SSRF
    # CWE-99999 maps nowhere -> honest unmapped bucket, not silently dropped.
    assert body["unmapped"]["cve_count"] == 1


# ── CAPEC ───────────────────────────────────────────────────────────────

def test_capec_projected_from_cwe_via_reference(client):
    _seed(client)
    body = _get(client, "capec")
    ids = {i["id"] for i in body["items"]}
    assert "CAPEC-664" in ids   # SSRF (from CWE-918)
    assert "CAPEC-66" in ids    # SQL Injection (from CWE-89)
    ssrf = next(i for i in body["items"] if i["id"] == "CAPEC-664")
    assert ssrf["name"] == "Server Side Request Forgery"
    assert "CWE-918" in ssrf["cwe_ids"]


# ── STRIDE ──────────────────────────────────────────────────────────────

def test_stride_heuristic_mapping_labelled_and_counted(client):
    _seed(client)
    body = _get(client, "stride")
    assert body["mapping"] == "heuristic"
    tampering = next(i for i in body["items"] if i["id"] == "T")
    # CWE-79 + CWE-89 are Tampering: CVE-0001, CVE-0002, CVE-0005 = 3 distinct.
    assert tampering["cve_count"] == 3
    info = next(i for i in body["items"] if i["id"] == "I")
    assert info["cve_count"] == 1  # CVE-0004 SSRF is Information Disclosure


# ── Scope selector ──────────────────────────────────────────────────────

def test_scope_kev_narrows_to_kev_only(client):
    _seed(client)
    body = _get(client, "cwe", scope="kev")
    assert body["scope"] == "kev"
    # Only KEV CVEs (0001: 79,89 ; 0004: 918) contribute.
    ids = {i["id"] for i in body["items"]}
    assert ids == {"CWE-79", "CWE-89", "CWE-918"}
    assert body["total_in_scope"] == 2


def test_scope_watchlist_narrows_to_watched(client):
    _seed(client)
    body = _get(client, "cwe", scope="watchlist")
    assert body["scope"] == "watchlist"
    assert body["total_in_scope"] == 1                # only CVE-2024-0001 pinned
    assert {i["id"] for i in body["items"]} == {"CWE-79", "CWE-89"}


def test_scope_stack_via_explicit_stack_param(client):
    _seed(client)
    body = _get(client, "cwe", scope="stack", stack="fastapi")
    assert body["scope"] == "stack"
    assert "fastapi" in body["terms"]
    # Only CVE-2024-0005 mentions fastapi -> its CWE-79.
    assert {i["id"] for i in body["items"]} == {"CWE-79"}
    assert body["total_in_scope"] == 1


def test_scope_stack_unavailable_without_stack_is_honest_not_full_corpus(client):
    _seed(client)
    body = _get(client, "cwe", scope="stack")
    # No saved stack (unauthenticated test client) and no ?stack override ->
    # empty + reason, NOT a silent whole-corpus fallback.
    assert body["items"] == []
    assert body["total_in_scope"] == 0


def test_severity_filter_narrows_scope(client):
    _seed(client)
    body = _get(client, "cwe", severity="critical")
    assert body["total_in_scope"] == 1                 # only CVE-2024-0001
    assert {i["id"] for i in body["items"]} == {"CWE-79", "CWE-89"}


def test_unknown_framework_is_404(client):
    res = client.get("/api/security-architecture/frameworks/nist")
    assert res.status_code == 404


def test_empty_corpus_yields_empty_workspace_not_error(client):
    body = _get(client, "owasp")   # nothing seeded
    assert body["items"] and all(i["cve_count"] == 0 for i in body["items"])
    assert body["total_in_scope"] == 0


# ── Pure helpers (no DB) ────────────────────────────────────────────────

def test_reference_reverse_maps_are_consistent():
    # CWE-89 (SQLi) is Injection (A03) and Tampering (T).
    assert "A03" in reference.owasp_categories_for_cwe("CWE-89")
    assert "T" in reference.stride_categories_for_cwe("CWE-89")
    assert "CAPEC-66" in reference.capec_for_cwe("CWE-89")
    assert reference.cwe_name("CWE-918") == "Server-Side Request Forgery (SSRF)"
    assert reference.cwe_name("CWE-404040") == "CWE-404040"  # graceful fallback


def test_parse_cwe_ids_normalises_and_dedupes():
    assert scope._parse_cwe_ids('["CWE-79", "cwe-79", "CWE-89", "junk"]') == ["CWE-79", "CWE-89"]
    assert scope._parse_cwe_ids(None) == []
    assert scope._parse_cwe_ids("not json") == []


def test_aggregate_unmapped_reconciles_with_total():
    scoped = {
        "rows": [
            {"cve_id": "CVE-2024-1", "severity": "HIGH", "epss_score": 0.1, "is_kev": False, "cwe_ids": ["CWE-89"]},
            {"cve_id": "CVE-2024-2", "severity": "LOW", "epss_score": 0.1, "is_kev": False, "cwe_ids": ["CWE-99999"]},
        ],
        "total_in_scope": 2, "sample_size": 2, "cve_with_cwe": 2, "scope": "all", "terms": [],
    }
    owasp = aggregate.owasp_workspace(scoped)
    mapped = sum(1 for i in owasp["items"] if i["cve_count"] > 0)
    assert mapped >= 1
    assert owasp["unmapped"]["cve_count"] == 1  # CWE-99999 has no OWASP mapping
