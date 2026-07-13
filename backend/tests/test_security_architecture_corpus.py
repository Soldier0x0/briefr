"""TM-1: corpus generator, loader, and drift CI.

Verifies:
- Pure extraction functions (scheduler jobs, DB tables, components,
  api_inventory) produce correct output from synthetic source text/route
  data -- independent of the live app or filesystem.
- The generator is deterministic (same input -> byte-for-byte-equivalent
  parsed output across two runs).
- Drift check: regenerating the corpus's generated layer into a temp dir
  and comparing against the committed files must match. Renaming a router
  changes the introspected module name, which changes components.yaml and
  api_inventory.yaml -- proving the drift test actually detects real drift,
  not just checking the generator ran.
- corpus_loader validates required fields, origin values, and related_ids
  cross-references; rejects malformed corpora.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
import yaml

from security_architecture.corpus_loader import CorpusValidationError, load_corpus

import generate_security_corpus as gen


# ── Pure extraction functions ─────────────────────────────────────────

def test_extract_scheduler_jobs_parses_id_and_name():
    source = """
scheduler.add_job(
    run_kev_sync,
    "interval",
    minutes=15,
    id="kev_metadata_sync",
    name="KEV Metadata Sync",
)
scheduler.add_job(
    run_nvd_sync,
    "interval",
    hours=1,
    id="nvd_incremental_sync",
    name="NVD Incremental Sync",
)
"""
    jobs = gen.extract_scheduler_jobs(source)
    assert [j["id"] for j in jobs] == ["kev_metadata_sync", "nvd_incremental_sync"]  # sorted
    assert jobs[0]["title"] == "KEV Metadata Sync"


def test_extract_scheduler_jobs_handles_name_before_id():
    """Gemini review on PR #491: the original regex required id= before
    name= in source order; a real job registered the other way around
    would be silently skipped. AST-based extraction doesn't care about
    keyword-argument order."""
    source = 'scheduler.add_job(f, "interval", name="Reordered Job", id="reordered_job")'
    jobs = gen.extract_scheduler_jobs(source)
    assert jobs == [{"id": "reordered_job", "title": "Reordered Job", "callable": "f"}]


def test_extract_scheduler_jobs_renaming_changes_output():
    """The literal acceptance criterion, at the pure-function level: renaming
    a job id changes what the generator emits."""
    before = 'scheduler.add_job(f, "interval", id="old_job_id", name="Old Job")'
    after = 'scheduler.add_job(f, "interval", id="new_job_id", name="New Job")'
    assert gen.extract_scheduler_jobs(before) != gen.extract_scheduler_jobs(after)


def test_extract_db_tables_dedupes_and_sorts():
    source = """
    "CREATE TABLE IF NOT EXISTS zebra (id INTEGER)",
    CREATE TABLE IF NOT EXISTS alpha (id INTEGER);
    "CREATE TABLE IF NOT EXISTS alpha (id INTEGER)",
    """
    assert gen.extract_db_tables(source) == ["alpha", "zebra"]


def test_build_components_skips_framework_internal_modules():
    routes_by_module = {
        "fastapi.applications": [("GET", "/docs")],
        "routers.forge": [("GET", "/api/forge/coverage"), ("POST", "/api/hunt-packs/generate")],
    }
    components = gen.build_components(routes_by_module)
    assert [c["id"] for c in components] == ["routers-forge"]
    assert components[0]["endpoint_count"] == 2
    assert components[0]["origin"] == "generated"
    assert components[0]["source_refs"] == [
        {"type": "file", "ref": "backend/routers/forge.py"}
    ]


def test_build_components_renaming_a_router_module_changes_output():
    """Acceptance criterion (§8, TM-1): 'renaming a router in a scratch
    branch makes the drift test fail' -- proven here at the pure-function
    level (component id/source_ref derive directly from the module name)."""
    before = gen.build_components({"routers.forge": [("GET", "/x")]})
    after = gen.build_components({"routers.forge_renamed": [("GET", "/x")]})
    assert before != after
    assert before[0]["id"] != after[0]["id"]


def test_build_api_inventory_sorted_by_path_then_method():
    routes_by_module = {"routers.a": [("POST", "/z"), ("GET", "/a")]}
    entries = gen.build_api_inventory(routes_by_module)
    assert [(e["method"], e["path"]) for e in entries] == [("GET", "/a"), ("POST", "/z")]


def test_build_scheduler_jobs_yaml_shape():
    jobs = [{"id": "x", "title": "X Job", "callable": "run_x"}]
    out = gen.build_scheduler_jobs_yaml(jobs)
    assert out[0]["id"] == "x"
    assert out[0]["origin"] == "generated"
    assert out[0]["summary"]


def test_build_db_tables_yaml_shape():
    out = gen.build_db_tables_yaml(["cves"])
    assert out[0]["id"] == "cves"
    assert out[0]["origin"] == "generated"
    assert out[0]["summary"]


# ── Self-stack (spec §4.5) ─────────────────────────────────────────────

def test_extract_requirements_terms_strips_pins_extras_and_comments():
    text = "fastapi==0.139.0\nuvicorn[standard]==0.49.0\n# comment\n\n-r other.txt\nbcrypt>=4.0\n"
    assert gen.extract_requirements_terms(text) == ["bcrypt", "fastapi", "uvicorn"]


def test_extract_package_json_terms_merges_deps_and_dev_deps():
    text = '{"dependencies": {"react": "^19.0.0"}, "devDependencies": {"vite": "^8.0.0"}}'
    assert gen.extract_package_json_terms(text) == ["react", "vite"]


def test_build_self_stack_yaml_shape_and_dedup():
    out = gen.build_self_stack_yaml(["fastapi"], ["react"], ["postgresql"])
    assert {e["term"] for e in out} == {"fastapi", "react", "postgresql"}
    assert all(e["origin"] == "generated" for e in out)
    assert all(e["id"].startswith("self-stack-") for e in out)
    # A term appearing in two sources collapses to one entry (id is derived
    # from the slugified term, not the source).
    out2 = gen.build_self_stack_yaml(["fastapi"], ["fastapi"], [])
    assert len(out2) == 1


def test_build_self_stack_yaml_renaming_a_dependency_changes_output():
    """Same acceptance-criterion shape as the router-rename test: a new
    dependency changes self_stack.yaml, which is what keeps the drift
    check honest about self-stack staleness (spec §4.5)."""
    before = gen.build_self_stack_yaml(["fastapi"], [], [])
    after = gen.build_self_stack_yaml(["fastapi", "django"], [], [])
    assert before != after


# ── Generator determinism + drift ─────────────────────────────────────

def test_generate_is_deterministic(tmp_path):
    out1 = gen.generate(tmp_path / "run1")
    out2 = gen.generate(tmp_path / "run2")
    for path1, path2 in zip(sorted(out1), sorted(out2)):
        assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")


def test_committed_corpus_has_no_drift(tmp_path):
    """The literal acceptance criterion: regenerate-and-diff. Compares
    parsed YAML (not raw bytes) so line-ending differences across
    checkouts/platforms never cause a false positive."""
    regenerated_dir = tmp_path / "regenerated"
    gen.generate(regenerated_dir)

    for filename in (
        "components.yaml",
        "api_inventory.yaml",
        "scheduler_jobs.yaml",
        "db_tables.yaml",
        "self_stack.yaml",
    ):
        committed = gen.CORPUS_DIR / filename
        fresh = regenerated_dir / filename
        with open(committed, encoding="utf-8") as f:
            committed_data = yaml.safe_load(f)
        with open(fresh, encoding="utf-8") as f:
            fresh_data = yaml.safe_load(f)
        assert committed_data == fresh_data, (
            f"{filename} has drifted from the code it describes -- "
            f"run `python scripts/generate_security_corpus.py` and commit the result"
        )


def test_committed_architecture_graph_has_no_drift(tmp_path):
    """TM-4: same drift check as the YAML generated layer, for
    graphs/architecture.json (JSON, not YAML -- compared as parsed data)."""
    import json

    regenerated_dir = tmp_path / "regenerated"
    gen.generate(regenerated_dir)

    committed = gen.CORPUS_DIR / "graphs" / "architecture.json"
    fresh = regenerated_dir / "graphs" / "architecture.json"
    with open(committed, encoding="utf-8") as f:
        committed_data = json.load(f)
    with open(fresh, encoding="utf-8") as f:
        fresh_data = json.load(f)
    assert committed_data == fresh_data, (
        "graphs/architecture.json has drifted from the code it describes -- "
        "run `python scripts/generate_security_corpus.py` and commit the result"
    )


def test_architecture_graph_nodes_match_generated_layer_exactly():
    """TM-4 acceptance (spec §8): 'graph nodes match generator output
    exactly' -- the node id set is exactly the union of component ids,
    job ids, and table ids from the other generated-layer files, not a
    hand-maintained parallel list."""
    import json

    with open(gen.CORPUS_DIR / "graphs" / "architecture.json", encoding="utf-8") as f:
        graph = json.load(f)
    with open(gen.CORPUS_DIR / "components.yaml", encoding="utf-8") as f:
        components = yaml.safe_load(f)["components"]
    with open(gen.CORPUS_DIR / "scheduler_jobs.yaml", encoding="utf-8") as f:
        jobs = yaml.safe_load(f)["jobs"]
    with open(gen.CORPUS_DIR / "db_tables.yaml", encoding="utf-8") as f:
        tables = yaml.safe_load(f)["tables"]

    expected_ids = (
        {c["id"] for c in components}
        | {f"job:{j['id']}" for j in jobs}
        | {f"table:{t['id']}" for t in tables}
    )
    assert {n["id"] for n in graph["nodes"]} == expected_ids


def test_extract_table_refs_anchors_to_sql_keywords():
    """A table name appearing only as a bare identifier/comment (not after
    FROM/JOIN/INTO/UPDATE/DELETE FROM) must NOT produce an edge -- the
    central 'no opinion rendered as measurement' principle applies to graph
    edges: a false positive here would fabricate an architectural
    dependency that doesn't exist."""
    known = {"users", "cves"}
    source = "# users are important\nSELECT * FROM cves WHERE id = ?\nuser_count = get_users_total()"
    assert gen.extract_table_refs(source, known) == ["cves"]


