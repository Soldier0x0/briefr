# Study Guide Prose-Depth Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every study-guide chapter that is still short of interview depth up to Concept · Why · How · Self-check, without changing the multi-file shell or the gap=0 inventory guarantee.

**Architecture:** Keep `docs/STUDY_GUIDE.html` as the editable source of truth. Deepen prose in-place by Part, regenerate `docs/study-guide/` with `scripts/build_study_guide_book.py`, and re-run `scripts/audit_study_guide.py` after each Part so coverage cannot regress. Curated scores live in `docs/planning/specs/study-guide-audit/INTERVIEW_COVERAGE.md`.

**Tech Stack:** Existing HTML textbook + `scripts/build_study_guide_book.py` + `scripts/audit_study_guide.py` + pytest; no new runtime dependencies.

## Global Constraints

- Editable source remains `docs/STUDY_GUIDE.html` (do **not** split to per-chapter source in this plan — that is a separate follow-on plan).
- After every content task: `python scripts/build_study_guide_book.py` then `python scripts/audit_study_guide.py` must still report `gap=0`.
- Truth order: running code → `docs/PRODUCT_STATUS.md` → study guide.
- Match existing chapter voice (concept / why / how / self-check; file chips; real paths).
- No product feature code changes; docs + generator/auditor tests only.
- Branch naming: `cursor/study-guide-prose-<topic>-9180`.
- One Part per PR when possible; merge via local green + Gemini disposition.

## Scope note (two tracks)

| Track | This plan? | Why |
|-------|------------|-----|
| A. Part-by-Part prose depth | **Yes** | Highest reader value; IR scores still lag on primer/roadmap/preface and short new chapters |
| B. Split editable source off monolith | **No — separate plan later** | Independent; safer after prose stabilizes so you do not migrate text twice |

---

## File map

| Path | Role |
|------|------|
| `docs/STUDY_GUIDE.html` | Editable chapter source (all prose edits land here) |
| `docs/study-guide/**` | Generated book (never hand-edit; regenerate) |
| `scripts/build_study_guide_book.py` | Book generator |
| `scripts/audit_study_guide.py` | Coverage gate |
| `docs/planning/specs/study-guide-audit/INTERVIEW_COVERAGE.md` | IR scorecard (curated) |
| `docs/planning/specs/study-guide-audit/STALE_CLAIMS.md` | Claim RCA log |
| `docs/HANDOVER.md` | Session next-pointer |
| `backend/tests/test_build_study_guide_book.py` | Generator regression |
| `backend/tests/test_audit_study_guide.py` | Auditor regression |

## Definition of “interview-ready” (per chapter)

A chapter passes when all are true:

1. **Concept** — defines the subsystem without jargon soup (≥1 `h4.subhead.concept` or equivalent clear definition paragraph).
2. **Why** — ≥1 BRIEFR-specific rationale (not generic best practice).
3. **How** — names real files/functions that exist on disk (chips or `<code>` paths verified by auditor).
4. **Self-check** — ≥2 `<li>` questions under `.self-check` (≥3 preferred).
5. Regenerated page exists under `docs/study-guide/pages/<id>.html`.

---

### Task 1: Freeze the IR backlog (scorecard refresh)

**Files:**
- Modify: `docs/planning/specs/study-guide-audit/INTERVIEW_COVERAGE.md`
- Modify: `docs/HANDOVER.md` (one line pointing at this plan)

**Interfaces:**
- Consumes: current `docs/STUDY_GUIDE.html` TOC ids
- Produces: ordered backlog list used by Tasks 2–6 (exact chapter ids below)

- [ ] **Step 1: Re-score chapters that the scorecard still marks IR=no or notes as stale**

Open `docs/STUDY_GUIDE.html` and verify these ids still need work (mark each `needs-depth` or `done` in INTERVIEW_COVERAGE):

| Priority | Chapter id | Likely work |
|----------|------------|-------------|
| P0 | `fe-analyst-shell` | Expand How with more real traces (drawer tabs, filter persistence) |
| P0 | `fe-admin-shell` | Expand How for FeedHealth freshness vs circuit; JobTable LOCKED |
| P0 | `fe-forge-wallboard` | Expand How for forge view params + wallboard cookie exchange |
| P0 | `fe-shared-utils` | Name 5–8 concrete utils/hooks with one-line jobs |
| P0 | `ie-retrieval-ops` | Add short code caption from `build_retrieval_health` return shape |
| P1 | `primer-mechanics` | Add self-check (≥3); strengthen How (point to where each concept appears later) |
| P1 | `preface` | Add self-check (≥2) about study method + regenerate command |
| P2 | `roadmap-future` | Point at audit folder + zero-gap status; refresh “next” vs PRODUCT_STATUS |
| P2 | `roadmap-nongoals` / `roadmap-reversed` | Light How: cite `ROADMAP.md` / license files |

