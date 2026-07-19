# PHASE 10 — User · Administrator · Developer · API · Architecture Documentation

*Refreshed against pinned SHA `ff23c18a4925b3b7082a2b1d1600884324d90d02` (workspace
HEAD during refresh: `267f174`). Evidence checked: `LICENSE`, `README.md`,
`docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`, `CONTRIBUTING.md`,
`docs/TROUBLESHOOTING.md`, `docs/index.md`, `docs/ONBOARDING.md`, repo-wide license/version
string search. `graphify query "license API reference version documentation PRODUCT_STATUS"`
was attempted first and failed because the CLI is unavailable in this environment.*

---

## Executive Summary

Documentation remains a **project strength** and has improved since the prior Phase 10 audit. The
two front-door consistency defects are now closed: the active license story has been flipped and
reconciled to **Business Source License 1.1**, and the README no longer frames the product as
"v1.1 beta" while `PRODUCT_STATUS.md` says v1.5.0.

The remaining risks are now mostly **drift prevention and operator/contributor usefulness**:
the API reference is still hand-maintained without a committed OpenAPI contract artifact; version
`1.5.0` is still duplicated across backend, frontend, and docs; troubleshooting is still a compact
symptom table rather than a full self-host support guide; the documentation map is better but still
relies on readers understanding "living truth" vs archive/snapshot freshness; and contributor docs
point at subsystems but do not yet provide task recipes for adding feeds, endpoints, or detection
content.

**Proposed Overall Score: 8.2 / 10** (up from 7.5). No `NEW-A` findings were needed.

---

## Status Table

| Finding | Status | Current disposition |
|---|---|---|
| F10.1 | CLOSED | Active license docs now agree on BSL-1.1; remaining proprietary/AGPL hits are historical/audit context. |
| F10.2 | OPEN | API reference is still prose-first; no committed `docs/openapi.json` or schema drift gate. |
| F10.3 | CLOSED | README now has `## Known limitations` without stale "v1.1 beta" framing. |
| F10.4 | OPEN | Version still appears in `backend/main.py`, `frontend/package.json`, `PRODUCT_STATUS.md`, and API examples. |
| F10.5 | UPDATED | `docs/TROUBLESHOOTING.md` exists and is linked, but remains thin for a self-hosted product. |
| F10.6 | UPDATED | `docs/index.md` and `DOCUMENTATION_PLAN.md` reduce sprawl, but freshness/authority labels are incomplete. |
| F10.7 | UPDATED | `ONBOARDING.md` has a subsystem map; task-oriented "how to extend" recipes are still missing. |

Status meanings: **CLOSED** = no longer a current defect; **UPDATED** = materially improved but
residual issue remains; **OPEN** = still structurally true.

---

## Findings

### F10.2 — Hand-written API reference can drift from code; no committed OpenAPI artifact · Status: OPEN · Priority: HIGH · Architectural
- **Location:** `docs/API_REFERENCE.md` (2,164 lines at refresh); no `docs/openapi.json`; production
  disables runtime OpenAPI via `openapi_url=None` when `BRIEFR_ENV=production`.
- **Current evidence:** `docs/API_REFERENCE.md` documents many current routes and now includes an
  "OpenAPI / Swagger" export recipe, but `Glob("**/openapi.json")` found no committed artifact.
- **Why it matters:** The prose reference is useful, but it is not the machine-readable API contract.
  Integrators and future agents cannot tell whether a route/field changed without running the app and
  manually comparing schema output.
- **Recommended solution:** Export `app.openapi()` in CI to `docs/openapi.json` or a tracked artifact,
  and add a drift gate that fails when route/field changes are not accompanied by API docs updates.
  Keep the prose reference as the human guide, generated or checked against the schema.
- **Acceptance criteria:** A committed or CI-published OpenAPI artifact exists; schema changes fail
  verification unless API docs are updated or intentionally acknowledged.
- **Effort:** Medium. **Type:** Architectural.

