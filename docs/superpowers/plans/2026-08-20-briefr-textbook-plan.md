# BRIEFR Textbook PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author a modular Markdown textbook grounded in the live BRIEFR codebase and render it to a print-ready PDF via Playwright.

**Architecture:** Ten parts / 37 chapters + appendices as separate Markdown files under `docs/textbook/`. A Node script merges chapters in TOC order, renders Mermaid blocks, and prints A4 PDF — extending the existing `generate_system_design_pdf.mjs` pattern.

**Tech Stack:** Markdown, Mermaid, Node.js + Playwright (from `frontend/package.json`), optional `marked` or existing HTML pipeline from SYSTEM_DESIGN script.

## Global Constraints

- Source of truth: `/agent/repos/briefr` code + `docs/PRODUCT_STATUS.md`; code wins over stale README claims.
- Document shipped vs planned honestly (STIX excluded, correlation OP client merge temporary, etc.).
- Dual audience: threat-intel concepts woven beside BRIEFR modules — no standalone glossary dump.
- Every major component: What / Why / How / Where / When.
- Each chapter: 5–8 review questions + trace pointers.
- No filler; textbook tone; consistent heading hierarchy.
- Do not edit unrelated product code except PDF build script + package script entry.

---

## File structure (locked)

```
docs/textbook/
├── _frontmatter.md              # Title page, copyright, reading map
├── part-01-foundations/
│   ├── ch01-vulnerability-intelligence-problem.md
│   ├── ch02-threat-signals-kev-epss.md
│   ├── ch03-mitre-sigma-detection-basics.md
│   └── ch04-threat-intel-primitives.md
├── part-02-architecture/
│   ├── ch05-system-shape-schema-split.md
│   ├── ch06-scheduler.md
│   └── ch07-resilience-caches-queues.md
├── part-03-ingestion/
│   ├── ch08-nvd-core-cve-record.md
│   ├── ch09-additive-enrichers.md
│   ├── ch10-ti-mirrors-blocklist.md
│   ├── ch11-otx-pulses.md
│   └── ch12-news-publications.md
├── part-04-scoring/
│   ├── ch13-threat-score.md
│   ├── ch14-environment-relevance.md
│   ├── ch15-operational-priority-ssvc.md
│   └── ch16-momentum-change-history.md
├── part-05-correlation/
│   ├── ch17-correlation-four-lanes.md
│   ├── ch18-infrastructure-graph.md
│   ├── ch19-campaigns-pulse-families.md
│   └── ch20-precompute-snapshots.md
├── part-06-detection/
│   ├── ch21-detection-context-class-router.md
│   ├── ch22-sigma-siem-yara.md
│   ├── ch23-sigmahq-index.md
│   └── ch24-forge-hunt-packs.md
├── part-07-ioc-investigation/
│   ├── ch25-ioc-lookup.md
│   ├── ch26-watchlist-retro-match.md
│   └── ch27-investigation-graph.md
├── part-08-llm-retrieval/
│   ├── ch28-llm-router-failover.md
│   ├── ch29-llm-workloads.md
│   └── ch30-embeddings-hybrid-search.md
├── part-09-surfaces/
│   ├── ch31-analyst-shell-drawer.md
│   ├── ch32-forge-incidents-advisories.md
│   ├── ch33-admin-operator.md
│   └── ch34-wallboard-kiosk.md
├── part-10-operations/
│   ├── ch35-deployment-posture.md
│   ├── ch36-shipped-vs-planned.md
│   └── ch37-codebase-map-traces.md
├── appendices/
│   ├── appendix-a-scheduler-catalog.md
│   ├── appendix-b-api-routes.md
│   ├── appendix-c-adr-summaries.md
│   └── appendix-d-env-vars.md
└── _toc.json                      # Chapter merge order for PDF script
scripts/generate_briefr_textbook_pdf.mjs
```

---

### Task 1: Scaffold textbook directory and TOC manifest

