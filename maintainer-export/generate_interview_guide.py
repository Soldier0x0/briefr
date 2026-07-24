#!/usr/bin/env python3
"""Generate interview prep pages and integrate into study-guide book."""

from __future__ import annotations

import html
import re
from pathlib import Path

from category_utils import CATEGORY_ORDER, ensure_categories
from interview_qa_data import SEGMENTS as BASE_SEGMENTS
from interview_qa_extra import merge_segments, wire_prev_next
from interview_qa_gap_fill import merge_gap_questions
from interview_qa_components import COMPONENT_SEGMENTS

ROOT = Path(__file__).resolve().parent
GUIDE = ROOT / "study-guide"
PAGES = GUIDE / "pages"
ASSETS = GUIDE / "assets"

FOOTER = """
    <footer>
      Built from a direct read of the BRIEFR codebase. When this disagrees with the repo, trust the repo.
      · <a href="preface.html">Book home</a>
      · <a href="../../learn/index.html">Learn pathways</a>
      · Regenerate interview section: <code>maintainer-export/generate_interview_guide.py</code>
    </footer>
  </main>
</div>
<script src="../assets/book.js"></script>
</body>
</html>
"""

INTERVIEW_CSS = """
.interview-qa {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  margin: 18px 0;
  background: var(--bg-card);
}
.interview-qa h4 {
  margin: 0 0 10px;
  font-size: 1rem;
  color: var(--tag-faq);
  line-height: 1.45;
}
.interview-qa .answer {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.55;
}
.interview-qa .answer strong { color: var(--text); }
.interview-category {
  margin: 28px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}
"""


def split_segments(segments: list[dict]) -> tuple[list[dict], list[dict]]:
    thematic: list[dict] = []
    components: list[dict] = []
    for seg in segments:
        if seg["slug"].startswith("iv-comp-"):
            components.append(seg)
        else:
            thematic.append(seg)
    return thematic, components


