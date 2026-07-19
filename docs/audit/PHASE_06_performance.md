# PHASE 6 — Performance · DB Query Performance · Frontend · Backend · Scalability · Resource Utilization

*Reviewed at pinned commit `ff23c18a4925b3b7082a2b1d1600884324d90d02`. Backend FastAPI
(ORJSON + GZip + asyncpg pool), frontend React 19 + Vite, Postgres-native DB layer with 176
`CREATE INDEX` mentions across backend DB/migration files.*

---

## Executive Summary

Performance engineering remains **above-average and deliberate**. The backend uses
`ORJSONResponse`, `GZipMiddleware`, an asyncpg pool with explicit backpressure
(`PoolExhaustedError` → 503), and pushes heavyweight work into schedulers/jobs rather than request
handlers. Pool stats are exposed through health/support-pack paths. The hot CVE feed already has
the right primitive for chronological scale — keyset/cursor pagination on `published+cve_id` — and
the chart wrappers are lazy-loaded by their consumers.

The main gaps are still **defaults and measurement**. The CVE list handler defaults to
`page`/OFFSET unless `pagination=keyset` is supplied. `vite.config.js` still has no
`manualChunks`, chunk warning policy, or bundle budget; Recharts imports are static inside three
wrapper files even though those wrappers are lazy-loaded. Pool defaults remain `min_size=1` and
`DATABASE_POOL_SIZE=10`. A conservative AST scan now finds 30 `await execute/fetch` candidates
inside `for` loops in `backend/db/` (some are chunked/set-based false positives, but still require
triage). There is still no load test, perf budget, or query-latency regression gate. Horizontal
scale remains limited by process-local `read_cache` and `asyncio.Lock` scheduler ownership, though
the docs now provide multi-worker API-only guidance and Procrastinate exists for durable outbound
jobs.

**Overall Score: 7.2 / 10.**

---

## Findings

### F6.1 — Status: UPDATED — Feed pagination defaults to OFFSET; keyset is opt-in · Priority: MEDIUM · Architectural
- **Location:** `backend/routers/cves.py` list handler — `page: int = Query(default=1)`,
  `pagination` param defaulting to non-keyset (`offset=0, page=1` when `pagination != "keyset"`);
  keyset path via `_encode_feed_cursor`/`_decode_feed_cursor` (`cves.py:416-422, 723-766`).
- **Description:** The correct primitive (keyset on `published DESC, cve_id DESC`, backed by an
  index) exists, but the default code path is OFFSET. `OFFSET n` scans and discards `n` rows, so
  page 500 of a growing CVE feed does linearly more work each page — the classic deep-pagination
  cliff.
- **Why it matters:** The CVE feed is the highest-traffic surface and grows monotonically
  (thousands of new CVEs/year). Default OFFSET means the busiest endpoint gets slower over the
  product's lifetime precisely as the dataset grows.
- **Evidence:** `page: int = Query(default=1)`, `pagination` default `None`, `keyset_mode =
  (pagination or "").strip().lower() == "keyset"`, and final query still appends
  `LIMIT ? OFFSET ?`.
- **Recommended solution:** Make keyset the **default** for chronological browsing (the UI's infinite
  scroll / "next" should send the cursor); reserve OFFSET only for explicit "jump to page N" if that
  UI exists. Verify the covering index `(published DESC, cve_id DESC)` is present and used
  (`EXPLAIN`). Cap max OFFSET as a guardrail.
- **Acceptance criteria:** `EXPLAIN` on the default feed query shows an index scan with bounded
  work independent of page depth; the UI paginates via cursor.
- **Effort:** Medium. **Type:** Architectural.

### F6.2 — Status: UPDATED — Recharts wrappers are lazy-loaded, but no `manualChunks` or bundle budget exists · Priority: MEDIUM · Quick Win
- **Location:** static `from 'recharts'` in `briefVendorChartRecharts.jsx`,
  `opsChartsRecharts.jsx`, `resourcesChartsRecharts.jsx`; `frontend/vite.config.js` has no
  `build.rollupOptions.output.manualChunks`, no chunk-size warning tuning, no bundle-size CI check.