**Files:**
- Create: `docs/textbook/_frontmatter.md`
- Create: `docs/textbook/_toc.json`
- Create: stub chapter files (headings + placeholder "TODO" only if user approved outline — replace with full content in Task 3+)

**Interfaces:**
- Consumes: approved design spec `docs/superpowers/specs/2026-08-20-briefr-textbook-design.md`
- Produces: `_toc.json` array of `{ "file": "...", "title": "..." }` in reading order

- [ ] **Step 1: Create `_toc.json`**

```json
[
  { "file": "_frontmatter.md", "title": "Front Matter" },
  { "file": "part-01-foundations/ch01-vulnerability-intelligence-problem.md", "title": "Chapter 1: The Vulnerability Intelligence Problem" }
]
```

(Full array matches design spec TOC — all 37 chapters + 4 appendices.)

- [ ] **Step 2: Write `_frontmatter.md`**

Include: title, version pin (`v1.5.0` / PRODUCT_STATUS date), dual-audience note, Apache-2.0 copyright, "code wins over docs" caveat.

- [ ] **Step 3: Commit scaffold**

```bash
git add docs/textbook/
git commit -m "docs: scaffold BRIEFR textbook directory and TOC manifest"
```

---

### Task 2: PDF generation script

**Files:**
- Create: `scripts/generate_briefr_textbook_pdf.mjs`
- Modify: `frontend/package.json` (add `"textbook:pdf": "node ../scripts/generate_briefr_textbook_pdf.mjs"`)

**Interfaces:**
- Consumes: `_toc.json`, chapter markdown files, Mermaid in fenced blocks
- Produces: `docs/textbook/BRIEFR_TEXTBOOK.pdf`

- [ ] **Step 1: Copy baseline from `generate_system_design_pdf.mjs`**

Adapt paths:
- `MD_PATH` → read `_toc.json`, concatenate files
- `PDF_PATH` → `docs/textbook/BRIEFR_TEXTBOOK.pdf`
- Add `@page` CSS: chapter breaks `h1 { page-break-before: always; }` except first

- [ ] **Step 2: Implement Mermaid rendering**

Reuse Playwright + mermaid.js injection from SYSTEM_DESIGN script pattern.

- [ ] **Step 3: Run dry build with front matter only**

```bash
cd /agent/repos/briefr/frontend && npm run textbook:pdf
```

Expected: PDF created with title page (may be short until chapters land).

