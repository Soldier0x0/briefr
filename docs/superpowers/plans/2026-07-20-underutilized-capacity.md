# Underutilized capacity utilization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully utilize BRIEFR capacity that is already built and **operator-enabled** (Procrastinate, embeddings, LLM extraction, correlation precompute, etc.) by adding durable execution, Admin visibility, Catch-up drain, FE surfaces, and hygiene — not by flipping `.env.example` defaults.

**Architecture:** Keep `api_queue` for HTTP pacing and APScheduler for cron triggers. Expand Procrastinate (`backend/jobs/`) as the durable work engine (already `PROCRASTINATE_ENABLED=1` on operator host). Add Admin outbound jobs UI over existing `GET /api/admin/jobs/outbound`. Enqueue LLM product extraction with bounded backoff on retryable DB errors. Widen Catch-up tick kicks. Surface semantic technique/campaign hits. Fix stack-backfill false auto-resume. Clean dead FE and misplaced `openpyxl`.

**Tech Stack:** FastAPI, Procrastinate 3.9.0, APScheduler, asyncpg/Postgres, React admin (design tokens + Radix), pytest, node:test, Alembic (no new broker).

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-07-20-underutilized-capacity-design.md`
- **Operator env assumption:** nearly all feature flags are **1**; disabled only Telegram / generic webhook secrets-URLs. Do **not** plan work as “enable flags from `.env.example`.” Do **not** read or commit operator `.env`.
- No Redis / RabbitMQ / Temporal / Flink.
- Do not replace `api_queue` pacing; do not raise `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` as the primary fix.
- Job ownership registry: APScheduler ids disjoint from `jobs:*` Procrastinate tasks; update `tests/test_job_ownership_registry.py` + `docs/SYSTEM_DESIGN.md` when adding tasks.
- Design-system tokens only in UI; Admin tables prefer shared `DataGrid` / existing admin table patterns.
- One wave ≈ one PR (`cursor/<wave>-91c2`); `./scripts/verify-local.sh` (or targeted pytest + `npm run build`) green before merge.
- Docs in same PR when runtime/API changes: `PRODUCT_STATUS.md`, `API_REFERENCE.md`, `HANDOVER.md`, `SYSTEM_DESIGN.md` as applicable.
- No graphify required for this program (operator: graphify index stale).

## File map

| Path | Responsibility |
|------|----------------|
| `backend/jobs/tasks.py` | Register new Procrastinate tasks |
| `backend/jobs/app.py` / `worker.py` | Unchanged gates; concurrency review only if needed |
| `backend/ml/product_extraction.py` | Split “run once” vs enqueue-friendly unit; retryable error detection |
| `backend/scheduler.py` | LLM job enqueues durable work; Catch-up tick kicks more jobs |
| `backend/db/outbound_jobs.py` | Optional filters (status/task) if Admin needs them |
| `backend/routers/admin/jobs.py` | Outbound list (+ optional health_ping defer) |
| `frontend/src/api.js` | `adminApi` outbound jobs helper |
| `frontend/src/pages/admin/OutboundJobsPanel.jsx` (new) | Admin Procrastinate job table |
| `frontend/src/pages/admin/SchedulerPage.jsx` or `ApiKeysPage.jsx` | Mount panel |
| `frontend/src/utils/hybridFeedSearch.js` | Stop dropping typed semantic hits |
| `backend/services/stack_backfill_worker.py` | Real delayed re-defer on rate-limit |
| `backend/catchup_mode.py` / Catch-up tick path | Kick additional enabled backlogs |
| `backend/requirements.txt` | Move `openpyxl` out of runtime if wave 6 |
| `docs/PRODUCT_STATUS.md`, `API_REFERENCE.md`, `HANDOVER.md`, `SYSTEM_DESIGN.md` | Runtime truth |

---

## Wave 1 — Admin outbound jobs panel

### Task 1: Frontend API client for outbound jobs

**Files:**
- Modify: `frontend/src/api.js`
- Test: `frontend/src/api.outboundJobs.test.js` (create) — or extend nearest admin api test pattern if one exists; else node:test on a small pure helper

**Interfaces:**
- Produces: `adminApi.listOutboundJobs({ limit?: number }) -> Promise<{ enabled: boolean, jobs: Array<...> }>`
- Consumes: existing `adminFetch` / admin request helpers in `api.js`

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/api.outboundJobs.test.js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// Prefer exporting a pure URL builder if fetch is hard to mock:
import { outboundJobsPath } from './apiOutboundJobs.js'

describe('outboundJobsPath', () => {
  it('includes limit query', () => {
    assert.equal(outboundJobsPath(50), '/api/admin/jobs/outbound?limit=50')
  })
  it('clamps limit to 1..200', () => {
    assert.equal(outboundJobsPath(0), '/api/admin/jobs/outbound?limit=1')
    assert.equal(outboundJobsPath(999), '/api/admin/jobs/outbound?limit=200')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/api.outboundJobs.test.js`  
