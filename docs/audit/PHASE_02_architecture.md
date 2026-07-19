# PHASE 2 — Backend · Frontend · Database · API · State-Management Architecture

*Reviewed at pinned refresh commit `ff23c18a4925b3b7082a2b1d1600884324d90d02` for the 2026-07-19 delta refresh. Prior baseline: `61c686f`. Scope: FastAPI backend, React 19 + Vite frontend, Postgres-native DB layer with SQLite test fallback, API shape, and state-management architecture. Current branch HEAD is `267f174`; source-code paths reviewed below are unchanged from the pinned SHA, with only audit coordination docs differing since the pin.*

---

## Executive Summary

The architecture is still coherent: `main.py` composes middleware and routers, routers mostly call domain DB facades, heavy jobs stay off the request path, session-cookie auth and live role checks are present, frontend HTTP is centralized in `api.js`, and admin/security invariants are increasingly executable. The biggest positive delta is that the prior admin-auth-by-convention concern now has a dedicated invariant test suite and is closed in this phase.

The major architecture debts remain the same class of right-layer problems: a leaky DB dialect boundary, two job systems in transition, unversioned API paths, no shared frontend server-state cache, and a top-level `App.jsx` state cluster. One finding improved from open to updated rather than closed (job ownership now has registry tests), but most architectural concerns still require structural cleanup.

**Overall Score: 7.2 / 10.** Prior score was 7.0. The slight increase reflects the closed admin-auth invariant and job-ownership guard, offset by larger dual-dialect and god-component evidence.

### Refresh classification

| ID | Status | Verdict |
|---|---|---|
| F2.1 | UPDATED | Dual-dialect markers increased to 496 across 19 DB files; abstraction still leaks. |
| F2.2 | UPDATED | Job ownership registry tests now exist, but APScheduler and Procrastinate still coexist. |
| F2.3 | OPEN | Product API routes remain unversioned. |
| F2.4 | UPDATED | Claim refined: no shared server-state cache; fetching is ad hoc via `api.js`, direct effects, and a small `useAsync`. |
| F2.5 | UPDATED | `App.jsx` grew to 1,112 LOC with 28 `useState` calls. |
| F2.6 | CLOSED | Moved to resolved appendix; admin/refresh route auth invariants are now tested. |
| F2.7 | OPEN | Credentialed CORS still lacks a validator rejecting wildcard origins. |
| F2.8 | UPDATED | Inline/deferred imports still exist in `main.py`, plus auth middleware deferred imports. |
| F2.9 | OPEN | No explicit repository/unit-of-work boundary found. |
| F2.10 | OPEN | Runtime OpenAPI disabled in prod and no exported `openapi*.json` artifact exists. |

---

## Findings

### F2.1 — Leaky dual-dialect DB abstraction; default test dialect still differs from production · Status: UPDATED · Priority: HIGH · Architectural
- **Location:** `backend/db/connection.py`, `backend/db/pg_adapt.py`, `backend/db/**`, `.github/workflows/backend-tests.yml`.
- **Description:** The DB facade still exposes one connection interface while callers and helpers preserve substantial dialect knowledge. The dual SQL surface grew to 496 `_SQLITE`/`_PG` markers across 19 DB files. CI does run a Postgres job, but the default lightweight path remains SQLite unless `DATABASE_URL` is set.
- **Why it matters:** A true abstraction hides dialect choice below call sites. Here, contributors still maintain parallel SQL and can pass fast tests against SQLite while breaking production Postgres semantics.
- **Evidence:** `backend/db/connection.py:46-110` has separate SQLite/Postgres execution behavior and calls `prepare_query`. `backend/db/pg_adapt.py:1-5` documents SQLite-oriented SQL translated for Postgres. `rg '_SQLITE|_PG' backend/db --count` → 496 across 19 files. `.github/workflows/backend-tests.yml:13-29` runs default pytest, while `test-postgres` is a separate job at lines 30-69.
- **Risk:** Postgres-only production defects, query drift, and high maintenance cost for every DB edit.
- **Recommended solution:** Make Postgres the primary test target for DB-heavy tests and move dialect selection into a named query registry/facade. Keep SQLite only as an explicit fast/dev fallback. Add a marker-count ratchet and a sibling-query guard.
- **Acceptance criteria:** Primary CI DB semantics are Postgres; no new `_PG` or `_SQLITE` marker lands without a named query owner; marker count can only decrease unless waived in audit docs.
- **Estimated effort:** Large. **Type:** Architectural.

