# Focused Audit — Idempotency & Exactly-Once Behavior

*Supplementary to the 11-phase engineering audit (README index). Scope: every path where a
duplicate trigger, a retry, or a crash-and-resume could cause double execution, double
counting, or a silently dropped side effect — scheduler jobs, the Procrastinate durable
outbound queue, webhook delivery, ingest upserts, and mutating HTTP endpoints. Refreshed from
pinned baseline `ff23c18a4925b3b7082a2b1d1600884324d90d02`; re-verified on current branch HEAD
`267f174b`.*

> Findings are written to be directly executable: concrete `file:line`, evidence, remediation
> with code sketch, acceptance criteria, effort, and Quick-Win/Architectural classification.
> Answers the outstanding recommendation in Phase 2 **F2.2** ("each job owned by exactly one
> system with a documented idempotency key").

> **Resolution status (2026-07-19 refresh):** every finding is dispositioned. **IDEM-A,
> IDEM-B, IDEM-C, IDEM-D — ✅ implemented** and re-verified against commits `89e8ee1c` /
> `1dfbad9f` plus current source. **IDEM-E — accepted** (no change). **IDEM-F — deferred**
> (non-goal until a versioned programmatic API). No open idempotency work remains.

---

## Executive Summary

BRIEFR is **mostly idempotent by design**, and in one place (webhook delivery) it is
textbook. The core ingest path is safe to re-run (`ON CONFLICT` upserts), scheduled jobs
cannot overlap within a process (`max_instances=1` + `coalesce=True`), the manual-refresh
endpoints share the *same* lock objects as the scheduled jobs, and notification/webhook
fan-out use atomic claim-before-send dedupe.

The prior weak surface, Tier-A **stack backfill**, is now idempotent at both enqueue and execution:
duplicate durable defers share a per-run `queueing_lock`, and duplicate/resumed/retried workers must
win `claim_run_running()` before advancing counters or checkpoints. The webhook crash-stranded
dedupe edge now self-heals in retention cleanup, and dual APScheduler/Procrastinate ownership is
documented and guarded.

The remaining two items are deliberate dispositions, not open bugs: IDEM-E accepts the
single-process check-then-acquire scheduler pattern because there is no `await` between check and
acquire and deployments use one scheduler owner; IDEM-F defers HTTP-level `Idempotency-Key` until a
retrying, versioned programmatic API exists.

**Idempotency posture score: 8.5 / 10.** No open double-run or silently-dropped-side-effect finding
remains in the audited surfaces. The score is not higher because the posture still depends on
documented single-owner scheduler operation and does not yet implement general HTTP idempotency keys.

---

## Strengths (idempotent by design — keep these patterns)

| Surface | Mechanism | Location |
|---------|-----------|----------|
| **Webhook delivery** | Atomic **claim-before-send** (`INSERT … ON CONFLICT DO NOTHING RETURNING`) + **rollback-on-failure** so a failed send can retry | `webhooks/engine.py:179`, `:236`; `db/webhooks.py:436` (`claim_webhook_destination_sent`) |
| **CVE ingest** | `upsert_cves` uses `ON CONFLICT(cve_id) DO UPDATE` — re-running any sync is safe | `db/cve.py:467`, `:30/:69/:157/:167` |
| **EPSS re-sync** | Q5 file-identity skip (sha256 + `score_date`) short-circuits an unchanged CSV; `sync_state` checkpoints | `feeds/file_identity.py`, `feeds/epss.py` |
| **Scheduled jobs** | `max_instances=1` + `coalesce=True` on every `add_job`; job-keyed `asyncio.Lock` in `scheduler_locks.py`; self-skip if locked | `scheduler.py:1901+`, `:299`; `scheduler_locks.py` |
| **Manual refresh vs scheduler** | `refresh_in_progress()` → `ingest_in_progress()` reads the **same** `scheduler_locks` locks, so a manual refresh 409s while a scheduled sync holds the lock | `routers/refresh.py:35`; `scheduler.py:274-284` |
| **Operator / user notifications** | `dedupe_key` with `UNIQUE(user_id, dedupe_key)`; normalized keys collapse digit-runs | `notifications/emit.py:203-228`; migration `015_user_notifications` |
| **Forge / correlation writes** | `ON CONFLICT(technique_id, cve_id)` / `ON CONFLICT(cve_id, actor_name)` upserts | `routers/forge.py:392`; `correlation/engine.py:181` |

---

## Findings

| ID | Status | Priority | Class | Current disposition |
|---|---|---:|---|---|
| IDEM-A | RESOLVED | MEDIUM | Quick Win | `claim_run_running()` is an atomic single-winner execution gate; stale `running` runs are reclaimable. |
| IDEM-B | RESOLVED | MEDIUM | Quick Win | Procrastinate defer uses per-run `queueing_lock`; `AlreadyEnqueued` is an idempotent no-op. |
| IDEM-C | RESOLVED | LOW–MEDIUM | Architectural | Background-job ownership registry + disjoint namespace test; duplicate execution contained by IDEM-A/B. |
| IDEM-D | RESOLVED | LOW | Quick Win | Daily retention cleanup purges only crash-stranded webhook dedupe claims. |
| IDEM-E | ACCEPTED | LOW | Quick Win | No change; safe under current single-process / single scheduler-owner assumptions. |
| IDEM-F | DEFERRED | LOW | Architectural | Non-goal until a versioned programmatic API with retrying clients exists. |

## Active dispositions

### IDEM-E — Manual-refresh guard is check-then-acquire, not an atomic acquire · Status: ACCEPTED (no change) · Priority: LOW · Quick Win
> **Disposition:** accepted as-is. Single-process asyncio has no `await` between the `.locked()` check and the acquire, so it is not a real TOCTOU today, and multi-process safety is already provided by the single-owner `BRIEFR_SCHEDULER_ENABLED` flag. Churning the scheduler hot paths for a cosmetic tightening isn't warranted; revisit only if the single-owner assumption is removed.

- **Location:** `backend/scheduler.py:298-301` — `run_nvd_incremental_sync` (and siblings) check
  `get_lock(...).locked()` and return, then acquire the lock later.
- **Description:** A check-then-act pattern. In single-process asyncio with no `await` between the
  check and the `async with lock`, this is effectively safe; it becomes a real TOCTOU only under
  multiple event loops / processes.
- **Why it matters:** Mostly cosmetic today because production pins a single scheduler owner
  (`BRIEFR_SCHEDULER_ENABLED`, Phase-3 I14/#444). Worth tightening if that guarantee ever relaxes.
- **Recommended solution:** Acquire non-blockingly and branch on the result instead of pre-checking:
  `if lock.locked(): return` → `acquired = lock.acquire()`-style non-blocking try, or wrap the whole
  body in `async with lock:` and rely on `max_instances=1` for the scheduled path.
- **Acceptance criteria:** No observable behavior change single-process; documented as multi-process
  safe once the owner-flag assumption is removed.
- **Effort:** Quick Win. **Type:** Quick Win.

### IDEM-F — No HTTP-level idempotency keys on mutating endpoints · Status: DEFERRED (non-goal) · Priority: LOW · Architectural (context)
> **Disposition:** deferred as a deliberate non-goal for the current single-operator, human-driven product. Mutations are already guarded by job-lock 409s and idempotent upserts. Adopt an `Idempotency-Key` convention only if/when a versioned programmatic API (Phase 2 F2.3) with retrying clients lands.

- **Location:** `routers/refresh.py:32+`, `routers/admin.py:2038` (`/feeds/epss/force-resync`),
  `routers/forge.py:300`, etc.
- **Description:** Mutating endpoints rely on job-lock 409s (`refresh_in_progress`) and idempotent
  upserts rather than client-supplied `Idempotency-Key` headers. A retrying/automated client that
  re-POSTs after a dropped response has no server-side dedupe beyond those guards.
- **Why it matters:** Fine for a single-operator self-hosted tool driven by a human UI; it matters if
  the API is ever consumed programmatically with retries (ties to Phase 2 **F2.3** API versioning).
- **Recommended solution:** Not needed now. If/when a versioned public API lands, adopt an
  `Idempotency-Key` convention on POST mutations backed by a short-TTL key store. Record as a
  deliberate non-goal until then.
- **Acceptance criteria:** N/A (documented decision).
- **Effort:** — **Type:** Architectural (deferred).

---

## Resolved since last audit

### IDEM-A — Stack backfill has no "already-running" guard → concurrent double-run · Status: RESOLVED · Priority: MEDIUM · Quick Win

- **Original risk:** overlapping `_process(run_id)` invocations could both set a run to `running`,
  fetch the same NVD pages, and double-count `cves_upserted` / checkpoint progress.
- **Fix confirmed:** commit `89e8ee1c` added `db.stack_backfill.claim_run_running()`, a conditional
  `UPDATE` that wins only when the run is non-terminal and not freshly `running`; stale `running`
  runs are reclaimable after `STACK_BACKFILL_STALE_SECONDS` (default 900s).
- **Current evidence:** `services/stack_backfill_worker.py` returns `already_running` when the claim
  loses; `tests/test_stack_backfill_idempotency.py` covers first-claim-wins, fresh-running loses,
  stale-running reclaims, and terminal runs do not reclaim.

### IDEM-B — Procrastinate defer carries no `queueing_lock` → duplicate pending jobs · Status: RESOLVED · Priority: MEDIUM · Quick Win

- **Original risk:** repeated Agree/Resume clicks could enqueue multiple pending
  `jobs:stack_backfill` rows for the same `run_id`.
- **Fix confirmed:** commit `89e8ee1c` changed `_kick_backfill()` to call
  `stack_backfill_tick.configure(queueing_lock=f"stack_backfill:{run_id}").defer_async(...)` and to
  treat `AlreadyEnqueued` as a no-op without falling back to in-process execution.
- **Current evidence:** `routers/stack_catalog.py` still carries the per-run queueing lock; the
  structural guard is asserted in `tests/test_stack_backfill_idempotency.py`.

### IDEM-C — Dual job systems can double-run a backfill across the enabled/disabled boundary · Status: RESOLVED · Priority: LOW–MEDIUM · Architectural

- **Original risk:** a durable Procrastinate job plus an in-process fallback task could both advance
  the same run across a `PROCRASTINATE_ENABLED` flip.
- **Fix confirmed:** commit `1dfbad9f` added the Background-job ownership registry in
  `docs/SYSTEM_DESIGN.md` and `tests/test_job_ownership_registry.py`, which keeps APScheduler and
  Procrastinate namespaces disjoint and documents each durable task's idempotency key.
- **Current evidence:** execution-level duplication is contained by IDEM-A and duplicate enqueues by
  IDEM-B; `jobs:stack_backfill` remains documented with `queueing_lock` + `claim_run_running`.

### IDEM-D — Webhook "stuck claim" on crash between claim-commit and clear · Status: RESOLVED · Priority: LOW · Quick Win

- **Original risk:** a crash after dedupe claim commit but before HTTP send/failure cleanup could
  permanently suppress that `(destination_id, event_type, dedupe_key)` alert.
- **Fix confirmed:** commit `1dfbad9f` added `db.cache_retention.purge_stranded_webhook_dedupe()` and
  wired it into `run_retention_cleanup()`.
- **Current evidence:** the sweep deletes only claims older than the 1h grace window, still within
  delivery-log retention, and with no successful delivery-log row; `tests/test_webhook_dedupe_stranded.py`
  covers stranded vs delivered vs mid-flight vs ancient claims.

---

## Immediate action items (ranked)

1. ~~**IDEM-A** — atomic run claim on stack backfill~~ ✅ **done** (`claim_run_running`).
2. ~~**IDEM-B** — `queueing_lock` on the backfill defer~~ ✅ **done**.
3. ~~**IDEM-D** — sweep crash-stranded `webhook_destination_dedupe` claims~~ ✅ **done** (`purge_stranded_webhook_dedupe`).
4. ~~**IDEM-C** — job-ownership registry + disjoint-namespace test (satisfies F2.2)~~ ✅ **done**.
5. **IDEM-E / IDEM-F** — accepted / deferred; revisit only if the single-process / single-operator assumptions relax.

## Long-term

- Adopt the webhook `IDEM-001` claim-before-act pattern as the **standard** for every future
  durable task; add it to the job-registry doc F2.2 asks for.
- When Phase 2/6 externalize locking (Redis / Postgres advisory locks, F3.1/F6.6), migrate the
  in-process `asyncio.Lock` scheduler exclusion and the IDEM-A run claim onto it in one pass so
  multi-process deployments inherit exactly-once for free.