- **Description:** `recharts` is one of the largest common React deps. The app now uses a good split
  point: the three `*Recharts.jsx` wrappers import Recharts statically, while their consumers
  (`BriefCharts.jsx`, `ResourcesPage.jsx`, `OpsCharts.jsx`) use `React.lazy`. What is still missing
  is an explicit bundle contract: no `manualChunks`, chunk-size policy, or CI size budget.
- **Why it matters:** First-paint/time-to-interactive for the analyst dashboard depends on initial
  JS weight; an unbounded vendor chunk on a security wallboard (often on modest hardware/TVs) hurts.
- **Evidence:** 3 static Recharts wrapper imports; 3 lazy consumers; `vite.config.js` has no
  `build.rollupOptions.output.manualChunks`, no `chunkSizeWarningLimit`, and no bundle-size check.
- **Recommended solution:** (a) Confirm the `*Recharts.jsx` wrappers are consumed via `React.lazy`/
  dynamic import so recharts is a separate async chunk; (b) add `manualChunks` splitting vendor
  (react/router/radix/recharts) into named chunks; (c) add a CI bundle-size budget (e.g.
  `rollup-plugin-visualizer` output + a size-limit gate) so regressions fail. Build the frontend and
  record baseline chunk sizes.
- **Acceptance criteria:** recharts is in its own async chunk; CI fails if the main bundle exceeds
  the budget.
- **Effort:** Quick Win. **Type:** Quick Win.

### F6.3 — Status: UPDATED — Connection pool `min_size=1` and default `max=10` — burst latency + low ceiling · Priority: MEDIUM · Quick Win
- **Location:** `backend/db/connection.py:188-208` (`min_size=1`, `max_size=max(1,
  settings.database_pool_size)`); `backend/settings.py:36` (`database_pool_size: int = 10`).
- **Description:** With `min_size=1`, the pool holds a single warm connection idle; a traffic burst
  must establish connections on demand (TCP + auth + TLS latency per new connection) up to 10. Ten
  concurrent DB-bound requests is a modest ceiling for a multi-analyst deployment, and the
  cold-start cost shows up as p99 latency spikes.
- **Why it matters:** Backpressure (`PoolExhaustedError` → 503) is correct, but a low/cold pool makes
  503s and latency spikes more likely under normal concurrency for larger teams.
- **Evidence:** `asyncpg.create_pool(min_size=1, max_size=max(1, settings.database_pool_size))`;
  `Settings.database_pool_size = 10`; `get_pool_stats()` reports `min/max/idle/in_use` through
  health/support-pack paths.
- **Recommended solution:** Set `min_size` to a configurable warm floor (e.g. 2–4) so bursts hit
  warm connections; document `database_pool_size` sizing guidance vs Postgres `max_connections` and
  expected concurrency in `OPERATIONS.md`; export pool stats to the metrics surface, not only health.
- **Acceptance criteria:** Warm-connection floor configurable and defaulted >1; pool-utilization
  metric exposed; sizing guidance documented.
- **Effort:** Quick Win. **Type:** Quick Win.

### F6.4 — Status: UPDATED — Potential N+1: 30 `await execute/fetch` candidates inside `for` loops in the DB layer · Priority: MEDIUM · Architectural
- **Location:** AST heuristic scan of `backend/db/**` — 30 sites with `await …execute/fetch…` inside
  a `for`/`async for` loop (candidates in enrichment/correlation/cache/batch paths).
- **Description:** Per-row queries in a loop are the canonical N+1 pattern; at scale they turn one
  logical operation into hundreds of round-trips. Some of these are legitimately batched already
  (e.g. `feeds/extended.py` uses `IN (…)` placeholders), so this needs per-site confirmation.
- **Why it matters:** N+1 in nightly enrichment/correlation multiplies job runtime and DB load; in a
  request path it multiplies latency.
