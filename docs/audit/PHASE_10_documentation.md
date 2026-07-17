# PHASE 10 — User · Administrator · Developer · API · Architecture Documentation

*Reviewed at commit `61c686f`. `README.md`, `docs/*` (20 top-level, 85 total), `docs/decisions/`
(6 ADRs), `docs/diagrams/` (10 mermaid), `docs/API_REFERENCE.md` (1,982 LOC), `CONTRIBUTING.md`.*

---

## Executive Summary

Documentation is a **genuine strength and unusually thorough** for a project this size. There are
**6 ADRs** with a template (real architecture-decision records: schema split, operational priority,
UI design system, correlation precompute, component-library strategy, encrypted settings), **10
mermaid diagrams** (architecture, schema, startup, and per-flow diagrams for feed/detail/IOC/NVD/
PDF/error handling), a **1,982-line API reference** that documents auth, request-IDs, rate limits,
multi-worker guidance, and error shapes, a 551-line `SYSTEM_DESIGN.md`, a 414-line README with
screenshots/features/data-sources/env-vars/keyboard-shortcuts, a `CONTRIBUTING.md`, an
`AGENT_METHODOLOGY.md`, and a living `PRODUCT_STATUS.md` explicitly designated as the source of
truth with a documented precedence rule.

The weaknesses are **consistency, freshness, and generation** — the classic failure modes of
hand-maintained docs at scale: (1) a **direct license contradiction** — `PRODUCT_STATUS.md`,
`README.md`, and `LICENSE` say **AGPL-3.0-or-later**, but `API_REFERENCE.md`'s header says
**"All rights reserved. Proprietary and confidential."**; (2) **stale version framing** — the
README's "Known limitations (**v1.1 beta**)" heading contradicts the actual **v1.5.0** release in
`PRODUCT_STATUS.md`/`main.py`/`package.json`; (3) the API reference is **hand-written, not generated**
from OpenAPI, so it will drift from the 130 real routes (Phase 2 F2.10 — no exported `openapi.json`);
(4) **doc sprawl** (Phase 1 F1.7) with overlapping user docs and a precedence-based truth model that
readers must know to trust anything; (5) **thin troubleshooting** (`TROUBLESHOOTING.md` is 24 lines)
for a self-hosted product; (6) **no single version source** (1.5.0 is duplicated across three files).

**Overall Score: 7.5 / 10.**

---

## Findings

### F10.1 — Contradictory license statements (AGPL vs "proprietary and confidential") · Priority: HIGH · Quick Win
- **Location:** `docs/API_REFERENCE.md:3` — "Copyright © 2026 Sai Harsha Vardhan. **All rights
  reserved. Proprietary and confidential.**" vs `docs/PRODUCT_STATUS.md:13`, `README.md`, `LICENSE`,
  `CONTRIBUTING.md`, and SPDX headers — all **AGPL-3.0-or-later**.
- **Description:** Two authoritative docs make **mutually exclusive** licensing claims. AGPL is a
  copyleft open-source license; "proprietary and confidential, all rights reserved" is its opposite.
  A downstream user/self-hoster reading the API reference would reasonably conclude the software is
  proprietary and that redistribution is forbidden.
- **Why it matters:** Licensing is legally load-bearing. A contradiction creates real ambiguity about
  redistribution/modification rights, undermines the AGPL intent (which the project appears to have
  chosen deliberately), and is a red flag in any enterprise legal review or OSS compliance scan.
- **Evidence:** `head -15 docs/API_REFERENCE.md` shows the proprietary header; `PRODUCT_STATUS.md`,
  `LICENSE`, README all state AGPL.
- **Risk:** Legal ambiguity; loss of AGPL guarantees; enterprise procurement/legal blocker.
- **Recommended solution:** Replace the `API_REFERENCE.md` header with the AGPL-3.0-or-later SPDX
  line used elsewhere (`SPDX-License-Identifier: AGPL-3.0-or-later`, Copyright © 2026 Sai Harsha
  Vardhan). Grep the whole repo for "proprietary"/"all rights reserved"/"confidential" and fix any
  other stragglers; add a CI check that no doc contains a license string conflicting with `LICENSE`.
- **Acceptance criteria:** Every doc states AGPL-3.0-or-later (or references `LICENSE`); a CI grep
  fails on "proprietary"/"all rights reserved" outside quoted third-party notices.
- **Effort:** Quick Win. **Type:** Quick Win.