def test_extract_table_refs_covers_join_into_update_delete():
    known = {"a", "b", "c", "d"}
    source = (
        "SELECT * FROM a JOIN b ON a.id=b.id; "
        "INSERT INTO c VALUES (1); "
        "UPDATE d SET x=1; "
        "DELETE FROM a WHERE id=1;"
    )
    assert gen.extract_table_refs(source, known) == ["a", "b", "c", "d"]


def test_build_architecture_graph_shape_and_determinism():
    components = [{
        "id": "routers-x", "title": "routers.x", "endpoint_count": 1,
        "source_refs": [{"type": "file", "ref": "backend/routers/x.py"}],
    }]
    jobs_yaml = [{
        "id": "job_x", "title": "Job X",
        "source_refs": [{"type": "job", "ref": "job_x"}],
    }]
    tables_yaml = [{
        "id": "tbl_x", "title": "tbl_x",
        "source_refs": [{"type": "table", "ref": "tbl_x"}],
    }]
    sources = {"routers-x": "SELECT * FROM tbl_x"}

    graph1 = gen.build_architecture_graph(components, jobs_yaml, tables_yaml, sources)
    graph2 = gen.build_architecture_graph(components, jobs_yaml, tables_yaml, sources)
    assert graph1 == graph2  # deterministic

    node_ids = {n["id"] for n in graph1["nodes"]}
    assert node_ids == {"routers-x", "job:job_x", "table:tbl_x"}
    assert graph1["edges"] == [{
        "id": "routers-x->table:tbl_x", "source": "routers-x",
        "target": "table:tbl_x", "kind": "references_table",
    }]
    # No x/y layout coordinates baked into the generated layer (advisor
    # note: presentation isn't a code fact and shouldn't force a corpus
    # regen on every layout tweak).
    assert all("x" not in n and "y" not in n for n in graph1["nodes"])