- **Evidence:** loop+await AST heuristic (30 matches); mitigated in several spots by `IN (…)`
  chunking or `executemany`, so this remains a triage queue rather than 30 confirmed bugs.
- **Recommended solution:** Audit each site; convert per-row queries to set-based `IN (…)` /
  `unnest($1::text[])` (Postgres) batch queries or `executemany`. Add a query-count assertion in
  tests for the hottest batch flows (fail if a fixed-size batch issues O(n) queries).
- **Acceptance criteria:** Batch flows issue O(1) queries for O(n) rows; a query-count test guards
  the ingest/enrich path.
- **Effort:** Medium. **Type:** Architectural.

### F6.5 — Status: OPEN — No load testing, perf budgets, or query-timing instrumentation · Priority: HIGH · Architectural
- **Location:** repo-wide — no `locust`/`k6`/`vegeta` scripts, no perf CI job, no per-endpoint
  latency budget; `docs/planning/specs/resource-benchmarking.md` explicitly parks synthetic load
  simulation and per-endpoint latency histograms.
- **Description:** Performance is currently a design property (good primitives) but not a measured or
  regression-gated one. There's no baseline for endpoint latency, no slow-query detection, and no
  load test proving the system's capacity or where it falls over.
- **Why it matters:** "Deployed to thousands of organizations" requires known capacity envelopes and
  regression protection; without measurement, a 10× slowdown in a hot query ships unnoticed until an
  operator complains.
- **Recommended solution:** (a) Add a lightweight load test (k6/locust) for the top endpoints (feed,
  stats, drawer bundle, IOC lookup) with target p95 budgets; run it in a scheduled/nightly CI job
  against a seeded Postgres. (b) Add slow-query logging (asyncpg `command_timeout` already set — log
  queries over a threshold). (c) Emit per-endpoint latency histograms via the metrics layer.
- **Acceptance criteria:** Documented p95 budgets per top endpoint; a load test enforces them;
  slow queries are logged with the request-id.
- **Effort:** Medium–Large. **Type:** Architectural.

### F6.6 — Status: UPDATED — Horizontal-scale ceiling from process-local caches & in-process scheduler locks · Priority: HIGH · Architectural (carries F3.1/F3.2)
- **Location:** `read_cache.py` (unbounded process-local dict), `scheduler_locks.py`
  (`asyncio.Lock`), `main.py` (scheduler started per process).
- **Description:** See Phase 3 F3.1/F3.2. From a performance/scalability lens: the app cannot be
  safely scaled horizontally for scheduler/ingest ownership without cluster-wide exclusion, and
  process-local caches still multiply cache state per worker. `OPERATIONS.md` now documents an
  API-only multi-worker pattern with exactly one scheduler owner, which is a useful mitigation but
  not a true multi-replica scheduler topology.
- **Why it matters:** These are the concrete blockers to answering "how do we serve more analysts?"
  with "add a replica."
- **Recommended solution:** Bound + optionally externalize the cache (Redis) and move scheduler
  exclusion to Postgres advisory locks / durable job ownership where appropriate; document the
  supported topology. Until then, keep the "one scheduler owner, N API-only workers" guidance and
  publish the measured capacity envelope from F6.5.
- **Acceptance criteria:** A documented, tested multi-replica topology with shared cache + durable
  locks; or an explicit single-node scaling statement with a measured capacity ceiling.
- **Effort:** Large. **Type:** Architectural.

### F6.7 — Status: UPDATED — Resource-utilization telemetry exists but no concrete autoscaling/limits guidance · Priority: LOW · Quick Win
- **Location:** `backend/resource_collector.py`, `backend/storage_metrics.py`,
  `backend/metrics/request_counter.py`, `db/resource_metrics.py`, admin ResourcesPage.
