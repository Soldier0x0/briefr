# Study Guide Completeness Audit — Design

**Date:** 2026-07-19  
**Status:** Approved for implementation (audit sub-project only)  
**Follow-ons (out of scope here):** multi-file responsive shell; Part-by-Part deep rewrites

## 1. Purpose

Produce a **source-of-truth audit** of `docs/STUDY_GUIDE.html` so later shell redesign and chapter rewrites are built on a correct, complete outline — not a prettier wrapper around gaps or stale claims.

Quality bar: thorough, clear, detailed; better than the current guide’s implicit “we covered everything” assumption. Prefer completeness and accuracy over speed.

## 2. Goals and non-goals

### Goals (this sub-project)

1. **Corrected chapter map** — proposed TOC for the eventual multi-file book (merge/split/add/remove with rationale).
2. **File-level inventory** — every in-scope runtime/deploy file mapped to a chapter, a gap, or explicit out-of-scope.
3. **Interview-ready coverage** — each current (and proposed) chapter scored for Concept · Why · How · Self-check.
4. **Stale-claim list** — places the guide disagrees with code or `docs/PRODUCT_STATUS.md` (runtime truth wins).
5. **Automation** — a repeatable script that regenerates the mechanical matrix so future audits are cheap.

### Non-goals

- New HTML shell / responsive redesign.
- Full chapter prose rewrites.
- Product code changes.
- Mapping every `backend/tests/**` file (tests covered via a Testing strategy chapter).
- Merging shell or rewrite work into this PR.

## 3. Inventory scope

### In scope (file-level)

| Area | Include |
|------|---------|
| `backend/` | Runtime Python packages and modules (feeds, routers, db, scoring, …) |
| `frontend/src/` | App source (pages, components, hooks, utils, styles, …) |
| `deploy/` | Ops/deploy surface operators must understand |
| Root load-bearing scripts | e.g. `scripts/verify-local.sh`, seed/postgres helpers named by the guide or PRODUCT_STATUS |

### Explicitly out of scope (still listed once as categories)

- `node_modules/`, `backend/.venv/`, build artifacts, lockfiles, `__pycache__`
- Individual test files under `backend/tests/` (aggregate → Testing strategy)
- Generated snapshots / archive docs under `docs/archive/` (reference only)
- Vendor/minified assets

### Truth order when sources disagree

1. Running code on `main`
2. `docs/PRODUCT_STATUS.md`
3. `docs/SYSTEM_DESIGN.md` / ADRs
4. Current `STUDY_GUIDE.html` prose

## 4. Architecture of the audit system

```
┌─────────────────────┐     ┌──────────────────────────┐
│ STUDY_GUIDE.html    │────▶│ Mention extractor        │
│ (TOC + file chips)  │     │ (ids, hrefs, chips, paths)│
└─────────────────────┘     └────────────┬─────────────┘
                                         │
┌─────────────────────┐     ┌────────────▼─────────────┐
│ backend/ frontend/  │────▶│ Filesystem inventory     │
│ deploy/ (scoped)    │     │ (normalize paths)        │
└─────────────────────┘     └────────────┬─────────────┘
                                         │
┌─────────────────────┐     ┌────────────▼─────────────┐
│ PRODUCT_STATUS.md   │────▶│ Stale / shipped overlay  │
│ + recent git signals│     │ (heuristic flags)        │
└─────────────────────┘     └────────────┬─────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │ Matrix + reports    │
                              │ JSON + Markdown     │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │ Agent deep pass     │
                              │ coverage scores,    │
                              │ corrected TOC, RCA  │
                              │ on flagged claims   │
                              └─────────────────────┘
```

### Automation unit

- **Script:** `scripts/audit_study_guide.py`
- **Inputs:** repo tree + `docs/STUDY_GUIDE.html` (+ optional `--product-status` path)
- **Outputs (regenerable):** under `docs/planning/specs/study-guide-audit/`
  - `inventory.json` — machine-readable matrix
  - `inventory.md` — human table (file → status → chapter/evidence)
  - `gaps.md` — files with no chapter ownership
  - `coverage-skeleton.md` — one row per TOC chapter for interview scoring
  - `summary.md` — counts and top gaps
- **Curated (hand-maintained after deep pass, same folder):**
  - `CORRECTED_TOC.md` — proposed book outline
  - `INTERVIEW_COVERAGE.md` — Concept/Why/How/Self-check scores + notes
  - `STALE_CLAIMS.md` — verified mismatches with RCA one-liners
  - `README.md` — how to re-run the auditor

Regenerable files must be clearly marked so a future `audit_study_guide.py` run does not clobber curated analysis without an explicit flag.

## 5. Matching rules (mechanical)

A disk file is **mentioned** if any of:

1. Exact or suffix path appears in guide text/chips (e.g. `feeds/nvd.py`, `backend/feeds/nvd.py`).
2. Module directory is named in a chapter’s file-chip list and the file is the package’s primary module (`__init__.py` alone does not count as coverage for siblings).
3. Router/page basename is discussed in the chapter body with an unambiguous file chip elsewhere in the guide.

Statuses per file:

| Status | Meaning |
|--------|---------|
| `covered` | Mentioned and owned by ≥1 chapter |
| `weak` | Directory mentioned but this file never named; or only glossary-level |
| `gap` | In-scope file with no ownership |
| `out_of_scope` | Explicit skip category |
| `orphan_mention` | Guide names a path that does not exist on disk (stale) |

## 6. Interview-ready rubric

For each chapter (current + proposed):

| Dimension | Pass means |
|-----------|------------|
| **Concept** | Reader can define the subsystem without jargon soup |
| **Why** | At least one BRIEFR-specific design rationale (not generic best practice) |
| **How** | Points at real files/functions and a traceable path |
| **Self-check** | ≥2 questions that fail if the reader only skimmed |

Scores: `strong` · `adequate` · `weak` · `missing`.  
A chapter is **interview-ready** only if all four are `adequate` or better and How cites paths that still exist.

## 7. Process

1. Implement and test `audit_study_guide.py`.
2. Run it; commit regenerable reports.
3. Deep pass: walk gaps against code + PRODUCT_STATUS; fill curated docs; RCA on stale claims (verify on HEAD, state why, propose guide fix — do not silently change product code).
4. Propose corrected TOC reflecting gaps (new chapters as stubs in the outline only).
5. Local verify (script unit tests + dry-run).
6. PR → address Gemini/review → merge when green.

## 8. Success criteria

- [ ] Every in-scope file appears exactly once in the inventory with a status.
- [ ] `gaps.md` is empty of “unknown” rows — every gap has a recommended chapter home or out-of-scope rationale.
- [ ] Orphan mentions in the guide are listed with RCA.
- [ ] Corrected TOC is reviewable as the outline for the shell sub-project.
- [ ] Re-running the script without `--write-curated` does not destroy curated analysis.
- [ ] `./scripts/verify-local.sh` still green (docs/scripts only; no product regress).

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Heuristic false “covered” | Prefer exact path chips; mark directory-only as `weak` |
| Audit bitrot | Script + regenerable outputs; README run instructions |
| Scope creep into rewrites | Hard non-goal; outline stubs only |
| PRODUCT_STATUS lag | Prefer code when status doc is silent; flag both when they disagree |

## 10. Follow-on sub-projects (not this PR)

1. **Shell** — multi-file static book (Part hubs + chapter pages), clean + responsive, migrate text under corrected TOC.
2. **Content Parts** — deep rewrite + fill gaps Part-by-Part with interview-ready bar.
