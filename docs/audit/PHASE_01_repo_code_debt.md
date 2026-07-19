# PHASE 1 — Repository Organization, Code Quality & Technical Debt

*Reviewed at pinned refresh commit `ff23c18a4925b3b7082a2b1d1600884324d90d02` for the 2026-07-19 delta refresh. Prior baseline: `61c686f` on `claude/engineering-audit-dzib4j`. Scope: repository structure, tooling, code-quality signals, and accumulated debt. Current branch HEAD is `267f174`; source-code paths reviewed below are unchanged from the pinned SHA, with only audit coordination docs differing since the pin.*

> **How to use this doc (for Cursor Composer 2.5):** Each finding carries a concrete Location, refreshed Evidence, a Recommended Solution, and Acceptance Criteria. Execute Quick Wins first (they unblock guardrails), then Architectural changes. Do not merge behavioral changes with formatting-only changes.

---

## Executive Summary

BRIEFR remains a disciplined codebase for its stage: backend concerns are mostly split into domain packages, the backend test corpus is substantial, Postgres and SQLite are both exercised in CI, and docs now have an even stronger archive/product-status discipline. The 2026-07-19 refresh did not find repo-wide chaos.

The thermo-nuclear bar still exposes several structural debt centers that should be treated before the codebase doubles: missing automated lint/format/type gates; god-files that are now larger than the prior audit (`admin.py` 2,746 LOC/72 routes, `scheduler.py` 2,600 LOC, `App.jsx` 1,112 LOC); dual-maintained risk scoring and DB dialect surfaces; and frontend tests that exist but are not CI-gated. Some counts improved slightly (swallowed broad exceptions are down from 28 to 27), but no Phase 1 prior finding is fully closed.

**Overall Score: 7.2 / 10.** Prior score was 7.5. The drop reflects growth in the largest files and the DB dialect duplication count, not a collapse in engineering quality.

### Refresh classification

| ID | Status | Verdict |
|---|---|---|
| F1.1 | OPEN | Still no lint/format/type-check gate or config files. |
| F1.2 | UPDATED | Admin router grew to 2,746 LOC and 72 route decorators; CVE router remains 1,996 LOC. |
| F1.3 | OPEN | Backend and frontend still carry parallel risk constants and logic. |
| F1.4 | UPDATED | `_SQLITE`/`_PG` markers increased to 496 across 19 `backend/db` files. |
| F1.5 | UPDATED | Large frontend files persist: `IOCLookup.jsx` 1,408 LOC, `App.jsx` 1,112 LOC, drawer files near/over 1k. |
| F1.6 | UPDATED | Silent broad catches decreased by one but still total 27. |
| F1.7 | UPDATED | Docs total grew to 128 markdown files; top-level docs remain 20. |
| F1.8 | OPEN | `AGENTS.md` and `CLAUDE.md` remain separate rulebooks. |
| F1.9 | OPEN | Settings/config ownership remains split across five modules. |
| F1.10 | OPEN | `backend/correlation/copy.py` still exists and is imported by four modules. |
| F1.11 | UPDATED | FE tests grew to 56 files but `test:unit` is still not wired into CI; five production `console.error` calls remain. |
| F1.12 | NEW | Scheduler god-file debt now has a final Phase 1 finding ID. |

---

## Findings

### F1.1 — No linter/formatter/type-checker; no style gate in CI · Status: OPEN · Priority: HIGH · Architectural
- **Location:** repo-wide. Absent: `backend/pyproject.toml`, `.ruff.toml`, `ruff.toml`, `.flake8`, `frontend/eslint.config.*`, `prettier.config.*`, `.prettierrc*`. `frontend/package.json` has `build`, `audit:ci`, and `test:unit`, but no lint/format scripts.
- **Description:** No automated lint, formatting, or static typing gate exists for Python or JavaScript. Safety conventions in `CLAUDE.md` and design-system constraints are still primarily review-enforced.
- **Why it matters:** A multi-year, agent-maintained codebase needs executable style and safety memory. Without it, every contributor must rediscover import order, broad-catch, logging, token, and UI rules manually.
- **Evidence:** `Glob **/{pyproject.toml,.ruff.toml,ruff.toml,.flake8,eslint.config.*,prettier.config.*,.prettierrc*}` returned 0 files. `.github/workflows/backend-tests.yml:12-123` runs pytest, Postgres pytest, dependency audit, frontend build, and Playwright smoke, but no ruff/eslint/prettier/pyright/mypy job. `frontend/package.json:6-12` has no lint script.
- **Risk:** Style drift, security-rule regressions past review, larger review diffs, and slower onboarding.
- **Recommended solution:**
  1. Add `ruff` and `ruff format --check` for backend with conservative rules first (`E`, `F`, `I`, `B`, `BLE`, `UP`, `SIM`, `LOG`; defer noisy security rules to a second pass).
  2. Add frontend ESLint flat config with React/hooks rules and Prettier format check.
  3. Land formatter output in a formatting-only PR, then make CI blocking.
  4. Add pyright or mypy in warn-only mode before making it blocking.
