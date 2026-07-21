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
DOCS_TOKENS = ROOT / "docs" / "assets" / "briefr-docs-tokens.css"

# Component styles only — palette/a11y from briefr-docs-tokens.css (prepended).
LEARN_CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text);
  font-family: ui-sans-serif, "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif;
  font-size: 16.5px; line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--text-link, var(--tag-what)); }
.wrap {
  max-width: none;
  margin: 0;
  padding: var(--space-wrap, 48px) clamp(20px, 4vw, 32px) 96px;
}
@media (min-width: 1100px) {
  .wrap { padding-left: 32px; padding-right: 32px; }
}
.eyebrow {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-muted); margin: 0 0 10px;
}
h1 {
  font-family: ui-serif, Georgia, "Times New Roman", serif;
  font-size: clamp(1.8rem, 3vw, 2.4rem); margin: 0 0 12px;
  letter-spacing: -0.02em; color: var(--text-heading, var(--text)); font-weight: 600;
}
.lede {
  color: var(--text-muted); font-size: 1.05rem; line-height: 1.55;
  margin: 0 0 36px; max-width: 62ch;
}
.chooser {
  display: grid; gap: 16px;
  grid-template-columns: 1fr;
}
@media (min-width: 560px) {
  .chooser { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 900px) {
  .chooser { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
.card {
  display: flex; flex-direction: column; gap: 10px; text-decoration: none; color: inherit;
  background: var(--bg-elevated); border: 1px solid var(--border);
  border-radius: var(--radius-lg, 10px);
  padding: 20px 18px; min-height: 180px; min-width: 0;
  transition: border-color var(--motion-fast, 120ms) var(--ease-standard, ease),
    transform var(--motion-fast, 120ms) var(--ease-standard, ease),
    box-shadow var(--motion-fast, 120ms) var(--ease-standard, ease);
}
.card:hover {
  border-color: var(--border-active, var(--accent));
  transform: translateY(-1px);
}
.card:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.card h2 {
  margin: 0; font-size: 1.15rem;
  font-family: ui-serif, Georgia, "Times New Roman", serif; font-weight: 600;
}
.card p { margin: 0; color: var(--text-muted); font-size: 0.92rem; line-height: 1.45; flex: 1; }
.card .meta {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em;
}
.foot { margin-top: 40px; font-size: 0.85rem; color: var(--text-muted); max-width: 74ch; }
.foot code {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.8rem; background: var(--code-bg); padding: 0.1em 0.35em;
  border-radius: var(--radius-sm, 4px); color: var(--accent-strong);
}
.back {
  display: inline-flex; align-items: center; min-height: 30px; margin-bottom: 24px;
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; text-decoration: none;
  color: var(--text-link, var(--tag-what));
}
.steps { list-style: none; margin: 28px 0 0; padding: 0; border-top: 1px solid var(--border); }
.steps li { border-bottom: 1px solid var(--border); }
.steps a {
  display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 12px; align-items: baseline;
  padding: 14px 4px; text-decoration: none; color: inherit; border-radius: var(--radius-sm, 4px);
}
.steps a:hover .title { color: var(--accent); }
.steps a:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.steps .n {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.75rem; color: var(--text-muted);
}
.steps .title { font-size: 1rem; }
.banner {
  margin: 0 0 28px; padding: 12px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-lg, 10px);
  background: var(--bg-elevated); color: var(--text-muted); font-size: 0.9rem; line-height: 1.45;
  max-width: 74ch;
}
@media (prefers-reduced-motion: reduce) {
  .card { transition: none; }
  .card:hover { transform: none; }
}
"""

KEEP_NAMES = frozenset({"pathways.json", "README.md"})


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _load_docs_tokens() -> str:
    if not DOCS_TOKENS.is_file():
        raise SystemExit(f"missing shared docs tokens: {DOCS_TOKENS}")
    return DOCS_TOKENS.read_text(encoding="utf-8").strip() + "\n"


def _page_shell(title: str, css_href: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{_esc(title)} — BRIEFR Learn</title>
  <link rel="stylesheet" href="{_esc(css_href)}">
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
{body}
</body>
</html>
"""


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
    (assets / "learn.css").write_text(_load_docs_tokens() + LEARN_CSS, encoding="utf-8")

    # Pathway link: docs/learn/pathways/x.html → docs/study-guide/pages/y.html
    book_href_prefix = "../../study-guide/pages"

    cards = []
    for pw in pathways:
        cards.append(
            f"""  <a class="card" href="pathways/{_esc(pw['id'])}.html">
    <span class="meta">{_esc(pw.get('eyebrow', 'Pathway'))}</span>
    <h2>{_esc(pw['title'])}</h2>
    <p>{_esc(pw['blurb'])}</p>
  </a>"""
        )

    index_body = f"""<main id="main-content" class="wrap">
  <p class="eyebrow">BRIEFR Learn</p>
  <h1>{_esc(data.get('title', 'BRIEFR Learn'))}</h1>
  <p class="lede">{_esc(data.get('tagline', ''))}</p>
  <div class="chooser">
{chr(10).join(cards)}
  </div>
  <p class="foot">Chapters open from the study guide at <code>docs/study-guide/</code>. Edit pathway order in <code>pathways.json</code>, then re-run this builder. Shared palette: <code>docs/assets/briefr-docs-tokens.css</code>.</p>
</main>
"""
    (out / "index.html").write_text(
        _page_shell(data.get("title", "BRIEFR Learn"), "assets/learn.css", index_body),
        encoding="utf-8",
    )

    for pw in pathways:
        steps_html = []
        for i, step in enumerate(pw["steps"], start=1):
            href = f"{book_href_prefix}/{step['id']}.html"
            steps_html.append(
                f"""  <li><a href="{_esc(href)}"><span class="n">{i:02d}</span><span class="title">{_esc(step['label'])}</span></a></li>"""
            )
        body = f"""<main id="main-content" class="wrap">
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
            _page_shell(pw["title"], "../assets/learn.css", body),
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
