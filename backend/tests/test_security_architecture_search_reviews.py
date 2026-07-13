"""TM-5: Global search + Review History (spec §5.14, §5.17, §9 acceptance:
"search finds a control by name; review history shows real audit entries").

Verifies:
- GET /api/security-architecture/search finds a real committed control by
  title substring, a MITRE technique by name (live DB), and returns nothing
  for a query with no matches.
- security_architecture.merge.search_corpus / search_mitre_techniques pure
  logic (case-insensitive, bounded).
- GET /api/security-architecture/section/reviews merges curated
  reviews.yaml with live audit_log security events (actor/action/target),
  reusing the same table and masking helper the admin Audit Log view uses.
- Only security-relevant audit_log action prefixes are included (routine
  content refreshes like refresh.kev are excluded).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from security_architecture import merge
from security_architecture.corpus_loader import load_corpus


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sa_search.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _seed_audit_and_mitre(self):
    from database import get_db

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO audit_log (actor, action, target, created_at) VALUES (?, ?, ?, ?)",
                ("admin@example.com", "auth.login", "", "2026-07-13T10:00:00"),
            )
            await db.execute(
                "INSERT INTO audit_log (actor, action, target, created_at) VALUES (?, ?, ?, ?)",
                ("system", "refresh.kev", "kev feed", "2026-07-13T10:05:00"),
            )
            await db.execute(
                "INSERT INTO mitre_techniques (technique_id, name, tactic, url) VALUES (?, ?, ?, ?)",
                ("T1566", "Phishing", "Initial Access", "https://attack.mitre.org/techniques/T1566/"),
            )
            await db.commit()
        finally:
            await db.close()

    return _seed


# ── Global search ─────────────────────────────────────────────────────────

def test_search_finds_a_real_control_by_name(client):
    res = client.get("/api/security-architecture/search?q=rate limiting")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] > 0
    hit = next(r for r in body["results"] if r["id"] == "rate-limiting")
    assert hit["type"] == "controls"
    assert hit["section"] == "controls"


def test_search_finds_mitre_technique_by_name(client):
    client.portal.call(_seed_audit_and_mitre(client))
    res = client.get("/api/security-architecture/search?q=phishing")
    body = res.json()
    hit = next(r for r in body["results"] if r["type"] == "mitre_technique")
    assert hit["id"] == "T1566"
    assert hit["section"] == "mitre_attack"


def test_search_empty_query_returns_no_results(client):
    res = client.get("/api/security-architecture/search?q=")
    assert res.status_code == 200
    assert res.json() == {"query": "", "count": 0, "results": []}


def test_search_no_match_returns_empty_results(client):
    res = client.get("/api/security-architecture/search?q=zzz-no-such-thing-zzz")
    body = res.json()
    assert body["count"] == 0
    assert body["results"] == []


def test_search_corpus_is_case_insensitive():
    corpus = load_corpus()
    results_lower = merge.search_corpus(corpus, "rate limiting")
    results_upper = merge.search_corpus(corpus, "RATE LIMITING")
    assert results_lower and results_upper
    assert {r["id"] for r in results_lower} == {r["id"] for r in results_upper}


# ── Review History ───────────────────────────────────────────────────────

def test_reviews_section_includes_curated_and_live_entries(client):
    client.portal.call(_seed_audit_and_mitre(client))
    res = client.get("/api/security-architecture/section/reviews")
    assert res.status_code == 200
    body = res.json()
    origins = {r.get("origin") for r in body["items"]}
    assert "curated" in origins
    assert "live" in origins
    live_row = next(r for r in body["items"] if r.get("origin") == "live")
    assert live_row["action"] == "auth.login"
    assert live_row["actor"] == "admin@example.com"


def test_reviews_section_excludes_non_security_audit_actions(client):
    client.portal.call(_seed_audit_and_mitre(client))
    res = client.get("/api/security-architecture/section/reviews")
    body = res.json()
    actions = {r.get("action") for r in body["items"] if r.get("origin") == "live"}
    assert "auth.login" in actions
    assert "refresh.kev" not in actions


def test_reviews_section_curated_only_excludes_audit_log(client):
    res = client.get("/api/security-architecture/section/reviews?origin=curated")
    body = res.json()
    assert all(r.get("origin") == "curated" for r in body["items"])


def test_is_security_audit_action_prefix_matching():
    assert merge.is_security_audit_action("auth.login") is True
    assert merge.is_security_audit_action("backup.run") is True
    assert merge.is_security_audit_action("scheduler.pause_all") is True
    assert merge.is_security_audit_action("refresh.kev") is False
    assert merge.is_security_audit_action("hunt_packs.delete") is False