### F10.4 — No single source of version truth · Status: OPEN · Priority: MEDIUM · Quick Win
- **Location:** `backend/main.py` (`version="1.5.0"`), `frontend/package.json` (`"version": "1.5.0"`),
  `docs/PRODUCT_STATUS.md` (`v1.5.0`), and `docs/API_REFERENCE.md` version response example.
- **Current evidence:** The stale README framing is fixed, and `/api/version` provides deployed
  version/commit visibility, but release version text is still manually duplicated.
- **Why it matters:** A release bump still depends on coordinated edits across backend metadata,
  frontend metadata, and docs. The prior F10.3 drift shows this class of mismatch is realistic.
- **Recommended solution:** Pick one repository version source (for example `VERSION` or a generated
  build metadata file), make backend/frontend/docs consume or verify it, and add a local/CI check for
  release-version consistency.
- **Acceptance criteria:** One authoritative version source; verification fails when checked-in
  version mentions drift.
- **Effort:** Quick Win. **Type:** Quick Win.

### F10.5 — Troubleshooting/support docs remain thin for self-hosted operation · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** `docs/TROUBLESHOOTING.md` (25 lines), `docs/ONBOARDING.md` troubleshooting section,
  `docs/SELF_HOST.md` link to troubleshooting.
- **Current evidence:** The one-table troubleshooting doc is discoverable and covers common first-run
  issues, while onboarding has a deeper developer/operator troubleshooting table. The standalone
  self-host support path is still too short for production operations.
- **Why it matters:** Self-hosted users need symptom -> likely cause -> exact diagnostic command ->
  safe fix. Today many real operator paths still require jumping to `ONBOARDING.md`, `OPERATIONS.md`,
  admin UI knowledge, or source files.
- **Recommended solution:** Expand `TROUBLESHOOTING.md` into a symptom-indexed runbook for database,
  migration, scheduler, backup/restore, auth/CORS, API key, webhook, feed freshness, request-ID, and
  support-pack workflows. Link exact `briefr-doctor.sh`, admin diagnostics, health, and log commands.
- **Acceptance criteria:** Troubleshooting covers the top operator failure modes with concrete
  commands and safe fixes; README/SELF_HOST/Admin error states point to it.
- **Effort:** Quick Win-Medium. **Type:** Quick Win.

### F10.6 — Documentation sprawl and freshness/authority signaling remain imperfect · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `docs/` (20 top-level Markdown files, 128 Markdown files total), `docs/index.md`,
  `docs/DOCUMENTATION_PLAN.md`, `docs/archive/snapshots/`, `docs/PRODUCT_STATUS.md`.
- **Current evidence:** `docs/index.md` now provides a short path picker, `DOCUMENTATION_PLAN.md`
  defines reader-facing vs deep/reference docs, and archive/planning buckets are documented. However,
  deep docs and snapshots still need readers to know that `PRODUCT_STATUS.md` wins and that snapshots
  may lag; some active docs still link snapshots as reference material.
- **Why it matters:** The doc set is broad enough that a new user or contributor can still land on a
  stale snapshot or deep reference without obvious freshness/authority context.
- **Recommended solution:** Add lightweight authority/freshness labels to `docs/index.md` or a small
  metadata table: living truth, reader guide, deep reference, generated/snapshot, historical archive.
  Where active docs link snapshots, label them as historical or replace with current generated sources.
- **Acceptance criteria:** Every promoted doc has a visible authority/freshness class; active entry
  docs no longer send readers to stale snapshots without a warning; stale/freshness checks are scripted.
- **Effort:** Medium. **Type:** Architectural.

### F10.7 — Developer onboarding still lacks task-oriented extension recipes · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `CONTRIBUTING.md`, `docs/ONBOARDING.md`, `docs/LEARNING_PATH.md`,
  `docs/STUDY_GUIDE.html` / `docs/study-guide/`.
- **Current evidence:** Contributor setup, danger-zone pointers, subsystem maps, learning modules, and
  the study guide are strong. The missing piece is still recipe-style guidance: "add a feed source",
  "add an API endpoint", "add a detection template/generator", "add a scheduler job safely".