- **Acceptance criteria:** CI fails on a deliberate lint/format violation; first formatter PR has no behavior changes; `verify-local.sh` or CI includes the lint gate.
- **Estimated effort:** Medium (1-2 days). **Type:** Architectural.

### F1.2 — God-file routing surfaces: `admin.py` and `cves.py` remain oversized · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/routers/admin.py`, `backend/routers/cves.py`.
- **Description:** Admin routing grew since the prior audit: one file now holds 2,746 LOC and 72 `@router.*` decorators. `cves.py` still declares four internal routers in one 1,996-line file (`changes_router`, `list_router`, `detail_router`, `intel_router`).
- **Why it matters:** Router god-files concentrate churn, make auth/rate-limit dependencies harder to audit, and increase merge-conflict risk. The CVE router already exposes the target split through its four router variables, so the right-layer boundary is visible but not executed.
- **Evidence:** `wc -l backend/routers/admin.py backend/routers/cves.py` → 2,746 and 1,996. `rg '@router\.' backend/routers/admin.py --count` → 72. `backend/routers/cves.py:101-104` declares four routers in one module.
- **Risk:** Reviewer fatigue and missed dependency drift in security-sensitive admin routes; higher conflict rate on shared feature work.
- **Recommended solution:** Convert `backend/routers/admin.py` into `backend/routers/admin/` with concern files (`system.py`, `config.py`, `storage.py`, `scheduler.py`, `webhooks.py`, `ai_ops.py`, `users.py`, etc.) and an aggregate `router` re-export. Split `backend/routers/cves.py` into `backend/routers/cves/{changes,list,detail,intel}.py`. Keep route paths/methods identical.
- **Acceptance criteria:** OpenAPI route set before/after is identical; `backend/tests/test_router_split.py` is updated as the route-map guard; each new router file targets <600 LOC.
- **Estimated effort:** Medium. **Type:** Architectural.

### F1.3 — Dual risk-scoring implementation with duplicated constants · Status: OPEN · Priority: HIGH · Architectural
- **Location:** `backend/scoring/risk.py`, `frontend/src/scoring/riskScore.js`, `backend/routers/config.py`.
- **Description:** Backend weights remain canonical, and the frontend fetches `/api/config/risk`, but the frontend still bundles identical fallback constants plus full scoring/classification helpers (`calculateThreatScore`, `threatBand`, `classifyEnvironment`, operational-priority helpers). This is a classic dual-maintenance correctness trap.
- **Why it matters:** BRIEFR's risk score is headline product output. If UI/PDF calculations diverge from API calculations, operators lose trust in the product's most important number.
- **Evidence:** `backend/scoring/risk.py:8-14` defines the six weights. `frontend/src/scoring/riskScore.js:10-17` duplicates them. `frontend/src/scoring/riskScore.js:326-565` still contains threat/raw scoring and operational priority helpers. `backend/routers/config.py:26-43` exposes the backend weights but does not remove frontend recomputation.
- **Risk:** UI/API/PDF drift when thresholds or formulas change.
- **Recommended solution:** First add a contract test that backend config weights equal the frontend fallback snapshot and fail on drift. Then move the frontend to render server-provided `score`, `components`, `band`, and operational-priority data, keeping frontend code for display wording only. If shared fallback is required, generate a checked-in JSON contract from backend constants.
- **Acceptance criteria:** Changing a backend weight without updating the generated contract fails tests; UI and PDF render the API score for a fixed CVE fixture; frontend no longer recomputes canonical risk.
- **Estimated effort:** Small guard / Medium architectural unification. **Type:** Architectural with Quick-Win guard.