# ── corpus_loader validation ───────────────────────────────────────────

def _write_minimal_corpus(directory: Path, **overrides) -> None:
    """A minimal valid corpus, with per-file overrides for negative tests."""
    files = {
        "manifest.yaml": {"version": 1, "schema_version": 1, "last_reviewed": "2026-01-01"},
        "components.yaml": {"components": []},
        "api_inventory.yaml": {"endpoints": []},
        "scheduler_jobs.yaml": {"jobs": []},
        "db_tables.yaml": {"tables": []},
        "self_stack.yaml": {"terms": []},
        "trust_boundaries.yaml": {"trust_boundaries": []},
        "controls.yaml": {"controls": []},
        "abuse_cases.yaml": {"abuse_cases": []},
        "threat_scenarios.yaml": {"threat_scenarios": []},
        "security_decisions.yaml": {"security_decisions": []},
        "risks.yaml": {"risks": []},
        "reviews.yaml": {"reviews": []},
    }
    files.update(overrides)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, data in files.items():
        with open(directory / filename, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)


def test_load_corpus_accepts_minimal_valid_corpus(tmp_path):
    _write_minimal_corpus(tmp_path)
    corpus = load_corpus(tmp_path)
    assert corpus["manifest"]["schema_version"] == 1
    assert corpus["components"]["components"] == []


def test_load_corpus_loads_real_committed_corpus():
    corpus = load_corpus()
    assert corpus["components"]["components"]
    assert corpus["scheduler_jobs"]["jobs"]
    assert corpus["db_tables"]["tables"]
    assert corpus["api_inventory"]["endpoints"]
    assert corpus["self_stack"]["terms"]
    assert all(c["origin"] == "generated" for c in corpus["components"]["components"])
    assert all(t["origin"] == "generated" for t in corpus["self_stack"]["terms"])


def test_load_corpus_rejects_missing_required_field(tmp_path):
    _write_minimal_corpus(
        tmp_path,
        **{"components.yaml": {"components": [{"id": "x", "title": "X", "origin": "generated"}]}},
    )
    with pytest.raises(CorpusValidationError, match="summary"):
        load_corpus(tmp_path)


