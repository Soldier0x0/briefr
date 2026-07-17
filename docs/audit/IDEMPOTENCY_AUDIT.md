# Focused Audit — Idempotency & Exactly-Once Behavior

*Supplementary to the 11-phase engineering audit (README index). Scope: every path where a
duplicate trigger, a retry, or a crash-and-resume could cause double execution, double
counting, or a silently dropped side effect — scheduler jobs, the Procrastinate durable
outbound queue, webhook delivery, ingest upserts, and mutating HTTP endpoints. Reviewed at
commit `f7dd1a7` on branch `claude/next-steps-plan-kl6fhe`.*

> **Assessment document — no code changes implemented here.** Findings are written to be
> directly executable: concrete `file:line`, evidence, remediation with code sketch,
> acceptance criteria, effort, and Quick-Win/Architectural classification. Answers the
> outstanding recommendation in Phase 2 **F2.2** ("each job owned by exactly one system with
> a documented idempotency key").

---

## Executive Summary

BRIEFR is **mostly idempotent by design**, and in one place (webhook delivery) it is
textbook. The core ingest path is safe to re-run (`ON CONFLICT` upserts), scheduled jobs
cannot overlap within a process (`max_instances=1` + `coalesce=True`), the manual-refresh
endpoints share the *same* lock objects as the scheduled jobs, and notification/webhook
fan-out use atomic claim-before-send dedupe.

The **one weak surface is the newest one**: the Tier-A **stack backfill** durable task (Q4).
It is the only custom Procrastinate task, and it does **not** follow the idempotency
discipline the rest of the codebase already demonstrates — it has no "already-running" guard
and its enqueue carries no `queueing_lock`, so a double-clicked *Agree/Resume* or a
Procrastinate retry overlapping the in-process fallback can run the same `run_id` twice and
corrupt its progress accounting (the underlying CVE upserts stay correct; the run's
`cves_upserted` / checkpoint bookkeeping does not).

Procrastinate is **at-least-once** — a worker crash re-runs the job — so every durable task
*must* be idempotent. The webhook path (`IDEM-001`) is the model to copy; the stack backfill
is the gap to close.

**Idempotency posture score: 7.5 / 10.** No data-corruption class in the CVE corpus itself;
the gaps are in one feature's run-state accounting and a couple of low-severity durability
edges.

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

### IDEM-A — Stack backfill has no "already-running" guard → concurrent double-run · Priority: MEDIUM · Quick Win
- **Location:** `backend/services/stack_backfill_worker.py:42-53` (`_process`). The early-return
  guard at `:49` covers `status in ("completed", "partial", "failed")` but **not `"running"`**;
  `:52` then sets `status="running"` unconditionally.
- **Description:** Two concurrent invocations of `_process(run_id)` for the same run both pass
  the guard (neither sees a terminal status), both set `running`, and both enter the page loop —
  reading the same `next_pending_checkpoint`, fetching the same NVD keyword pages, and both
  incrementing `cves_upserted` / advancing checkpoints against the same rows.
- **Why it matters:** Concurrency arises easily: a double-clicked *Agree/Resume* (`_kick_backfill`
  is called once per request with no debounce), a Procrastinate **retry** overlapping the still-
  running original, or the Procrastinate job overlapping the in-process fallback (IDEM-C). The CVE
  rows themselves stay correct (idempotent upserts), but the run's progress accounting double-counts
  and the checkpoint state races — the operator sees wrong coverage numbers and possibly a run that
  flips between `running`/`partial` nondeterministically.
- **Evidence:** `:49` `if run.get("status") in ("completed", "partial", "failed"): return`;
  no `"running"` in that set; no advisory lock or atomic claim around the transition.
- **Risk:** Corrupted run accounting; wasted NVD quota (Q2 metering shows inflated calls);
  operator confusion. Not CVE-corpus corruption.
- **Recommended solution:** Claim the run atomically before processing — turn the read-then-write
  into a single conditional update, or take a Postgres advisory lock keyed on `run_id`:
  ```python
  # Atomic claim: only one caller wins the transition into "running".
  claimed = await claim_run_running(db, run_id)   # UPDATE stack_backfill_runs
  #   SET status='running' WHERE id=$1 AND status <> 'running' RETURNING id
  if not claimed:
      return {"ok": True, "status": "already_running"}
  ```
  (On Postgres, `pg_try_advisory_lock(hashtext('stack_backfill:'||$run_id))` is an alternative
  that also self-releases on connection loss — preferable once F3.1/F6.6 externalize locking.)
- **Acceptance criteria:** Two overlapping `process_stack_backfill_run(run_id)` calls result in
  exactly one advancing the run; the other returns `already_running` without touching counters.
  Regression test drives two concurrent calls and asserts `cves_upserted` is not double-counted.
- **Effort:** Quick Win. **Type:** Quick Win.

### IDEM-B — Procrastinate defer carries no `queueing_lock` → duplicate pending jobs · Priority: MEDIUM · Quick Win
- **Location:** `backend/routers/stack_catalog.py:154` — `await stack_backfill_tick.defer_async(run_id=run_id)`.
- **Description:** The defer passes no `queueing_lock`, so repeated *Agree/Resume* clicks enqueue
  multiple `jobs:stack_backfill` rows for the same `run_id`. Procrastinate's `queueing_lock` exists
  precisely to reject a duplicate *pending* job.
- **Why it matters:** With `concurrency=1` (`jobs/app.py:56`) duplicates run sequentially, so the
  second usually sees a terminal status and no-ops — **but** if the first paused at `partial`, the
  second resumes it, and combined with IDEM-A (no running-guard) the overlap window is real. It also
  inflates the `procrastinate_jobs` table and the admin outbound-jobs list with redundant rows.
- **Evidence:** `defer_async(run_id=run_id)` with no `queueing_lock=`; `db/outbound_jobs.py:15`
  selects a `queueing_lock` column that is always NULL for this task.
- **Recommended solution:** Give the task a per-run queueing lock so a duplicate defer is rejected
  while one is pending:
  ```python
  await stack_backfill_tick.configure(
      queueing_lock=f"stack_backfill:{run_id}",
  ).defer_async(run_id=run_id)
  ```
  Handle `procrastinate.exceptions.AlreadyEnqueued` (or the AlreadyEnqueued no-op, per version) as
  "resume already queued" rather than an error.
- **Acceptance criteria:** Two rapid resume requests for the same run enqueue **one** pending job;
  the admin outbound list shows a single row; a test asserts the second defer is rejected/no-op.
- **Effort:** Quick Win. **Type:** Quick Win.

### IDEM-C — Dual job systems can double-run a backfill across the enabled/disabled boundary · Priority: LOW–MEDIUM · Architectural
- **Location:** `backend/routers/stack_catalog.py:144-163` (`_kick_backfill`); `backend/main.py:130`
  (`start_inprocess_worker`) + `start_scheduler()` in the same lifespan. Cross-references Phase 2 **F2.2**.
- **Description:** `_kick_backfill` chooses Procrastinate **or** an in-process `asyncio.create_task`
  per call based on `PROCRASTINATE_ENABLED`. A durable job deferred while enabled can survive a
  restart where the flag flips, and a subsequent resume then kicks an **in-process** task for the
  same `run_id` — two systems advancing one run.
- **Why it matters:** This is the exact "mid-migration double-run" risk F2.2 called out, concretized
  for the one custom durable task. IDEM-A's guard contains the damage; without it, the two systems
  race.
- **Evidence:** feature-flag branch at `:148`; in-process fallback at `:161`; both worker and
  scheduler started in `main.py` lifespan.
- **Recommended solution:** Land IDEM-A (single-winner run claim) as the safety net, then per F2.2
  add a job-registry note declaring `jobs:stack_backfill` **owned by exactly one system**, and make
  `_kick_backfill` refuse the in-process path when a durable job for that run is already pending
  (query `procrastinate_jobs` by the IDEM-B queueing lock).
- **Acceptance criteria:** With a pending durable job for `run_id`, a second kick does not spawn an
  in-process task; the job-registry doc lists each task's owner-system + idempotency key.
- **Effort:** Medium. **Type:** Architectural.

### IDEM-D — Webhook "stuck claim" on crash between claim-commit and clear · Priority: LOW · Quick Win
- **Location:** `backend/webhooks/engine.py:179-245`. The dedupe claim is committed at `:185`
  **before** the HTTP send (`:189`); a failed send clears it at `:240`.
- **Description:** Correct under normal flow, but if the process crashes (or the DB connection drops)
  **after** the claim commit and **before** the failure-path clear, the `webhook_destination_dedupe`
  row persists with no successful delivery — permanently suppressing that
  `(destination_id, event_type, dedupe_key)` alert.
- **Why it matters:** A silently dropped operator alert (e.g. a KEV or backup-failure webhook) is
  exactly the kind of missed signal webhooks exist to prevent. Low probability, high-ish impact per
  occurrence.
- **Evidence:** claim commit at `:185`, send at `:189`, clear only on the reached failure branch `:236`.
- **Recommended solution:** Give `webhook_destination_dedupe` a TTL and sweep it in the existing
  `cache_retention_cleanup` job (it already ages `ai_operations`/`webhook_delivery_log`), so a stuck
  claim self-heals after, say, 24h. Alternatively record the claim with a `pending` vs `sent` state
  and only treat `sent` as suppressing.
- **Acceptance criteria:** A dedupe row with no matching successful `webhook_delivery_log` entry is
  purged after the TTL; delivery can then be re-attempted.
- **Effort:** Quick Win. **Type:** Quick Win.

### IDEM-E — Manual-refresh guard is check-then-acquire, not an atomic acquire · Priority: LOW · Quick Win
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

### IDEM-F — No HTTP-level idempotency keys on mutating endpoints · Priority: LOW · Architectural (context)
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

## Immediate action items (ranked)

1. **IDEM-A** — atomic run claim on stack backfill (highest value; closes the only real double-run). Quick Win.
2. **IDEM-B** — `queueing_lock` on the backfill defer. Quick Win, pairs with A.
3. **IDEM-D** — TTL-sweep `webhook_destination_dedupe` to self-heal stuck claims. Quick Win.
4. **IDEM-C** — job-registry doc + single-owner enforcement for `jobs:stack_backfill` (satisfies F2.2). Medium.
5. **IDEM-E / IDEM-F** — note-only; revisit if the single-process / single-operator assumptions relax.

## Long-term

- Adopt the webhook `IDEM-001` claim-before-act pattern as the **standard** for every future
  durable task; add it to the job-registry doc F2.2 asks for.
- When Phase 2/6 externalize locking (Redis / Postgres advisory locks, F3.1/F6.6), migrate the
  in-process `asyncio.Lock` scheduler exclusion and the IDEM-A run claim onto it in one pass so
  multi-process deployments inherit exactly-once for free.
