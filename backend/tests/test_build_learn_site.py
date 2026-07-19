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


def test_build_learn_links_sibling_study_guide(learn_mod, tmp_path: Path):
    book = ROOT / "docs" / "study-guide"
    pathways = ROOT / "docs" / "learn" / "pathways.json"
    assert book.is_dir()
    out = tmp_path / "learn"
    out.mkdir()
    (out / "pathways.json").write_text(pathways.read_text(encoding="utf-8"), encoding="utf-8")
    n = learn_mod.build(out / "pathways.json", book, out)
    assert n == 3
    assert (out / "index.html").is_file()
    assert not (out / "book").exists()
    page = (out / "pathways" / "analyst.html").read_text(encoding="utf-8")
    assert "../study-guide/pages/" in page
    assert (out / "pathways.json").is_file()  # preserved


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
