# Durable outbound queue, API metering & stack-driven backfill

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Follow [`execution-playbook.md`](execution-playbook.md) for dual-DB tests and stop-and-replan triggers.

**Status:** Planning — awaiting maintainer activation (do not implement until sprint checkboxes are added and this spec is approved).  
**Created:** 2026-07-16  
**Goal:** Persist outbound API work across restarts, count every outbound call with attribution, then let operators declare a versioned stack and opt in to Tier-A historical CVE fetch without breaking existing ingest.

**Architecture:** PostgreSQL-backed jobs via **Procrastinate**; universal metering at `resilient_request`; CPE-seeded product catalog + stack UX; checkpointed **Tier A** backfill (NVD catalog + KEV + EPSS bulk) with deep enrichment left on existing schedulers.

**Tech stack:** FastAPI, asyncpg/Postgres, Procrastinate, existing `resilient_client` / `api_queue` pacing, React inventory UX, Alembic.

## Global constraints

- Production remains **Postgres-required**; SQLite stays test/dev fallback — any new SQL needs dual-path or Postgres-only with tests both ways per `CLAUDE.md`.
- **No RabbitMQ / Redis / Flink / Celery** for this program — durable queue = Postgres (Procrastinate).
- **Heavy work never on the request path** — Agree enqueues jobs; UI polls status.
- **Feature flags default off** until each phase is verified: `PROCRASTINATE_ENABLED`, `API_CALL_EVENTS_ENABLED`, `STACK_BACKFILL_ENABLED`.
- Keep in-memory `api_queue` for **pacing**; Procrastinate for **durable units of work**. Do not rip out domain pacing tables.
- Stack backfill **Agree = Tier A only** (NVD rows + CVSS from NVD + KEV flags + EPSS via bulk CSV). OTX / Sploitus / CIRCL / LLM / full correlation stay on existing capped schedulers (priority queue later, not blocking Agree).
- UPSERT into `cves` may only touch **NVD-owned columns** — never clobber `summary`, LLM products, `has_poc` operator state, etc. (mirror existing upsert guard patterns in `db/cve.py`).
- Secrets never in log message strings; use structured `extra` + existing redaction.
- Docs in the same PR when runtime/API changes: `PRODUCT_STATUS.md`, `API_REFERENCE.md`, `SYSTEM_DESIGN.md` as applicable.

---

## Problem (evidence from prod corpus 2026-07-16)

| Fact | Value |
|------|--------|
| Total CVEs | ~23,339 |
| Share published in 2026 | ~78% (18,135) |
| Share 2025+2026 | ~85% |
| Pre-2015 | &lt;1% (KEV / lastMod drip, not a year policy) |

Rolling `NVD_DAYS_BACK` ingest is fine for a threat feed; it is a **blind spot for legacy stack matching** (e.g. Java 8). Full NVD mirror is deferred; **inventory-driven Tier A backfill** is the fix.

---

## Non-goals

- Hand-maintained “all software + all versions” spreadsheet as source of truth (use **NVD CPE dictionary** sync + cache).
- Filling every dependent table (OTX, exploits, correlation campaigns) inside Agree.
- Replacing APScheduler cron jobs, inbound `rate_limit`, webhook SSRF, or auth with generic frameworks.
- Sidecar second Postgres for corpus dumps (optional curiosity only; not this program).

---

## File map (planned)

| Path | Responsibility |
|------|----------------|
| `backend/requirements.txt` | Add `procrastinate` (pin compatible with psycopg / Python 3.12) |
| `backend/jobs/` (new) | Procrastinate app, worker bootstrap, task modules |
| `backend/jobs/context.py` | contextvars: `actor_type`, `actor_id`, `job_id`, `run_id`, `trigger` |
| `backend/alembic/versions/0xx_*.py` | Procrastinate schema (or documented `procrastinate schema` apply) + `api_call_events` + catalog + backfill runs |
| `backend/resilient_client.py` | Meter every outbound attempt; read attribution contextvars |
| `backend/db/api_metering.py` (new) | Event insert + rollup/`last_called_at` helpers |
| `backend/tracking.py` | Keep rollups; stop being the only opt-in path (delegate from choke point) |
| `backend/feeds/cpe_catalog.py` (new) | CPE dictionary sync → `software_catalog` |
| `backend/db/stack_backfill.py` (new) | Run/checkpoint CRUD; ETA estimator |
| `backend/jobs/tasks/stack_backfill.py` | Per-product page fetch tasks |
| `backend/routers/stack.py` or extend me/stack routes | Catalog autocomplete, Agree, run status |
| `frontend` inventory / stack UI | Category, typeahead, version, gap banner, progress |
| Admin quota / API usage UI | Last call, actor breakdown, recent events |

