# PHASE 2 — Backend · Frontend · Database · API · State-Management Architecture

*Reviewed at commit `61c686f`. FastAPI backend, React 19 + Vite frontend, Postgres-native
`db/` package with SQLite test fallback.*

---

## Executive Summary

The architecture is **coherent and layered**, not accidental. The backend follows a clean
`main.py` (composition root) → `routers/*` (HTTP) → `db/*` (data facade) →
`connection.py` (async pool) topology, with cross-cutting concerns (auth, security headers,
request-id, gzip) implemented as explicitly ordered middleware and the request-id contextvar
deliberately set outermost. Heavy work is pushed off the request path into `scheduler.py`.
Auth is enforced twice — a global session middleware plus per-route dependencies
(`require_user`/`require_admin`) that re-read role from the DB so demotions take effect
immediately. The frontend centralizes HTTP in `api.js` with a token-refresh interceptor and
`credentials: 'include'`, uses a hand-rolled `useAsync` (stale-while-revalidate with
`AbortController`), three React contexts, and lazy-loads admin/security routes.

The weaknesses are architectural-debt patterns that scale poorly: (1) the DB layer is a
**leaky dual-dialect abstraction** (`pg_adapt.py` + 401 `_SQLITE`/`_PG` constants) where the
default test dialect ≠ production dialect; (2) **two coexisting job systems** (APScheduler +
Procrastinate) mid-migration; (3) **no API URL/header versioning** (`/api/...`, never
`/api/v1/...`) so breaking changes have no migration path; (4) the frontend has **no shared
server-cache layer** — every component fetches independently through `useAsync`, so there's
no request dedup or cross-component invalidation; (5) `App.jsx` is a **god-component** holding
~25 `useState` slices; (6) the session middleware **skips** admin prefixes and relies on
router-level `require_admin` by convention — correct today, fragile against a forgotten dependency.

**Overall Score: 7 / 10.**

---

## Findings

### F2.1 — Leaky dual-dialect DB abstraction; default test dialect ≠ production · Priority: HIGH · Architectural
- **Location:** `backend/db/connection.py` (SqliteConnection vs asyncpg pool),
  `backend/db/pg_adapt.py` (`adapt_params`, `prepare_query`), `_SQLITE`/`_PG` constants across
  15 files (~401), `db/config.py::is_postgres()`.
- **Description:** The `db/` package presents a unified `get_connection()`/`DbConnection`
  surface, but the abstraction leaks: callers still maintain parallel SQL per dialect, and
  `pg_adapt` rewrites placeholders/params at runtime. The default pytest run uses SQLite while
  production is Postgres, so the primary test signal exercises the non-production engine.
- **Why it matters:** A true abstraction would let callers write one query; here every query
  is a two-dialect maintenance point, and the fast CI path can't catch Postgres-only bugs
  (regex, JSONB, `ON CONFLICT`, array ops, `RETURNING`, window functions).
- **Evidence:** `SqliteConnection` wrapper in `connection.py:44`; `pg_adapt` imported into the
  connection layer; `grep -c '_SQLITE|_PG' db` → 401 across 15 files.
- **Risk:** Postgres-only production defects escaping the default suite; ongoing dual-write tax.
- **Recommended solution:** Two-track. (a) Make Postgres the **default** test target via
  Testcontainers/pytest fixture so the abstraction is validated against production semantics;
  keep SQLite as an opt-in fast lane. (b) Push the remaining dialect divergence *into* the
  facade (a small query-builder or per-dialect SQL registry keyed by name) so call sites are
  dialect-agnostic. Add a guard test that every `_PG` constant has a `_SQLITE` sibling or an
  explicit `# pg-only` marker.
- **Acceptance criteria:** CI's primary DB job runs Postgres; no `_PG` constant lacks a sibling
  or marker; call sites reference named queries, not raw dialect strings (progressively).
- **Effort:** Large. **Type:** Architectural.

### F2.2 — Two coexisting background-job systems (APScheduler + Procrastinate) · Priority: MEDIUM · Architectural
- **Location:** `backend/scheduler.py` (2,431 LOC, APScheduler, 31 jobs) and
  `backend/jobs/` (`app.py`, `worker.py`, `tasks.py`) + `db/outbound_jobs.py` +
  migration `028_procrastinate_schema.py`. Started in `main.py` lifespan
  (`start_scheduler()` AND `start_inprocess_worker()`), Procrastinate feature-flagged, Postgres-only.
- **Description:** A durable job foundation (Procrastinate) is being introduced alongside the
  existing in-process APScheduler. Both run in the same lifespan today.