- [ ] **Step 4: Add `docs/textbook/*.pdf` to `.gitignore` if not already**

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_briefr_textbook_pdf.mjs frontend/package.json .gitignore
git commit -m "docs: add BRIEFR textbook PDF generator script"
```

---

### Task 3: Part I — Foundations (Chapters 1–4)

**Files:**
- Create: `docs/textbook/part-01-foundations/ch01-*.md` through `ch04-*.md`

**Interfaces:**
- Consumes: `docs/PRODUCT.md`, `docs/HOW_IT_WORKS.md`, `feeds/kev.py`, `feeds/epss.py`, `detection/`, `correlation/`
- Produces: ~4,000–6,000 words/part; each chapter ends with review questions

- [ ] **Step 1: Write Chapter 1** (problem framing; no BRIEFR-specific code depth yet)

- [ ] **Step 2: Write Chapter 2** (KEV/EPSS/PoC; cite `scheduler.py` job IDs)

- [ ] **Step 3: Write Chapter 3** (ATT&CK/Sigma/DetectionContext intro)

- [ ] **Step 4: Write Chapter 4** (IOC/pulse/campaign/evidence concepts tied to `correlation/`)

- [ ] **Step 5: Run PDF build; verify Part I renders**

```bash
cd /agent/repos/briefr/frontend && npm run textbook:pdf
```

- [ ] **Step 6: Commit**

```bash
git add docs/textbook/part-01-foundations/
git commit -m "docs(textbook): Part I foundations chapters 1-4"
```

---

### Task 4: Part II — Platform architecture (Chapters 5–7)

**Files:**
- Create: `part-02-architecture/ch05-*.md` through `ch07-*.md`

- [ ] **Step 1: Chapter 5** — four layers, ADR-001 schema split, mermaid diagram from `docs/diagrams/architecture.mermaid`

- [ ] **Step 2: Chapter 6** — full scheduler overview; job catalog table (abbreviated; full in Appendix A)

- [ ] **Step 3: Chapter 7** — resilient_client, api_queue, caches

- [ ] **Step 4: PDF smoke build + commit**

```bash
git commit -m "docs(textbook): Part II architecture chapters 5-7"
```

---

### Task 5: Part III — Ingestion (Chapters 8–12)

**Files:**
- Create: `part-03-ingestion/ch08-*.md` through `ch12-*.md`

- [ ] **Step 1: Chapter 8** — NVD pipeline step-by-step with `feeds/nvd.py` + `cve_record_v5.py`

- [ ] **Step 2: Chapter 9** — cvelistV5/Vulnrichment additive merge

- [ ] **Step 3: Chapter 10** — TI mirrors + Tranco; document 7-day clamp + ThreatFox URL quirk

- [ ] **Step 4: Chapter 11** — OTX nightly vs continuous; stale serve behavior

- [ ] **Step 5: Chapter 12** — RSS vs publications split; CISA overlap note

- [ ] **Step 6: Include ingest pipeline mermaid from `docs/assets` or `docs/diagrams`**

- [ ] **Step 7: Commit**

```bash
git commit -m "docs(textbook): Part III ingestion chapters 8-12"
```

---

### Task 6: Part IV — Scoring (Chapters 13–16)

**Files:**
- Create: `part-04-scoring/ch13-*.md` through `ch16-*.md`

- [ ] **Step 1: Chapter 13** — Threat formula with weight table from `scoring/threat.py`

- [ ] **Step 2: Chapter 14** — Environment tiers; UNKNOWN vs NO_MATCH (ADR-002 semantic fix)

- [ ] **Step 3: Chapter 15** — OP + SSVC + client-side correlation escalation quirk

- [ ] **Step 4: Chapter 16** — momentum signals

- [ ] **Step 5: Commit**

```bash
git commit -m "docs(textbook): Part IV scoring chapters 13-16"
```

---

### Task 7: Part V — Correlation (Chapters 17–20)

**Files:**
- Create: `part-05-correlation/ch17-*.md` through `ch20-*.md`

- [ ] **Step 1: Chapter 17** — four lanes + priority formula

- [ ] **Step 2: Chapter 18** — IOC graph + hub cap

- [ ] **Step 3: Chapter 19** — campaigns + pulse families

- [ ] **Step 4: Chapter 20** — precompute default off (ADR-004)

- [ ] **Step 5: Embed correlation pipeline diagram**

- [ ] **Step 6: Commit**

```bash
git commit -m "docs(textbook): Part V correlation chapters 17-20"
```

---

### Task 8: Part VI — Detection (Chapters 21–24)

**Files:**
- Create: `part-06-detection/ch21-*.md` through `ch24-*.md`

- [ ] **Step 1: Chapters 21–24** per design spec; flag defaults table for DetectionContext jobs

- [ ] **Step 2: Commit**

```bash
git commit -m "docs(textbook): Part VI detection chapters 21-24"
```

---

### Task 9: Part VII — IOC & investigation (Chapters 25–27)

**Files:**
- Create: `part-07-ioc-investigation/ch25-*.md` through `ch27-*.md`

- [ ] **Step 1: Chapter 25** — distinguish `enrichment/ioc.py` from `ioc/retro_match.py`

- [ ] **Step 2: Chapters 26–27** — watchlist/webhooks; investigation graph caps

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(textbook): Part VII IOC and investigation chapters 25-27"
```

---

