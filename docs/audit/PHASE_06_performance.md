# PHASE 6 — Performance · DB Query Performance · Frontend · Backend · Scalability · Resource Utilization

*Reviewed at commit `61c686f`. Backend FastAPI (ORJSON + GZip + asyncpg pool), frontend
React 19 + Vite, Postgres with ~250 index definitions.*

---

## Executive Summary

Performance engineering here is **above-average and deliberate**. The backend uses
`ORJSONResponse` (fast serialization), `GZipMiddleware` (min 256 bytes), an asyncpg connection
pool with explicit backpressure (`PoolExhaustedError` → 503), and pushes all heavy work
(ML/enrichment/LLM/correlation) into the scheduler off the request path. The schema is
**well-indexed** (~250 `CREATE INDEX` across migrations + `db/init.py`). The hot CVE feed already
supports **keyset/cursor pagination** (`pagination=keyset`, base64 `published+cve_id` cursor) —
the correct primitive for a chronological feed at scale. The frontend shows real discipline:
**heavy dependencies are dynamically imported** (`jspdf`, `html2canvas`, `write-excel-file`, the
PDF/XLSX exporters all lazy-load), routes use `React.lazy` (5 split points), and `useAsync`
aborts in-flight requests.

The gaps are **scale-ceiling and measurement** issues: (1) keyset pagination exists but is
**opt-in** — the feed defaults to `page`/OFFSET, which degrades on deep pages of a large CVE
corpus; (2) **`recharts` (a heavy chart lib) is imported statically** in chart wrappers and there's
**no `manualChunks`/bundle budget** in `vite.config.js`, so the vendor chunk is unbounded and
unmeasured; (3) the connection pool `min_size=1` (default `max=10`) means burst latency from
cold-connection establishment and a low concurrency ceiling; (4) ~20 `await execute/fetch` calls
sit inside `for` loops in `db/` (potential N+1); (5) **no load/performance testing or perf budgets
exist** anywhere — performance is asserted, not measured. Plus the process-local unbounded caches
and in-process scheduler locks from Phase 3 (F3.1/F3.2) are the dominant horizontal-scale limits.

**Overall Score: 7 / 10.**

---

## Findings

### F6.1 — Feed pagination defaults to OFFSET; keyset is opt-in · Priority: MEDIUM · Architectural
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
- **Evidence:** `page`/`offset` default branch in the list handler; keyset gated behind
  `pagination=keyset`.
- **Recommended solution:** Make keyset the **default** for chronological browsing (the UI's infinite
  scroll / "next" should send the cursor); reserve OFFSET only for explicit "jump to page N" if that
  UI exists. Verify the covering index `(published DESC, cve_id DESC)` is present and used
  (`EXPLAIN`). Cap max OFFSET as a guardrail.
- **Acceptance criteria:** `EXPLAIN` on the default feed query shows an index scan with bounded
  work independent of page depth; the UI paginates via cursor.
- **Effort:** Medium. **Type:** Architectural.

### F6.2 — `recharts` imported statically; no `manualChunks` or bundle budget · Priority: MEDIUM · Quick Win
- **Location:** static `from 'recharts'` in `briefVendorChartRecharts.jsx`,
  `opsChartsRecharts.jsx`, `resourcesChartsRecharts.jsx`; `frontend/vite.config.js` has no
  `build.rollupOptions.output.manualChunks`, no chunk-size warning tuning, no bundle-size CI check.
- **Description:** `recharts` is one of the largest common React deps (~hundreds of KB). It's
  loaded via `*Recharts.jsx` wrapper files (a good split point) but imported statically there; unless
  every consumer lazy-imports those wrappers, recharts lands in the main/vendor chunk. With no
  `manualChunks` and no size budget, total bundle size is unmeasured and can regress silently.
- **Why it matters:** First-paint/time-to-interactive for the analyst dashboard depends on initial
  JS weight; an unbounded vendor chunk on a security wallboard (often on modest hardware/TVs) hurts.
