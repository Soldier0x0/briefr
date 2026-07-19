"""Tests for scripts/build_learn_site.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_learn_site.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_learn_site", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_learn_site"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def learn_mod():
    return _load()


def test_build_learn_site_from_repo_book(learn_mod, tmp_path: Path):
    book = ROOT / "docs" / "study-guide"
    pathways = ROOT / "docs" / "learn" / "pathways.json"
    assert book.is_dir()
    assert pathways.is_file()
    out = tmp_path / "learn-site"
    n = learn_mod.build(pathways, book, out)
    assert n == 3
    assert (out / "index.html").is_file()
    assert (out / "DEPLOY.md").is_file()
    assert (out / "book" / "pages" / "preface.html").is_file()
    for pid in ("system-design", "analyst", "architect"):
        page = (out / "pathways" / f"{pid}.html").read_text(encoding="utf-8")
        assert "../book/pages/" in page
        assert "All pathways" in page
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "pathways/system-design.html" in index
    assert "pathways/analyst.html" in index
    assert "pathways/architect.html" in index


def test_build_fails_on_missing_step(learn_mod, tmp_path: Path):
    book = tmp_path / "book"
    (book / "pages").mkdir(parents=True)
    (book / "pages" / "preface.html").write_text("x", encoding="utf-8")
    pathways = tmp_path / "pathways.json"
    pathways.write_text(
        json.dumps(
            {
                "title": "T",
                "tagline": "t",
                "pathways": [
                    {
                        "id": "x",
                        "title": "X",
                        "blurb": "b",
                        "steps": [{"id": "missing-chapter", "label": "Nope"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as ei:
        learn_mod.build(pathways, book, out)
    assert "missing-chapter" in str(ei.value)
