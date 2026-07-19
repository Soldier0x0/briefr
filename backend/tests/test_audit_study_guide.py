"""Unit tests for scripts/audit_study_guide.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_study_guide.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("audit_study_guide", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_study_guide"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def audit():
    return _load_mod()


def test_normalize_backend_shorthand(audit, tmp_path: Path):
    (tmp_path / "backend" / "feeds").mkdir(parents=True)
    (tmp_path / "backend" / "feeds" / "nvd.py").write_text("#x\n", encoding="utf-8")
    assert audit.normalize_repo_path("feeds/nvd.py", root=tmp_path) == "backend/feeds/nvd.py"
    assert audit.normalize_repo_path("backend/feeds/nvd.py", root=tmp_path) == "backend/feeds/nvd.py"


def test_normalize_frontend_shorthand(audit, tmp_path: Path):
    (tmp_path / "frontend" / "src" / "pages").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "pages" / "Feed.jsx").write_text("x", encoding="utf-8")
    assert (
        audit.normalize_repo_path("pages/Feed.jsx", root=tmp_path)
        == "frontend/src/pages/Feed.jsx"
    )


def test_iter_inventory_skips_tests(audit, tmp_path: Path):
    (tmp_path / "backend" / "feeds").mkdir(parents=True)
    (tmp_path / "backend" / "tests").mkdir(parents=True)
    (tmp_path / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (tmp_path / "backend" / "tests" / "test_x.py").write_text("x", encoding="utf-8")
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "App.jsx").write_text("x", encoding="utf-8")
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "briefr-backend.service").write_text("x", encoding="utf-8")

    files = audit.iter_inventory_files(tmp_path)
    assert "backend/feeds/nvd.py" in files
    assert "frontend/src/App.jsx" in files
    assert "deploy/briefr-backend.service" in files
    assert not any(f.startswith("backend/tests/") for f in files)


def test_parse_guide_extracts_toc_and_mentions(audit):
    html = """
    <html><body>
    <aside><nav id="toc">
      <a class="toc-link" href="#be-data">Ch 9 · Data layer</a>
      <a class="toc-link" href="#in-feeds">Ch 14 · Feeds</a>
    </nav></aside>
    <main>
      <section class="page chapter" id="be-data">
        <div class="files"><span class="chip">db/connection.py</span></div>
        <p>See backend/db/connection.py for the pool.</p>
      </section>
      <section class="page chapter" id="in-feeds">
        <span class="chip">feeds/nvd.py</span>
        <p>Also mentions backend/feeds/missing_feed.py which does not exist.</p>
      </section>
    </main>
    </body></html>
    """
    parsed = audit.parse_guide(html)
    assert parsed.toc_order == ["be-data", "in-feeds"]
    assert parsed.chapters["be-data"].title.startswith("Ch 9")
    # Mentions collected (normalization may keep backend/ form even if missing on real disk)
    assert any("connection.py" in p for p in parsed.all_mentions)
    assert any("nvd.py" in p for p in parsed.chapters["in-feeds"].mentioned_paths)


def test_classify_covered_weak_gap_orphan(audit):
    chapters = {
        "in-feeds": audit.Chapter(
            id="in-feeds",
            title="Feeds",
            mentioned_paths={"backend/feeds/nvd.py"},
        )
    }
    inventory = [
        "backend/feeds/nvd.py",
        "backend/feeds/kev.py",
        "backend/routers/health.py",
    ]
    all_mentions = {"backend/feeds/nvd.py", "backend/feeds/ghost.py"}
    rows = audit.classify_files(inventory, chapters, all_mentions)
    by_path = {r.path: r for r in rows}
    assert by_path["backend/feeds/nvd.py"].status == "covered"
    assert by_path["backend/feeds/kev.py"].status == "weak"
    assert by_path["backend/routers/health.py"].status == "gap"
    assert by_path["backend/feeds/ghost.py"].status == "orphan_mention"


def test_suggest_chapter_home(audit):
    assert audit.suggest_chapter_home("backend/feeds/otx.py") == "in-feeds"
    assert audit.suggest_chapter_home("backend/operator_settings.py") == "api-usersettings"
    assert audit.suggest_chapter_home("deploy/nginx.conf") == "devops-deploy"


def test_bare_chip_and_glob_expand(audit, tmp_path: Path):
    (tmp_path / "backend" / "db").mkdir(parents=True)
    (tmp_path / "backend" / "main.py").write_text("x", encoding="utf-8")
    (tmp_path / "backend" / "db" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "backend" / "db" / "b.py").write_text("x", encoding="utf-8")
    html = """
    <nav id="toc"><a class="toc-link" href="#be-data">Data</a></nav>
    <section class="page chapter" id="be-data">
      <div class="files">
        <span class="chip">main.py</span>
        <span class="chip">db/*.py — 2 files</span>
      </div>
    </section>
    """
    parsed = audit.parse_guide(html, root=tmp_path)
    assert "backend/main.py" in parsed.chapters["be-data"].mentioned_paths
    assert "backend/db/a.py" in parsed.chapters["be-data"].mentioned_paths
    assert "backend/db/b.py" in parsed.chapters["be-data"].mentioned_paths


def test_iter_inventory_ignores_dotted_parents_outside_repo(audit, tmp_path: Path):
    """Regression: skip checks must use paths relative to root, not absolute parents.

    Gemini review on #688: if the repo lives under e.g. /.cache/.../workspace,
    absolute path.parts would falsely skip every file.
    """
    # Simulate a dotted ancestor by nesting the fake repo under .cache/
    nest = tmp_path / ".cache" / "agent" / "repo"
    (nest / "backend" / "feeds").mkdir(parents=True)
    (nest / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (nest / "frontend" / "src").mkdir(parents=True)
    (nest / "deploy").mkdir()
    files = audit.iter_inventory_files(nest)
    assert "backend/feeds/nvd.py" in files


def test_run_writes_regenerable_reports(audit, tmp_path: Path):
    guide = tmp_path / "STUDY_GUIDE.html"
    guide.write_text(
        """
        <nav id="toc"><a class="toc-link" href="#preface">Preface</a></nav>
        <header class="page hero" id="preface"><p>Hello backend/main.py</p></header>
        """,
        encoding="utf-8",
    )
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.py").write_text("x", encoding="utf-8")
    (tmp_path / "backend" / "orphan_mod.py").write_text("x", encoding="utf-8")
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "deploy").mkdir()

    out = tmp_path / "out"
    # Point module ROOT-dependent helpers at tmp via run(root=...)
    stats = audit.run(guide, out, root=tmp_path)
    assert (out / "inventory.json").is_file()
    assert (out / "inventory.md").is_file()
    assert (out / "gaps.md").is_file()
    assert (out / "coverage-skeleton.md").is_file()
    assert (out / "summary.md").is_file()
    assert "gap" in stats["counts"]
    # curated names must not be auto-created
    assert not (out / "CORRECTED_TOC.md").exists()


def test_bare_prefers_shallow_duplicate(audit, tmp_path: Path):
    (tmp_path / "backend" / "db").mkdir(parents=True)
    (tmp_path / "backend" / "api_metering.py").write_text("root\n", encoding="utf-8")
    (tmp_path / "backend" / "db" / "api_metering.py").write_text("deep\n", encoding="utf-8")
    assert audit.normalize_repo_path("api_metering.py", root=tmp_path) == "backend/api_metering.py"


def test_frontend_test_js_is_out_of_scope(audit, tmp_path: Path):
    (tmp_path / "frontend" / "src" / "utils").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "utils" / "cveFilters.js").write_text("export {}", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "utils" / "cveFilters.test.js").write_text("test", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "deploy").mkdir()
    inventory = audit.iter_inventory_files(tmp_path)
    assert "frontend/src/utils/cveFilters.test.js" in inventory
    chapters = {
        "fe-shared-utils": audit.Chapter(
            id="fe-shared-utils",
            title="Utils",
            mentioned_paths={"frontend/src/utils/cveFilters.js"},
        )
    }
    rows = audit.classify_files(
        inventory, chapters, chapters["fe-shared-utils"].mentioned_paths, root=tmp_path
    )
    by = {r.path: r for r in rows}
    assert by["frontend/src/utils/cveFilters.js"].status == "covered"
    assert by["frontend/src/utils/cveFilters.test.js"].status == "out_of_scope"
    assert "test" in by["frontend/src/utils/cveFilters.test.js"].notes.lower()


def test_empty_package_init_is_out_of_scope(audit, tmp_path: Path):
    (tmp_path / "backend" / "feeds").mkdir(parents=True)
    (tmp_path / "backend" / "feeds" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "deploy").mkdir()
    inventory = audit.iter_inventory_files(tmp_path)
    chapters = {
        "in-feeds": audit.Chapter(
            id="in-feeds",
            title="Feeds",
            mentioned_paths={"backend/feeds/nvd.py"},
        )
    }
    rows = audit.classify_files(
        inventory, chapters, {"backend/feeds/nvd.py"}, root=tmp_path
    )
    by = {r.path: r for r in rows}
    assert by["backend/feeds/__init__.py"].status == "out_of_scope"


def test_strict_exits_nonzero_on_weak(audit, tmp_path: Path):
    guide = tmp_path / "STUDY_GUIDE.html"
    guide.write_text(
        """
        <nav id="toc"><a class="toc-link" href="#in-feeds">Feeds</a></nav>
        <section class="page chapter" id="in-feeds">
          <span class="chip">backend/feeds/nvd.py</span>
        </section>
        """,
        encoding="utf-8",
    )
    root = tmp_path / "repo"
    (root / "backend" / "feeds").mkdir(parents=True)
    (root / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (root / "backend" / "feeds" / "kev.py").write_text("x", encoding="utf-8")
    (root / "frontend" / "src").mkdir(parents=True)
    (root / "deploy").mkdir()
    out = tmp_path / "out"
    code = audit.main(
        ["--guide", str(guide), "--out", str(out), "--root", str(root), "--strict"]
    )
    assert code == 1