### F10.2 — Hand-written API reference will drift from code; no generated OpenAPI · Priority: HIGH · Architectural
- **Location:** `docs/API_REFERENCE.md` (1,982 LOC, prose, ~172 endpoint mentions vs 130 actual
  routes); no exported `openapi.json` (Phase 2 F2.10); OpenAPI disabled in prod.
- **Description:** The API reference is excellent in content but manually maintained, so it inevitably
  drifts from the real router definitions (params renamed, response fields added/removed, new routes
  undocumented). There's no automated link between the docs and the FastAPI schema.
- **Why it matters:** An API reference that silently disagrees with the running API is worse than none
  for integrators; for a product courting external API consumers, contract accuracy is essential.
- **Recommended solution:** Export `openapi.json` in CI (Phase 2 F2.10) as the machine-readable source
  of truth; either (a) generate the human reference (or an appendix) from it, or (b) add a CI check
  that every route in `app.routes` is mentioned in `API_REFERENCE.md` and flags undocumented routes.
  Adopt the `/api/v1` versioning (F2.3) and document the version policy here.
- **Acceptance criteria:** A committed `openapi.json`; CI fails when a route is undocumented or the
  exported schema changes without a doc update.
- **Effort:** Medium. **Type:** Architectural.

### F10.3 — Stale version framing in README ("v1.1 beta") vs v1.5.0 release · Priority: MEDIUM · Quick Win
- **Location:** `README.md:389` "## Known limitations (v1.1 beta)"; `README.md:406` beta-flip note;
  actual `PRODUCT_STATUS.md:12` "v1.5.0", `main.py:161` `version="1.5.0"`, `package.json:3` `1.5.0`.
- **Description:** The README still frames the product as "v1.1 beta" in its limitations/known-issues
  section while the shipped release is v1.5.0. First-time readers (the README is the front door) get
  an outdated maturity signal and possibly stale limitations.
- **Why it matters:** The README is the primary public impression; a stale version/beta framing
  misrepresents maturity and erodes confidence.
- **Recommended solution:** Update the README's version/limitations framing to v1.5.0 and reconcile the
  "known limitations" list with the current `PRODUCT_STATUS.md`. Cross-reference PRODUCT_STATUS as the
  living truth.
- **Acceptance criteria:** README states the current version; limitations match PRODUCT_STATUS.
- **Effort:** Quick Win. **Type:** Quick Win.

### F10.4 — No single source of version truth (1.5.0 duplicated across ≥3 files) · Priority: MEDIUM · Quick Win
- **Location:** `backend/main.py:161` (`version="1.5.0"`), `frontend/package.json:3` (`1.5.0`),
  `docs/PRODUCT_STATUS.md:12` (`v1.5.0`), plus README references.
- **Description:** The version string is hand-duplicated in multiple places with no single source, so
  a release bump requires editing several files and they can drift (as F10.3 shows they already have).
- **Recommended solution:** Pick a single source (e.g. a `VERSION` file or `package.json`), have the
  backend read it (or inject at build), and reference it in docs via a generated snippet; add a CI
  check that all version strings match.
- **Acceptance criteria:** One authoritative version; CI fails on mismatch.
- **Effort:** Quick Win. **Type:** Quick Win.

### F10.5 — Thin troubleshooting/support documentation for a self-hosted product · Priority: MEDIUM · Quick Win
- **Location:** `docs/TROUBLESHOOTING.md` (24 lines); `deploy/briefr-doctor.sh` exists (a real
  diagnostic) but isn't matched by a comprehensive troubleshooting guide.
- **Description:** For software self-hosted by operators without vendor support, a 24-line
  troubleshooting doc is thin. Common failure modes (DB connection, migration failures, scheduler not
  running, LLM provider errors, backup/restore issues, "database is locked" — which CLAUDE.md itself
  warns about) deserve documented symptoms→causes→fixes.
- **Why it matters:** Self-hosted support burden falls on docs; thin troubleshooting drives support
  requests and abandonment.
- **Recommended solution:** Expand `TROUBLESHOOTING.md` into a symptom-indexed guide covering the
  top failure modes, each with the exact `briefr-doctor.sh`/log-grep commands (using request-IDs) and
  fixes. Link from README and error states (the UI already surfaces `ref: <request-id>`).
- **Acceptance criteria:** Troubleshooting covers the top ~15 operator failure modes with commands
  and fixes; linked from README/error UI.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

### F10.6 — Documentation sprawl + precedence-based truth model (carries F1.7) · Priority: MEDIUM · Architectural
- **Location:** `docs/` (20 top-level, 85 total); overlapping user docs (`USE`, `HOW_IT_WORKS`,
  `LEARNING_PATH`, `ONBOARDING`); `PRODUCT_STATUS.md` designated "wins when others disagree";
  snapshots "may lag"; `DOCUMENTATION_PLAN.md` governs structure.
