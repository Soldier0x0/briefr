# Catch-up mode v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Admin-only, time-boxed Catch-up mode that raises internal backlog throughput and spends LLM politeness headroom while never exceeding provider rate-limit floors.

**Architecture:** In-process `catchup_mode` state machine (auto-expire + End early) consulted by embeddings/correlation cap helpers and LLM headroom. A 5-minute scheduler tick kicks eligible backlog jobs. Admin REST under `/api/admin/catchup*` + Scheduler page card with neutral copy. GPU stays out of scope.

**Tech Stack:** FastAPI admin router (`require_admin`), APScheduler, existing `api_queue` / `source_rate_limits` / `ai/llm_pacing`, React admin JSX + design tokens, pytest + node:test.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-07-20-catchup-mode-design.md`
- Branch: `cursor/catchup-mode-91c2` off fresh `origin/main` (plan docs may land first on `cursor/catchup-mode-plan-91c2`)
- Default duration **6 hours**; max **24 hours**; wind-down **5 minutes** before `ends_at`
- Neutral product copy exactly as in the design §6.1
- Never enlarge DB commit chunks; never bypass `api_queue` / Retry-After
- Admin-only (`require_admin`); no analyst nav item
- GPU acceleration: do not implement
- Design-system tokens only in UI; use existing `DateTimePicker` for custom end
- Update `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md`, `docs/HANDOVER.md` in the same feature PR
- Local gate: `./scripts/verify-local.sh` (or targeted pytest + `npm run build`) before merge

## File map

| Path | Responsibility |
|------|----------------|
| `backend/catchup_mode.py` | State machine, expire, effective caps/headroom helpers |
| `backend/tests/test_catchup_mode.py` | Unit tests for state + effective values |
| `backend/ml/embeddings.py` | Use catch-up effective max per run |
| `backend/correlation/config.py` | Use catch-up effective precompute max |
| `backend/ai/llm_pacing.py` | Apply catch-up headroom when active |
| `backend/scheduler.py` | Register `catchup_tick` job; wire kick helpers |
| `backend/routers/admin/catchup.py` | GET/POST start/stop endpoints |
| `backend/routers/admin/__init__.py` | Import side-effect registration |
| `backend/tests/test_admin_catchup.py` | API tests (auth, 409, expire) |
| `frontend/src/pages/admin/CatchupCard.jsx` | Scheduler UI card |
| `frontend/src/pages/admin/catchupCopy.js` | Neutral strings + formatters |
| `frontend/src/pages/admin/catchupCopy.test.js` | Copy/format unit tests |
| `frontend/src/pages/admin/SchedulerPage.jsx` | Mount card (operator only) |
| `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md`, `docs/HANDOVER.md` | Runtime docs |

---

### Task 1: Catch-up state machine + effective helpers

**Files:**
- Create: `backend/catchup_mode.py`
- Create: `backend/tests/test_catchup_mode.py`

**Interfaces:**
- Produces:
  - `is_catchup_active() -> bool`
  - `get_catchup_status() -> dict`
  - `start_catchup(*, duration_hours: float | None = None, ends_at: datetime | None = None, started_by: str | None = None) -> dict`
  - `stop_catchup(*, reason: str = "ended_early") -> dict`
  - `effective_embeddings_max_per_run(base: int) -> int`
  - `effective_correlation_precompute_max_per_run(base: int) -> int`
  - `effective_llm_headroom_pct(base: int) -> int`
  - `reset_catchup_for_tests() -> None`
  - Constants: `DEFAULT_DURATION_HOURS = 6`, `MAX_DURATION_HOURS = 24`, `WIND_DOWN_SECONDS = 300`, `CATCHUP_LLM_HEADROOM_PCT = 95`

- [x] **Step 1: Write the failing tests**

```python
# backend/tests/test_catchup_mode.py
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catchup_mode as cm


def setup_function():
    cm.reset_catchup_for_tests()


def test_default_inactive():
    assert cm.is_catchup_active() is False
    st = cm.get_catchup_status()
    assert st["active"] is False


