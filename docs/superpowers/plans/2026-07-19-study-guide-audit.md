# Study Guide Audit Automation — Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate a thorough completeness audit of `docs/STUDY_GUIDE.html` (inventory + gaps + coverage skeleton) and publish curated analysis (corrected TOC, interview scores, stale claims) ready for the shell sub-project.

**Architecture:** A Python CLI walks scoped repo paths, extracts path/chapter mentions from the study guide HTML, joins them into a matrix, and writes regenerable Markdown/JSON under `docs/planning/specs/study-guide-audit/`. A deep agent pass then fills curated docs without being overwritten by default re-runs.

**Tech Stack:** Python 3.12 stdlib only for the auditor; pytest for unit tests; existing `docs/STUDY_GUIDE.html` + `docs/PRODUCT_STATUS.md` as inputs.

## Global Constraints

- Inventory scope: `backend/` (exclude `tests/`, `.venv`, `__pycache__`), `frontend/src/`, `deploy/`; tests only as aggregate.
- Runtime truth: code > `PRODUCT_STATUS.md` > study guide.
- No product feature code changes; no HTML shell redesign in this plan.
- Regenerable outputs must not clobber curated files unless `--write-curated` (unused in default path).
- Commit message style: imperative, focused.

## File map

| Path | Role |
|------|------|
| `scripts/audit_study_guide.py` | CLI auditor |
| `backend/tests/test_audit_study_guide.py` | Unit tests (path normalize, mention extract, status join) |
| `docs/planning/specs/study-guide-audit/*` | Reports + curated analysis |
| `docs/superpowers/specs/2026-07-19-study-guide-audit-design.md` | Design (already written) |
| `docs/HANDOVER.md` | Note audit artifact location for next shell work |
| `docs/LEARNING_PATH.md` | One-line pointer to audit folder (optional, minimal) |

---

### Task 1: Auditor core + tests

**Files:** `scripts/audit_study_guide.py`, `backend/tests/test_audit_study_guide.py`

- [ ] Write failing tests for: inventory path filtering, HTML mention extraction, orphan detection, status classification (`covered`/`weak`/`gap`/`orphan_mention`).
- [ ] Implement inventory walker + HTML parser (regex/HTMLParser; no new deps).
- [ ] Implement join + report writers (`inventory.json`, `inventory.md`, `gaps.md`, `coverage-skeleton.md`, `summary.md`).
- [ ] Run pytest on the new test file; fix until green.
- [ ] Commit.

### Task 2: Run auditor on the real repo

- [ ] Run `python scripts/audit_study_guide.py` from repo root.
- [ ] Spot-check summary counts; fix false positives that mark whole trees covered from a single directory chip if needed.
- [ ] Commit generated regenerable reports.

### Task 3: Deep curated analysis

- [ ] Fill `STALE_CLAIMS.md` with verified mismatches (RCA one-liner each).
- [ ] Fill `INTERVIEW_COVERAGE.md` for all current TOC chapters.
- [ ] Fill `CORRECTED_TOC.md` proposing adds/splits for gaps (especially recent PRODUCT_STATUS items: retrieval health, embeddings, operator settings, etc.).
- [ ] Write `README.md` with re-run instructions.
- [ ] Commit.

### Task 4: Docs pointers + verify + PR

- [ ] Append HANDOVER entry pointing at the audit folder and next shell sub-project.
- [ ] Run `./scripts/verify-local.sh` (or targeted pytest + note if full gate blocked).
- [ ] Push branch `cursor/study-guide-audit-9180`, open PR, wait for Gemini, disposition comments, merge when green.

## Verification

- `cd backend && pytest tests/test_audit_study_guide.py -q`
- `python scripts/audit_study_guide.py` exits 0 and refreshes regenerable files
- Curated docs present and internally consistent with `summary.md` gap themes
