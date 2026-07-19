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
    mod = _load()
    yield mod
    sys.modules.pop("build_learn_site", None)


def _mini_book(tmp_path: Path, page_ids: list[str]) -> Path:
    book = tmp_path / "study-guide"
    pages = book / "pages"
    pages.mkdir(parents=True)
    for pid in page_ids:
        (pages / f"{pid}.html").write_text(f"<html>{pid}</html>", encoding="utf-8")
    return book


def test_build_learn_links_sibling_study_guide(learn_mod, tmp_path: Path):
    page_ids = ["preface", "system-design", "fe-analyst-shell", "be-auth", "sec-identity"]
    book = _mini_book(tmp_path, page_ids)
    pathways = tmp_path / "pathways.json"
    pathways.write_text(
        json.dumps(
            {
                "title": "BRIEFR Learn",
                "tagline": "t",
                "pathways": [
                    {
                        "id": "analyst",
                        "title": "Analyst",
                        "eyebrow": "Role",
                        "blurb": "b",
                        "audience": "a",
                        "steps": [
                            {"id": "preface", "label": "Preface"},
                            {"id": "fe-analyst-shell", "label": "Shell"},
                        ],
                    },
                    {
                        "id": "system-design",
                        "title": "SD",
                        "eyebrow": "Track",
                        "blurb": "b",
                        "audience": "a",
                        "steps": [
                            {"id": "system-design", "label": "Diagrams"},
                            {"id": "be-auth", "label": "Auth"},
                        ],
                    },
                    {
                        "id": "architect",
                        "title": "Architect",
                        "eyebrow": "Role",
                        "blurb": "b",
                        "audience": "a",
                        "steps": [
                            {"id": "sec-identity", "label": "Identity"},
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "learn"
    out.mkdir()
    (out / "pathways.json").write_text(pathways.read_text(encoding="utf-8"), encoding="utf-8")
    n = learn_mod.build(out / "pathways.json", book, out)
    assert n == 3
    assert (out / "index.html").is_file()
    assert not (out / "book").exists()
    page = (out / "pathways" / "analyst.html").read_text(encoding="utf-8")
    assert "../study-guide/pages/preface.html" in page
    assert "../study-guide/pages/fe-analyst-shell.html" in page
    assert (out / "pathways.json").is_file()
    css = (out / "assets" / "learn.css").read_text(encoding="utf-8")
    assert "--bg: #0a0a08" in css
    assert "--accent: #e85533" in css
    assert "color-scheme: dark" in css
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="#main-content"' in index
    assert 'id="main-content"' in index
    assert 'name="color-scheme" content="dark"' in index


def test_build_fails_on_missing_step(learn_mod, tmp_path: Path):
    book = _mini_book(tmp_path, ["preface"])
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