- [ ] **Step 2: Write the backlog table into INTERVIEW_COVERAGE.md**

Replace the outdated “Missing `operator_settings` chip” style notes with a section:

```markdown
## Prose-depth backlog (2026-07-19 plan)

| Order | id | Target | Status |
|------:|----|--------|--------|
| 1 | fe-analyst-shell | deepen How + 1 code caption | pending |
| 2 | fe-admin-shell | deepen How (health vs freshness, jobs) | pending |
| 3 | fe-forge-wallboard | deepen How (URL params, kiosk cookie) | pending |
| 4 | fe-shared-utils | name concrete helpers | pending |
| 5 | ie-retrieval-ops | code caption for health payload | pending |
| 6 | primer-mechanics | self-check + later-chapter map | pending |
| 7 | preface | self-check | pending |
| 8 | roadmap-future | audit pointer + PRODUCT_STATUS next | pending |
```

- [ ] **Step 3: Commit**

```bash
git checkout -b cursor/study-guide-prose-backlog-9180
git add docs/planning/specs/study-guide-audit/INTERVIEW_COVERAGE.md docs/HANDOVER.md
git commit -m "docs: freeze study-guide prose-depth backlog"
git push -u origin cursor/study-guide-prose-backlog-9180
```

---

### Task 2: Deepen Part I-B — analyst + admin shells

**Files:**
- Modify: `docs/STUDY_GUIDE.html` sections `id="fe-analyst-shell"` and `id="fe-admin-shell"`
- Regenerate: `docs/study-guide/pages/fe-analyst-shell.html`, `fe-admin-shell.html`
- Test: auditor + builder via commands below

**Interfaces:**
- Consumes: `frontend/src/App.jsx` (`?tab=`, hidden panels), `frontend/src/pages/admin/FeedHealthPage.jsx`, `SchedulerPage.jsx`
- Produces: longer How sections; still gap=0

- [ ] **Step 1: Write a failing structural gate test for self-check counts on these ids**

Create `backend/tests/test_study_guide_chapter_gates.py`:

```python
"""Structural gates for study-guide interview-ready chapters."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "STUDY_GUIDE.html"


def _section(html: str, chapter_id: str) -> str:
    m = re.search(
        rf'<(section|header|div)\b[^>]*\bid="{re.escape(chapter_id)}"[^>]*>',
        html,
    )
    assert m, f"missing chapter {chapter_id}"
    start = m.start()
    # depth-aware close of the opening tag name
    tag = m.group(1)
    i = m.end()
    depth = 1
    for tm in re.finditer(rf"</?{tag}\b[^>]*>", html[i:], re.I):
        token = tm.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start : i + tm.end()]
        elif not token.endswith("/>"):
            depth += 1
    raise AssertionError(f"unclosed chapter {chapter_id}")


def test_fe_analyst_shell_has_self_check_and_how():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "fe-analyst-shell")
    assert 'class="self-check"' in sec
    assert sec.count("<li>") >= 3
    assert "subhead how" in sec or "subhead why" in sec
    assert "App.jsx" in sec
```

- [ ] **Step 2: Run test — expect PASS already for self-check; extend assertions that will fail until deepened**

Add to the same test file:

```python
def test_fe_analyst_shell_mentions_hidden_panels_and_drawer():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "fe-analyst-shell")
    assert "hidden" in sec.lower()
    assert "DetailDrawer" in sec
    assert "FilterBar" in sec
    # depth marker — must explain URL ownership with an example tab value
    assert "tab=feed" in sec or "?tab=" in sec


def test_fe_admin_shell_mentions_health_vs_freshness():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "fe-admin-shell")
    assert "FeedHealth" in sec or "FeedHealthPage" in sec
    assert "fresh" in sec.lower()  # freshness callout
    assert "SchedulerPage" in sec or "LOCKED" in sec
```

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_study_guide_chapter_gates.py -q --tb=short
```

Expected: FAIL on missing `tab=feed` / `fresh` / `LOCKED` phrasing until Step 3.

- [ ] **Step 3: Expand prose in `STUDY_GUIDE.html`**

In `fe-analyst-shell`, add a How subsection that states:

1. `?tab=feed` (and siblings) are written by `selectAppTab` / `buildAppTabSearchParams` in `App.jsx`.
2. FEED uses `hidden` panels so filters/scroll survive tab switches.
3. `DetailDrawer/` tabs (Overview / Intel / Detect / Related) are the investigation surface; MITRE pills call `openForgeTechnique`.

In `fe-admin-shell`, add a How subsection that states:

1. `FeedHealthPage` distinguishes circuit/HTTP OK from sync freshness (stale-but-healthy callout).
2. `SchedulerPage` / shared `JobTable` show `progress_message` while job is `LOCKED`.
3. `?p=` selects the admin page module.

Keep chips; do not invent files.

- [ ] **Step 4: Regenerate + audit + re-run gates**

```bash
python scripts/build_study_guide_book.py
python scripts/audit_study_guide.py   # must print gap=0
cd backend && .venv/bin/python -m pytest tests/test_study_guide_chapter_gates.py tests/test_audit_study_guide.py tests/test_build_study_guide_book.py -q
```

Expected: `gap=0`; all tests PASS.

- [ ] **Step 5: Commit + PR**

```bash
git add docs/STUDY_GUIDE.html docs/study-guide backend/tests/test_study_guide_chapter_gates.py docs/planning/specs/study-guide-audit
git commit -m "docs: deepen study-guide analyst and admin shell chapters"
git push -u origin cursor/study-guide-prose-shells-9180
# open PR, wait for Gemini, disposition, merge
```

---

### Task 3: Deepen Part I-B — Forge/wallboard + shared utils

**Files:**
- Modify: `docs/STUDY_GUIDE.html` (`fe-forge-wallboard`, `fe-shared-utils`)
- Regenerate: matching `docs/study-guide/pages/*.html`
- Modify: `backend/tests/test_study_guide_chapter_gates.py`

**Interfaces:**
- Consumes: `components/Forge.jsx`, `pages/WallboardPage.jsx`, `hooks/*`, `utils/cveFilters.js`, `api.js`
- Produces: named helper inventory (8 concrete files max — YAGNI)

- [ ] **Step 1: Add failing gates**

```python
def test_fe_forge_mentions_view_params_and_wallboard_token():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "fe-forge-wallboard")
    assert "view" in sec  # Forge internal view param
    assert "WALLBOARD_TOKEN" in sec or "wallboard" in sec.lower()
    assert "HuntPack" in sec or "BacklogView" in sec


def test_fe_shared_utils_names_concrete_modules():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "fe-shared-utils")
    for name in ("useAsync", "useWatchlist", "cveFilters", "appLinks", "api.js"):
        assert name in sec
```

Run pytest on these two — expect FAIL until prose updated.

- [ ] **Step 2: Expand `fe-forge-wallboard` How**

Cover: Forge URL params beyond `tab=forge`; backlog/hunt-pack views; wallboard cookie exchange (raw token not stored long-lived in the kiosk tab). Cite `pages/WallboardPage.jsx` + backend wallboard session chapter cross-link (Ch 30 / api-ops).

- [ ] **Step 3: Expand `fe-shared-utils` How**

Add a mini-table (existing `.mini-table` class) with ≤8 rows, e.g.:

| Module | Job |
|--------|-----|
| `hooks/useAsync.js` | async status helper for page loads |
| `hooks/useWatchlist.js` | pin/watchlist state |
| `utils/cveFilters.js` | feed filter pure logic |
| `utils/appLinks.js` | deep-link builders |
| `api.js` | fetch façade + `requestId` on errors |

- [ ] **Step 4: Regenerate, audit gap=0, pytest PASS, commit, PR, Gemini, merge**

```bash
python scripts/build_study_guide_book.py && python scripts/audit_study_guide.py
cd backend && .venv/bin/python -m pytest tests/test_study_guide_chapter_gates.py -q
```

---

### Task 4: Retrieval-ops code caption + PRODUCT_STATUS alignment

**Files:**
- Modify: `docs/STUDY_GUIDE.html` (`ie-retrieval-ops`)
- Optionally append: `docs/planning/specs/study-guide-audit/STALE_CLAIMS.md` if any PRODUCT_STATUS mismatch found
- Regenerate book page

**Interfaces:**
- Consumes: `backend/services/retrieval_health.py` (`build_retrieval_health` return dict)
- Produces: `<pre class="code">` caption listing keys: `embeddings_enabled`, `auto_on_ingest`, `counts`, `pending`, `degraded`

- [ ] **Step 1: Failing gate**

```python
def test_ie_retrieval_ops_documents_degraded_reasons():
    html = GUIDE.read_text(encoding="utf-8")
    sec = _section(html, "ie-retrieval-ops")
    for key in ("embeddings_enabled", "auto_on_ingest", "degraded", "cold_index"):
        assert key in sec
```

- [ ] **Step 2: Add abridged code block** sourced from the real return shape in `build_retrieval_health` (keys only / illustrative object — no invented fields).

- [ ] **Step 3: Diff against `docs/PRODUCT_STATUS.md` Embeddings row** — if the guide disagrees, fix guide or log RCA in `STALE_CLAIMS.md`.

- [ ] **Step 4: Regenerate, audit, pytest, commit, PR, merge**

---

### Task 5: Primer + preface interview loops

**Files:**
- Modify: `docs/STUDY_GUIDE.html` (`primer-mechanics`, `preface`)
- Regenerate pages

**Interfaces:**
- Consumes: primer concept cards already in HTML
- Produces: `.self-check` blocks; primer How that maps each primer term → later chapter id

- [ ] **Step 1: Failing gates**

```python
def test_primer_has_self_check():
    sec = _section(GUIDE.read_text(encoding="utf-8"), "primer-mechanics")
    assert 'class="self-check"' in sec
    assert sec.count("<li>") >= 3


def test_preface_has_self_check_and_regen_command():
    sec = _section(GUIDE.read_text(encoding="utf-8"), "preface")
    assert 'class="self-check"' in sec
    assert "build_study_guide_book.py" in sec
```

- [ ] **Step 2: Implement self-checks + primer→chapter map** (e.g. circuit breaker → Ch 16, watermark → Ch 14, EPSS → Ch 18).

- [ ] **Step 3: Regenerate, audit gap=0, pytest, commit, PR, merge**

---

### Task 6: Roadmap/future alignment + scorecard closeout

**Files:**
- Modify: `docs/STUDY_GUIDE.html` (`roadmap-future` at minimum)
- Modify: `docs/planning/specs/study-guide-audit/INTERVIEW_COVERAGE.md` (mark backlog rows done)
- Modify: `docs/HANDOVER.md`

**Interfaces:**
- Consumes: audit summary counts; PRODUCT_STATUS “what's next”
- Produces: closed prose-depth backlog; HANDOVER next = source-split plan (optional)

- [ ] **Step 1: Update `roadmap-future` to cite**

  - `docs/planning/specs/study-guide-audit/` (zero-gap inventory)
  - retrieval ops as shipped (not “near-term next”) if PRODUCT_STATUS still says shipped

- [ ] **Step 2: Full gate suite**

```bash
python scripts/build_study_guide_book.py
python scripts/audit_study_guide.py    # gap=0 required
cd backend && .venv/bin/python -m pytest \
  tests/test_study_guide_chapter_gates.py \
  tests/test_audit_study_guide.py \
  tests/test_build_study_guide_book.py -q
```

- [ ] **Step 3: Mark all backlog rows `done` in INTERVIEW_COVERAGE.md; HANDOVER entry**

- [ ] **Step 4: Final PR merge for this track**

---

### Task 7 (out of scope here): Source-split plan stub only

Do **not** implement in this plan. When starting later, create a new plan file:

`docs/superpowers/plans/YYYY-MM-DD-study-guide-source-split.md`

Intended goal then: per-chapter source under e.g. `docs/study-guide/src/*.html` (or markdown) compiled by an extended builder, with `STUDY_GUIDE.html` either generated or retired. Requires its own design approval.

---

## Verification matrix (every content PR)

| Check | Command | Pass criteria |
|-------|---------|---------------|
| Chapter gates | `pytest backend/tests/test_study_guide_chapter_gates.py -q` | green |
| Auditor | `python scripts/audit_study_guide.py` | `gap=0` |
| Builder | `python scripts/build_study_guide_book.py` | exits 0; page count ≥ 69 |
| Builder unit | `pytest backend/tests/test_build_study_guide_book.py -q` | green |
| Gemini | wait ~1–2 min on PR | disposition each actionable comment |
| Docs | HANDOVER + INTERVIEW_COVERAGE updated when IR status changes | yes |

## Self-review (plan vs remaining work)

1. **Spec coverage:** HANDOVER “deeper prose polish” → Tasks 2–6; “split editable source” → Task 7 deferred. Audit gap=0 preserved via global constraint + every-task audit step.
2. **Placeholders:** none — gates and file paths are concrete.
3. **Type/name consistency:** chapter ids match TOC (`fe-analyst-shell`, `ie-retrieval-ops`, etc.); generator/auditor script names match repo.

---

## Execution order (PRs)

1. Task 1 backlog freeze (small docs PR)  
2. Task 2 analyst+admin  
3. Task 3 forge+utils  
4. Task 4 retrieval caption  
5. Task 5 primer+preface  
6. Task 6 roadmap + closeout  
