# Resource Benchmarking — BRIEFR + PostgreSQL utilization telemetry

**Status:** Plan of record — **no implementation in this document**
**Date:** 2026-07-11
**Audit basis:** direct trace — no continuous resource sampling exists today (no psutil
in the app, no metrics-history table; admin has ops charts for job durations and
static storage/DB sizes only).

**Execution:** per [`execution-playbook.md`](execution-playbook.md). Two PRs (RB-1, RB-2).

**Goal:** answer, from the admin panel, with real data: what does BRIEFR + Postgres
actually consume — CPU, RAM, disk IOPS, requests, DB transactions — per minute, with
peak / average / low over 1 / 3 / 7 / 30-day windows.

**Explicitly NOT in scope:**
- Synthetic load simulation (Option 2 from planning discussion — separate dev-only
  script if ever needed; build only when a capacity-projection question actually exists)
- Prometheus/Grafana/OpenTelemetry exporters (self-hosted single box; admin page is
  the consumer)
- Per-endpoint latency histograms (revisit only if the collected data shows a problem
  worth localizing)
- Alerting thresholds (data first; alerts are a later, evidence-driven decision)

---

## 1. Design

### 1.1 Scope of measurement

Process-tree scoped, not whole-machine: the BRIEFR process tree (uvicorn worker(s) +
scheduler) and local PostgreSQL processes, discovered via `psutil`. Two system-wide
context gauges (total CPU %, total RAM %) ride along per sample so contention from
*other* software is distinguishable from BRIEFR's own footprint.

**Honest limitation (recorded up front):** if Postgres runs in a container or on
another host, psutil cannot see its processes — process metrics for PG go NULL and the
page says so; `pg_stat_*` SQL metrics (transactions, blocks, cache ratio, DB size)
keep working regardless. UI labels the two groups separately so this degradation is
visible, not silent.

### 1.2 Collector

One scheduler job, `resource_metrics_sample`, every 60 s:

- **New job id → danger zone 2:** the id must be added to the scheduler-lock mapping
  in `routers/admin.py` in the same PR.
- Runs only in the scheduler-enabled replica (`BRIEFR_SCHEDULER_ENABLED`) — API-only
  replicas never sample (their utilization is visible from the process tree anyway
  when co-located; multi-host replicas are out of scope like remote PG).
- psutil reads: per-tree CPU %, RSS, cumulative disk read/write bytes + op counts.
  Rates (IOPS, bytes/s) are **deltas between consecutive samples**, computed by the
  collector, which keeps the previous cumulative values in memory. First sample after
  process start stores NULL rates — never a garbage spike.
- Request count: an in-process counter incremented by the existing request middleware,
  read-and-reset each sample. Counter lives in the API process; on multi-worker
  deployments each worker counts its own and the collector sums visible trees.
  <!-- ponytail: in-memory counter, lost on restart — a gap of ≤60s of request counts
       is acceptable; durable counters are not worth a table write per request -->
- Postgres (only when `DATABASE_URL` is PG): one query against `pg_stat_database` for
  the BRIEFR database — `xact_commit`, `xact_rollback`, `blks_read`, `blks_hit`,
  `tup_returned`, DB size. Deltas computed the same way; cache-hit % derived
  (`blks_hit / (blks_hit + blks_read)` over the delta).
- Disk free bytes on the data volume.

Budget: one psutil scan + one PG stats query per minute — milliseconds of work,
scheduler-side, nothing on the request path (danger zone 6).

### 1.3 Storage

`resource_metrics` — one row per sample:

```
ts (PK), briefr_cpu_pct, briefr_rss_bytes, briefr_io_read_bps, briefr_io_write_bps,
briefr_iops_r, briefr_iops_w, pg_cpu_pct, pg_rss_bytes, pg_iops_r, pg_iops_w,
req_count, pg_xact_per_min, pg_blks_read_per_min, pg_cache_hit_pct,
pg_db_size_bytes, disk_free_bytes, sys_cpu_pct, sys_mem_pct
```

