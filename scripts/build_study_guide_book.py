#!/usr/bin/env python3
"""Build docs/study-guide/ multi-file book from docs/STUDY_GUIDE.html.

Usage (repo root):
  python scripts/build_study_guide_book.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "docs" / "STUDY_GUIDE.html"
DEFAULT_OUT = ROOT / "docs" / "study-guide"

CSS_EXTRA = """
/* ---- Multi-file book responsive shell ---- */
.shell { position: relative; }
.nav-toggle {
  display: none; position: fixed; top: 12px; left: 12px; z-index: 40;
  width: 42px; height: 42px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--bg-elevated); color: var(--text); cursor: pointer;
  box-shadow: 0 4px 16px var(--shadow);
}
.nav-toggle:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--accent-soft); }
.nav-backdrop {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 25;
}
body.nav-open .nav-backdrop { display: block; }
aside .toc-link.active { box-shadow: inset 3px 0 0 var(--accent); }
.page { display: block; animation: none; }
@media (max-width: 880px) {
  .nav-toggle { display: inline-flex; align-items: center; justify-content: center; }
  aside {
    position: fixed; top: 0; left: 0; bottom: 0; width: min(320px, 88vw);
    height: 100vh; z-index: 30; transform: translateX(-105%);
    transition: transform 0.16s ease-out; border-right: 1px solid var(--border);
    box-shadow: 8px 0 24px var(--shadow);
  }
  body.nav-open aside { transform: none; }
  main { padding: 64px 18px 120px; max-width: none; }
  .brand h1 { font-size: 1.02rem; }
  .page-nav { flex-direction: column; }
  .page-nav a { text-align: left !important; }
}
@media (prefers-reduced-motion: reduce) {
  aside { transition: none; }
}
"""

BOOK_JS = r"""
(function () {
  const PROGRESS_KEY = 'briefr-study-progress-v1';
  const PAGE_ID = document.body.dataset.pageId || '';
  const ASSETS_BASE = document.body.dataset.assetsBase || 'assets/';

  const toggle = document.getElementById('nav-toggle');
  const backdrop = document.getElementById('nav-backdrop');
  function setNav(open) {
    document.body.classList.toggle('nav-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  if (toggle) toggle.addEventListener('click', () => setNav(!document.body.classList.contains('nav-open')));
  if (backdrop) backdrop.addEventListener('click', () => setNav(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setNav(false); });

  document.querySelectorAll('.toc-link').forEach(link => {
    const href = link.getAttribute('href') || '';
    const id = href.replace(/^.*\//, '').replace(/\.html$/, '');
    const labelHtml = link.innerHTML;
    link.innerHTML = '';
    const check = document.createElement('span');
    check.className = 'toc-check';
    check.dataset.page = id;
    check.title = 'Mark as read';
    const label = document.createElement('span');
    label.className = 'toc-label';
    label.innerHTML = labelHtml;
    link.appendChild(check);
    link.appendChild(label);
    if (id === PAGE_ID) link.classList.add('active');
  });

  function loadProgress() {
    try { return new Set(JSON.parse(localStorage.getItem(PROGRESS_KEY) || '[]')); }
    catch (e) { return new Set(); }
  }
  function saveProgress(set) {
    try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(Array.from(set))); } catch (e) {}
  }
  let progress = loadProgress();
  function renderProgress() {
    const checks = document.querySelectorAll('.toc-check');
    checks.forEach(cb => cb.classList.toggle('done', progress.has(cb.dataset.page)));
    const total = checks.length;
    const done = Array.from(checks).filter(cb => progress.has(cb.dataset.page)).length;
    const label = document.getElementById('progress-label');
    const fill = document.getElementById('progress-fill');
    if (label) label.textContent = done + ' / ' + total + ' read';
    if (fill) fill.style.width = (total ? (done / total * 100) : 0) + '%';
  }
  const toc = document.getElementById('toc');
  if (toc) toc.addEventListener('click', (e) => {
    const check = e.target.closest('.toc-check');
    if (!check) return;
    e.preventDefault();
    e.stopPropagation();
    const id = check.dataset.page;
    if (progress.has(id)) progress.delete(id); else progress.add(id);
    saveProgress(progress);
    renderProgress();
  });
  const resetBtn = document.getElementById('progress-reset');
  if (resetBtn) resetBtn.addEventListener('click', () => {
    progress = new Set();
    saveProgress(progress);
    renderProgress();
  });
  renderProgress();

  let searchIndex = null;
  fetch(ASSETS_BASE + 'search-index.json').then(r => r.json()).then(data => { searchIndex = data; }).catch(() => {});
  const searchInput = document.getElementById('search');
  const emptyMsg = document.getElementById('search-empty');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim().toLowerCase();
      const links = document.querySelectorAll('.toc-link');
      const groups = document.querySelectorAll('.toc-group');
      if (!q) {
        links.forEach(l => l.classList.remove('hidden-by-search'));
        groups.forEach(g => g.classList.remove('hidden-by-search'));
        if (emptyMsg) emptyMsg.style.display = 'none';
        return;
      }
      const matchIds = new Set();
      if (searchIndex) {
        searchIndex.forEach(row => {
          if ((row.title + ' ' + row.text).toLowerCase().includes(q)) matchIds.add(row.id);
        });
      }
      let anyVisible = false;
      groups.forEach(g => { g.dataset.anyMatch = '0'; });
      links.forEach(l => {
        const href = l.getAttribute('href') || '';
        const id = href.replace(/^.*\//, '').replace(/\.html$/, '');
        const match = matchIds.has(id) || l.textContent.toLowerCase().includes(q);
        l.classList.toggle('hidden-by-search', !match);
        if (match) {
          anyVisible = true;
          const g = l.closest('.toc-group');
          if (g) g.dataset.anyMatch = '1';
        }
      });
      groups.forEach(g => g.classList.toggle('hidden-by-search', g.dataset.anyMatch !== '1'));
      if (emptyMsg) emptyMsg.style.display = anyVisible ? 'none' : 'block';
    });
    searchInput.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const firstMatch = document.querySelector('.toc-link:not(.hidden-by-search)');
      if (firstMatch) location.href = firstMatch.getAttribute('href');
    });
  }
})();
"""


def _has_exact_class(attrs: str, name: str) -> bool:
    m = re.search(r'\bclass="([^"]*)"', attrs)
    if not m:
        return False
    return name in m.group(1).split()


def extract_pages(html: str) -> list[dict]:
    """Extract top-level .page elements with depth-aware tag matching."""
    opener = re.compile(
        r"<(section|header|div)\b([^>]*)>",
        re.I,
    )
    pages: list[dict] = []
    pos = 0
    while True:
        m = opener.search(html, pos)
        if not m:
            break
        tag, attrs = m.group(1).lower(), m.group(2)
        if not _has_exact_class(attrs, "page"):
            pos = m.end()
            continue
        id_m = re.search(r'\bid="([^"]+)"', attrs)
        if not id_m:
            pos = m.end()
            continue
        start = m.start()
        i = m.end()
        depth = 1
        tag_re = re.compile(rf"</?{tag}\b[^>]*>", re.I)
        end = None
        for tm in tag_re.finditer(html, i):
            token = tm.group(0)
            if token.startswith("</"):
                depth -= 1
                if depth == 0:
                    end = tm.end()
                    break
            elif not token.endswith("/>"):
                depth += 1
        if end is None:
            pos = m.end()
            continue
        full = html[start:end]
        pid = id_m.group(1)
        title_m = re.search(r"<h[123][^>]*>(.*?)</h[123]>", full, re.S)
        title = re.sub("<[^>]+>", "", title_m.group(1)).strip() if title_m else pid
        text = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", full)).strip()
        pages.append({"id": pid, "title": title, "html": full, "text": text})
        pos = end
    return pages


def render_shell(
    *,
    page_id: str,
    title: str,
    content: str,
    pages_prefix: str,
    assets_prefix: str,
    prev_id: str | None,
    next_id: str | None,
    prev_title: str,
    next_title: str,
    toc: str,
) -> str:
    toc_local = toc.replace("PAGES_PREFIX", pages_prefix)
    nav_prev = (
        f'<a class="prev" href="{pages_prefix}{prev_id}.html"><span class="nav-label">&larr; Previous</span>'
        f'<span class="nav-title">{prev_title}</span></a>'
        if prev_id
        else '<span class="spacer"></span>'
    )
    nav_next = (
        f'<a class="next" href="{pages_prefix}{next_id}.html"><span class="nav-label">Next &rarr;</span>'
        f'<span class="nav-title">{next_title}</span></a>'
        if next_id
        else '<span class="spacer"></span>'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — BRIEFR Study Guide</title>
  <link rel="stylesheet" href="{assets_prefix}book.css">
</head>
<body data-page-id="{page_id}" data-pages-base="{pages_prefix}" data-assets-base="{assets_prefix}">
<button type="button" class="nav-toggle" id="nav-toggle" aria-label="Open table of contents" aria-expanded="false" aria-controls="book-aside">☰</button>
<div class="nav-backdrop" id="nav-backdrop"></div>
<div class="shell">
  <aside id="book-aside">
    <div class="brand"><span class="mark">▮</span><h1><a href="{pages_prefix}preface.html" style="color:inherit;text-decoration:none">BRIEFR — Study Guide</a></h1></div>
    <p class="brand-sub">A full architecture textbook</p>
    <input id="search" type="search" placeholder="Search files, functions, concepts…" autocomplete="off">
    <p id="search-empty">No matches. Try a shorter term.</p>
    <div class="toc-progress"><span id="progress-label">0 / 0 read</span><button class="toc-reset" id="progress-reset" type="button">reset</button></div>
    <div class="toc-progress-bar"><div class="toc-progress-bar-fill" id="progress-fill"></div></div>
    {toc_local}
  </aside>
  <main>
    {content}
    <div class="page-nav" id="page-nav">{nav_prev}{nav_next}</div>
    <footer>
      Built from a direct read of the BRIEFR codebase. When this disagrees with the repo, trust the repo.
      · <a href="{pages_prefix}preface.html">Book home</a>
      · Regenerate: <code>scripts/build_study_guide_book.py</code>
    </footer>
  </main>
</div>
<script src="{assets_prefix}book.js"></script>
</body>
</html>
"""