### Task 10: Part VIII — LLM & retrieval (Chapters 28–30)

**Files:**
- Create: `part-08-llm-retrieval/ch28-*.md` through `ch30-*.md`

- [ ] **Step 1: Chapter 28** — failover chain from `ai/model_catalog.py` (not stale SYSTEM_DESIGN Anthropic chain)

- [ ] **Step 2: Chapters 29–30** — workloads + embeddings

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(textbook): Part VIII LLM and retrieval chapters 28-30"
```

---

### Task 11: Part IX — Surfaces (Chapters 31–34)

**Files:**
- Create: `part-09-surfaces/ch31-*.md` through `ch34-*.md`

- [ ] **Step 1: Chapters 31–34** — frontend paths + corresponding API routes

- [ ] **Step 2: Commit**

```bash
git commit -m "docs(textbook): Part IX analyst and admin surfaces chapters 31-34"
```

---

### Task 12: Part X — Operations (Chapters 35–37)

**Files:**
- Create: `part-10-operations/ch35-*.md` through `ch37-*.md`

- [ ] **Step 1: Chapter 36** — honest shipped/planned inventory from PRODUCT_STATUS

- [ ] **Step 2: Chapter 37** — five guided code traces with file paths

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(textbook): Part X operations chapters 35-37"
```

---

### Task 13: Appendices

**Files:**
- Create: `docs/textbook/appendices/appendix-a-*.md` through `appendix-d-*.md`

- [ ] **Step 1: Appendix A** — generate scheduler catalog from `scheduler.py` + `_JOB_RUN_MAP` (verify against code)

- [ ] **Step 2: Appendix B** — route table from `docs/API_REFERENCE.md` cross-checked with `routers/`

- [ ] **Step 3: Appendices C–D** — ADR summaries + env var flags

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(textbook): appendices A-D"
```

---

### Task 14: Final PDF, self-review, and delivery

**Files:**
- Modify: any chapters failing placeholder scan
- Output: `docs/textbook/BRIEFR_TEXTBOOK.pdf`

- [ ] **Step 1: Self-review checklist**

  - Spec coverage: every PRODUCT_STATUS major area maps to a chapter
  - Placeholder scan: no TBD/TODO in final text
  - Type/name consistency: job IDs, env vars, file paths match code
  - LLM chain matches `model_catalog.py` (not old docs)

- [ ] **Step 2: Full PDF build**

```bash
cd /agent/repos/briefr/frontend && npm run textbook:pdf
```

Expected: multi-chapter PDF with rendered Mermaid, page breaks, review questions visible.

- [ ] **Step 3: Spot-check PDF** (page count, TOC links if generated, code blocks wrap)

- [ ] **Step 4: Final commit + push**

```bash
git add docs/textbook/ docs/superpowers/
git commit -m "docs: complete BRIEFR textbook source and PDF build"
git push -u origin cursor/briefr-textbook-pdf-8647
```

- [ ] **Step 5: Open draft PR** (documentation-only; no PRODUCT_STATUS change unless user requests)

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Dual audience | All chapter tasks |
| What/Why/How/Where/When template | Task 3+ |
| Code-grounded (not generic CVE tool) | Tasks 5–12 cite real modules |
| Quirks/half-finished | Ch 6, 15, 20, 36 |
| Review questions per chapter | Task 3+ |
| Mermaid/ASCII diagrams | Tasks 4, 5, 7 |
| PDF-ready output | Task 2, 14 |
| Appendices | Task 13 |

No placeholders in plan steps — all paths and commands are concrete.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-20-briefr-textbook-plan.md`.

**Waiting on user:** Confirm or revise the **Proposed table of contents** in the design spec before Task 3 (full chapter authoring).

**Two execution options after TOC approval:**

1. **Subagent-Driven (recommended)** — one subagent per part (10 parts), review between parts
2. **Inline Execution** — batch parts with checkpoints in this session

Which approach do you prefer after you approve the outline?
