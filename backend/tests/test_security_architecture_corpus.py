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


# ── corpus_loader validation ───────────────────────────────────────────

def _write_minimal_corpus(directory: Path, **overrides) -> None:
    """A minimal valid corpus, with per-file overrides for negative tests."""
    files = {
        "manifest.yaml": {"version": 1, "schema_version": 1, "last_reviewed": "2026-01-01"},
        "components.yaml": {"components": []},
        "api_inventory.yaml": {"endpoints": []},
        "scheduler_jobs.yaml": {"jobs": []},
        "db_tables.yaml": {"tables": []},
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
    assert all(c["origin"] == "generated" for c in corpus["components"]["components"])


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