- **Evidence:** static recharts imports; no build/chunk config in `vite.config.js`.
- **Recommended solution:** (a) Confirm the `*Recharts.jsx` wrappers are consumed via `React.lazy`/
  dynamic import so recharts is a separate async chunk; (b) add `manualChunks` splitting vendor
  (react/router/radix/recharts) into named chunks; (c) add a CI bundle-size budget (e.g.
  `rollup-plugin-visualizer` output + a size-limit gate) so regressions fail. Build the frontend and
  record baseline chunk sizes.
- **Acceptance criteria:** recharts is in its own async chunk; CI fails if the main bundle exceeds
  the budget.
- **Effort:** Quick Win. **Type:** Quick Win.

### F6.3 — Connection pool `min_size=1` and default `max=10` — burst latency + low ceiling · Priority: MEDIUM · Quick Win
- **Location:** `backend/db/connection.py:188-208` (`min_size=1`, `max_size=max(1,
  settings.database_pool_size)`); `backend/settings.py:36` (`database_pool_size: int = 10`).
- **Description:** With `min_size=1`, the pool holds a single warm connection idle; a traffic burst
  must establish connections on demand (TCP + auth + TLS latency per new connection) up to 10. Ten
  concurrent DB-bound requests is a modest ceiling for a multi-analyst deployment, and the
  cold-start cost shows up as p99 latency spikes.
- **Why it matters:** Backpressure (`PoolExhaustedError` → 503) is correct, but a low/cold pool makes
  503s and latency spikes more likely under normal concurrency for larger teams.
- **Recommended solution:** Set `min_size` to a warm floor (e.g. 2–4) so bursts hit warm
  connections; document `database_pool_size` sizing guidance vs Postgres `max_connections` and
  expected concurrency in `OPERATIONS.md`. Expose pool stats (already available via
  `get_pool_stats`) as a metric so operators can tune.
- **Acceptance criteria:** Warm-connection floor configurable and defaulted >1; pool-utilization
  metric exposed; sizing guidance documented.
- **Effort:** Quick Win. **Type:** Quick Win.

### F6.4 — Potential N+1: ~20 `await execute/fetch` inside `for` loops in the DB layer · Priority: MEDIUM · Architectural
- **Location:** heuristic scan of `backend/db/**` — ~20 sites with `await …execute/fetch…` inside a
  `for` loop (candidates in enrichment/correlation/batch paths).
- **Description:** Per-row queries in a loop are the canonical N+1 pattern; at scale they turn one
  logical operation into hundreds of round-trips. Some of these are legitimately batched already
  (e.g. `feeds/extended.py` uses `IN (…)` placeholders), so this needs per-site confirmation.
- **Why it matters:** N+1 in nightly enrichment/correlation multiplies job runtime and DB load; in a
  request path it multiplies latency.
- **Evidence:** loop+await heuristic (20 matches); mitigated in some spots by `IN (…)` batching.
- **Recommended solution:** Audit each site; convert per-row queries to set-based `IN (…)` /
  `unnest($1::text[])` (Postgres) batch queries or `executemany`. Add a query-count assertion in
  tests for the hottest batch flows (fail if a fixed-size batch issues O(n) queries).
- **Acceptance criteria:** Batch flows issue O(1) queries for O(n) rows; a query-count test guards
  the ingest/enrich path.
- **Effort:** Medium. **Type:** Architectural.

### F6.5 — No load testing, perf budgets, or query-timing instrumentation · Priority: HIGH · Architectural
- **Location:** repo-wide — no `locust`/`k6`/`vegeta` scripts, no perf CI job, no per-endpoint
  latency budget; `structured_logging`/`metrics/request_counter.py` exist but no query-timing or
  slow-query log surfaced.
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

### F6.6 — Horizontal-scale ceiling from process-local caches & in-process scheduler locks · Priority: HIGH · Architectural (carries F3.1/F3.2)
- **Location:** `read_cache.py` (unbounded process-local dict), `scheduler_locks.py`
  (`asyncio.Lock`), `main.py` (scheduler started per process).
- **Description:** See Phase 3 F3.1/F3.2. From a performance/scalability lens: the app cannot be
  safely scaled horizontally for throughput without (a) a shared cache (else N× upstream/DB load and
  inconsistent reads) and (b) cluster-wide job exclusion (else duplicate ingest). Vertical scaling
  (bigger box, more workers) is also limited because the cache/locks are per-process, not per-host.