- **Why it matters:** Task recipes prevent inconsistent extensions and encode project-specific
  invariants: Postgres-native SQL, scheduler lock mapping, request-path limits, redaction rules,
  OpenAPI/API_REFERENCE updates, and UI design-system constraints.
- **Recommended solution:** Add short recipe sections inside `ONBOARDING.md` (rather than new top-level
  docs) for the common extension points, each linking the relevant source files, tests, danger zones,
  and docs that must be updated.
- **Acceptance criteria:** Developer docs include recipes for at least feed source, endpoint, scheduler
  job, and detection content changes; each includes tests/docs checklist.
- **Effort:** Quick Win-Medium. **Type:** Quick Win.

## Overall Score: **8.2 / 10**

| Sub-audit | Score |
|---|---:|
| User Documentation | 8 / 10 |
| Administrator Documentation | 8 / 10 |
| Developer Documentation | 8 / 10 |
| API Documentation | 7.5 / 10 |
| Architecture Documentation | 8.5 / 10 |

## Strengths
- Public-facing license and README version framing are now consistent.
- `docs/index.md` gives a short reader path; `DOCUMENTATION_PLAN.md` defines the doc structure.
- API reference is content-rich and current enough to mention auth/session, request IDs, rate limits,
  wallboard, retrieval, admin, security architecture, and OpenAPI export.
- `PRODUCT_STATUS.md` remains a strong living-truth page, and the study guide/learning path materially
  improve developer understanding.

## Remaining Weaknesses
- API contract drift prevention is still missing (F10.2).
- Version strings are still manually duplicated (F10.4).
- Troubleshooting is discoverable but not yet a full self-host operator runbook (F10.5).
- Freshness/authority labels for deep docs and snapshots remain incomplete (F10.6).
- Contributor docs orient readers but do not yet teach safe extension workflows (F10.7).

## Immediate Action Items
1. Export/commit or CI-publish OpenAPI and add a schema/doc drift gate (F10.2).
2. Add a release-version consistency check and single source of truth (F10.4).
3. Expand `TROUBLESHOOTING.md` into an operator-grade symptom runbook (F10.5).

## Production-Readiness Assessment (Phase 10 areas)
**Strong and improving — 8.2/10.** The prior legal/license blocker and README version mismatch are
resolved in current active docs. The next maturity step is automation: generated or verified API
contract artifacts, version consistency checks, and freshness labels so the doc set stays reliable as
the product continues to move.

---

## Resolved since last audit

#### F10.1 — Contradictory license statements · Status: CLOSED
- **Previous finding:** Active docs mixed AGPL-3.0-or-later with a proprietary/confidential API
  reference header.
- **Current evidence:** `LICENSE` is Business Source License 1.1; `README.md`, `CONTRIBUTING.md`,
  `docs/API_REFERENCE.md`, `docs/SYSTEM_DESIGN.md`, `docs/ONBOARDING.md`, and
  `docs/PRODUCT_STATUS.md` all point to BSL-1.1 / `BUSL-1.1` for active current docs. `backend/main.py`
  also exposes BSL metadata in FastAPI. Repo-wide search still finds old "proprietary/confidential"
  strings only in archive/snapshot/session docs and this audit history, plus canonical "All Rights
  Reserved" text inside the BSL license itself.
- **Disposition:** Closed for active documentation. Remaining historical/audit mentions should not be
  edited as part of this Phase 10 docs-only refresh.

#### F10.3 — Stale README "v1.1 beta" framing · Status: CLOSED
- **Previous finding:** README said "Known limitations (v1.1 beta)" while the product was v1.5.0.
- **Current evidence:** At pinned SHA, README contains `## Known limitations` with no "v1.1 beta"
  heading; `PRODUCT_STATUS.md`, `backend/main.py`, and `frontend/package.json` all say `1.5.0`.
- **Disposition:** Closed. The broader version-SSOT issue remains a separate open finding.