- **Why it matters:** Two schedulers = two mental models, two failure modes, two lock schemes,
  and ambiguity about where a new job belongs. Mid-migration states are where jobs get
  double-run or silently dropped. CLAUDE.md already flags scheduler-lock/admin-router coupling.
- **Evidence:** both `start_scheduler` and `start_inprocess_worker` invoked in lifespan;
  `028_procrastinate_schema.py` migration present.
- **Risk:** Duplicate/dropped jobs, operator confusion, lock desync during the transition.
- **Recommended solution:** Write an explicit migration ADR: which job classes move to
  Procrastinate, in what order, and the cutover/rollback plan. Add a single "job registry"
  doc/table listing every job, its owner-system, idempotency key, and lock. Gate the overlap so
  a job runs in exactly one system. Deep-dive in Phase 3 (Scheduler audit).
- **Acceptance criteria:** Each job is owned by exactly one system with a documented idempotency
  key; a test asserts no job id is registered in both.
- **Effort:** Medium–Large. **Type:** Architectural.

### F2.3 — No API versioning strategy (`/api/...`, never `/api/v1/...`) · Priority: HIGH · Architectural
- **Location:** all routers under `backend/routers/*` mount at `/api/...`; `main.py` sets
  FastAPI `version="1.5.0"` (metadata only). `grep '/api/v[0-9]'` → none.
- **Description:** There is no URL or header versioning. The frontend and any external
  consumers bind to unversioned paths, so any breaking change to a response shape breaks all
  clients simultaneously with no parallel-run path.
- **Why it matters:** For a platform "deployed to thousands of organizations and maintained for
  years," self-hosters upgrade on their own cadence; unversioned APIs make backward-incompatible
  evolution effectively impossible without coordinated downtime. This is the biggest
  *forward-compatibility* gap in the architecture.
- **Evidence:** no versioned prefixes; version lives only in OpenAPI metadata.
- **Risk:** Locked-in response contracts; painful upgrades; no deprecation runway.
- **Recommended solution:** Adopt `/api/v1/` now (alias current unversioned routes to `v1` with
  a deprecation window), and define a versioning policy (URL-major + additive-minor; document in
  `docs/API_REFERENCE.md`). Add an `X-API-Version` response header. New breaking shapes land under `v2`.
- **Acceptance criteria:** All routes reachable under `/api/v1/`; policy documented; a contract
  test pins v1 response schemas.
- **Effort:** Medium. **Type:** Architectural.