---

## Phase overview (ship independently)

| Phase | PR theme | Delivers | Depends |
|-------|----------|----------|---------|
| **P0** | Procrastinate foundation | Durable jobs, worker, feature flag, admin “queue jobs” read | — |
| **P1** | Universal API metering | Every outbound call counted + attributed; UI quota refresh | P0 optional but preferred for `queue` actor |
| **P2** | CPE software catalog | Table + sync job + autocomplete API | — (can parallel P1) |
| **P3** | Stack UX + Tier A backfill | Versioned stack items, Agree, ETA, progress, checkpoints | P0 + P2 (+ P1 for honest call counts) |
| **P4** (optional) | EPSS file identity skip | `score_date`/SHA-256 skip + keep row-delta apply | Independent; small; can insert after P0 |

Deep correlation prioritization for stack CVE IDs = **follow-on**, not P3 exit criteria.

---

## Status model (shared)

### Outbound job / HTTP outcome → user status

| Outcome | Job / event state | UI copy |
|---------|-------------------|---------|
| 2xx + DB commit | `succeeded` | Done |
| 404 / client error (bad CPE) | `failed_terminal` | Not found — fix stack entry |
| 429 / paced | `deferred` until Retry-After / pacing window | Waiting on rate limit (source) |
| 5xx / network | retry then `on_hold` | Source down — on hold |
| Process crash | stalled → worker retry | Resuming… |

### Attribution (`actor_type`)

`user` | `job` | `queue` | `cli` | `system`

Set via contextvars at scheduler entry, request dependency, CLI main, Procrastinate task wrapper.

---

## Phase P0 — Procrastinate foundation

### Acceptance

- [ ] `procrastinate` dependency pinned; schema applied via Alembic or documented one-shot with migration note in `docs/POSTGRES.md`
- [ ] Worker can run in-process (dev) or documented systemd/sidecar command (prod) behind `PROCRASTINATE_ENABLED`
- [ ] Sample no-op / health task defer + complete survives process restart
- [ ] Flag off → **zero behavior change**
- [ ] Tests: defer → worker → success; stalled retry path smoke

### Task P0.1 — Dependency + app skeleton

**Files:** `backend/requirements.txt`, `backend/jobs/__init__.py`, `backend/jobs/app.py`, `backend/jobs/worker.py`

- [ ] Pin Procrastinate compatible with existing psycopg
- [ ] `App` connector uses `DATABASE_URL` (Postgres only when enabled; SQLite tests skip or use PG fixture)
- [ ] Document: SQLite CI does not run Procrastinate worker tests — use `postgres_migrations` marker

### Task P0.2 — Schema + feature flag

**Files:** Alembic migration, `backend/config_schema.py`, `backend/.env.example`, `docs/POSTGRES.md`

- [ ] Apply Procrastinate tables (prefer official schema migration approach)
- [ ] `PROCRASTINATE_ENABLED` default `0`
- [ ] Startup: if enabled, open app; optionally start worker task with bounded concurrency

### Task P0.3 — Context wrapper + admin read API

**Files:** `backend/jobs/context.py`, `backend/routers/admin.py` (or jobs admin), tests

- [ ] Helper `outbound_context(actor_type=..., job_id=..., ...)`
- [ ] `GET /api/admin/jobs/outbound` (or under existing scheduler page) lists recent Procrastinate jobs (allowlisted fields only)
- [ ] Commit

---

## Phase P1 — Universal outbound API metering

### Acceptance

- [ ] Every `resilient_request` attempt records: source, host/path class, status, latency, actor_type, job_id/run_id, request_id, ts
- [ ] Rollups + `last_called_at` per source update from the same path (not a second optional `record_api_call` only)
- [ ] CI/test guard: no new direct `httpx.AsyncClient` / `httpx.request` outside allowed modules (list in test)
- [ ] Admin quota UI shows used / limit / last call / breakdown by actor_type
- [ ] Retention job for events (e.g. 30 days); rollups retained
- [ ] Retries count **per HTTP attempt** (document in API_REFERENCE)

