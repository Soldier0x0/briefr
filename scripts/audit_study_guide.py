#!/usr/bin/env python3
"""Audit docs/STUDY_GUIDE.html coverage against the runtime codebase.

Regenerates mechanical reports under docs/planning/specs/study-guide-audit/.
Does not overwrite curated analysis files (CORRECTED_TOC.md, etc.).

Usage (repo root):
  python scripts/audit_study_guide.py
  python scripts/audit_study_guide.py --out docs/planning/specs/study-guide-audit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GUIDE = ROOT / "docs" / "STUDY_GUIDE.html"
DEFAULT_OUT = ROOT / "docs" / "planning" / "specs" / "study-guide-audit"
PRODUCT_STATUS = ROOT / "docs" / "PRODUCT_STATUS.md"

# Extensions treated as "source" for inventory purposes.
SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".mjs",
    ".sh",
    ".yml",
    ".yaml",
    ".service",
    ".conf",
    ".toml",
    ".ini",
    ".md",
    ".json",
}

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "coverage",
    ".turbo",
}

# Path prefixes relative to repo root that are inventoried at file level.
INVENTORY_ROOTS = (
    "backend",
    "frontend/src",
    "deploy",
)

# Under backend/, skip these subtrees for file-level rows (listed as categories).
BACKEND_SKIP_PREFIXES = (
    "backend/tests/",
    "backend/.venv/",
)

CURATED_NAMES = frozenset(
    {
        "CORRECTED_TOC.md",
        "INTERVIEW_COVERAGE.md",
        "STALE_CLAIMS.md",
        "README.md",
    }
)

PATH_LIKE_RE = re.compile(
    r"(?:"
    r"backend/[a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+"
    r"|frontend/src/[a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+"
    r"|deploy/[a-zA-Z0-9_./\-]+"
    r"|(?:(?:ai|alembic|auth|backup|brief|correlation|db|detection|diagnostics|"
    r"enrichment|feeds|intel|ioc|jobs|matching|metrics|migration|ml|monitoring|"
    r"notifications|onboarding|preferences|proof|routers|scoring|scripts|"
    r"security_architecture|services|templates|threat_model|wallboard|webhooks|"
    r"components|pages|hooks|utils|context|config|styles|theme)/"
    r"[a-zA-Z0-9_./\-*\.]+\.[a-zA-Z0-9]+)"
    r"|(?:[a-zA-Z0-9_\-]+/(?:[a-zA-Z0-9_\-]+/)*[a-zA-Z0-9_\-]+\.(?:py|js|jsx|ts|tsx|css|mjs|sh))"
    r")"
)

# Bare module filenames commonly used in chapter file chips.
BARE_FILE_RE = re.compile(
    r"\b([a-zA-Z_][a-zA-Z0-9_]*\.(?:py|js|jsx|ts|tsx|css|mjs|service|conf|sh))\b"
)

GLOB_CHIP_RE = re.compile(
    r"\b((?:[a-zA-Z0-9_\-]+/)+)\*\.(py|js|jsx|ts|tsx|css)\b"
)

CHAPTER_ID_RE = re.compile(r'id="([a-zA-Z0-9_\-]+)"')


@dataclass
class Chapter:
    id: str
    title: str
    mentioned_paths: set[str] = field(default_factory=set)


@dataclass
class FileRow:
    path: str
    status: str  # covered | weak | gap | out_of_scope | orphan_mention
    chapters: list[str] = field(default_factory=list)
    evidence: str = ""
    notes: str = ""


def normalize_repo_path(raw: str, root: Path = ROOT) -> str | None:
    """Normalize a path-like string to a repo-relative posix path, or None."""
    s = raw.strip().strip("`'\"")
    s = s.replace("\\", "/")
    if not s or s.endswith("/") or "*" in s:
        return None
    while s.startswith("./"):
        s = s[2:]

    candidates: list[str] = [s]
    if s.startswith("scripts/") and not (root / s).is_file():
        # Guide often says scripts/foo.py for backend/scripts/foo.py
        candidates.append("backend/" + s)
    if not s.startswith(("backend/", "frontend/", "deploy/", "scripts/", "docs/")):
        if s.startswith(
            (
                "feeds/",
                "routers/",
                "db/",
                "ai/",
                "ml/",
                "correlation/",
                "detection/",
                "scoring/",
                "jobs/",
                "webhooks/",
                "wallboard/",
                "auth/",
                "brief/",
                "enrichment/",
                "ioc/",
                "matching/",
                "monitoring/",
                "security_architecture/",
                "services/",
                "threat_model/",
                "proof/",
                "preferences/",
                "onboarding/",
                "diagnostics/",
                "backup/",
                "migration/",
                "metrics/",
                "notifications/",
                "intel/",
                "templates/",
                "alembic/",
                "frameworks/",
            )
        ):
            candidates.append("backend/" + s)
            if s.startswith("frameworks/"):
                candidates.append("backend/security_architecture/" + s)
        if s.startswith(
            ("components/", "pages/", "hooks/", "utils/", "context/", "config/", "styles/", "theme/", "scoring/")
        ):
            candidates.append("frontend/src/" + s)
        if "/" not in s and s.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".mjs")):
            for prefix in ("backend/", "frontend/src/", "frontend/", "deploy/"):
                candidates.append(prefix + s)
            hits: list[str] = []
            for base in ("backend", "frontend/src", "deploy"):
                folder = root / base
                if not folder.is_dir():
                    continue
                for hit in folder.rglob(s):
                    if not hit.is_file():
                        continue
                    try:
                        rel_parts = hit.relative_to(root).parts
                    except ValueError:
                        continue
                    if any(should_skip_dir(part) for part in rel_parts):
                        continue
                    rel = hit.relative_to(root).as_posix()
                    if base == "backend" and any(rel.startswith(p) for p in BACKEND_SKIP_PREFIXES):
                        continue
                    hits.append(rel)
            if hits:
                hits.sort(key=lambda p: (-p.count("/"), p))
                candidates.insert(0, hits[0])

    seen: set[str] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if (root / c).is_file():
            return Path(c).as_posix()

    # Qualified missing paths become orphan candidates; bare misses are dropped
    qualified = s.startswith(("backend/", "frontend/", "deploy/", "scripts/", "docs/")) or (
        "/" in s
        and s.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".mjs", ".service", ".conf", ".sh"))
    )
    if not qualified:
        return None
    for c in candidates:
        if c.startswith(("backend/", "frontend/", "deploy/", "scripts/", "docs/")):
            return Path(c).as_posix()
    return Path("backend/" + s).as_posix() if not s.startswith("backend/") else s


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".")


def iter_inventory_files(root: Path = ROOT) -> list[str]:
    files: list[str] = []
    for inv_root in INVENTORY_ROOTS:
        base = root / inv_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            try:
                rel_path = path.relative_to(root)
            except ValueError:
                continue
            if any(should_skip_dir(part) for part in rel_path.parts):
                continue
            rel = rel_path.as_posix()
            if any(rel.startswith(p) for p in BACKEND_SKIP_PREFIXES):
                continue
            # Skip alembic version noise? Keep versions — migrations are load-bearing.
            if path.suffix.lower() not in SOURCE_SUFFIXES and path.name not in {
                "Dockerfile",
                "Makefile",
                "Procfile",
            }:
                # allow extensionless deploy units already covered by .service
                if inv_root != "deploy":
                    continue
            files.append(rel)
    return files


class GuideParser(HTMLParser):
    """Extract TOC chapters and path-like mentions scoped to active chapter."""

    def __init__(self, root: Path = ROOT) -> None:
        super().__init__()
        self.root = root
        self.chapters: dict[str, Chapter] = {}
        self.toc_order: list[str] = []
        self._in_toc = False
        self._toc_depth = 0
        self._current_chapter: str | None = None
        self._capture_toc_link = False
        self._toc_href: str | None = None
        self._toc_title_parts: list[str] = []
        self._page_ids: set[str] = set()
        self.all_mentions: set[str] = set()
        self.orphan_raw: list[str] = []
        self._chip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "nav" and ad.get("id") == "toc":
            self._in_toc = True
            self._toc_depth = 0
        if self._in_toc:
            self._toc_depth += 1

        classes = set((ad.get("class") or "").split())
        cid = ad.get("id") or ""
        if tag in {"section", "header", "article", "div"} and "page" in classes and cid:
            self._page_ids.add(cid)
            self._current_chapter = cid
            if cid not in self.chapters:
                self.chapters[cid] = Chapter(id=cid, title=cid)

        if self._in_toc and tag == "a" and "toc-link" in classes:
            href = ad.get("href") or ""
            if href.startswith("#"):
                self._capture_toc_link = True
                self._toc_href = href[1:]
                self._toc_title_parts = []

        if tag == "span" and "chip" in classes:
            self._chip = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_toc:
            self._toc_depth -= 1
            if self._toc_depth <= 0 and tag == "nav":
                self._in_toc = False
                self._toc_depth = 0
        if self._capture_toc_link and tag == "a":
            title = re.sub(r"\s+", " ", "".join(self._toc_title_parts)).strip()
            cid = self._toc_href or ""
            if cid:
                ch = self.chapters.get(cid) or Chapter(id=cid, title=title or cid)
                ch.title = title or ch.title
                self.chapters[cid] = ch
                if cid not in self.toc_order:
                    self.toc_order.append(cid)
            self._capture_toc_link = False
            self._toc_href = None
            self._toc_title_parts = []
        if tag == "span" and getattr(self, "_chip", False):
            self._chip = False

    def handle_data(self, data: str) -> None:
        if self._capture_toc_link:
            self._toc_title_parts.append(data)
        self._ingest_text(data)

    def _ingest_text(self, data: str) -> None:
        text = data.strip()
        if not text:
            return

        # Glob chips: db/*.py, correlation/*.py, alembic/versions/*.py
        for m in GLOB_CHIP_RE.finditer(text):
            prefix = m.group(1).rstrip("/")
            ext = m.group(2)
            for base in (prefix, f"backend/{prefix}", f"frontend/src/{prefix}"):
                folder = self.root / base
                if not folder.is_dir():
                    continue
                for path in sorted(folder.glob(f"*.{ext}")):
                    if not path.is_file():
                        continue
                    try:
                        rel = path.relative_to(self.root).as_posix()
                    except ValueError:
                        continue
                    self.all_mentions.add(rel)
                    if self._current_chapter and self._current_chapter in self.chapters:
                        self.chapters[self._current_chapter].mentioned_paths.add(rel)

        for m in PATH_LIKE_RE.finditer(text):
            raw = m.group(0)
            # Trim trailing punctuation leftovers
            raw = raw.rstrip(".,;:)")
            # Skip glob forms already handled
            if "*" in raw:
                continue
            self._record_path(raw)

        # Bare filenames ONLY inside file chips (prose false-positives like Next.js / Chart.js)
        if self._chip:
            for m in BARE_FILE_RE.finditer(text):
                self._record_path(m.group(1))

    def _record_path(self, raw: str) -> None:
        norm = normalize_repo_path(raw, root=self.root)
        if norm is None:
            return
        self.all_mentions.add(norm)
        if self._current_chapter and self._current_chapter in self.chapters:
            self.chapters[self._current_chapter].mentioned_paths.add(norm)
        if not (self.root / norm).is_file():
            self.orphan_raw.append(raw)


def parse_guide(html: str, root: Path = ROOT) -> GuideParser:
    parser = GuideParser(root=root)
    parser.feed(html)
    # Fallback: if TOC empty, use page ids order from regex
    if not parser.toc_order:
        for m in CHAPTER_ID_RE.finditer(html):
            cid = m.group(1)
            if cid in parser._page_ids and cid not in parser.toc_order:
                parser.toc_order.append(cid)
    return parser


def directory_of(path: str) -> str:
    return str(Path(path).parent).replace("\\", "/")


# Inventory roots and other directories that are too broad for "weak" sibling inference.
BROAD_DIRS = frozenset(
    {
        ".",
        "backend",
        "frontend",
        "frontend/src",
        "deploy",
        "scripts",
        "docs",
    }
)


def classify_files(
    inventory: list[str],
    chapters: dict[str, Chapter],
    all_mentions: set[str],
    root: Path = ROOT,
) -> list[FileRow]:
    # Build reverse index: path -> chapters
    path_to_chapters: dict[str, set[str]] = defaultdict(set)
    dir_to_chapters: dict[str, set[str]] = defaultdict(set)
    for cid, ch in chapters.items():
        for p in ch.mentioned_paths:
            path_to_chapters[p].add(cid)
            parent = directory_of(p)
            if parent not in BROAD_DIRS:
                dir_to_chapters[parent].add(cid)

    rows: list[FileRow] = []
    inventory_set = set(inventory)

    for path in inventory:
        owners = sorted(path_to_chapters.get(path, set()))
        if owners:
            rows.append(
                FileRow(
                    path=path,
                    status="covered",
                    chapters=owners,
                    evidence="exact path mention in chapter body/chips",
                )
            )
            continue

        parent = directory_of(path)
        dir_owners = sorted(dir_to_chapters.get(parent, set())) if parent not in BROAD_DIRS else []
        # Weak: package dir mentioned via another file in same dir
        if dir_owners:
            rows.append(
                FileRow(
                    path=path,
                    status="weak",
                    chapters=dir_owners,
                    evidence=f"sibling/dir coverage under {parent}/",
                    notes="File never named; only directory-level association",
                )
            )
            continue

        rows.append(
            FileRow(
                path=path,
                status="gap",
                chapters=[],
                evidence="",
                notes="No study-guide ownership found",
            )
        )

    # Orphan mentions: in guide, not on disk / not in inventory
    for mention in sorted(all_mentions):
        if mention in inventory_set:
            continue
        if (root / mention).is_file():
            # File exists but outside inventory roots (e.g. scripts/) — note as covered-external
            owners = sorted(path_to_chapters.get(mention, set()))
            rows.append(
                FileRow(
                    path=mention,
                    status="covered" if owners else "weak",
                    chapters=owners,
                    evidence="mentioned; outside primary inventory roots",
                    notes="Exists on disk but not under backend/frontend/src/deploy inventory roots",
                )
            )
        else:
            owners = sorted(path_to_chapters.get(mention, set()))
            rows.append(
                FileRow(
                    path=mention,
                    status="orphan_mention",
                    chapters=owners,
                    evidence="named in STUDY_GUIDE.html",
                    notes="Path does not exist on disk — likely stale",
                )
            )

    # Stable category rows for skipped tests
    rows.append(
        FileRow(
            path="backend/tests/**",
            status="out_of_scope",
            chapters=[],
            evidence="",
            notes="Aggregate into Testing strategy chapter; not file-mapped",
        )
    )
    return rows


def suggest_chapter_home(path: str) -> str:
    """Heuristic recommended chapter home for a gap file."""
    rules = [
        (r"^backend/feeds/", "in-feeds"),
        (r"^backend/routers/", "api-routers"),
        (r"^backend/db/", "be-data"),
        (r"^backend/alembic/", "be-alembic"),
        (r"^backend/correlation/", "ie-correlation"),
        (r"^backend/detection/", "ie-detection"),
        (r"^backend/scoring/", "ie-scoring"),
        (r"^backend/ai/", "ie-ml-providers"),
        (r"^backend/ml/", "ie-ml"),
        (r"^backend/jobs/", "in-jobs"),
        (r"^backend/webhooks/", "api-webhooks"),
        (r"^backend/wallboard/", "api-ops"),
        (r"^backend/auth/", "be-auth"),
        (r"^backend/security_architecture/", "api-secarch"),
        (r"^backend/monitoring/", "api-ops"),
        (r"^backend/backup/", "api-ops"),
        (r"^backend/brief/", "ie-brief"),
        (r"^backend/matching/", "ie-matching"),
        (r"^backend/threat_model/", "ie-threatmodel"),
        (r"^backend/ioc/", "ie-threatmodel"),
        (r"^backend/enrichment/", "ie-ml"),
        (r"^deploy/", "devops-deploy"),
        (r"^frontend/src/pages/", "fe-state"),
        (r"^frontend/src/components/", "fe-state"),
        (r"^frontend/src/hooks/", "fe-state"),
        (r"^frontend/src/utils/", "fe-state"),
        (r"^frontend/src/styles/", "fe-design"),
        (r"^frontend/src/theme/", "fe-design"),
        (r"^frontend/src/context/", "fe-state"),
        (r"^frontend/src/config/", "fe-libs"),
        (r"^frontend/src/scoring/", "ie-scoring"),
        (r"^backend/operator_settings\.py$", "api-usersettings"),
        (r"^backend/scheduler", "in-scheduler"),
        (r"^backend/api_queue", "in-queue"),
        (r"^backend/rate_limit", "be-ratelimit"),
        (r"^backend/settings", "be-config"),
        (r"^backend/main\.py$", "be-bootstrap"),
        (r"^backend/database\.py$", "be-shim"),
    ]
    for pat, chapter in rules:
        if re.search(pat, path):
            return chapter
    return "TBD — needs outline decision"


def write_reports(out: Path, rows: list[FileRow], chapters: dict[str, Chapter], toc_order: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r.status] += 1

    payload = {
        "generated": today,
        "guide": "docs/STUDY_GUIDE.html",
        "counts": dict(counts),
        "chapters": [
            {
                "id": cid,
                "title": chapters[cid].title if cid in chapters else cid,
                "mention_count": len(chapters[cid].mentioned_paths) if cid in chapters else 0,
            }
            for cid in toc_order
        ],
        "files": [asdict(r) for r in rows],
    }
    (out / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # inventory.md
    lines = [
        f"# Study guide file inventory",
        "",
        f"_Regenerated {today} by `scripts/audit_study_guide.py`. Do not hand-edit; re-run the script._",
        "",
        f"| Status | Count |",
        f"|--------|------:|",
    ]
    for key in ("covered", "weak", "gap", "orphan_mention", "out_of_scope"):
        lines.append(f"| `{key}` | {counts.get(key, 0)} |")
    lines += [
        "",
        "| Path | Status | Chapters | Evidence / notes |",
        "|------|--------|----------|------------------|",
    ]
    for r in rows:
        ch = ", ".join(f"`{c}`" for c in r.chapters) if r.chapters else "—"
        note = (r.evidence + ("; " + r.notes if r.notes else "")).replace("|", "\\|")
        lines.append(f"| `{r.path}` | `{r.status}` | {ch} | {note} |")
    lines.append("")
    (out / "inventory.md").write_text("\n".join(lines), encoding="utf-8")

    # gaps.md
    gap_lines = [
        f"# Study guide coverage gaps",
        "",
        f"_Regenerated {today} by `scripts/audit_study_guide.py`._",
        "",
        "Every in-scope file with status `gap` or `orphan_mention`, plus a heuristic chapter home.",
        "",
        "| Path | Status | Recommended chapter id |",
        "|------|--------|------------------------|",
    ]
    for r in rows:
        if r.status not in {"gap", "orphan_mention"}:
            continue
        home = "N/A — remove/update mention" if r.status == "orphan_mention" else suggest_chapter_home(r.path)
        gap_lines.append(f"| `{r.path}` | `{r.status}` | `{home}` |")
    gap_lines.append("")
    (out / "gaps.md").write_text("\n".join(gap_lines), encoding="utf-8")

    # coverage skeleton
    cov = [
        f"# Interview coverage skeleton",
        "",
        f"_Regenerated {today}. Fill scores in `INTERVIEW_COVERAGE.md` (curated); this file only lists chapters._",
        "",
        "| Chapter id | Title | Mentions | Concept | Why | How | Self-check | Interview-ready? |",
        "|------------|-------|---------:|---------|-----|-----|------------|------------------|",
    ]
    for cid in toc_order:
        ch = chapters.get(cid) or Chapter(id=cid, title=cid)
        cov.append(
            f"| `{cid}` | {ch.title.replace('|', '/')} | {len(ch.mentioned_paths)} |  |  |  |  |  |"
        )
    cov.append("")
    (out / "coverage-skeleton.md").write_text("\n".join(cov), encoding="utf-8")

    # summary
    gaps = [r for r in rows if r.status == "gap"]
    orphans = [r for r in rows if r.status == "orphan_mention"]
    weak = [r for r in rows if r.status == "weak"]
    top_gap_dirs: dict[str, int] = defaultdict(int)
    for r in gaps:
        parts = r.path.split("/")
        key = "/".join(parts[:3]) if len(parts) >= 3 else r.path
        top_gap_dirs[key] += 1
    top = sorted(top_gap_dirs.items(), key=lambda kv: (-kv[1], kv[0]))[:25]

    summary = [
        f"# Study guide audit summary",
        "",
        f"_Regenerated {today} by `scripts/audit_study_guide.py`._",
        "",
        "## Counts",
        "",
        f"- Covered: **{counts.get('covered', 0)}**",
        f"- Weak (dir-only): **{counts.get('weak', 0)}**",
        f"- Gaps: **{counts.get('gap', 0)}**",
        f"- Orphan mentions: **{counts.get('orphan_mention', 0)}**",
        f"- Out of scope rows: **{counts.get('out_of_scope', 0)}**",
        f"- TOC chapters: **{len(toc_order)}**",
        "",
        "## Top gap directories",
        "",
    ]
    if top:
        summary.append("| Prefix | Gap files |")
        summary.append("|--------|----------:|")
        for pref, n in top:
            summary.append(f"| `{pref}` | {n} |")
    else:
        summary.append("_No gaps._")
    summary += [
        "",
        "## Next curated docs",
        "",
        "- `CORRECTED_TOC.md` — proposed outline for the multi-file shell",
        "- `INTERVIEW_COVERAGE.md` — fill from `coverage-skeleton.md`",
        "- `STALE_CLAIMS.md` — start from orphan mentions + PRODUCT_STATUS deltas",
        "",
        f"Orphans sample: {', '.join(f'`{o.path}`' for o in orphans[:12]) or '_none_'}",
        f"Weak sample: {', '.join(f'`{w.path}`' for w in weak[:12]) or '_none_'}",
        "",
    ]
    (out / "summary.md").write_text("\n".join(summary), encoding="utf-8")

    return {"counts": dict(counts), "gap_dirs": top}


def run(guide_path: Path, out: Path, root: Path = ROOT) -> dict:
    html = guide_path.read_text(encoding="utf-8")
    parsed = parse_guide(html, root=root)
    inventory = iter_inventory_files(root)
    rows = classify_files(inventory, parsed.chapters, parsed.all_mentions, root=root)
    # Prefer TOC order; append any page chapters missing from TOC
    toc = list(parsed.toc_order)
    for cid in parsed.chapters:
        if cid not in toc and cid in parsed._page_ids:
            toc.append(cid)
    return write_reports(out, rows, parsed.chapters, toc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--guide", type=Path, default=DEFAULT_GUIDE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)

    if not args.guide.is_file():
        print(f"error: guide not found: {args.guide}", file=sys.stderr)
        return 2

    stats = run(args.guide, args.out, args.root)
    counts = stats["counts"]
    print(
        "study-guide audit:"
        f" covered={counts.get('covered', 0)}"
        f" weak={counts.get('weak', 0)}"
        f" gap={counts.get('gap', 0)}"
        f" orphan={counts.get('orphan_mention', 0)}"
        f" → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
