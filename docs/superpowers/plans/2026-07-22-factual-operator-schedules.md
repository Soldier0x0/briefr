# Factual operator schedules — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove orphaned “auto daily …” / cache-refresh schedule claims so FEED footer and config help only describe jobs that actually run.

**Architecture:** Stop surfacing `CACHE_REFRESH_HOUR` / `CACHE_REFRESH_MINUTE` as a live refresh schedule in the health payload and UI. Keep next-refresh tied to the real `nvd_incremental_sync` (or documented next job) only. Mark or remove dead config fields with honest help text.

**Tech Stack:** FastAPI `backend/routers/health.py`, `backend/scheduler.py`, React `frontend/src/App.jsx`, `backend/config_schema.py`, docs.

**Spec SSOT:** [`../specs/2026-07-22-ux-ops-rca-collection-design.md`](../specs/2026-07-22-ux-ops-rca-collection-design.md) Program A.

## Global Constraints

- Data shown to operators must be completely factual — fake schedule claims must not appear.
- Do not invent a new daily job to “make the label true.”
- Semantic tokens / UI chrome unchanged except copy.
- Merge gate: `./scripts/verify-local.sh`.
- Docs: `PRODUCT_STATUS.md` + prepend `HANDOVER.md` if operator-visible copy changes.

---

### Task 1: Stop advertising orphaned daily schedule in health + footer

**Files:**
- Modify: `backend/scheduler.py` (`get_refresh_schedule`)
- Modify: `backend/routers/health.py` (refresh_schedule response)
- Modify: `frontend/src/App.jsx` (`FeedRefreshStatus`, `formatScheduleLabel`)
- Test: `backend/tests/test_health_refresh_schedule.py` (create)
- Test: `frontend/src/App.feedRefreshStatus.test.js` (create if no existing; else extend)

**Interfaces:**
- Consumes: existing `/api/health` shape with `next_refresh_utc`
- Produces: health either omits `refresh_schedule` or returns `null` / `{ orphaned: true }` that UI never renders as “auto daily”

- [ ] **Step 1: Write the failing backend test**

```python
# backend/tests/test_health_refresh_schedule.py
def test_health_refresh_schedule_not_advertised_as_live_job(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    # Either absent, null, or explicitly not a live cron claim
    sched = body.get("refresh_schedule")
    assert sched in (None, {}) or sched.get("live") is False
    # Must still expose next NVD-style refresh when available
    assert "next_refresh_utc" in body or body.get("next_refresh_utc") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_health_refresh_schedule.py -q`  
Expected: FAIL (today `refresh_schedule` includes hour/minute from `CACHE_REFRESH_*`)

- [ ] **Step 3: Implement backend honesty**

In `get_refresh_schedule()` (or health assembly): stop returning hour/minute as an active schedule. Prefer:

```python
def get_refresh_schedule() -> dict | None:
    """Deprecated orphaned CACHE_REFRESH_* — not bound to any APScheduler job."""
    return None
```

Remove footer consumption of schedule, or keep field only for admin diagnostics as `{"legacy_cache_refresh_env": {...}, "live": False}` — UI must not print “auto daily”.

- [ ] **Step 4: Fix `FeedRefreshStatus` copy**

In `frontend/src/App.jsx`, delete the `(auto daily {scheduleLabel})` fragment entirely:

```jsx
{nextUtcLabel && (
  <span>
    Next refresh at {nextUtcLabel}
    {nextUserLabel && timezone !== 'UTC' && <> · {nextUserLabel}</>}
  </span>
)}
```

Remove unused `formatScheduleLabel` / `refreshSchedule` props if nothing else needs them (update call sites).

- [ ] **Step 5: Run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_health_refresh_schedule.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/scheduler.py backend/routers/health.py backend/tests/test_health_refresh_schedule.py frontend/src/App.jsx
git commit -m "fix(ops): stop advertising orphaned daily cache refresh schedule"
```

---

### Task 2: Honest config schema + env docs for CACHE_REFRESH_*

**Files:**
- Modify: `backend/config_schema.py` (`CACHE_REFRESH_HOUR`, `CACHE_REFRESH_MINUTE` help_text)
- Modify: `backend/.env.example` (comment)
- Modify: `docs/ONBOARDING.md` or any “Feed cache maintenance” claim (grep first)
- Modify: `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`
- Test: `backend/tests/test_config_schema.py` (assert help_text does not claim a live extended-data refresh job)

**Interfaces:**
- Consumes: existing `ConfigField` entries
- Produces: help text that states vars are unused / reserved / no scheduler job

- [ ] **Step 1: Grep for dishonest copy**

Run: `rg -n "CACHE_REFRESH|auto daily|extended-data-source cache|Feed cache maintenance" backend docs frontend`  
List every hit; update all operator-facing ones in this task.

- [ ] **Step 2: Write / adjust schema test**

```python
def test_cache_refresh_help_does_not_claim_live_job():
    from config_schema import FIELDS  # or whatever export name exists
    fields = {f.key: f for f in FIELDS}
    help_h = fields["CACHE_REFRESH_HOUR"].help_text.lower()
    assert "not scheduled" in help_h or "unused" in help_h or "no job" in help_h
    assert "extended-data-source cache refresh runs" not in help_h
```

- [ ] **Step 3: Update help + `.env.example`**

Example help:

```text
Unused — no APScheduler job reads CACHE_REFRESH_HOUR (kept for env compatibility).
```

- [ ] **Step 4: Docs**

PRODUCT_STATUS: note FEED footer next-refresh is NVD incremental only; daily CACHE_REFRESH claim removed.  
HANDOVER: newest entry first with RCA (orphaned env) + fix.

- [ ] **Step 5: verify-local + commit**

```bash
./scripts/verify-local.sh
git add backend/config_schema.py backend/.env.example backend/tests/test_config_schema.py docs/PRODUCT_STATUS.md docs/HANDOVER.md docs/ONBOARDING.md
git commit -m "docs(ops): mark CACHE_REFRESH_* as unused; align operator copy"
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| Remove fake auto-daily footer | Task 1 |
| Honest config / env / onboarding | Task 2 |
| Do not invent daily job | Both |
| PRODUCT_STATUS / HANDOVER | Task 2 |