def build(src: Path, out: Path) -> int:
    html = src.read_text(encoding="utf-8")
    style_m = re.search(r"<style>(.*?)</style>", html, re.S)
    toc_m = re.search(r"(<nav id=\"toc\">.*?</nav>)", html, re.S)
    if not style_m or not toc_m:
        raise SystemExit("STUDY_GUIDE.html missing <style> or #toc")
    pages = extract_pages(html)
    if not pages:
        raise SystemExit("no .page sections found")

    assets = out / "assets"
    page_dir = out / "pages"
    assets.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    (assets / "book.css").write_text(style_m.group(1).strip() + "\n" + CSS_EXTRA, encoding="utf-8")
    (assets / "book.js").write_text(BOOK_JS, encoding="utf-8")
    index = [{"id": p["id"], "title": p["title"], "text": p["text"][:12000]} for p in pages]
    (assets / "search-index.json").write_text(json.dumps(index), encoding="utf-8")

    toc_html = re.sub(r'href="#([a-zA-Z0-9_\-]+)"', r'href="PAGES_PREFIX\1.html"', toc_m.group(1))

    for i, p in enumerate(pages):
        content = p["html"]
        if 'class="page ' in content and "active" not in content.split(">", 1)[0]:
            content = content.replace('class="page ', 'class="page active ', 1)
        doc = render_shell(
            page_id=p["id"],
            title=p["title"],
            content=content,
            pages_prefix="",
            assets_prefix="../assets/",
            prev_id=pages[i - 1]["id"] if i else None,
            next_id=pages[i + 1]["id"] if i + 1 < len(pages) else None,
            prev_title=pages[i - 1]["title"] if i else "",
            next_title=pages[i + 1]["title"] if i + 1 < len(pages) else "",
            toc=toc_html,
        )
        (page_dir / f"{p['id']}.html").write_text(doc, encoding="utf-8")

    (out / "index.html").write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=pages/preface.html">
  <title>BRIEFR Study Guide</title>
  <link rel="canonical" href="pages/preface.html">
</head>
<body>
  <p>Opening the study guide… <a href="pages/preface.html">Continue</a>.</p>
</body>
</html>
""",
        encoding="utf-8",
    )
    (out / "README.md").write_text(
        """# BRIEFR Study Guide (multi-file book)

Open [`index.html`](index.html) in a browser.

Generated from `docs/STUDY_GUIDE.html` by `scripts/build_study_guide_book.py`.

Features: responsive sidebar drawer (≤880px), cross-page search index, read progress, prev/next.
""",
        encoding="utf-8",
    )
    print(f"wrote {len(pages)} pages → {out}")
    return len(pages)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.src.is_file():
        print(f"error: missing {args.src}", file=sys.stderr)
        return 2
    build(args.src, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