- **Why it matters:** These are the concrete blockers to answering "how do we serve more analysts?"
  with "add a replica."
- **Recommended solution:** Bound + optionally externalize the cache (Redis) and move exclusion to
  Postgres advisory locks / Procrastinate (Phase 2 F2.2), then document a supported horizontal-scale
  topology. Until then, publish the single-node capacity envelope from F6.5.
- **Acceptance criteria:** A documented, tested multi-replica topology with shared cache + durable
  locks; or an explicit single-node scaling statement with a measured capacity ceiling.
- **Effort:** Large. **Type:** Architectural.

### F6.7 — Resource-utilization telemetry exists but no autoscaling/limits guidance · Priority: LOW · Quick Win
- **Location:** `backend/resource_collector.py`, `backend/storage_metrics.py`,
  `backend/metrics/request_counter.py`, `db/resource_metrics.py`, admin ResourcesPage.
- **Description:** The product already samples resource metrics (a genuine strength — most tools
  don't). What's missing is guidance/limits: recommended CPU/RAM/disk envelopes, container
  resource limits in `deploy/`, and what the resource-sampler job itself costs.
- **Why it matters:** Operators need capacity-planning numbers; unbounded resource use (e.g. the
  unbounded read cache, F3.1) shows up here first.
- **Recommended solution:** Document baseline resource envelopes (idle + under-load) in
  `OPERATIONS.md`; set container resource `limits`/`requests` in `deploy/` manifests; alert on the
  cache-size metric once F3.9 lands.
- **Acceptance criteria:** Documented resource envelopes; container limits set; memory alertable.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Overall Score: **7 / 10**

| Sub-audit | Score |
|---|---|
| Performance (general) | 7.5 / 10 |
| Database Query Performance | 7.5 / 10 |
| Frontend Performance | 7.5 / 10 |
| Backend Performance | 7.5 / 10 |
| Scalability | 5.5 / 10 |
| Resource Utilization | 7 / 10 |

## Strengths
- Fast serialization (ORJSON) + gzip + asyncpg pool with explicit backpressure (503 on exhaustion).
- ~250 indexes; keyset pagination primitive already implemented for the feed.
- Disciplined frontend code-splitting: heavy exporters (`jspdf`/`html2canvas`/`write-excel-file`)
  dynamically imported; `React.lazy` route splits; abortable fetches.
- Heavy work kept off the request path; resource metrics already sampled.

## Weaknesses
- OFFSET is the feed default (F6.1); recharts static + no bundle budget (F6.2); cold/low pool (F6.3).
- Possible N+1 in batch flows (F6.4); no load testing / perf budgets / slow-query logging (F6.5).
- Horizontal-scale blocked by process-local cache + in-process locks (F6.6).

## Immediate Action Items
1. Make keyset the default feed pagination; verify the covering index with `EXPLAIN` (F6.1).
2. Add `manualChunks` + a CI bundle-size budget; confirm recharts is an async chunk (F6.2).
3. Raise pool `min_size` and document sizing (F6.3).

## Long-Term Recommendations
1. Stand up load testing with p95 budgets + slow-query logging + latency histograms (F6.5).
2. Externalize cache + durable locks to unlock horizontal scale (F6.6).
3. Eliminate confirmed N+1 with set-based queries + query-count tests (F6.4).
4. Publish resource envelopes and container limits (F6.7).

## Production-Readiness Assessment (Phase 6 areas)
**Ready for single-node; not for horizontal scale — 7/10.** The per-request performance primitives
are solid and a well-tuned single node will serve a substantial analyst team. The two real blockers
are (1) the absence of any measured capacity/regression gate (F6.5) — you can't sign off "fast" you
haven't measured — and (2) the horizontal-scale ceiling from process-local cache/locks (F6.6).
Make keyset the feed default (F6.1) before the CVE corpus grows further. Recommend: measure and
publish a single-node capacity envelope now; treat horizontal scale as a post-F6.6/F2.2 milestone.