### F2.4 — Frontend has no shared server-state cache; per-component fetching via `useAsync` · Priority: HIGH · Architectural
- **Location:** `frontend/src/hooks/useAsync.js`, `frontend/src/api.js` (60+ `fetch*`
  functions); no `@tanstack/react-query`/SWR in `package.json` dependencies (react-table is
  present but that's table state, not server cache).
- **Description:** `useAsync` is a solid per-call SWR-lite (abort + stale-while-revalidate) but
  holds no shared cache. Two components needing the same resource issue two requests; there is
  no cross-component cache invalidation, no background refetch coordination, no request dedup.
- **Why it matters:** As the UI grows (feed + drawer + wallboard + admin all touching CVE/stat
  data), this produces redundant network traffic, inconsistent snapshots between components, and
  manual invalidation glue. It's the frontend analog of not having a data layer.
- **Evidence:** `useAsync` keeps state in local `useState`/`useRef` only; no cache store; each
  `fetch*` in `api.js` is called ad-hoc by components.
- **Risk:** Duplicate requests, UI inconsistency (component A shows stale, B shows fresh),
  growing manual-refresh wiring in `App.jsx`.
- **Recommended solution:** Introduce a query cache. Lightest-touch: adopt `@tanstack/react-query`
  with query keys mirroring the `api.js` function names; migrate incrementally (leaf components
  first). If avoiding a dependency, build a minimal keyed cache + subscription around `useAsync`.
  Either way, define canonical query keys and invalidation on mutations.
- **Acceptance criteria:** Same resource requested by two mounted components hits the network
  once; a mutation invalidates the relevant cached queries; no manual `tick()`/refresh-key glue
  for shared data.
- **Effort:** Medium–Large. **Type:** Architectural.

### F2.5 — `App.jsx` god-component: ~25 `useState` slices in one shell · Priority: MEDIUM · Architectural
- **Location:** `frontend/src/App.jsx` (1,088 LOC) — filters, stats, selectedCVE, drawer
  loading/error, digest, palette, timezone, feedHealth, refresh schedule, ioc prefill, atlas
  filter, etc. (`App.jsx:313-364`).
- **Description:** The top-level shell owns a large, heterogeneous state surface as flat
  `useState`. Unrelated concerns (search palette, IOC prefill, feed health, digest modal) live
  in one component, so any update risks re-rendering the whole shell.
- **Why it matters:** Broad re-renders hurt perf; the sheer count makes the loading/empty/error
  discipline hard to audit per feature; it's the hardest file to modify safely.
- **Evidence:** state-hook inventory at `App.jsx:313-364`.
- **Recommended solution:** Group related state into `useReducer` slices or dedicated contexts
  (e.g. a `FeedContext` for filters/stats/selection, a `UIContext` for palette/digest/about).
  Extract the drawer orchestration into its own component. Combine with F2.4 so server data
  leaves component state entirely.
- **Acceptance criteria:** `App.jsx` <500 LOC; shared feed state in a reducer/context; React
  Profiler shows the shell not re-rendering on unrelated state changes.
- **Effort:** Medium. **Type:** Architectural.

### F2.6 — Session middleware skips admin prefixes; RBAC relies on router-level dependency by convention · Priority: MEDIUM · Architectural
- **Location:** `backend/auth_middleware.py:24-28` (`_ADMIN_PREFIXES = ("/api/admin/",
  "/api/refresh")` are *skipped* by the session gate), relying on
  `routers/admin.py:68` (`dependencies=[Depends(require_admin), ...]`).
- **Description:** The global session middleware deliberately does **not** gate admin/refresh
  paths, assuming the routers gate themselves. This is currently correct (admin router applies
  `require_admin` at router scope), but it's defense-by-convention: a new admin sub-router or a
  route mounted outside the aggregate that forgets the dependency would be **both** un-gated by
  middleware and un-gated by the route → unauthenticated access.
- **Why it matters:** Auth-bypass risk is the highest-severity class; relying on every future
  contributor to remember a router dependency is fragile for a multi-year codebase.
- **Evidence:** `_skip_session_gate` returns True for `/api/admin/`; admin gating lives only in
  the router `dependencies=`.
- **Risk:** Future auth bypass on a forgotten admin route.
- **Recommended solution:** Make the middleware *enforce at least authentication* on admin
  prefixes (require a valid session), letting the router add the role check on top — defense in
  depth, so a forgotten router dependency still fails closed. Add a startup assertion/test that
  every route under `/api/admin/` has `require_admin` in its dependency chain (introspect
  `app.routes`).
- **Acceptance criteria:** A test enumerates `app.routes` and fails if any `/api/admin/*` route
  lacks `require_admin`; an unauthenticated request to a hypothetical un-gated admin route is 401.
- **Effort:** Small–Medium. **Type:** Architectural (security-hardening).

### F2.7 — CORS `allow_credentials=True` with method list omitting PUT/PATCH; header allowlist · Priority: LOW · Quick Win
- **Location:** `backend/main.py:115-126` — `allow_methods=["GET","POST","DELETE","OPTIONS"]`,
  `allow_credentials=True`, explicit `allow_origins=settings.allowed_origins_list`.
- **Description:** Credentials-CORS with an explicit origins list is correct (not `*`). The API
  is POST/DELETE-only (no PUT/PATCH), which is a deliberate style but means partial updates ride
  on POST. Worth confirming `allowed_origins_list` can never resolve to `["*"]` in any config path.
- **Why it matters:** Credentialed CORS + a wildcard origin is a serious vuln; verifying the
  config can't degrade to `*` is cheap insurance. (Deep-dive in Phase 7.)
- **Recommended solution:** Add a settings validator that rejects `*` when
  `allow_credentials=True`; document the POST-for-mutation convention in `API_REFERENCE.md`.
- **Acceptance criteria:** Startup fails if origins resolve to `*` with credentials on.
- **Effort:** Quick Win. **Type:** Quick Win.

### F2.8 — Composition root imports are eager and ordering-sensitive; some deferred imports inside functions · Priority: LOW · Quick Win
- **Location:** `backend/main.py` (top-level router imports; deferred `from backup.manager
  import ...`, `from jobs.worker import ...` inside lifespan; `from dependencies import
  require_user` inside middleware).
- **Description:** Mixed eager/deferred import strategy — deferred imports are used to break
  cycles and speed cold import. It works but obscures the dependency graph and hides import-time
  failures until runtime (e.g. the Procrastinate worker import is wrapped in a broad `except`).
- **Why it matters:** Ordering-sensitive composition roots are brittle; runtime-deferred imports
  can mask a broken module until the code path is first hit.
- **Recommended solution:** Document why each deferred import is deferred (cycle vs cold-start);
  where it's only for cold-start, hoist to module top. Ensure the worker-start `except` logs at
  `error` (it does — good) and surfaces to health.
- **Acceptance criteria:** Each in-function import has a one-line comment stating the reason.
- **Effort:** Quick Win. **Type:** Quick Win.

### F2.9 — DB access pattern: facade is good, but no repository/unit-of-work boundary · Priority: LOW · Architectural
- **Location:** `backend/db/*` (per-domain modules: `cve.py`, `correlation.py`, `enrichment.py`,
  …) called directly from routers; `database.py::get_db`/`write_audit_log`.
- **Description:** The `db/` package is a clean, well-named facade (`get_connection`, typed
  `DbConnection`, per-domain query modules). There is no explicit repository interface or
  unit-of-work/transaction boundary abstraction, so transaction scope is managed ad-hoc per call
  site. For most CRUD this is fine; for multi-write operations (ingest + enrich + correlate) it
  can lead to partial writes if not carefully wrapped.
- **Why it matters:** Data-integrity for multi-step writes depends on each call site remembering
  to open a transaction; there's no enforced boundary.
- **Evidence:** per-domain `db/*` modules invoked directly; no `UnitOfWork`/`@transactional`.
- **Recommended solution:** For the known multi-write flows (ingest pipeline, correlation
  materialization), introduce an explicit transaction context manager and route those flows
  through it. Keep single-read/single-write call sites as-is. Cross-reference Phase 4 (Data
  Integrity).
- **Acceptance criteria:** Multi-write flows execute in one transaction; a failure mid-flow
  leaves no partial rows (regression test).
- **Effort:** Medium. **Type:** Architectural.

### F2.10 — OpenAPI/docs disabled in production removes machine-readable contract · Priority: LOW · Quick Win
- **Location:** `backend/main.py` — `docs_url`/`redoc_url`/`openapi_url` set to `None` when
  `settings.is_production`.
- **Description:** Hiding interactive docs in prod is a reasonable hardening choice, but it also
  removes the OpenAPI JSON that external integrators / SDK generators need. There's no exported
  static OpenAPI artifact checked into the repo or docs.
- **Why it matters:** Enterprise consumers expect a stable machine-readable contract; without an
  exported spec, integration is guesswork and API drift is invisible.
- **Recommended solution:** Keep runtime docs off in prod, but add a build/CI step that exports
  `openapi.json` to `docs/` (or an artifact) and diff it in CI to catch unintended contract
  changes. Feeds F2.3 (versioning) and Phase 10 (API docs).
- **Acceptance criteria:** A committed/exported `openapi.json`; CI fails on undocumented contract
  drift.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Overall Score: **7 / 10**

| Sub-audit | Score |
|---|---|
| Backend Architecture | 7.5 / 10 |
| Frontend Architecture | 7 / 10 |
| Database Architecture | 6.5 / 10 |
| API Architecture | 6.5 / 10 |
| State Management | 7 / 10 |

## Strengths
- Clear composition-root → router → db-facade → pool layering; heavy work off the request path.
- Deliberate, documented middleware ordering (request-id contextvar outermost); backpressure via
  `PoolExhaustedError` → 503.
- Defense-in-depth auth intent (session middleware + per-route `require_user`/`require_admin`
  with live DB role re-read so demotions take effect immediately).
- Clean centralized frontend HTTP layer with token-refresh interceptor; abort-aware `useAsync`;
  code-splitting for admin/security routes; well-scoped contexts.

## Weaknesses
- Leaky dual-dialect DB layer with wrong default test dialect (F2.1).
- Two job systems mid-migration (F2.2); no API versioning (F2.3).
- No frontend server-cache layer (F2.4); `App.jsx` god-component (F2.5).
- RBAC-by-convention on admin prefixes (F2.6).

## Immediate Action Items
1. Add a startup test asserting every `/api/admin/*` route carries `require_admin` (F2.6).
2. Add settings validator forbidding `*` origins with credentialed CORS (F2.7).
3. Export/commit `openapi.json` and diff in CI (F2.10).
4. Decide and document the API-versioning policy; alias routes under `/api/v1/` (F2.3).

## Long-Term Recommendations
1. Make Postgres the default test dialect and push dialect divergence into the facade (F2.1).
2. Complete the APScheduler→Procrastinate migration behind a documented job registry (F2.2).
3. Introduce a frontend query cache and decompose `App.jsx` state (F2.4, F2.5).
4. Add explicit transaction boundaries for multi-write flows (F2.9).

## Production-Readiness Assessment (Phase 2 areas)
**Conditionally ready — 7/10.** The runtime architecture is sound and will serve current load.
The gaps are forward-compatibility and scale-of-maintenance issues: no API versioning (F2.3) is
the most consequential for a self-hosted, many-org product, and the dual-dialect/dual-scheduler
transitions (F2.1, F2.2) are the riskiest in-flight states. None block a single-tenant launch;
all should be resolved before committing to external API consumers or large-scale multi-org rollout.
