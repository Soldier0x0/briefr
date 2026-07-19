#!/usr/bin/env python3
"""Build thin learn pathway pages next to the study-guide book.

Writes static HTML under docs/learn/ (chooser + pathway lists) that link into
docs/study-guide/pages/. Does not copy or rebuild the textbook.

Usage (repo root):
  python scripts/build_learn_site.py
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHWAYS = ROOT / "docs" / "learn" / "pathways.json"
DEFAULT_BOOK = ROOT / "docs" / "study-guide"
DEFAULT_OUT = ROOT / "docs" / "learn"

LEARN_CSS = """
:root {
  --bg: #0c0e12;
  --bg-elevated: #141820;
  --border: #2a3140;
  --text: #e8ecf4;
  --text-muted: #9aa3b5;
  --accent: #e85533;
  --accent-soft: rgba(232, 85, 51, 0.28);
  --focus-ring: 0 0 0 3px var(--accent-soft);
  --radius: 10px;
  --font: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--font); }
a { color: var(--accent); }
a:focus-visible { outline: none; box-shadow: var(--focus-ring); border-radius: 4px; }
.wrap { max-width: 920px; margin: 0 auto; padding: 48px 24px 96px; }
.eyebrow { font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin: 0 0 10px; }
h1 { font-size: clamp(1.8rem, 3vw, 2.4rem); margin: 0 0 12px; letter-spacing: -0.02em; }
.lede { color: var(--text-muted); font-size: 1.05rem; line-height: 1.55; margin: 0 0 36px; max-width: 62ch; }
.chooser { display: grid; gap: 16px; }
@media (min-width: 720px) { .chooser { grid-template-columns: repeat(3, 1fr); } }
.card {
  display: flex; flex-direction: column; gap: 10px; text-decoration: none; color: inherit;
  background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 20px 18px; min-height: 180px; transition: border-color 0.15s ease, transform 0.15s ease;
}
.card:hover { border-color: var(--accent); transform: translateY(-1px); }
.card:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.card h2 { margin: 0; font-size: 1.15rem; }
.card p { margin: 0; color: var(--text-muted); font-size: 0.92rem; line-height: 1.45; flex: 1; }
.card .meta { font-family: var(--mono); font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.foot { margin-top: 40px; font-size: 0.85rem; color: var(--text-muted); }
.foot code { font-family: var(--mono); font-size: 0.8rem; }
.back { display: inline-block; margin-bottom: 24px; font-family: var(--mono); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; text-decoration: none; }
.steps { list-style: none; margin: 28px 0 0; padding: 0; border-top: 1px solid var(--border); }
.steps li { border-bottom: 1px solid var(--border); }
.steps a {
  display: grid; grid-template-columns: 48px 1fr; gap: 12px; align-items: baseline;
  padding: 14px 4px; text-decoration: none; color: inherit;
}
.steps a:hover .title { color: var(--accent); }
.steps .n { font-family: var(--mono); font-size: 0.75rem; color: var(--text-muted); }
.steps .title { font-size: 1rem; }
.banner {
  margin: 0 0 28px; padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-elevated); color: var(--text-muted); font-size: 0.9rem; line-height: 1.45;
}
@media (prefers-reduced-motion: reduce) {
  .card { transition: none; }
  .card:hover { transform: none; }
}
"""

KEEP_NAMES = frozenset({"pathways.json", "README.md"})


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def build(
    pathways_path: Path = DEFAULT_PATHWAYS,
    book_src: Path = DEFAULT_BOOK,
    out: Path = DEFAULT_OUT,
) -> int:
    data = json.loads(pathways_path.read_text(encoding="utf-8"))
    pathways = data["pathways"]
    pages_dir = book_src / "pages"
    if not pages_dir.is_dir():
        raise SystemExit(
            f"error: study-guide pages missing at {pages_dir}; "
            "run scripts/build_study_guide_book.py first"
        )

    missing: list[str] = []
    for pw in pathways:
        for step in pw["steps"]:
            if not (pages_dir / f"{step['id']}.html").is_file():
                missing.append(f"{pw['id']}:{step['id']}")
    if missing:
        raise SystemExit("error: pathway steps missing from book: " + ", ".join(missing))

    out.mkdir(parents=True, exist_ok=True)
    # Clear previous generated outputs only
    for child in list(out.iterdir()):
        if child.name in KEEP_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    assets = out / "assets"
    pathways_dir = out / "pathways"
    assets.mkdir()
    pathways_dir.mkdir()
    (assets / "learn.css").write_text(LEARN_CSS, encoding="utf-8")

    # Sibling link: docs/learn/pathways/x.html → docs/study-guide/pages/y.html
    book_href_prefix = "../study-guide/pages"

    cards = []
    for pw in pathways:
        cards.append(
            f"""  <a class="card" href="pathways/{_esc(pw['id'])}.html">
    <span class="meta">{_esc(pw.get('eyebrow', 'Pathway'))}</span>
    <h2>{_esc(pw['title'])}</h2>
    <p>{_esc(pw['blurb'])}</p>
  </a>"""
        )

    index_body = f"""<main class="wrap">
  <p class="eyebrow">BRIEFR Learn</p>
  <h1>{_esc(data.get('title', 'BRIEFR Learn'))}</h1>
  <p class="lede">{_esc(data.get('tagline', ''))}</p>
  <div class="chooser">
{chr(10).join(cards)}
  </div>
  <p class="foot">Chapters open from the study guide at <code>docs/study-guide/</code>. Edit pathway order in <code>pathways.json</code>, then re-run this builder.</p>
</main>
"""
    (out / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(data.get('title', 'BRIEFR Learn'))} — BRIEFR Learn</title>
  <link rel="stylesheet" href="assets/learn.css">
</head>
<body>
{index_body}
</body>
</html>
""",
        encoding="utf-8",
    )

    for pw in pathways:
        steps_html = []
        for i, step in enumerate(pw["steps"], start=1):
            href = f"{book_href_prefix}/{step['id']}.html"
            steps_html.append(
                f"""  <li><a href="{_esc(href)}"><span class="n">{i:02d}</span><span class="title">{_esc(step['label'])}</span></a></li>"""
            )
        body = f"""<main class="wrap">
  <a class="back" href="../index.html">← All pathways</a>
  <p class="eyebrow">{_esc(pw.get('eyebrow', 'Pathway'))}</p>
  <h1>{_esc(pw['title'])}</h1>
  <p class="lede">{_esc(pw['blurb'])}</p>
  <div class="banner"><strong>Audience:</strong> {_esc(pw.get('audience', ''))} · Each step opens a chapter in the audited study guide. Pathways reorder facts; they do not invent architecture.</div>
  <ol class="steps">
{chr(10).join(steps_html)}
  </ol>
</main>
"""
        (pathways_dir / f"{pw['id']}.html").write_text(
            f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(pw['title'])} — BRIEFR Learn</title>
  <link rel="stylesheet" href="../assets/learn.css">
</head>
<body>
{body}
</body>
</html>
""",
            encoding="utf-8",
        )

    return len(pathways)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pathways", type=Path, default=DEFAULT_PATHWAYS)
    ap.add_argument("--book", type=Path, default=DEFAULT_BOOK)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    n = build(args.pathways, args.book, args.out)
    print(f"learn: {n} pathways → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