### F2.2 — Two background-job systems coexist, but ownership guard now exists · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/scheduler.py`, `backend/jobs/`, `backend/main.py`, `backend/tests/test_job_ownership_registry.py`.
- **Description:** APScheduler remains the main in-process scheduler and Procrastinate remains feature-flagged durable-job infrastructure. The refresh found a meaningful mitigation: job ownership is now guarded by `test_job_ownership_registry.py`, which documents Procrastinate tasks and asserts scheduler/procrastinate namespaces are disjoint. The architectural transition is still incomplete because both systems are started from the app lifespan when enabled.
- **Why it matters:** Two job systems can be safe during migration only if ownership is explicit and overlap is impossible. The new guard helps, but the codebase still has two operational models and two lifecycle paths.
- **Evidence:** `backend/main.py:123-133` starts APScheduler and then the in-process Procrastinate worker. `backend/jobs/app.py:1-19` makes Procrastinate feature-flagged. `backend/tests/test_job_ownership_registry.py:1-10` describes the invariant; lines 57-73 assert the registry is current and namespaces are disjoint. `backend/scheduler.py` is 2,600 LOC.
- **Risk:** Duplicate/dropped jobs during migration, operator confusion, and lock/idempotency drift.
- **Recommended solution:** Finish the migration plan as executable ownership: one registry entry per job with owner system, idempotency key, lock, and health surface. Split scheduler jobs by domain so APScheduler composition is thin. Keep the disjoint-namespace test and add a test that every job visible in admin appears in the registry.
- **Acceptance criteria:** Every job has one owner and one registry row; adding a Procrastinate task without docs/tests fails; scheduler file shrinks to composition and job registration.
- **Estimated effort:** Medium-Large. **Type:** Architectural.

### F2.3 — No first-party API versioning strategy · Status: OPEN · Priority: HIGH · Architectural
- **Location:** `backend/main.py`, `backend/routers/*`, `frontend/src/api.js`, `docs/API_REFERENCE.md`.
- **Description:** Product routes are mounted under unversioned `/api/...` paths. FastAPI metadata has `version="1.5.0"`, but there is no `/api/v1` route namespace or response-version policy.
- **Why it matters:** Self-hosted users upgrade on their own cadence. Without a versioned contract, breaking response-shape changes require all clients to move at once.
- **Evidence:** `rg '/api/v[0-9]' /workspace` finds third-party upstream URLs, audit docs, and tests fixtures, but no first-party router mount. `backend/main.py:299-326` includes all routers directly, without a versioned aggregate. `backend/main.py:161-177` sets OpenAPI metadata only.
- **Risk:** No deprecation runway, brittle integrations, and blocked external API consumers.
- **Recommended solution:** Alias current routes under `/api/v1` while keeping unversioned routes for a documented deprecation window. Add an `X-API-Version` response header and versioning policy in `docs/API_REFERENCE.md`.
- **Acceptance criteria:** Every current route is reachable under `/api/v1`; contract tests pin v1 response schemas; new breaking shapes require v2.
- **Estimated effort:** Medium. **Type:** Architectural.

### F2.4 — No shared frontend server-state cache; fetching remains ad hoc · Status: UPDATED · Priority: HIGH · Architectural
- **Location:** `frontend/src/api.js`, `frontend/src/hooks/useAsync.js`, frontend components/pages.
- **Description:** The prior wording overstated `useAsync` usage. Current evidence shows an even more general issue: `api.js` centralizes fetch functions, but server state is consumed through ad hoc component effects, promises, utility calls, and one small `useAsync` hook. There is no shared query cache, request dedup, or mutation invalidation layer.
- **Why it matters:** As feed, drawer, wallboard, admin, ARCH, and Forge all touch shared resources, independent fetches produce redundant network traffic and inconsistent snapshots.
- **Evidence:** `frontend/package.json:13-39` includes `@tanstack/react-table` but no `@tanstack/react-query` or SWR. `frontend/src/api.js:73-638` exports many fetch functions. `rg 'fetch[A-Z].*\(' frontend/src` shows direct calls across `App.jsx`, `CVEFeed.jsx`, `DetailDrawer/index.jsx`, `IOCLookup.jsx`, admin/security pages, utilities, and PDF code. `frontend/src/hooks/useAsync.js:10-57` stores only local component state.
- **Risk:** Duplicate requests, manual refresh glue, stale UI pockets, and higher complexity as mutations grow.
- **Recommended solution:** Introduce a query cache with canonical query keys. Prefer `@tanstack/react-query` unless the project decides to keep zero dependency; otherwise build a tiny keyed cache/subscription layer around `api.js`. Migrate leaf components first, then feed/drawer.
- **Acceptance criteria:** Two mounted components requesting the same resource share one network request; mutations invalidate affected keys; manual refresh-key/tick wiring shrinks.
- **Estimated effort:** Medium-Large. **Type:** Architectural.