def test_load_corpus_rejects_invalid_origin(tmp_path):
    _write_minimal_corpus(
        tmp_path,
        **{"components.yaml": {"components": [
            {"id": "x", "title": "X", "summary": "S", "origin": "made-up"}
        ]}},
    )
    with pytest.raises(CorpusValidationError, match="invalid origin"):
        load_corpus(tmp_path)


def test_load_corpus_curated_record_requires_review_fields(tmp_path):
    _write_minimal_corpus(
        tmp_path,
        **{"controls.yaml": {"controls": [
            {"id": "x", "title": "X", "summary": "S", "origin": "curated"}
        ]}},
    )
    with pytest.raises(CorpusValidationError, match="review_date"):
        load_corpus(tmp_path)


def test_load_corpus_rejects_dangling_related_id(tmp_path):
    _write_minimal_corpus(
        tmp_path,
        **{"controls.yaml": {"controls": [
            {
                "id": "x", "title": "X", "summary": "S", "origin": "curated",
                "review_date": "2026-01-01", "evidence": [], "related_ids": ["nonexistent"],
            }
        ]}},
    )
    with pytest.raises(CorpusValidationError, match="unknown related_ids"):
        load_corpus(tmp_path)


def test_load_corpus_rejects_non_list_related_ids(tmp_path):
    """Gemini review on PR #491: a typo'd related_ids: my-id (string, not a
    list) would previously iterate character-by-character and raise a
    confusing 'unknown related_ids entry m' error."""
    _write_minimal_corpus(
        tmp_path,
        **{"controls.yaml": {"controls": [
            {
                "id": "x", "title": "X", "summary": "S", "origin": "curated",
                "review_date": "2026-01-01", "evidence": [], "related_ids": "my-id",
            }
        ]}},
    )
    with pytest.raises(CorpusValidationError, match="must be a list"):
        load_corpus(tmp_path)


def test_load_corpus_rejects_missing_top_level_key(tmp_path):
    """Gemini review on PR #491: a corpus file missing its expected
    top-level list key (e.g. components.yaml with no 'components' key)
    would previously load silently, then crash downstream (get_overview())
    with an opaque KeyError / 500."""
    _write_minimal_corpus(tmp_path, **{"components.yaml": {"wrong_key": []}})
    with pytest.raises(CorpusValidationError, match="missing required top-level key"):
        load_corpus(tmp_path)


def test_load_corpus_resolves_cross_file_related_ids(tmp_path):
    """A control referencing a component (different file) must resolve."""
    _write_minimal_corpus(
        tmp_path,
        **{
            "components.yaml": {"components": [
                {"id": "comp-x", "title": "X", "summary": "S", "origin": "generated"}
            ]},
            "controls.yaml": {"controls": [
                {
                    "id": "ctrl-x", "title": "X", "summary": "S", "origin": "curated",
                    "review_date": "2026-01-01", "evidence": [], "related_ids": ["comp-x"],
                }
            ]},
        },
    )
    corpus = load_corpus(tmp_path)
    assert corpus["controls"]["controls"][0]["related_ids"] == ["comp-x"]


def test_load_corpus_missing_file_errors(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(CorpusValidationError, match="Missing corpus file"):
        load_corpus(tmp_path)


def test_get_corpus_empty_directory_raises_corpus_error_not_value_error(tmp_path):
    """Gemini review on PR #491: an empty/missing corpus directory made
    get_corpus()'s max() over an empty mtime sequence raise a bare
    ValueError instead of falling through to load_corpus()'s descriptive
    CorpusValidationError."""
    from security_architecture.corpus_loader import get_corpus

    tmp_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(CorpusValidationError, match="Missing corpus file"):
        get_corpus(tmp_path)


# ── Router stub (TM-1: manifest + overview only) ──────────────────────

def test_manifest_and_overview_endpoints():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        manifest = client.get("/api/security-architecture/manifest")
        assert manifest.status_code == 200
        body = manifest.json()
        assert body["schema_version"] == 1
        assert "components" in body["sections"]

        overview = client.get("/api/security-architecture/overview")
        assert overview.status_code == 200
        body = overview.json()
        assert body["generated"]["components"] > 0
        assert body["generated"]["api_endpoints"] > 0
        # Risks are honestly empty until a real review pass (see manifest.yaml
        # notes). Controls got a real curated seed in TM-3 (spec §5.9).
        assert body["curated"]["risks"] == 0
        assert body["curated"]["controls"] > 0


def test_security_architecture_routes_require_session_auth():
    """Not in auth_middleware.py's public/admin-exempt prefixes -- must be
    gated by the global session_auth_middleware like every other analyst
    route (matches spec §4.4: 'All routes: session auth (analyst+)')."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        client.cookies.clear()
        res = client.get("/api/security-architecture/manifest")
        assert res.status_code == 401