### F1.4 — Parallel `_SQLITE`/`_PG` SQL constants expanded across the DB layer · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/db/**`, `backend/db/connection.py`, `backend/db/pg_adapt.py`.
- **Description:** The dual-dialect maintenance surface grew from the prior ~401 markers to 496 `_SQLITE`/`_PG` markers across 19 `backend/db` files. The connection layer still adapts SQLite-oriented SQL at runtime for Postgres while many DB modules also maintain native parallel constants.
- **Why it matters:** The primary production database is Postgres, but default local tests can still pass against SQLite while production-only SQL breaks elsewhere. Dual constants invite drift and make every query edit a two-query edit.
- **Evidence:** `rg '_SQLITE|_PG' backend/db --count` returned 496 matches across 19 files; largest concentrations include `backend/db/correlation.py` (95), `backend/db/metadata.py` (57), `backend/db/cache.py` (57), and `backend/db/cve.py` (52). `backend/db/connection.py:46-110` contains separate SQLite/Postgres connection behavior. `backend/db/pg_adapt.py:1-5` documents legacy SQLite-oriented query adaptation.
- **Risk:** Postgres-only bugs, asymmetric test confidence, and ongoing query drift.
- **Recommended solution:** Make Postgres the default developer/CI DB target where feasible, keep SQLite as explicit fast fallback, and introduce a named-query registry or helper layer so call sites select a logical query rather than owning two SQL strings. Add a ratchet test that the marker count cannot increase without an explicit audit waiver.
- **Acceptance criteria:** Primary test job runs Postgres or a local Postgres fixture; every `_PG` query has a sibling/marker guard; marker count is tracked and only decreases.
- **Estimated effort:** Large for default-Postgres infra; Small for ratchet guard. **Type:** Architectural.

### F1.5 — Oversized frontend components still mix state, fetching, and presentation · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `frontend/src/components/IOCLookup.jsx`, `frontend/src/App.jsx`, `frontend/src/components/DetailDrawer/*`.
- **Description:** Large frontend modules remain over the thermo-nuclear ~1k LOC smell line or close to it. The largest components own fetching, derived state, presentation, and error handling in one file.
- **Why it matters:** Loading/empty/error/data discipline becomes hard to audit in 800-1,400 LOC files, and unrelated state changes can re-render broad UI surfaces.
- **Evidence:** `wc -l` → `IOCLookup.jsx` 1,408, `App.jsx` 1,112, `DetailDrawer/index.jsx` 1,002, `DetailDrawer/IntelTab.jsx` 944, `DetailDrawer/OverviewTab.jsx` 833. `App.jsx:313-364` still contains a dense state cluster.
- **Risk:** Slow review, accidental rerendering, inconsistent async state UX, and expensive future refactors.
- **Recommended solution:** Extract data hooks and presentational slices by workflow (`useIocLookup`, `useDrawerRisk`, `useDrawerBundle`, `FeedShell`, `DrawerShell`). Keep behavior identical and move one concern at a time. After F1.1, add `max-lines` as a warning with existing exceptions documented.
- **Acceptance criteria:** No component >600 LOC without an explicit architecture note; extracted hooks have focused tests where behavior is nontrivial; `npm run build` stays green after each extraction.
- **Estimated effort:** Medium. **Type:** Architectural.

### F1.6 — Silent broad exception swallowing remains common · Status: UPDATED · Priority: MEDIUM · Quick Win + guard
- **Location:** backend non-test code.
- **Description:** Silent `except Exception:` followed by `pass` remains in 27 non-test sites. The prior count was 28, so this improved slightly but remains a real RCA and observability gap.
- **Why it matters:** The repo's debugging rules demand RCA-first behavior; silent broad catches erase the evidence needed for RCA.
- **Evidence:** Python scan found 27 sites, including `backend/routers/admin.py:130`, `backend/routers/admin.py:456`, `backend/routers/cves.py:1304`, `backend/db/init.py:1084`, `backend/scoring/risk.py:569`, and `backend/webhooks/engine.py:223`.
- **Risk:** Hidden partial failures, stale data, missed operator alerts, and hard-to-reproduce production issues.
- **Recommended solution:** Triage by ownership: narrow expected exception types, add contextual `logger.debug` or `logger.warning(..., exc_info=True)` where failures are genuinely ignorable, and add a ruff `BLE001` ratchet once the known list is burned down.
- **Acceptance criteria:** No silent broad catches remain; every broad catch has a comment and log; CI blocks new silent catches.
- **Estimated effort:** Small-Medium. **Type:** Quick Win.