### Task P1.1 — Schema

**Files:** Alembic, `backend/db/api_metering.py`, `backend/db/init.py` if needed for SQLite stubs

```text
api_call_events (
  id,                          -- bigserial / uuid
  ts TIMESTAMPTZ NOT NULL,     -- always timestamptz (align with Alembic 026 style)
  source, pacing_key, method, host, path_template,
  status_code, ok, latency_ms,
  actor_type,                  -- user | job | queue | cli | system
  actor_id TEXT,               -- TEXT: user id, job id, or uuid — never typed as int-only
  job_id, run_id, queue_task, request_id, error_class
)
-- plus last_called_at TIMESTAMPTZ on api_usage or sync_state key per source
-- SQLite tests: store ts as ISO text; PG uses timestamptz
```

### Task P1.2 — Choke-point instrumentation

**Files:** `backend/resilient_client.py`, `backend/jobs/context.py`, `backend/tracking.py`

- [ ] After each attempt (success or final status), write event (async, failure to meter must not fail the HTTP caller — log warning)
- [ ] Update rollup counters (reuse flush pattern from `tracking.py`)
- [ ] Wire `job_log_context` / Procrastinate wrapper to set contextvars

### Task P1.3 — UI + docs

**Files:** Admin API keys / usage surfaces, `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

- [ ] Surface last call + actor breakdown
- [ ] Application log extras already carry job_id when present — verify sample
- [ ] Commit

---

## Phase P2 — CPE software catalog

### Acceptance

- [ ] `software_catalog` populated from NVD CPE 2.3 dictionary (scheduler job, not request path)
- [ ] Autocomplete `GET` after ≥3 characters (trigram or `ILIKE` + limit)
- [ ] Categories mapped (app / library / os / web_server / firewall / database / other) — curated mapping table or heuristics + override
- [ ] Versions: suggest from CPE version strings when present; **always allow free-typed version**
- [ ] Catalog sync is Procrastinate or APScheduler job; respects NVD pacing + metering

### Task P2.1 — Tables + sync

**Files:** Alembic, `backend/feeds/cpe_catalog.py`, scheduler or Procrastinate task

- [ ] Columns: `cpe_uri` (**PRIMARY KEY** or UNIQUE — required for idempotent incremental sync), `vendor`, `product`, `display_name`, `category`, `title`, `versions_json` (optional cache), `updated_at TIMESTAMPTZ`
- [ ] Sync incremental where possible; full refresh documented

### Task P2.2 — Autocomplete API + tests

**Files:** router, frontend API helper, pytest

- [ ] Rate-limit autocomplete modestly
- [ ] Empty / short query → 400 or empty list (no full table scan)

---

## Phase P3 — Stack UX + Tier A backfill

### Acceptance

- [ ] Operator can add multiple products with versions (mixed ages); categories expanded
- [ ] Save stack **always** succeeds locally without NVD
- [ ] Gap banner when corpus coverage for stack terms is shallow; **Agree** enqueues Tier A run
- [ ] Preflight ETA: products × estimated pages × NVD pacing (+ EPSS/KEV constants)
- [ ] Progress: per-product checkpoint; resume after crash; rate-limit defer; 5xx on_hold; 404 terminal per product
- [ ] Personalized ETA updates as pages complete
- [ ] Cap: max products / max CVEs / max runtime per run — overflow “continue later”
- [ ] On complete/partial: stack matching uses new rows; UI states deep intel is background
- [ ] `STACK_BACKFILL_ENABLED=0` → no Agree path

### ETA sketch (document in UI)

```text
nvd_calls ≈ Σ ceil(est_cves[p] / 2000)
nvd_eta   ≈ nvd_calls * paced_seconds   # ~50 req/30s with key
tier_A    ≈ nvd_eta + epss_bulk_eta + kev_eta
```

Show range (low/high). Without `NVD_API_KEY`, warn and use anonymous pacing or refuse large runs.

### Task P3.1 — Data model for stack items + runs

**Files:** Alembic, `user_preferences` / profile JSON evolution or `user_stack_items` table, `stack_backfill_runs`, `stack_backfill_checkpoints`

### Task P3.2 — Tier A worker tasks

**Files:** `backend/jobs/tasks/stack_backfill.py`, `backend/db/stack_backfill.py`, NVD CPE/keyword fetch helpers

- [ ] One Procrastinate job per product page or per product with internal paging + checkpoint
- [ ] UPSERT allowlist only
- [ ] After catalog pages: trigger/wait EPSS apply for new IDs (bulk CSV — prefer existing sync + filter); KEV flag match
- [ ] Never call OTX/Sploitus/CIRCL in this task

### Task P3.3 — Frontend

**Files:** inventory / stack components, CSS tokens only

- [ ] Typeahead product (≥3 chars), version suggest + free type
- [ ] Gap banner + Agree + progress (poll run status)
- [ ] Status copy for deferred / on_hold / not_found
- [ ] Browser verify: save without Agree; Agree small stack; kill worker mid-run → Resume

### Task P3.4 — Docs + PRODUCT_STATUS

- [ ] Document flags, quotas, Tier A vs background enrichment honesty
- [ ] Commit

---

## Phase P4 (optional) — EPSS file identity skip

### Acceptance

- [ ] Store `score_date` + SHA-256 of `epss_scores-current.csv.gz` after successful apply
- [ ] Matching identity → skip gunzip/parse/snapshot/update
- [ ] Keep existing row-delta `update_epss_scores`
- [ ] Force resync admin action clears stored identity
- [ ] Reusable helper pattern documented for other whole-file feeds (CTID CSV later)

---

## Error isolation (must not break existing)

| Failure | Existing feed / stack save |
|---------|----------------------------|
| Procrastinate disabled / down | App runs as today |
| Metering insert fails | HTTP path still succeeds; warning logged |
| Backfill fails mid-run | Prior checkpoints kept; no stack wipe; hourly NVD unchanged |
| Catalog sync fails | Autocomplete empty; free-text stack still works |

---

## Test matrix

| Phase | SQLite pytest | Postgres pytest | Other |
|-------|---------------|-----------------|-------|
| P0 | skip worker or mock | required | — |
| P1 | events to SQLite if table exists | required | httpx-outbound guard test |
| P2–P3 | API unit + mocked NVD | integration | `npm run build`; browser for P3 |
| Merge gate | `./scripts/verify-local.sh` | `--full` when PG available | |

---

## PR sequence (suggested)

1. **PR-Q1** — P0 Procrastinate foundation  
2. **PR-Q2** — P1 metering + admin UI  
3. **PR-Q3** — P2 CPE catalog + autocomplete  
4. **PR-Q4** — P3 stack UX + Tier A backfill  
5. **PR-Q5** (optional) — P4 EPSS identity skip  

Do not open P3 before P0+P2. P1 can land before or right after P0.

---

## Open questions (maintainer)

| # | Question | Default if unanswered |
|---|----------|------------------------|
| 1 | Procrastinate worker: in-process asyncio task vs separate systemd unit? | In-process when enabled for single-box deploy; document split worker as optional |
| 2 | Autocomplete catalog: full CPE sync vs “featured + search NVD live”? | Full CPE sync job + local autocomplete |
| 3 | Event retention days for `api_call_events`? | 30 days |
| 4 | Second Agree checkbox for “queue deep correlation”? | **No** in P3 — background only |
| 5 | Activate on sprint now or park until Forge path design merges? | Maintainer call |

---

## Related (out of scope here)

- Forge ATT&CK path navigator design: [`forge-attack-path-navigator-design.md`](forge-attack-path-navigator-design.md)  
- Full NVD corpus sidecar dump/merge  
- Replacing `api_queue` pacing with a generic limiter  

---

## Activation checklist

When maintainer activates:

- [ ] Add sprint checkboxes to `docs/planning/SPRINT_2026-07.md` (or next sprint) for PR-Q1…Q4  
- [ ] Add BACKLOG row linking this spec  
- [ ] Resolve open questions 1–5  
- [ ] Implement via subagent-driven-development / executing-plans — **one PR phase at a time**  
- [ ] Update `PRODUCT_STATUS.md` + `HANDOVER.md` as each PR merges  