Expected: FAIL module not found / export missing

- [ ] **Step 3: Minimal implementation**

Create `frontend/src/apiOutboundJobs.js`:

```js
export function outboundJobsPath(limit = 50) {
  const n = Math.max(1, Math.min(200, Number(limit) || 50))
  return `/api/admin/jobs/outbound?limit=${n}`
}
```

Wire `adminApi.listOutboundJobs` in `api.js` to GET that path with existing admin credentials handling.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/api.outboundJobs.test.js`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/apiOutboundJobs.js frontend/src/api.outboundJobs.test.js frontend/src/api.js
git commit -m "feat(admin): client helper for Procrastinate outbound jobs list"
```

### Task 2: OutboundJobsPanel UI

**Files:**
- Create: `frontend/src/pages/admin/OutboundJobsPanel.jsx`
- Create: `frontend/src/pages/admin/OutboundJobsPanel.test.js` (copy/format or empty-state helpers if extracted)
- Modify: `frontend/src/pages/admin/SchedulerPage.jsx` (preferred mount — next to JobTable) **or** `ApiKeysPage.jsx` under Durable jobs section
- Modify: `docs/API_REFERENCE.md` (note UI consumer), `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`

**Interfaces:**
- Consumes: `adminApi.listOutboundJobs`
- Produces: operator-visible table of `id, task_name, status, attempts, scheduled_at, queueing_lock`

- [ ] **Step 1: Write failing empty-state / copy test**

```js
// frontend/src/pages/admin/outboundJobsCopy.test.js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { outboundJobsEmptyMessage } from './outboundJobsCopy.js'

describe('outboundJobsEmptyMessage', () => {
  it('explains disabled flag', () => {
    assert.match(outboundJobsEmptyMessage({ enabled: false }), /PROCRASTINATE_ENABLED/i)
  })
  it('explains empty queue when enabled', () => {
    assert.match(outboundJobsEmptyMessage({ enabled: true }), /No durable jobs/i)
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

`cd frontend && node --test src/pages/admin/outboundJobsCopy.test.js`

- [ ] **Step 3: Implement copy + panel**

- Loading / empty / error / data four states (design-system).
- When `enabled: false`, show message (still relevant for other deploys).
- When enabled + jobs: mono table columns from allowlisted API fields only (no payloads).
- Refresh button; poll every 15s while Scheduler page visible (`useVisibilityAwareInterval` if practical).
- HelpTip: durable queue ≠ header `api_queue` pacing indicator.

- [ ] **Step 4: Mount on SchedulerPage (operator)**; `npm run build`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(admin): OutboundJobsPanel for Procrastinate job rows"
```

---

## Wave 2 — Durable LLM product extraction + bounded auto-retry

### Task 3: Retryable error classifier + ownership registry update