### F2.5 — `App.jsx` god-component keeps heterogeneous state in one shell · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `frontend/src/App.jsx`.
- **Description:** `App.jsx` grew to 1,112 LOC and still owns a broad mix of navigation, filters, stats, selected CVE, drawer lifecycle, digest modal, command palette, timezone, feed health, IOC prefill, atlas filter, mounted tab state, and tutorial state.
- **Why it matters:** Top-level shells should compose feature state, not own every feature's local lifecycle. Broad `useState` clusters make rerender behavior and loading/error boundaries hard to reason about.
- **Evidence:** `wc -l frontend/src/App.jsx` → 1,112. `rg 'useState\(' frontend/src/App.jsx` shows 28 state hooks, including the dense cluster at `App.jsx:313-364` and mounted/drawer/tutorial state at `App.jsx:907-910`.
- **Risk:** Accidental broad rerenders, fragile feature additions, and difficult manual testing of state interactions.
- **Recommended solution:** Extract feature shells and reducers: feed state, drawer orchestration, global UI controls, and routing/tab persistence. Pair with F2.4 so server state leaves `App.jsx` rather than being moved to another component.
- **Acceptance criteria:** `App.jsx` <500 LOC; feed/drawer/UI state have clear owners; profiler confirms unrelated state changes do not rerender the whole shell.
- **Estimated effort:** Medium. **Type:** Architectural.

### F2.7 — Credentialed CORS lacks a wildcard-origin validator · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `backend/main.py`, `backend/settings.py`, `backend/config_schema.py`.
- **Description:** CORS still uses explicit origins with `allow_credentials=True`, which is correct when origins are non-wildcard. The missing guard is a validator that rejects `*` whenever credentials are enabled.
- **Why it matters:** Credentialed CORS with wildcard origins is a serious security misconfiguration. A startup/schema guard is cheap and makes the safe state invariant executable.
- **Evidence:** `backend/main.py:196-206` sets `allow_origins=settings.allowed_origins_list` and `allow_credentials=True`. `backend/settings.py:91-93` splits `allowed_origins` with no wildcard rejection. `backend/config_schema.py:223` exposes `ALLOWED_ORIGINS` as a config field.
- **Risk:** Future config change could degrade CORS safety.
- **Recommended solution:** Add a settings validator or startup assertion: if `allow_credentials=True`, `allowed_origins_list` must not contain `*`. Also validate admin config saves for `ALLOWED_ORIGINS`.
- **Acceptance criteria:** Startup and config apply fail for wildcard origins with credentials enabled; tests cover both paths.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F2.8 — Composition root and middleware still contain deferred imports · Status: UPDATED · Priority: LOW · Quick Win
- **Location:** `backend/main.py`, `backend/auth_middleware.py`.
- **Description:** Deferred imports remain in the composition root and auth middleware. Some are probably cycle or startup-cost driven, but the reasons are not documented per import, and the no-inline-imports rule makes this a debt item unless each exception is justified.
- **Why it matters:** Deferred imports hide dependency failures until runtime paths execute and make graph reasoning harder for operators and agents.
- **Evidence:** `backend/main.py:68`, `107`, `131`, `145`, and `152` import inside functions. `backend/auth_middleware.py:94-96` imports DB/search-token/rate-limit helpers inside request middleware. `backend/main.py:135-136` logs and continues when the Procrastinate worker import/start path fails.
- **Risk:** Runtime-only import failures and unclear circular-dependency boundaries.
- **Recommended solution:** Hoist imports that are not true cycles. For the rest, add a one-line comment stating why the import must be deferred and add a lightweight import test for the module path.
- **Acceptance criteria:** Every inline import has a documented reason; non-cycle imports are top-level; import smoke tests cover deferred modules.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

### F2.9 — DB facade lacks explicit unit-of-work boundaries for multi-write flows · Status: OPEN · Priority: LOW · Architectural
- **Location:** `backend/db/*`, routers/services that perform multi-step writes.
- **Description:** The DB package is a useful facade, but there is no explicit repository or unit-of-work abstraction. Transactions exist inside connection behavior, but multi-write business flows still rely on call sites to remember boundaries and ordering.
- **Why it matters:** Multi-write flows such as ingest, enrichment, correlation materialization, stack backfill, and alert delivery need all-or-nothing behavior where partial writes would mislead operators.
- **Evidence:** `rg '\b(UnitOfWork|unit_of_work|transactional)\b' backend` found no matches. `backend/db/connection.py:102-110` starts transactions in the Postgres connection path, but no higher-level transaction boundary names business operations.
- **Risk:** Partial state after mid-flow failure and hard-to-test data integrity.
- **Recommended solution:** Add a small transaction context for known multi-write flows rather than a broad repository rewrite. Name transaction scopes by business operation and test rollback on injected failure.
- **Acceptance criteria:** Critical multi-write flows run inside explicit transaction contexts; failure mid-flow leaves no partial rows; tests prove rollback.
- **Estimated effort:** Medium. **Type:** Architectural.

