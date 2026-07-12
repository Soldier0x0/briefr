"""TM-2: Security Architecture shell UI backend support.

TM-2 is shell + Overview only (threat-modeling-security-architecture.md §8).
The overview endpoint gains a `tiles[]` array -- each tile is a count whose
inputs are visible and whose `section`/`filter` drill straight into the
generic `/section/{id}` endpoint added here, so "every tile click lands on
its pre-filtered source rows" (spec §9.4) is provable server-side, not just
asserted in JSX. No composite grades, no invented arithmetic -- every value
is a len() or a direct field comparison over corpus rows.

This generic section endpoint is a TM-2 shell convenience -- it serves raw
corpus rows for any manifest data section. TM-3+ supersedes it with the
typed per-section endpoints in spec §4.4 (graph/architecture, stride, mitre,
...); that's an intentional, documented divergence, not scope creep.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_overview_tiles_are_counts_with_drill_targets():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/overview")
        assert res.status_code == 200
        body = res.json()
        tiles = body["tiles"]
        assert len(tiles) >= 6

        by_id = {t["id"]: t for t in tiles}
        # Generated-layer tiles must be non-zero against the real committed
        # corpus -- these are the ones whose drill-through is demonstrably
        # non-vacuous (populated tables), unlike the still-empty curated ones.
        assert by_id["components"]["value"] > 0
        assert by_id["endpoints"]["value"] > 0
        assert by_id["scheduler_jobs"]["value"] > 0
        assert by_id["db_tables"]["value"] > 0

        for tile in tiles:
            assert tile["section"], f"tile {tile['id']} has no drill target"
            assert "filter" in tile
            assert tile["help"], f"tile {tile['id']} has no discoverable explanation"


def test_overview_curated_tiles_reflect_empty_corpus_honestly():
    with TestClient(app) as client:
        body = client.get("/api/security-architecture/overview").json()
        by_id = {t["id"]: t for t in body["tiles"]}
        # Curated layer is genuinely empty pre-review (TM-1 manifest note) --
        # the tile must say 0, not fabricate a number.
        assert by_id["open_risks"]["value"] == 0
        assert by_id["critical_open_risks"]["value"] == 0
        assert by_id["controls"]["value"] == 0


def test_section_endpoint_returns_generated_components():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/section/components")
        assert res.status_code == 200
        body = res.json()
        assert body["section"] == "components"
        assert body["type"] == "components"
        assert body["count"] == len(body["items"])
        assert body["count"] > 0
        assert all(item["origin"] == "generated" for item in body["items"])


def test_section_endpoint_type_param_switches_generated_collection():
    with TestClient(app) as client:
        endpoints = client.get("/api/security-architecture/section/components?type=endpoints").json()
        jobs = client.get("/api/security-architecture/section/components?type=jobs").json()
        tables = client.get("/api/security-architecture/section/components?type=tables").json()
        assert endpoints["type"] == "endpoints"
        assert endpoints["count"] > 0
        assert jobs["type"] == "jobs"
        assert jobs["count"] > 0
        assert tables["type"] == "tables"
        assert tables["count"] > 0


def test_section_endpoint_filters_by_status_and_severity():
    with TestClient(app) as client:
        # risks.yaml is currently an empty curated stub -- filters must not
        # error on an empty list, and must return an honestly empty result.
        res = client.get("/api/security-architecture/section/risks?status=open&severity=critical")
        assert res.status_code == 200
        body = res.json()
        assert body["section"] == "risks"
        assert body["count"] == 0
        assert body["items"] == []


def test_section_endpoint_unknown_section_404s():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/section/not-a-real-section")
        assert res.status_code == 404


def test_section_endpoint_requires_session_auth():
    with TestClient(app) as client:
        client.cookies.clear()
        res = client.get("/api/security-architecture/section/components")
        assert res.status_code == 401
