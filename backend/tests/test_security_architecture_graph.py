"""TM-4: System Architecture graph + Trust Boundaries + Attack Surface
(threat-modeling-security-architecture.md §5.2, §5.3, §8).

Verifies:
- GET /graph/architecture serves the exact committed graphs/architecture.json
  content (no read-time filtering).
- security_architecture.graphs pure helpers: endpoint<->control glob
  matching, attack-surface counts, node-context joins -- in isolation with
  synthetic corpora, independent of the live app or committed corpus.
- GET /graph/attack-surface and GET /context/{node_id} against the real app.
- /section/trust_boundaries now returns TM-4's curated seed rows.
- All new routes require session auth (same gate as every other
  security-architecture route).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from main import app
from security_architecture import graphs
from security_architecture.corpus_loader import get_corpus


# ── Pure helpers ───────────────────────────────────────────────────────

def test_endpoint_matches_pattern_exact():
    assert graphs._endpoint_matches_pattern("/api/auth/login", "/api/auth/login")
    assert not graphs._endpoint_matches_pattern("/api/auth/login", "/api/auth/refresh")


def test_endpoint_matches_pattern_prefix_glob():
    assert graphs._endpoint_matches_pattern("/api/auth/login", "/api/auth/*")
    assert graphs._endpoint_matches_pattern("/api/auth", "/api/auth/*")
    assert not graphs._endpoint_matches_pattern("/api/authenticate", "/api/auth/*")


def test_endpoint_matches_pattern_wildcard():
    assert graphs._endpoint_matches_pattern("/api/anything/at/all", "*")


def test_linked_controls_for_endpoint():
    controls = [
        {"id": "c1", "related_apis": ["/api/auth/*"]},
        {"id": "c2", "related_apis": ["/api/cves/*"]},
        {"id": "c3", "related_apis": ["*"]},
    ]
    linked = graphs.linked_controls_for_endpoint("/api/auth/login", controls)
    assert {c["id"] for c in linked} == {"c1", "c3"}


def test_build_attack_surface_counts_and_rows():
    corpus = {
        "api_inventory": {"endpoints": [
            {"method": "GET", "path": "/api/auth/login", "component_id": "routers-auth"},
            {"method": "GET", "path": "/api/unreviewed/thing", "component_id": "routers-x"},
        ]},
        "controls": {"controls": [
            {"id": "c1", "related_apis": ["/api/auth/*"]},
        ]},
    }
    surface = graphs.build_attack_surface(corpus)
    assert surface["total_endpoints"] == 2
    assert surface["reviewed_endpoints"] == 1
    assert surface["unreviewed_endpoints"] == 1
    by_path = {e["path"]: e for e in surface["endpoints"]}
    assert by_path["/api/auth/login"]["linked_control_count"] == 1
    assert by_path["/api/auth/login"]["linked_control_ids"] == ["c1"]
    assert by_path["/api/unreviewed/thing"]["linked_control_count"] == 0


def test_build_node_context_component_gathers_endpoints_controls_tables():
    corpus = {
        "components": {"components": [
            {"id": "routers-x", "summary": "S", "owner": "platform"},
        ]},
        "api_inventory": {"endpoints": [
            {"method": "GET", "path": "/api/x", "component_id": "routers-x"},
        ]},
        "controls": {"controls": [
            {"id": "c1", "related_apis": ["/api/x"]},
        ]},
    }
    graph = {
        "nodes": [
            {"id": "routers-x", "kind": "component", "cluster": "api"},
            {"id": "table:t1", "kind": "table", "cluster": "database"},
        ],
        "edges": [
            {"id": "routers-x->table:t1", "source": "routers-x", "target": "table:t1", "kind": "references_table"},
        ],
    }
    ctx = graphs.build_node_context("routers-x", corpus, graph)
    assert ctx["summary"] == "S"
    assert [e["path"] for e in ctx["endpoints"]] == ["/api/x"]
    assert [c["id"] for c in ctx["controls"]] == ["c1"]
    assert [t["id"] for t in ctx["tables"]] == ["table:t1"]
    assert len(ctx["outbound"]) == 1


def test_build_node_context_table_gathers_referenced_by():
    corpus = {"components": {"components": []}, "api_inventory": {"endpoints": []}, "controls": {"controls": []}}
    graph = {
        "nodes": [
            {"id": "routers-x", "kind": "component", "cluster": "api"},
            {"id": "table:t1", "kind": "table", "cluster": "database"},
        ],
        "edges": [
            {"id": "routers-x->table:t1", "source": "routers-x", "target": "table:t1", "kind": "references_table"},
        ],
    }
    ctx = graphs.build_node_context("table:t1", corpus, graph)
    assert [n["id"] for n in ctx["referenced_by"]] == ["routers-x"]


def test_build_node_context_unknown_node_returns_none():
    assert graphs.build_node_context("nope", {}, {"nodes": [], "edges": []}) is None


# ── Loader ─────────────────────────────────────────────────────────────

def test_get_architecture_graph_loads_committed_file():
    graph = graphs.get_architecture_graph()
    assert graph["nodes"]
    assert {n["kind"] for n in graph["nodes"]} == {
        "component", "job", "table", "core", "external",
    }
    # No layout coordinates in the generated file (presentation isn't a
    # code fact -- computed by the frontend instead).
    assert all("x" not in n and "y" not in n for n in graph["nodes"])


def test_get_architecture_graph_missing_file_raises(tmp_path):
    from security_architecture.graphs import ArchitectureGraphError

    missing = tmp_path / "does-not-exist.json"
    import pytest
    with pytest.raises(ArchitectureGraphError):
        graphs.get_architecture_graph(missing)


def test_get_architecture_graph_cache_is_keyed_per_path(tmp_path):
    """Gemini review, PR #496: a single-slot module-level cache would
    return the wrong file's contents when called with two different paths
    in sequence -- must be keyed by path, not last-call-wins."""
    import json

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"nodes": [{"id": "a"}], "edges": []}))
    b.write_text(json.dumps({"nodes": [{"id": "b"}], "edges": []}))

    graph_a = graphs.get_architecture_graph(a)
    graph_b = graphs.get_architecture_graph(b)
    assert graph_a["nodes"][0]["id"] == "a"
    assert graph_b["nodes"][0]["id"] == "b"
    # Re-fetch a after b -- must still be a's content, not b's.
    assert graphs.get_architecture_graph(a)["nodes"][0]["id"] == "a"


# ── Router endpoints ─────────────────────────────────────────────────

def test_graph_architecture_endpoint_matches_committed_file():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/graph/architecture")
        assert res.status_code == 200
        body = res.json()
        committed = graphs.get_architecture_graph()
        assert body == committed


def test_attack_surface_endpoint_shape():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/graph/attack-surface")
        assert res.status_code == 200
        body = res.json()
        assert body["total_endpoints"] > 0
        assert body["reviewed_endpoints"] + body["unreviewed_endpoints"] == body["total_endpoints"]
        assert body["endpoints"][0]["linked_control_count"] >= 0


def test_context_endpoint_known_component_node():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/context/routers-cves-list")
        assert res.status_code == 200
        body = res.json()
        assert body["kind"] == "component"
        assert body["endpoints"]


def test_context_endpoint_unknown_node_404():
    with TestClient(app) as client:
        res = client.get("/api/security-architecture/context/not-a-real-node")
        assert res.status_code == 404


def test_trust_boundaries_section_has_tm4_curated_rows():
    corpus = get_corpus()
    boundaries = corpus["trust_boundaries"]["trust_boundaries"]
    assert len(boundaries) >= 2
    assert all(b["origin"] == "curated" for b in boundaries)
    assert all(b["related_ids"] for b in boundaries)

    with TestClient(app) as client:
        res = client.get("/api/security-architecture/section/trust_boundaries")
        assert res.status_code == 200
        assert res.json()["count"] >= 2


# ── Auth gate ──────────────────────────────────────────────────────────

def test_new_graph_routes_require_session_auth():
    with TestClient(app) as client:
        client.cookies.clear()
        for path in (
            "/api/security-architecture/graph/architecture",
            "/api/security-architecture/graph/attack-surface",
            "/api/security-architecture/context/routers-cves-list",
        ):
            res = client.get(path)
            assert res.status_code == 401, path