### F2.10 — Production disables runtime OpenAPI without an exported contract artifact · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `backend/main.py`, docs/build artifacts.
- **Description:** Production disables interactive docs and OpenAPI JSON, which is acceptable hardening, but the repo still has no exported `openapi.json` artifact or CI diff to preserve a machine-readable contract.
- **Why it matters:** API versioning and external integrations need a stable contract. Without exported OpenAPI, API drift is discovered by humans or clients after breakage.
- **Evidence:** `backend/main.py:174-176` sets `docs_url`, `redoc_url`, and `openapi_url` to `None` in production. `Glob **/openapi*.json` returned 0 files.
- **Risk:** Invisible API drift and poor integration ergonomics.
- **Recommended solution:** Add a script/CI step that imports the app, exports OpenAPI for non-production settings, and either commits `docs/openapi.json` or publishes it as an artifact. Pair with F2.3 so `/api/v1` schemas are pinned.
- **Acceptance criteria:** OpenAPI export exists; CI fails on unreviewed contract drift; API docs reference the exported artifact.
- **Estimated effort:** Quick Win. **Type:** Quick Win.

## Overall Score: **7.2 / 10**

| Sub-audit | Score |
|---|---:|
| Backend Architecture | 7.7 / 10 |
| Frontend Architecture | 6.8 / 10 |
| Database Architecture | 6.3 / 10 |
| API Architecture | 6.7 / 10 |
| State Management | 6.8 / 10 |

## Strengths
- Clear FastAPI composition, middleware ordering, and router/db layering.
- Heavy work remains off request paths; scheduler ownership now has a registry guard.
- Admin/refresh RBAC invariant is now covered by tests and moved out of the open findings.
- Centralized frontend API helper remains a good base for a future query-cache layer.

## Weaknesses
- DB dialect abstraction still leaks heavily and grew in marker count (F2.1).
- Two job systems remain in transition despite improved guardrails (F2.2).
- API contract lacks versioning and exported OpenAPI (F2.3, F2.10).
- Frontend server state and shell state remain right-layer issues (F2.4, F2.5).

## Immediate Action Items
1. Add wildcard-origin rejection for credentialed CORS (F2.7).
2. Export OpenAPI and add contract drift checking (F2.10).
3. Document/hoist deferred imports (F2.8).
4. Keep extending job ownership registry until every scheduler job is covered (F2.2).

## Long-Term Recommendations
1. Make Postgres the primary DB test semantics and collapse SQL dialect duplication behind named query owners.
2. Adopt `/api/v1` with contract tests and a deprecation policy.
3. Introduce a shared frontend query cache and move server state out of `App.jsx`.
4. Add explicit transaction contexts for critical multi-write flows.

## Production-Readiness Assessment (Phase 2 areas)
**Conditionally ready — 7.2/10.** The current architecture is sound for self-hosted single-tenant operation. The remaining gaps are mostly future-scale and integration risks: dual dialects, job-system migration, unversioned APIs, no exported contract, and frontend server-state ownership. The closed admin-auth invariant is an important reliability win, but the codebase still needs structural cleanup before broader external API or multi-org commitments.

---

## Resolved since last audit

### Resolved F2.6 — Session middleware skips admin prefixes; RBAC relies on router-level dependency by convention · Status: CLOSED
- **Original concern:** `auth_middleware.py` skips `/api/admin/` and `/api/refresh`, so safety depended on router-level `require_admin` being applied consistently.
- **Why closed:** The code still intentionally skips those prefixes in session middleware, but the convention is now guarded by executable security invariants. `backend/tests/test_security_invariants.py:1-10` states the invariant and enumerates admin/refresh routes from routers automatically. `backend/tests/test_security_invariants.py:117-158` verifies unauthenticated requests get 401, non-admin roles get 403, and demoted admin JWTs are rejected after DB role changes.
- **Verification:** Re-verified on 2026-07-19 against pinned refresh SHA `ff23c18a4925b3b7082a2b1d1600884324d90d02`; current source matches pinned source for this path.