**Files:**
- Create: `backend/jobs/retry_policy.py`
- Create: `backend/tests/test_jobs_retry_policy.py`
- Modify: `backend/tests/test_job_ownership_registry.py` (after task 4 registers name — or update in task 4)

**Interfaces:**
- Produces:
  - `is_retryable_job_error(exc: BaseException) -> bool`
  - `next_retry_delay_seconds(attempt: int) -> int | None`  # None = give up
  - Constants: `RETRY_DELAYS_SECONDS = (180, 240, 300)`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/test_jobs_retry_policy.py
from jobs.retry_policy import is_retryable_job_error, next_retry_delay_seconds

class DatabaseError(Exception):
    pass

def test_timeout_message_is_retryable():
    assert is_retryable_job_error(DatabaseError("Database command timeout")) is True

def test_auth_error_not_retryable():
    assert is_retryable_job_error(RuntimeError("missing API key")) is False

def test_backoff_sequence():
    assert next_retry_delay_seconds(1) == 180
    assert next_retry_delay_seconds(2) == 240
    assert next_retry_delay_seconds(3) == 300
    assert next_retry_delay_seconds(4) is None
```

- [ ] **Step 2: Run FAIL** — `cd backend && pytest tests/test_jobs_retry_policy.py -q`

- [ ] **Step 3: Implement `jobs/retry_policy.py`** matching tests (match substring `command timeout` / `TimeoutError` / asyncpg timeout class names used in `db/errors.py`).

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(jobs): bounded retry policy for durable tasks"
```

### Task 4: Procrastinate task `jobs:llm_product_extraction`

**Files:**
- Modify: `backend/jobs/tasks.py`
- Modify: `backend/ml/product_extraction.py` (ensure callable without holding one DB conn across LLM HTTP — prefer existing `db=None` pool-scoped path)
- Modify: `backend/scheduler.py` `run_llm_extraction_sync` — enqueue instead of / in addition to inline run
- Modify: `backend/tests/test_job_ownership_registry.py` — add `llm_product_extraction`
- Modify: `docs/SYSTEM_DESIGN.md` ownership table
- Test: `backend/tests/test_llm_extraction_durable.py` (create)

**Interfaces:**
- Produces: `@blueprint.task(name="llm_product_extraction", queue="briefr")` async def taking optional `trigger: str = "scheduler"`
- `queueing_lock="llm_product_extraction"` so only one pending extraction tick
- On retryable failure: `defer_async` / Procrastinate retry with `schedule_in` per `next_retry_delay_seconds(attempts)`
- Consumes: `run_llm_product_extraction`, `retry_policy`, `outbound_context`

- [ ] **Step 1: Failing test — task registered + lock name**

```python
# backend/tests/test_llm_extraction_durable.py
from jobs.tasks import blueprint

def test_llm_extraction_task_registered():
    # Adapt to Procrastinate 3.9 blueprint introspection used elsewhere in repo
    names = {getattr(t, "name", None) for t in getattr(blueprint, "tasks", {}).values()} \
        if hasattr(blueprint, "tasks") else set()
    # Prefer AST approach like test_job_ownership_registry if blueprint API differs
    from tests.test_job_ownership_registry import _defined_procrastinate_tasks
    assert "llm_product_extraction" in _defined_procrastinate_tasks()
```

Update `DOCUMENTED_PROCRASTINATE_TASKS` to include `llm_product_extraction` in the same PR **after** adding the task (test drives registry).

- [ ] **Step 2: Implement task wrapper**

```python
# sketch in jobs/tasks.py
@blueprint.task(name="llm_product_extraction", queue="briefr")
async def llm_product_extraction_tick(*, trigger: str = "scheduler") -> dict:
    with outbound_context(actor_type="queue", queue_task="jobs:llm_product_extraction", trigger=trigger):
        return await run_llm_product_extraction()  # db=None path
```