def test_start_default_six_hours():
    st = cm.start_catchup(duration_hours=None, started_by="op")
    assert st["active"] is True
    assert st["duration_hours"] == 6
    assert cm.is_catchup_active() is True
    ends = datetime.fromisoformat(st["ends_at"].replace("Z", "+00:00"))
    started = datetime.fromisoformat(st["started_at"].replace("Z", "+00:00"))
    assert timedelta(hours=5, minutes=50) < (ends - started) < timedelta(hours=6, minutes=10)


def test_start_while_active_raises():
    cm.start_catchup(duration_hours=2)
    try:
        cm.start_catchup(duration_hours=2)
        assert False, "expected CatchupConflictError"
    except cm.CatchupConflictError:
        pass


def test_stop_ends_early():
    cm.start_catchup(duration_hours=6)
    st = cm.stop_catchup(reason="ended_early")
    assert st["active"] is False
    assert st["cleared_reason"] == "ended_early"
    assert cm.is_catchup_active() is False


def test_expire_clears_active():
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    cm.start_catchup(ends_at=past + timedelta(seconds=1), started_by="t")
    # Force ends_at into the past via internal helper if needed:
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) - timedelta(seconds=1))
    assert cm.is_catchup_active() is False
    assert cm.get_catchup_status()["cleared_reason"] == "expired"


def test_effective_caps_and_headroom():
    assert cm.effective_embeddings_max_per_run(2000) == 2000
    assert cm.effective_llm_headroom_pct(85) == 85
    cm.start_catchup(duration_hours=1)
    assert cm.effective_embeddings_max_per_run(2000) == 4000
    assert cm.effective_embeddings_max_per_run(3000) == 5000  # hard cap
    assert cm.effective_correlation_precompute_max_per_run(500) == 1000
    assert cm.effective_correlation_precompute_max_per_run(1500) == 2000
    assert cm.effective_llm_headroom_pct(85) == 95
    assert cm.effective_llm_headroom_pct(99) == 99  # never lower than base; never >100
    assert cm.effective_llm_headroom_pct(100) == 100


def test_reject_over_max_duration():
    try:
        cm.start_catchup(duration_hours=25)
        assert False
    except cm.CatchupValidationError:
        pass


def test_in_wind_down():
    cm.start_catchup(duration_hours=1)
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) + timedelta(seconds=60))
    st = cm.get_catchup_status()
    assert st["active"] is True
    assert st["in_wind_down"] is True
    assert st["should_start_new_work"] is False
```

- [x] **Step 2: Run tests — expect FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_catchup_mode.py -q`
Expected: FAIL (module missing)

- [x] **Step 3: Implement `backend/catchup_mode.py`**

Minimal implementation notes:
- Module-level lock (`threading.Lock`) around mutations.
- `CatchupConflictError` / `CatchupValidationError` subclasses of `Exception`.
- ISO timestamps in status as `...Z` UTC.
- `effective_llm_headroom_pct`: if inactive → `base`; if active → `min(100, max(base, CATCHUP_LLM_HEADROOM_PCT))`.
- `should_start_new_work`: active and not within `WIND_DOWN_SECONDS` of `ends_at`.
- `reset_catchup_for_tests` / `_force_ends_at_for_tests` for tests only.
- Persistence to `sync_state` can be stubbed no-op in Task 1; wire in Task 3 if cleaner — prefer Task 1 pure memory, Task 3 adds optional persist hooks called from start/stop.

- [x] **Step 4: Run tests — expect PASS**

Run: `cd backend && .venv/bin/python -m pytest tests/test_catchup_mode.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/catchup_mode.py backend/tests/test_catchup_mode.py
git commit -m "feat(catchup): state machine and effective throughput helpers"
```

---

### Task 2: Wire effective helpers into embeddings, correlation, LLM pacing