def build_toc_links(segments: list[dict]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    thematic_links: list[tuple[str, str]] = []
    component_links: list[tuple[str, str]] = []
    thematic, components = split_segments(segments)
    for seg in thematic:
        if seg["slug"] == "iv-part":
            thematic_links.append((f"{seg['slug']}.html", "How to use this section"))
            continue
        num = seg["chapter_num"].replace("Interview · ", "").strip()
        thematic_links.append((f"{seg['slug']}.html", f"{num} · {seg['title']}"))
    for seg in components:
        num = seg["chapter_num"].replace("Components · ", "").strip()
        component_links.append((f"{seg['slug']}.html", f"{num} · {seg['title']}"))
    return thematic_links, component_links


def toc_block(
    thematic_links: list[tuple[str, str]],
    component_links: list[tuple[str, str]],
) -> str:
    t_rows = "\n".join(
        f'        <a class="toc-link toc-sub" href="{href}">{label}</a>'
        for href, label in thematic_links
    )
    c_rows = "\n".join(
        f'        <a class="toc-link toc-sub" href="{href}">{label}</a>'
        for href, label in component_links
    )
    return f"""
      <div class="toc-group">
        <div class="toc-group-title">Part VII · Interview preparation</div>
{t_rows}
      </div>
      <div class="toc-group">
        <div class="toc-group-title">Part VIII · Component reference</div>
{c_rows}
      </div>
"""


def _strip_interview_toc(toc_inner: str) -> str:
    marker = '      <div class="toc-group">\n        <div class="toc-group-title">Reference</div>'
    if "Part VII · Interview preparation" not in toc_inner:
        return toc_inner
    head, _, tail = toc_inner.partition(marker)
    head = re.sub(
        r"\n      <div class=\"toc-group\">\n        <div class=\"toc-group-title\">Part VII.*$",
        "",
        head,
        flags=re.DOTALL,
    )
    return head + marker + tail


def _inject_toc(
    toc_inner: str,
    thematic_links: list[tuple[str, str]],
    component_links: list[tuple[str, str]],
) -> str:
    marker = '      <div class="toc-group">\n        <div class="toc-group-title">Reference</div>'
    cleaned = _strip_interview_toc(toc_inner)
    return cleaned.replace(
        marker,
        toc_block(thematic_links, component_links) + "\n" + marker,
    )


def _qa_html(questions: list[dict]) -> str:
    if not questions:
        return ""
    categorized = ensure_categories(questions)
    by_cat: dict[str, list[dict]] = {key: [] for key, _ in CATEGORY_ORDER}
    for item in categorized:
        by_cat[item["category"]].append(item)

    parts: list[str] = []
    for key, label in CATEGORY_ORDER:
        items = by_cat.get(key, [])
        if not items:
            continue
        parts.append(f'      <h4 class="interview-category">{html.escape(label)}</h4>')
        for item in items:
            q = html.escape(item["q"])
            parts.append(
                f'      <div class="interview-qa">\n'
                f'        <h4>Q: {q}</h4>\n'
                f'        <p class="answer"><strong>A:</strong> {item["a"]}</p>\n'
                f"      </div>"
            )
    return "\n".join(parts)


def _shell_parts() -> tuple[str, str, str]:
    preface = (PAGES / "preface.html").read_text(encoding="utf-8")
    m = re.search(
        r"(<!DOCTYPE html>.*?<nav id=\"toc\" aria-label=\"Chapters\">)(.*?)(</nav>\s*</aside>\s*<main id=\"main-content\">)",
        preface,
        re.DOTALL,
    )
    if not m:
        raise SystemExit("could not parse preface.html shell")
    return m.group(1), m.group(2), m.group(3)


def render_page(
    seg: dict,
    toc_inner: str,
    thematic_links: list[tuple[str, str]],
    component_links: list[tuple[str, str]],
) -> str:
    head, _, main_open = _shell_parts()
    toc = _inject_toc(toc_inner, thematic_links, component_links)
    title = html.escape(seg["title"])
    page_title = f"{title} — BRIEFR Study Guide"
    chapter = html.escape(seg.get("chapter_num", "Interview"))
    dek = seg.get("dek", "")
    dek_html = f'<p class="dek">{html.escape(dek)}</p>' if dek else ""
    body_extra = seg.get("body_html", "")
    qa_block = _qa_html(seg.get("questions", []))

    prev_href, prev_title = seg["prev"]
    next_href, next_title = seg["next"]

    head = re.sub(
        r"<title>.*?</title>",
        f"<title>{page_title}</title>",
        head,
        count=1,
        flags=re.DOTALL,
    )
    head = re.sub(
        r'data-page-id="[^"]+"',
        f'data-page-id="{seg["page_id"]}"',
        head,
        count=1,
    )

    return (
        f"{head}{toc}{main_open}\n"
        f'    <section class="page active chapter" id="{seg["page_id"]}">\n'
        f'      <div class="chapter-head">\n'
        f'        <span class="chapter-num">{chapter}</span>\n'
        f"        <h3>{title}</h3>\n"
        f"        {dek_html}\n"
        f"      </div>\n"
        f'      <div class="prose">\n{body_extra}\n      </div>\n'
        f"{qa_block}\n"
        f"    </section>\n"
        f'    <nav class="page-nav" id="page-nav" aria-label="Page">'
        f'<a class="prev" href="{prev_href}"><span class="nav-label">&larr; Previous</span>'
        f'<span class="nav-title">{html.escape(prev_title)}</span></a>'
        f'<span class="spacer"></span>'
        f'<a class="next" href="{next_href}"><span class="nav-label">Next &rarr;</span>'
        f'<span class="nav-title">{html.escape(next_title)}</span></a>'
        f"</nav>\n"
        f"{FOOTER}"
    )


def patch_nav(path: Path, *, prev: tuple[str, str] | None, next_: tuple[str, str] | None) -> None:
    text = path.read_text(encoding="utf-8")
    if prev:
        href, title = prev
        text = re.sub(
            r'<a class="prev" href="[^"]+">.*?</a>',
            f'<a class="prev" href="{href}"><span class="nav-label">&larr; Previous</span>'
            f'<span class="nav-title">{html.escape(title)}</span></a>',
            text,
            count=1,
            flags=re.DOTALL,
        )
    if next_:
        href, title = next_
        text = re.sub(
            r'<a class="next" href="[^"]+">.*?</a>',
            f'<a class="next" href="{href}"><span class="nav-label">Next &rarr;</span>'
            f'<span class="nav-title">{html.escape(title)}</span></a>',
            text,
            count=1,
            flags=re.DOTALL,
        )
    path.write_text(text, encoding="utf-8")


def patch_all_tocs(
    thematic_links: list[tuple[str, str]],
    component_links: list[tuple[str, str]],
) -> None:
    block = toc_block(thematic_links, component_links)
    marker = '      <div class="toc-group">\n        <div class="toc-group-title">Reference</div>'
    for path in PAGES.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            continue
        if "Part VII · Interview preparation" in text:
            text = _strip_interview_toc(text)
        text = text.replace(marker, block + "\n" + marker)
        path.write_text(text, encoding="utf-8")


def prepare_segments() -> list[dict]:
    merged = merge_segments(BASE_SEGMENTS)
    merged = merge_gap_questions(merged)
    # Re-wire after secarch insert shifted order
    slugs = [s["slug"] for s in merged]
    if "iv-secarch-threatmodel" in slugs:
        ordered = [
            "iv-part",
            "iv-architecture",
            "iv-security",
            "iv-secarch-threatmodel",
            "iv-backend-db",
            "iv-nvd-pipeline",
            "iv-ingest-scheduler",
            "iv-correlation-scoring",
            "iv-campaign-ioc",
            "iv-ml-embeddings",
            "iv-detection-forge",
            "iv-frontend-ux",
            "iv-api-ops",
            "iv-devops-deploy",
            "iv-tests-docs",
            "iv-product-behavioral",
        ]
        by_slug = {s["slug"]: s for s in merged}
        merged = [by_slug[s] for s in ordered if s in by_slug]
    wired = wire_prev_next(merged)
    chapter_idx = 0
    for seg in wired:
        if seg["slug"] == "iv-part":
            continue
        chapter_idx += 1
        seg["chapter_num"] = f"Interview · {chapter_idx}"
        if seg.get("questions"):
            seg["questions"] = ensure_categories(seg["questions"])

    comp_wired: list[dict] = []
    for i, seg in enumerate(COMPONENT_SEGMENTS):
        row = dict(seg)
        row["chapter_num"] = f"Components · {i + 1}"
        row["questions"] = ensure_categories(row.get("questions", []))
        comp_wired.append(row)
    if comp_wired:
        wired[-1]["next"] = (f"{comp_wired[0]['slug']}.html", comp_wired[0]["title"])
        comp_wired[0]["prev"] = (f"{wired[-1]['slug']}.html", wired[-1]["title"])
        for i in range(1, len(comp_wired)):
            comp_wired[i]["prev"] = (
                f"{comp_wired[i - 1]['slug']}.html",
                comp_wired[i - 1]["title"],
            )
            comp_wired[i - 1]["next"] = (
                f"{comp_wired[i]['slug']}.html",
                comp_wired[i]["title"],
            )
        comp_wired[-1]["next"] = ("glossary.html", "Glossary")
        wired.extend(comp_wired)
    return wired


def main() -> None:
    segments = prepare_segments()
    thematic_links, component_links = build_toc_links(segments)
    _, toc_inner, _ = _shell_parts()

    css_path = ASSETS / "book.css"
    css = css_path.read_text(encoding="utf-8")
    if ".interview-qa" not in css:
        css_path.write_text(css.rstrip() + "\n" + INTERVIEW_CSS + "\n", encoding="utf-8")
    elif ".interview-category" not in css:
        css_path.write_text(css.rstrip() + "\n.interview-category {\n  margin: 28px 0 8px;\n}\n", encoding="utf-8")

    for seg in segments:
        out = PAGES / f"{seg['slug']}.html"
        out.write_text(
            render_page(seg, toc_inner, thematic_links, component_links),
            encoding="utf-8",
        )
        print("wrote", out.name)

    patch_all_tocs(thematic_links, component_links)

    first, last = segments[0], segments[-1]
    patch_nav(PAGES / "roadmap-future.html", prev=None, next_=(f"{first['slug']}.html", first["title"]))
    patch_nav(PAGES / "glossary.html", prev=(f"{last['slug']}.html", last["title"]), next_=None)

    total_q = sum(len(s.get("questions", [])) for s in segments)
    cats: dict[str, int] = {}
    for seg in segments:
        for q in ensure_categories(seg.get("questions", [])):
            cats[q["category"]] = cats.get(q["category"], 0) + 1
    print(f"done — {len(segments)} pages, {total_q} questions, categories: {cats}")


if __name__ == "__main__":
    main()