Scheduler `run_llm_extraction_sync`: if Procrastinate enabled → `configure(queueing_lock="llm_product_extraction").defer_async(trigger="scheduler")` and treat `AlreadyEnqueued` as success; else keep today’s inline behavior.

On exception inside task: if `is_retryable_job_error(exc)` and delay := `next_retry_delay_seconds(attempts)` → re-defer with `schedule_in=timedelta(seconds=delay)` (use Procrastinate 3.9 schedule API already used in docs/tests if present; otherwise store next_run in job and let worker policy handle — verify against installed Procrastinate API in-tree tests before coding).

- [ ] **Step 3: pytest ownership + durable tests + targeted LLM tests**

`pytest tests/test_job_ownership_registry.py tests/test_llm_extraction_durable.py tests/test_llm_product_extraction.py -q`

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(jobs): durable llm_product_extraction with bounded retry"
```

### Task 5: Manual Retry enqueues durable job

**Files:**
- Modify: `backend/routers/admin/jobs.py` (run map for `llm_product_extraction`)
- Test: extend admin scheduler run tests if present

- [ ] When operator clicks Run / Retry on LLM job, prefer Procrastinate defer with `trigger="manual"` and higher priority if API allows.
- [ ] Commit: `feat(admin): manual LLM extraction run defers durable job`

---

## Wave 3 — Catch-up drains more enabled backlogs

### Task 6: Expand `run_catchup_tick` kicks

**Files:**
- Modify: `backend/scheduler.py` (`run_catchup_tick`)
- Modify: `backend/tests/test_catchup_tick.py`
- Modify: `docs/superpowers/specs/2026-07-20-catchup-mode-design.md` (note expanded drain) **or** PRODUCT_STATUS only if preferring no spec edit
- Modify: `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`

**Operator assumption:** embeddings, correlation precompute, LLM extraction, CPE catalog sync are **enabled** — tick should kick them (respect existing job locks / enabled gates).

- [ ] **Step 1: Failing test** — tick invokes kick helpers for embeddings, correlation precompute, and LLM extraction enqueue (mock/monkeypatch).

- [ ] **Step 2: Implement** sequential kicks with try/except per kick (one failure must not abort others); still no bypass of `api_queue`.

- [ ] **Step 3: PASS + commit** `feat(catchup): tick drains LLM extraction and CPE when enabled`

---

## Wave 4 — Semantic typed hits in FEED

### Task 7: Stop dropping technique/campaign hits

**Files:**
- Modify: `frontend/src/utils/hybridFeedSearch.js`
- Modify: `frontend/src/utils/hybridFeedSearch.test.js` (create/extend)
- Possibly `frontend/src/components/CVEFeed.jsx` for non-CVE result rendering

- [ ] **Step 1: Failing test** — hits with `entity_type` technique/campaign are not all filtered out; CVE hits still map via `semanticHitToCveCard`.

- [ ] **Step 2: Implement** either:
  - **A (minimal):** sectioned lists “CVEs” / “Techniques” / “Campaigns” in search results UI, or
  - **B:** keep CVE list + show count badge “+N related techniques/campaigns” with expandable rows.

Prefer **A** if CVEFeed structure allows with small diff; else **B**.

- [ ] **Step 3: `npm run build` + unit tests; commit** `feat(feed): surface semantic technique and campaign hits`

---

## Wave 5 — Stack backfill true auto-resume

### Task 8: Re-defer on rate-limit deferred status

**Files:**
- Modify: `backend/services/stack_backfill_worker.py`
- Modify: `backend/tests/test_stack_backfill_idempotency.py` (or new test)
- Modify: `backend/routers/stack_catalog.py` if kick helper needs `schedule_in`

- [ ] **Step 1: Failing test** — when worker sets deferred due to rate limit, a Procrastinate job is scheduled in the future (mock `defer_async` / `configure(schedule_in=...)`).

- [ ] **Step 2: Replace “will resume automatically” lie with actual `schedule_in` using retry_policy delays (or stack-specific 180s).

- [ ] **Step 3: PASS + commit** `fix(stack-backfill): actually schedule durable resume after rate limit`

---

## Wave 6 — FE dead-code + openpyxl hygiene

### Task 9: Remove or quarantine confirmed dead FE

**Files (delete only if zero importers confirmed by live `rg`):**
- Candidates: `frontend/src/pages/admin/shared/ActionProgress.jsx`, `RunningJobsPanel.jsx`, `OperatorSystemActions.jsx`, `adminListResponse.js`
- `frontend/src/theme/light-theme.css` if still unimported
- Orphan ARCH sections only with gate-test updates (`archTabRemovalGate` etc.)

- [ ] **Step 1:** `rg` importers; list in PR body.
- [ ] **Step 2:** Delete dead files; fix broken imports; update gates.
- [ ] **Step 3:** `npm run build`; commit `chore(fe): remove unused admin shared and theme dead weight`

### Task 10: Move openpyxl off runtime requirements

**Files:**
- Modify: `backend/requirements.txt` (remove openpyxl)
- Create or modify: `requirements-docs.txt` / `scripts/README.md` note for `generate_technical_inventory_xlsx.py`

- [ ] **Step 1:** Confirm `rg openpyxl backend` only requirements + corpus yaml.
- [ ] **Step 2:** Relocate pin; document `pip install openpyxl` for that script.
- [ ] **Step 3:** Commit `chore(deps): drop openpyxl from backend runtime requirements`

---

## Wave 7 — Ops polish

### Task 11: `health_ping` canary from Admin

**Files:**
- Modify: `backend/routers/admin/jobs.py` — `POST /api/admin/jobs/outbound/ping` (admin-only) defers `health_ping`
- Modify: OutboundJobsPanel — “Ping queue” button
- Tests: API 401/403/200; AlreadyEnqueued OK

### Task 12: Admin schema gaps for env-only flags

**Files:**
- Modify: `backend/config_schema.py` — add `CORRELATION_PRECOMPUTE_ENABLED` (and optionally detection-context flags) as Admin-visible booleans with `restart_required` as appropriate
- Modify: admin config GET merge
- Docs: PRODUCT_STATUS note

### Task 13: Docs drift cleanup

**Files:**
- `docs/planning/specs/durable-outbound-queue-and-stack-backfill.md` — tick shipped checkboxes or banner “shipped; see PRODUCT_STATUS”
- `docs/planning/SPRINT_2026-07.md` — reconcile encrypted SSOT / composer parked vs shipped
- `docs/HANDOVER.md` — newest entry for utilization program

---

## Verification matrix (per wave PR)

| Check | Command |
|-------|---------|
| Backend unit | `cd backend && pytest tests/<touched> -q` |
| Ownership | `pytest tests/test_job_ownership_registry.py -q` |
| Frontend | `cd frontend && npm run build` + touched `node --test` |
| Full gate | `./scripts/verify-local.sh` when practical |

## Out of scope (explicit)

- Telegram / generic webhook enablement
- Raising DB command timeout to 300s as primary strategy
- Full APScheduler → Procrastinate migration
- Temporal / Redis
- Graphify refresh (optional separate chore)

---

## Spec coverage self-review

| Design § | Tasks |
|----------|-------|
| Operator env assumption | Global constraints + Waves avoid “enable flag” work |
| Admin outbound UI | Tasks 1–2 |
| Durable LLM + retry | Tasks 3–5 |
| Catch-up drain | Task 6 |
| Typed semantic hits | Task 7 |
| Stack auto-resume | Task 8 |
| FE/deps hygiene | Tasks 9–10 |
| Canary + schema + docs | Tasks 11–13 |
| Non-goals | Out of scope section |

Placeholder scan: none intentional. Types/names: `llm_product_extraction`, `RETRY_DELAYS_SECONDS`, `outboundJobsPath`, `OutboundJobsPanel` consistent across tasks.