**Files:**
- Modify: `backend/ml/embeddings.py` (`get_embeddings_max_per_run`, ingest max if used for backfill path)
- Modify: `backend/correlation/config.py` (`get_correlation_precompute_max_per_run`)
- Modify: `backend/ai/llm_pacing.py` (`limits_from_env` / headroom read)
- Modify: `backend/tests/test_catchup_mode.py` (integration-style monkeypatch tests) **or** extend existing embedding/correlation tests

**Interfaces:**
- Consumes: `effective_*` from Task 1
- Produces: existing public getters return catch-up-aware values when active

- [x] **Step 1: Failing test — embeddings max doubles when catch-up on**

```python
def test_embeddings_getter_respects_catchup(monkeypatch):
    import catchup_mode as cm
    from ml import embeddings as emb

    cm.reset_catchup_for_tests()
    monkeypatch.setenv("EMBEDDINGS_MAX_PER_RUN", "2000")
    assert emb.get_embeddings_max_per_run() == 2000
    cm.start_catchup(duration_hours=1)
    assert emb.get_embeddings_max_per_run() == 4000
```

- [x] **Step 2: Run — expect FAIL** (getter ignores catch-up)

- [x] **Step 3: Implement wiring**

In `get_embeddings_max_per_run`:

```python
def get_embeddings_max_per_run() -> int:
    base = int(os.environ.get("EMBEDDINGS_MAX_PER_RUN", "2000"))
    from catchup_mode import effective_embeddings_max_per_run
    return effective_embeddings_max_per_run(base)
```

Same pattern for `get_correlation_precompute_max_per_run` in `correlation/config.py`.

In `ai/llm_pacing.py` `limits_from_env`, after reading `headroom`:

```python
from catchup_mode import effective_llm_headroom_pct
headroom = effective_llm_headroom_pct(headroom)
```

Do **not** change `get_source_pacing` non-LLM intervals.

- [x] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_catchup_mode.py tests/test_correlation_precompute.py -q --tb=line`
Expected: PASS (adjust any brittle hard-coded max assertions if they assume env literally)

- [x] **Step 5: Commit**

```bash
git add backend/ml/embeddings.py backend/correlation/config.py backend/ai/llm_pacing.py backend/tests/test_catchup_mode.py
git commit -m "feat(catchup): apply caps and LLM headroom when active"
```

---

### Task 3: Admin API + optional last-session sync_state

**Files:**
- Create: `backend/routers/admin/catchup.py`
- Modify: `backend/routers/admin/__init__.py` (import `catchup`)
- Create: `backend/tests/test_admin_catchup.py`
- Modify: `backend/catchup_mode.py` (persist `catchup_mode_last` via sync_state helpers; clear-on-boot helper callable from `main.py` lifespan)

**Interfaces:**
- Produces HTTP:
  - `GET /api/admin/catchup` → status dict + `api_queue` summary fields (`total_queued`, `total_active`, throttled request count)
  - `POST /api/admin/catchup/start` body `{"duration_hours": 6}` or `{"ends_at": "..."}`
  - `POST /api/admin/catchup/stop`
- Consumes: `catchup_mode.*`, `dependencies.audit`, `api_queue.get_api_queue_status`

- [x] **Step 1: Failing API tests**

```python
# backend/tests/test_admin_catchup.py — follow existing admin TestClient auth patterns
# from tests that hit /api/admin/jobs or /api/admin/backups

def test_catchup_start_stop_roundtrip(admin_client):
    r = admin_client.get("/api/admin/catchup")
    assert r.status_code == 200
    assert r.json()["active"] is False

    r = admin_client.post("/api/admin/catchup/start", json={"duration_hours": 6})
    assert r.status_code == 200
    assert r.json()["active"] is True

    r = admin_client.post("/api/admin/catchup/start", json={"duration_hours": 2})
    assert r.status_code == 409

    r = admin_client.post("/api/admin/catchup/stop", json={})
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_catchup_requires_admin(anon_client):
    assert anon_client.get("/api/admin/catchup").status_code in (401, 403)