### F1.7 — Documentation sprawl still exceeds the repo's own SSOT discipline · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `docs/`.
- **Description:** The doc corpus grew to 128 markdown files, with 20 top-level docs and 29 archived docs. `PRODUCT_STATUS.md` and `HANDOVER.md` do provide strong truth hierarchy, but the corpus still relies on human navigation rather than an executable index/authority map.
- **Why it matters:** A large audit/planning/documentation tree can make agents resurrect stale plans or edit the wrong document unless authority is obvious.
- **Evidence:** Python count over `docs/` → 20 top-level `.md`, 128 total `.md`, 29 under `docs/archive/`. `docs/PRODUCT_STATUS.md:1-4` explicitly declares itself the production truth source.
- **Risk:** Stale docs mistaken for runtime truth; higher audit/update cost.
- **Recommended solution:** Keep `docs/index.md` or `docs/DOCUMENTATION_PLAN.md` as the authoritative map with labels: runtime truth, planning, generated, archive, snapshot. Add a small doc-audit script that reports top-level docs without authority labels.
- **Acceptance criteria:** Every doc has an authority category; no top-level markdown file lacks an index entry; stale snapshot/archive paths are visibly marked.
- **Estimated effort:** Quick Win for index; Medium for consolidation. **Type:** Quick Win.

### F1.8 — `AGENTS.md` and `CLAUDE.md` remain near-duplicate rulebooks · Status: OPEN · Priority: LOW · Quick Win
- **Location:** root `AGENTS.md` and `CLAUDE.md`.
- **Description:** Two root-level agent instruction files remain large and overlapping. The duplication is intentional for multiple agent harnesses, but it creates a maintenance path where rules can diverge.
- **Why it matters:** Agents follow whichever file the harness injects; contradictory or stale safety rules can change behavior.
- **Evidence:** `wc -l AGENTS.md CLAUDE.md` → 156 and 144 LOC. Both contain overlapping error-investigation, PR, testing, and danger-zone rules.
- **Risk:** Policy drift and inconsistent agent behavior.
- **Recommended solution:** Make one file canonical and generate the second from shared sections, or make one a thin pointer plus harness-specific additions only.
- **Acceptance criteria:** Shared rules live in one source; a test/script verifies the generated/pointer file is current.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F1.9 — Config/settings ownership remains spread across five modules · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `backend/settings.py`, `backend/config_schema.py`, `backend/operator_settings.py`, `backend/db/config.py`, `backend/routers/config.py`.
- **Description:** Config behavior is split across runtime settings, admin schema, DB persistence, DB backend selection, and the risk config endpoint. The split is understandable, but module responsibilities are not declared strongly enough to prevent overlap.
- **Why it matters:** Config bugs are often wrong-layer bugs: a key can be added to schema but not persistence, persisted but not reload-safe, or runtime-only but displayed as mutable.
- **Evidence:** `wc -l` across the five modules totals 772 LOC. `backend/settings.py:91-93` exposes `allowed_origins_list`; `backend/config_schema.py` declares operator-editable fields; `backend/routers/config.py:26-43` serves risk config.
- **Risk:** Duplicate config keys, wrong apply strategy, or operator UI lying about persistence/restart requirements.
- **Recommended solution:** Add module docstrings that state each layer's ownership and a test that every admin-editable key has one schema owner, one apply strategy, and a declared persistence mode.
- **Acceptance criteria:** No config key appears in two ownership layers without an explicit bridge; docs/tests fail on missing owner/apply strategy.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F1.10 — `correlation/copy.py` still shadows a stdlib module name · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `backend/correlation/copy.py`.
- **Description:** The module name still collides with Python's standard `copy` module and actually holds narrative/sanitization helpers, not copy semantics.
- **Why it matters:** Shadowing a stdlib name is a needless comprehension tax and can mislead imports/searches.
- **Evidence:** `Glob backend/**/copy.py` finds `backend/correlation/copy.py`. Imports remain in `backend/correlation/ioc_graph.py`, `backend/correlation/clusters.py`, `backend/correlation/campaigns.py`, and `backend/brief/service.py`.
- **Risk:** Confusing imports and future shadowing mistakes.
- **Recommended solution:** Rename to `backend/correlation/narrative.py` or `text.py`; update imports in one mechanical PR.
- **Acceptance criteria:** No project module named `copy.py`; tests importing correlation/brief services pass.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F1.11 — Frontend unit tests are still not CI-gated; production console calls remain · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** `frontend/package.json`, `.github/workflows/backend-tests.yml`, frontend JSX files.
- **Description:** Frontend unit tests exist and grew from the prior 47 to 56 files, but CI still does not run `npm run test:unit`. The frontend build is still nested in Playwright smoke rather than a standalone frontend job. Five production JSX `console.error` calls remain.
- **Why it matters:** Tests that are not CI-gated are advisory. Console calls may be intentional boundary logging, but without lint policy there is no difference between approved error-boundary logs and stray debug output.
- **Evidence:** `frontend/package.json:6-12` defines `test:unit`. `.github/workflows/backend-tests.yml:95-123` builds frontend only inside `playwright-smoke`; `rg 'test:unit' .github/workflows` finds no CI invocation. Python count found 56 `frontend/src/**/*.test.js` files and 5 production JSX `console.*` calls.
- **Risk:** Broken frontend unit tests can ship; debug logging can leak into production UI console.
- **Recommended solution:** Add a `frontend-tests` CI job running `npm ci --ignore-scripts`, `npm run test:unit`, and `npm run build`. After F1.1, enforce `no-console` with an allowlist for named error-boundary files or replace these with a shared `reportUiError` helper.
- **Acceptance criteria:** A failing FE unit test fails CI; build has its own job; console policy is explicit and enforced.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F1.12 — Scheduler god-file exceeds the thermo-nuclear size bar · Status: NEW · Priority: MEDIUM · Architectural
- **Location:** `backend/scheduler.py`.
- **Description:** The scheduler module is now 2,600 LOC, larger than either prior Phase 1 router finding except `admin.py`. It owns job definitions, orchestration, lock coupling, and operational behavior in one file while the durable-job migration is also active.
- **Why it matters:** Background jobs are where heavy work belongs, so scheduler clarity is a production-safety concern. At 2.6k LOC, new jobs are likely to be added by copy/paste into the same file instead of through a registry or per-domain owner modules.
- **Evidence:** `wc -l backend/scheduler.py` → 2,600. `backend/main.py:123-133` starts APScheduler and the Procrastinate worker in the same lifespan. `backend/tests/test_job_ownership_registry.py:1-10` exists because this area now needs executable ownership invariants.
- **Risk:** Double-run/dropped jobs, lock drift, and hard-to-review scheduler changes.
- **Recommended solution:** Split scheduler ownership by job domain behind a registry (`feeds`, `ai`, `retention`, `watchlist`, `stack`, `embeddings`), leaving `scheduler.py` as composition/root wiring only.
- **Acceptance criteria:** `scheduler.py` <700 LOC; job IDs/locks remain tested via the existing ownership registry; adding a job requires a registry entry and owner module.
- **Estimated effort:** Medium-Large. **Type:** Architectural.

