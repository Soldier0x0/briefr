# Plan: Full documentation library refresh (2026-07-21)

**Branch:** `cursor/docs-library-refresh-af21`  
**Authority:** live codebase + last ~40 merged PRs (#687–#729). Do **not** treat graphify as source of truth.  
**Out of scope:** `docs/archive/**` (immutable), one-off Gemini dumps, inventing features.

## Goal

Bring every living doc (reader guides, deep reference, learn/study-guide, ADRs/design notes where claims drifted, README/community entrypoints) in line with production truth after Waves 1–7, Phase 1 scoring, UX RCA, router splits, and related ships. Then refresh graphify from the updated tree.

## Truth sources (in order)

1. Code: `backend/`, `frontend/`, `deploy/`, `scripts/`
2. `docs/PRODUCT_STATUS.md` (living ops truth — extend, do not contradict)
3. Recent HANDOVER entries + merged PR titles
4. Existing doc format/structure per `DOCUMENTATION_PLAN.md`

## Workstreams

### A — Living reference (P0)

| Doc | Fix |
|-----|-----|
| `SYSTEM_DESIGN.md` | Postgres-first framing; scheduler/job inventory; endpoint map; remove obsolete SQLite decision; ARCH→Security posture; Forge pushContext; hybrid search / drawer bundle / durable jobs / catch-up |
| `README.md` | RSS×5; Recharts; `POST /risk`; FEED/hybrid; screenshots; env flags; no Chart.js |
| `API_REFERENCE.md` | OpenAPI path; integrity dialect-aware; Chart.js→Recharts; fill gaps for catch-up, outbound jobs, retrieval health, metering, stack backfill where thin |
| `OPERATIONS.md` | Last-updated + catch-up / Procrastinate / embeddings ops notes aligned with code |
| `PRODUCT_STATUS.md` | Documentation rollout row; minor primitive inventory tighten if needed |
| `HANDOVER.md` | New entry for this refresh |

### B — Reader + contributor guides (P0)

| Doc | Fix |
|-----|-----|
| `USE.md` | Tabs, drawer IA, FEED hybrid, Forge views, Admin/Scheduler catch-up, shell Back/`?cve=`, wallboard |
| `HOW_IT_WORKS.md` | Scoring OP/SSVC; hybrid retrieval; durable jobs; point primary study path to `study-guide/` |
| `SELF_HOST.md` | Env flags for Procrastinate / embeddings / rate-limit store; Postgres 16+pgvector note |
| `TROUBLESHOOTING.md` | Hybrid search empty, catch-up, durable queue, embeddings, stack backfill |
| `ONBOARDING.md` | LLM multi-provider; extraction defaults; `pg_adapt.py`; UI conventions date; verify-local |
| `LEARNING_PATH.md` | Replace `dialect.py`; Threat/OP/SSVC scoring modules; hybrid/durable/security posture |
| `PRODUCT.md` | Dark-only; drop dual visual-mode |
| `index.md` | Study guide → multi-file book primary |

### C — Design / community (P1)

| Doc | Fix |
|-----|-----|
| `design/design-system.md` | Implemented vs target primitives; dark-only parity |
| `IMAGE_BRIEFS.md` / `assets/README.md` | Reconcile screenshot path claims |
| `DOCUMENTATION_PLAN.md` | Note learn/ + study-guide/ generation workflow if missing |
| `POSTGRES.md` | pgvector / embeddings extension if thin |

### D — Study guide + learn (P0)

1. Edit **source** `docs/STUDY_GUIDE.html` (router package split, admin jobs paths, durable LLM job, catch-up, light-theme inventory removal, path chips).
2. Fix `scripts/build_learn_site.py` relative links (`../../study-guide/pages`).
3. Regenerate: `python scripts/build_study_guide_book.py` then `python scripts/build_learn_site.py`.
4. Refresh `docs/planning/specs/study-guide-audit/STALE_CLAIMS.md` + `gaps.md` after audit script.

### E — Graphify (last)

After all docs committed: `graphify update .` (or project equivalent). Do not use graphify to decide doc content.

### F — PR / Gemini

Open draft PR; triage Gemini review comments; validate real vs noise; fix real doc errors before merge.

## Explicit non-edits

- `docs/archive/**`
- Historical beta specs
- Specs that are intentional design history (unless a claim says “current” and is wrong — then correct or mark shipped)

## Verification

- Spot-check: no `dialect.py`, Chart.js-as-runtime, RSS×6, `GET /risk`, SQLite-as-prod in living docs
- Regenerate study-guide + learn without error
- `python scripts/audit_study_guide.py` gap count improved or documented
- Link sanity on index → USE / SELF_HOST / study-guide
