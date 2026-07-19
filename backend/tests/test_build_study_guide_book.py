"""Tests for scripts/build_study_guide_book.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_study_guide_book.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_study_guide_book", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_study_guide_book"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build_mod():
    return _load()


def test_extract_and_build_minimal_book(build_mod, tmp_path: Path):
    src = tmp_path / "STUDY_GUIDE.html"
    src.write_text(
        """
        <html><head><style>body{color:red}</style></head><body>
        <nav id="toc">
          <a class="toc-link" href="#preface">Preface</a>
          <a class="toc-link" href="#ch1">Chapter 1</a>
        </nav>
        <main>
          <header class="page hero" id="preface"><h1>Preface</h1><p>Hello</p></header>
          <section class="page chapter" id="ch1"><h3>One</h3><p>Body</p></section>
        </main>
        </body></html>
        """,
        encoding="utf-8",
    )
    out = tmp_path / "book"
    n = build_mod.build(src, out)
    assert n == 2
    assert (out / "index.html").is_file()
    assert (out / "pages" / "preface.html").is_file()
    assert (out / "pages" / "ch1.html").is_file()
    assert (out / "assets" / "book.css").is_file()
    assert (out / "assets" / "book.js").is_file()
    assert (out / "assets" / "search-index.json").is_file()
    preface = (out / "pages" / "preface.html").read_text(encoding="utf-8")
    assert 'href="ch1.html"' in preface
    assert "nav-toggle" in preface
    assert "book.css" in preface
    assert 'href="#main-content"' in preface
    assert 'id="main-content"' in preface
    assert 'aria-label="Search study guide"' in preface
    css = (out / "assets" / "book.css").read_text(encoding="utf-8")
    assert "--bg: #0a0a08" in css
    assert "--accent: #e85533" in css
    assert "color-scheme: dark" in css
    assert ".skip-link" in css


def test_committed_book_matches_fresh_rebuild(build_mod, tmp_path: Path):
    """G5: committed docs/study-guide/ must match regenerating from STUDY_GUIDE.html."""
    guide = ROOT / "docs" / "STUDY_GUIDE.html"
    committed = ROOT / "docs" / "study-guide"
    assert guide.is_file()
    assert committed.is_dir()

    out = tmp_path / "book"
    n = build_mod.build(guide, out)
    assert n >= 60

    committed_pages = sorted(p.name for p in (committed / "pages").glob("*.html"))
    fresh_pages = sorted(p.name for p in (out / "pages").glob("*.html"))
    assert fresh_pages == committed_pages

    for name in ("index.html", "assets/book.css", "assets/book.js", "assets/search-index.json"):
        left = (committed / name).read_text(encoding="utf-8")
        right = (out / name).read_text(encoding="utf-8")
        assert left == right, f"G5 drift in {name}"

    for page in fresh_pages:
        left = (committed / "pages" / page).read_text(encoding="utf-8")
        right = (out / "pages" / page).read_text(encoding="utf-8")
        assert left == right, f"G5 drift in pages/{page}"