- **Description:** The product already samples resource metrics (a genuine strength — most tools
  don't), and `OPERATIONS.md` gives high-level concurrency guidance. What's still missing is
  concrete guidance/limits: recommended CPU/RAM/disk envelopes, container resource limits in
  `deploy/`, and what the resource-sampler job itself costs.
- **Why it matters:** Operators need capacity-planning numbers; unbounded resource use (e.g. the
  unbounded read cache, F3.1) shows up here first.
- **Recommended solution:** Document baseline resource envelopes (idle + under-load) in
  `OPERATIONS.md`; set container resource `limits`/`requests` in `deploy/` manifests; alert on the
  cache-size metric once F3.9 lands.
- **Acceptance criteria:** Documented resource envelopes; container limits set; memory alertable.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Status Table

| ID | Status | Note |
|---|---|---|
| F6.1 | UPDATED | Keyset exists; default feed path still uses OFFSET. |
| F6.2 | UPDATED | Recharts wrappers are lazy-loaded, but no bundle budget/manual chunks. |
| F6.3 | UPDATED | Pool stats exposed; `min_size=1`, default max 10 remain. |
| F6.4 | UPDATED | AST heuristic refreshed: 30 loop+await DB candidates. |
| F6.5 | OPEN | Load simulation and latency histograms remain out of scope/not implemented. |
| F6.6 | UPDATED | Multi-worker API-only guidance exists; scheduler/cache scale limits remain. |
| F6.7 | UPDATED | Resource telemetry exists; concrete CPU/RAM/disk limits still missing. |

## Overall Score: **7.2 / 10**

| Sub-audit | Score |
|---|---|
| Performance (general) | 7.5 / 10 |
| Database Query Performance | 7.4 / 10 |
| Frontend Performance | 7.7 / 10 |
| Backend Performance | 7.6 / 10 |
| Scalability | 5.8 / 10 |
| Resource Utilization | 7.2 / 10 |

## Strengths
- Fast serialization (ORJSON) + gzip + asyncpg pool with explicit backpressure (503 on exhaustion).
- 176 `CREATE INDEX` mentions across backend DB/migration files; keyset pagination primitive
  already implemented for the feed.
- Disciplined frontend code-splitting: heavy exporters (`jspdf`/`html2canvas`/`write-excel-file`)
  dynamically imported; Recharts wrappers consumed through `React.lazy`; abortable fetches.
- Heavy work kept off the request path; resource metrics and pool stats already sampled/exposed.

## Weaknesses
- OFFSET is the feed default (F6.1); no bundle budget/manual chunks (F6.2); cold/low pool (F6.3).
- Possible N+1 in batch flows (F6.4); no load testing / perf budgets / slow-query logging (F6.5).
- Horizontal-scale limited by process-local cache + in-process scheduler locks; API-only
  multi-worker guidance is a mitigation, not full cluster ownership (F6.6).

## Immediate Action Items
1. Make keyset the default feed pagination; verify the covering index with `EXPLAIN` (F6.1).
2. Add `manualChunks` + a CI bundle-size budget; keep Recharts in an async chunk (F6.2).
3. Raise pool `min_size` and document sizing (F6.3).

## Long-Term Recommendations
1. Stand up load testing with p95 budgets + slow-query logging + latency histograms (F6.5).
2. Externalize cache + durable locks to unlock horizontal scale (F6.6).
3. Eliminate confirmed N+1 with set-based queries + query-count tests (F6.4).
4. Publish resource envelopes and container limits (F6.7).

## Production-Readiness Assessment (Phase 6 areas)
**Ready for single-node; not for horizontal scale — 7.2/10.** The per-request performance primitives
are solid and a well-tuned single node will serve a substantial analyst team. The two real blockers
are (1) the absence of any measured capacity/regression gate (F6.5) — you can't sign off "fast" you
haven't measured — and (2) the horizontal-scale ceiling from process-local cache/locks (F6.6).
Make keyset the feed default (F6.1) before the CVE corpus grows further. Recommend: measure and
publish a single-node capacity envelope now; treat horizontal scale as a post-F6.6/F2.2 milestone.

## Resolved since last audit

- No F6.x findings are fully closed in this refresh. F6.2, F6.3, F6.6, and F6.7 have partial
  mitigations, but their acceptance criteria are not met.