```

Use the repo’s real fixture names (`client` + login helper) — match `tests/test_admin_*.py` patterns exactly when implementing.

- [x] **Step 2: Run — expect FAIL** (404)

- [x] **Step 3: Implement router**

```python
# backend/routers/admin/catchup.py (sketch)
@router.get("/catchup")
async def get_catchup(request: Request):
    from catchup_mode import get_catchup_status
    from api_queue import get_api_queue_status
    status = get_catchup_status()
    q = get_api_queue_status()
    return {**status, "api_queue": {
        "total_queued": q.get("total_queued", 0),
        "total_active": q.get("total_active", 0),
        "has_pending": q.get("has_pending", False),
    }}

@router.post("/catchup/start")
async def start_catchup_endpoint(request: Request):
    body = await request.json()
    # validate → start_catchup → audit catchup.start → return status
    ...

@router.post("/catchup/stop")
async def stop_catchup_endpoint(request: Request):
    # stop_catchup → audit catchup.stop
    ...
```

Map `CatchupConflictError` → HTTP 409; `CatchupValidationError` → 400.

Call `clear_catchup_after_restart()` once from app lifespan in `main.py` (after DB ready) so a crashed “active” session becomes `cleared_reason=restart` in last-session blob only.

- [x] **Step 4: Run API tests — PASS**

- [x] **Step 5: Commit**

```bash
git add backend/routers/admin/catchup.py backend/routers/admin/__init__.py backend/catchup_mode.py backend/main.py backend/tests/test_admin_catchup.py
git commit -m "feat(catchup): admin start/stop/status API"
```

---

### Task 4: Scheduler Catch-up tick

**Files:**
- Modify: `backend/scheduler.py`
- Modify: `backend/tests/test_catchup_mode.py` (or new `tests/test_catchup_tick.py`)

**Interfaces:**
- Consumes: `is_catchup_active`, `get_catchup_status()["should_start_new_work"]`
- Produces: job id `catchup_tick` (IntervalTrigger minutes=5)

- [x] **Step 1: Failing test**

```python
def test_catchup_tick_skips_when_inactive(monkeypatch):
    import catchup_mode as cm
    from scheduler import run_catchup_tick

    cm.reset_catchup_for_tests()
    called = {"n": 0}
    async def boom(*a, **k):
        called["n"] += 1
    monkeypatch.setattr("scheduler.run_embeddings_backfill_job", boom, raising=False)
    # Prefer monkeypatching the real kick targets used inside run_catchup_tick
    import asyncio
    assert asyncio.run(run_catchup_tick()) is True
    assert called["n"] == 0
```

Implementers: align monkeypatch targets with whatever thin wrappers `run_catchup_tick` calls (existing `run_embeddings_backfill` job function / correlation precompute entry). Prefer calling the same functions Admin “Retry now” uses from `_JOB_RUN_MAP` for `embeddings_backfill` only when enabled.

- [x] **Step 2: Implement `async def run_catchup_tick()`**

Logic:
1. If not `should_start_new_work`: return True (no-op).
2. If embeddings enabled and embeddings lock free: await embeddings backfill job function.
3. If correlation precompute enabled: run one precompute slice via existing nightly helper (import from correlation / scheduler private helper — do not duplicate).
4. Never start backup / NVD full / destructive jobs.
5. Register with `IntervalTrigger(minutes=5)` id=`catchup_tick`, name=`Catch-up tick`.

Add to admin job catalog (`frontend/src/pages/admin/catalog.js`) with operator name **Catch-up tick**.

- [x] **Step 3: Tests PASS + commit**

```bash
git add backend/scheduler.py backend/tests/test_catchup_tick.py frontend/src/pages/admin/catalog.js
git commit -m "feat(catchup): five-minute backlog tick while active"
```

---

### Task 5: Admin Scheduler UI card

**Files:**
- Create: `frontend/src/pages/admin/catchupCopy.js`
- Create: `frontend/src/pages/admin/catchupCopy.test.js`
- Create: `frontend/src/pages/admin/CatchupCard.jsx`
- Modify: `frontend/src/pages/admin/SchedulerPage.jsx`
- Modify: `frontend/src/api.js` or adminApi helpers if needed for new routes

**Interfaces:**
- Consumes: `GET/POST /api/admin/catchup*`
- Produces: operator-only card above job table

- [x] **Step 1: Failing unit tests for copy**

```javascript
// frontend/src/pages/admin/catchupCopy.test.js
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { CATCHUP_DESCRIPTION, formatCatchupEndsIn, durationPresets } from './catchupCopy.js'

