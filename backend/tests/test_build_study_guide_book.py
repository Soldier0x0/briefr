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