- ~1,440 rows/day; pruned at **30 days** by the existing retention-job pattern
  (~43k rows steady state — no aggregation tables, no rollups; a 7-day window scan is
  ~10k rows and trivially fast).
- Forward-only Alembic + `db/init.py` SQLite parity (danger zone 1: test both ways).
  On SQLite all `pg_*` SQL-derived columns are NULL; psutil columns work everywhere
  including Windows dev.

### 1.4 API (read-only, admin auth)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/admin/resources?window=1d\|3d\|7d\|30d` | Series + summary |

Response: `{ "series": [...], "summary": { "<metric>": { "peak": x, "peak_at": ts,
"avg": x, "low": x } } }`. Series is downsampled server-side to ≤ 500 points per
metric (bucket-average, peak preserved per bucket) so the 30-day window doesn't ship
43k rows to the browser. Summary computed over raw rows, not the downsampled series —
peaks are real peaks.

### 1.5 Admin page

New admin section **RESOURCES** (existing admin shell, sidebar, tokens):

- Window selector: 1d / 3d / 7d / 30d (URL `?p=resources&window=7d` — deep-linkable,
  matches admin `?p=` pattern).
- Chart.js via existing `chartLoader.js` — trend lines for: BRIEFR CPU / PG CPU
  (one chart, two series), RAM (same pairing), disk IOPS r+w, requests/min,
  PG transactions/min, PG cache-hit %, disk free.
- Stat cards per chart: **peak (with timestamp), average, low** over the window —
  drill-through rule from the TM spec applies: every number is a real aggregate of
  visible rows, no composite scores.
- Every metric label carries a HelpTip explaining exactly what is measured and what
  is excluded (e.g. "BRIEFR process tree only — not system-wide; see SYS CPU for
  context"). PRODUCT.md principle 1.
- Designed empty/degraded states: fresh install (< 1 h of data), SQLite dev mode
  ("Postgres metrics unavailable — SQLite fallback"), remote-PG mode (process metrics
  NULL, SQL metrics live).

---

## 2. Implementation phases

### RB-1 — Table + collector + retention

- `psutil` pinned in `requirements.txt` (the one new dependency)
- Alembic migration + `db/init.py` parity for `resource_metrics`
- Middleware request counter; collector job + scheduler-lock mapping entry
  (`routers/admin.py`, danger zone 2); retention prune wired into the existing
  retention job pattern
- Tests: delta math (including restart → NULL-rate first sample), SQLite NULL
  `pg_*` columns, both-DB runs
- Acceptance: after two collector ticks on a dev server, `resource_metrics` has rows
  with non-NULL rates; job visible with lock in admin scheduler page; pytest green
  both ways

### RB-2 — API + admin Resources page

- `GET /api/admin/resources` with downsampling + raw-row summary
- Admin RESOURCES page per §1.5
- Docs same PR: `API_REFERENCE.md`, `PRODUCT_STATUS.md`, `SYSTEM_DESIGN.md`
- Acceptance: browser-verified 1d/3d/7d/30d switching; peak card timestamp matches a
  real sample row; degraded states render designed messages (verify SQLite mode);
  `npm run build` green; UI verification walk per playbook §3

---

## 3. Open questions

| # | Question | Default if silent |
|---|----------|-------------------|
| Q1 | Sample interval 60 s enough? | **Yes** — optimization decisions need trends, not sub-minute spikes; interval env-tunable (`RESOURCE_SAMPLE_INTERVAL_SECONDS`) |
| Q2 | Retention 30 d enough? | **Yes** — matches the longest window; env-tunable via existing retention config pattern |
| Q3 | Where in admin nav? | **New RESOURCES entry under the ops group**, beside Storage — not merged into Overview (Overview is posture, this is analysis) |