---

## Overall Score: **7.2 / 10**

| Sub-audit | Score |
|---|---:|
| Repository Organization | 8 / 10 |
| Code Quality | 6.8 / 10 |
| Technical Debt | 6.8 / 10 |

## Strengths
- Strong test investment and CI coverage of backend plus Postgres path.
- Clear docs truth hierarchy (`PRODUCT_STATUS`, `HANDOVER`, planning/archive split).
- No evidence of committed secrets or casual TODO sprawl in the refreshed sample.
- Security/reliability conventions are written down and increasingly backed by tests.

## Weaknesses
- No lint/format/type gate (F1.1), which keeps many written rules unenforced.
- Multiple god-files exceed the ~1k LOC bar (F1.2, F1.5, F1.12).
- Dual-maintained correctness surfaces remain in risk scoring and DB SQL (F1.3, F1.4).
- Frontend tests and console policy remain outside CI enforcement (F1.11).

## Immediate Action Items
1. Add frontend unit-test/build CI job (F1.11).
2. Add risk-weight contract guard and DB dialect marker ratchet (F1.3, F1.4).
3. Burn down silent broad catches or at least log them (F1.6).
4. Rename `correlation/copy.py` and document config module ownership (F1.10, F1.9).

## Long-Term Recommendations
1. Introduce ruff + eslint/prettier + type-checking as blocking gates after format-only PRs.
2. Split `admin.py`, `cves.py`, `scheduler.py`, and the oversized frontend components by true ownership boundaries.
3. Collapse dual-maintained scoring and dialect logic into single canonical contracts.
4. Convert doc/rule duplication into generated or indexed SSOT surfaces.

## Production-Readiness Assessment (Phase 1 areas)
**Conditionally ready — 7.2/10.** The repository is healthy enough for self-hosted production, but maintainability risks are growing faster than guardrails. The next best code-judo moves are not new abstractions; they are executable gates and deletions/splits that reduce duplicated logic and giant files.

---

## Resolved since last audit

None.