describe('catchupCopy', () => {
  it('exposes neutral description', () => {
    assert.match(CATCHUP_DESCRIPTION, /rate limits/i)
    assert.match(CATCHUP_DESCRIPTION, /may feel slower/i)
    assert.doesNotMatch(CATCHUP_DESCRIPTION, /laptop|server|overnight/i)
  })

  it('default preset is 6h', () => {
    assert.equal(durationPresets.find(p => p.default)?.hours, 6)
  })
})
```

- [x] **Step 2: Implement copy module + CatchupCard**

UI requirements:
- Tokens only (`--space-*`, `--text-*`, `--status-*`, etc.)
- Presets 2 / 6 / 8 hours; custom end via shared `DateTimePicker`
- States: loading skeleton, off (empty), on (data), error with `ref: <request-id>`
- Buttons: **Start Catch-up**, **End early**
- Show wind-down note when `in_wind_down`
- Render only when admin operator mode (SchedulerPage already operator-gated via AdminPage — do not add to `ANALYST_NAV`)

- [x] **Step 3: Mount in SchedulerPage**

Place card under page subtitle, above job table.

- [x] **Step 4: Run FE tests + build**

```bash
cd frontend && node --test src/pages/admin/catchupCopy.test.js
cd frontend && npm run build
```

Expected: PASS / build OK

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/catchupCopy.js frontend/src/pages/admin/catchupCopy.test.js frontend/src/pages/admin/CatchupCard.jsx frontend/src/pages/admin/SchedulerPage.jsx
git commit -m "feat(catchup): admin Scheduler Catch-up card"
```

---

### Task 6: Docs + verify + PR

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` (Admin / scheduler row — Catch-up mode)
- Modify: `docs/API_REFERENCE.md` (document three endpoints)
- Modify: `docs/HANDOVER.md` (newest entry)
- Optional: tick a line in `docs/planning/SPRINT_2026-07.md` if a checkbox is added

- [x] **Step 1: Docs updates** (runtime truth + API + handover RCA-free feature note)

- [ ] **Step 2: Local verify**

```bash
cd backend && .venv/bin/python -m pytest tests/test_catchup_mode.py tests/test_admin_catchup.py tests/test_catchup_tick.py -q
cd frontend && node --test src/pages/admin/catchupCopy.test.js && npm run build
# preferred:
./scripts/verify-local.sh
```

- [ ] **Step 3: Push + PR**

Title: `feat: Catch-up mode v1 (admin time-boxed backlog drain)`

Body must cite design path and locked decisions (admin-only, 6h default, scope B, neutral copy, no GPU).

- [ ] **Step 4: Gemini disposition → merge when maintainer asks**

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Admin-only control | Tasks 3, 5 |
| Default 6h / presets / max 24h | Tasks 1, 5 |
| Internal + paced external (LLM headroom; non-LLM floors unchanged) | Tasks 2, 4 |
| Neutral copy | Task 5 + design §6.1 |
| Auto-expire / End early / restart clears | Tasks 1, 3 |
| Wind-down 5 min | Tasks 1, 4 |
| No GPU | Global constraint |
| Docs PRODUCT_STATUS / API_REFERENCE / HANDOVER | Task 6 |
| Small commit chunks unchanged | Global constraint |

**Placeholder scan:** none intentional — implementers must still bind TestClient fixtures to this repo’s real admin auth helpers (named in Task 3 step note).

**Type consistency:** `duration_hours: float`, ISO `ends_at` strings with `Z`, status keys `active`, `in_wind_down`, `should_start_new_work`, `cleared_reason` used across backend + FE.