- **Description:** The set is large and curated but relies on readers knowing the precedence rule
  ("PRODUCT_STATUS wins", "snapshots lag") to trust any given page. Overlapping user-facing docs
  fragment the "how do I use this" journey.
- **Why it matters:** A precedence-based truth model is fragile; new contributors and users won't
  know it, so they'll trust a stale page. Consolidation reduces drift surface.
- **Recommended solution:** Make `docs/index.md` an authoritative, labeled map ("authoritative" vs
  "snapshot — may lag", with last-updated dates); consolidate the overlapping user docs into one
  user guide with sections; add a doc-freshness CI check (front-matter `last_verified` date; warn if
  stale). Enforce `DOCUMENTATION_PLAN.md` structure.
- **Acceptance criteria:** `index.md` labels every doc's authority + freshness; user journey lives in
  one consolidated guide; stale docs flagged.
- **Effort:** Medium. **Type:** Architectural.

### F10.7 — Developer onboarding lacks "how to extend" guides (add feed/detection/endpoint) · Priority: LOW · Quick Win
- **Location:** `CONTRIBUTING.md` (setup + PR guidelines), `AGENT_METHODOLOGY.md`, `SYSTEM_DESIGN.md`;
  no task-oriented contributor guides.
- **Description:** Setup and process docs are good, and `SYSTEM_DESIGN.md`/diagrams explain the
  architecture, but there's no "here's how you add a new feed source / detection generator / API
  endpoint / correlation signal" walkthrough — the highest-leverage docs for growing a contributor
  base and keeping new code consistent with the danger-zone rules in CLAUDE.md.
- **Why it matters:** Task-oriented guides are what turn a reader into a contributor and keep
  extensions consistent (dialect-safe SQL, scheduler-lock sync, redaction rules).
- **Recommended solution:** Add short "extending BRIEFR" guides for the common extension points,
  each pointing at the relevant danger-zone rules and a reference PR.
- **Acceptance criteria:** Guides exist for adding a feed, a detection generator, and an endpoint;
  each references the applicable CLAUDE.md danger zone.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

---

## Overall Score: **7.5 / 10**

| Sub-audit | Score |
|---|---|
| User Documentation | 7 / 10 |
| Administrator Documentation | 8 / 10 |
| Developer Documentation | 7.5 / 10 |
| API Documentation | 7 / 10 |
| Architecture Documentation | 8.5 / 10 |

## Strengths
- 6 ADRs + template; 10 mermaid diagrams (architecture/schema/startup/flows) — excellent architecture
  documentation.
- Comprehensive, content-rich API reference (auth, rate limits, request-IDs, multi-worker guidance).
- Living `PRODUCT_STATUS.md` with a stated precedence model; strong admin/ops runbooks (Phase 8);
  `CONTRIBUTING.md` + `AGENT_METHODOLOGY.md`.
- Curated `docs/archive/` discipline; `DOCUMENTATION_PLAN.md` governs structure.

## Weaknesses
- License contradiction AGPL vs proprietary (F10.1) — the standout.
- Hand-maintained API docs drift risk (F10.2); stale README version (F10.3); no single version source
  (F10.4); thin troubleshooting (F10.5); sprawl + precedence-truth (F10.6).

## Immediate Action Items
1. **Fix the license contradiction in `API_REFERENCE.md` (F10.1)** + repo-wide grep.
2. Update README "v1.1 beta" framing to v1.5.0 (F10.3); unify the version source (F10.4).
3. Export `openapi.json` and add an undocumented-route CI check (F10.2, with F2.10).

## Long-Term Recommendations
1. Generate/verify API docs against OpenAPI; adopt `/api/v1` and document the version policy (F10.2).
2. Consolidate user docs; label authority + freshness in `index.md`; add a freshness CI check (F10.6).
3. Expand troubleshooting (F10.5) and add "how to extend" contributor guides (F10.7).

## Production-Readiness Assessment (Phase 10 areas)
**Strong docs, one must-fix — 7.5/10.** Documentation depth (ADRs, diagrams, runbooks, API reference)
already exceeds the bar for a self-hosted product and reflects real care. **The license contradiction
(F10.1) must be fixed before any release** — it's a legal-clarity issue, not a nicety. The
drift-prevention items (F10.2, F10.4, F10.6) are what keep this strong documentation from decaying as
the product evolves; prioritize the OpenAPI export and version unification. Troubleshooting depth
(F10.5) is the main *user-support* gap for self-hosters.
