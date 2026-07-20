# Catch-up mode v1 — Design

**Status:** Accepted for planning (maintainer decisions 2026-07-20)  
**Implementation plan:** [`../plans/2026-07-20-catchup-mode.md`](../plans/2026-07-20-catchup-mode.md)  
**Created:** 2026-07-20  
**Audience:** Implementers (Cursor agents / maintainers)

## 1. Goal

Give operators a **time-boxed Catch-up mode** so that when interactive load is low (away from the console), BRIEFR drains local and paced-external backlog faster — without exceeding provider rate limits, and without requiring GPU.

## 2. Locked decisions (maintainer)

| # | Decision |
|---|----------|
| 1 | **Admin-only** operator control (not analyst nav / not wallboard). |
| 2 | **Default duration = 6 hours** (presets: 2h / 6h / 8h + custom end time). |
| 3 | **Scope B:** internal backlog **plus** paced external drain (still behind `api_queue`). |
| 4 | **Neutral copy** — one wording for laptop and server (no “overnight laptop” vs “prod server” split). |
| — | **GPU acceleration parked** (later discussion; not in v1). |

## 3. Problem

Polite defaults (small embedding caps, scheduled intervals, LLM headroom ~85%, single-flight locks) protect interactive UX. When the operator is away, that politeness leaves backlog idle. Catch-up is an explicit, temporary profile change — not a permanent env tweak.

## 4. Non-negotiables

1. **Never** bypass `api_queue`, `Retry-After`, or `schedule_source_pause` clamps.
2. **Never** raise provider ceilings above documented / computed floors in `source_rate_limits` / `ai/llm_pacing` (Catch-up only spends **our** politeness headroom).
3. **Auto-expire** on timer; **End early** returns to polite profile immediately.
4. Process restart → Catch-up **clears** (safe default); UI may show “interrupted by restart” from last session stamp.
5. Keep **small DB commit chunks** (do not enlarge `ADDITIVE_ENRICHMENT_COMMIT_CHUNK` or similar).
6. Jobs remain **checkpointed / idempotent**; Catch-up only starts work through existing job entry points.
7. Wind-down: stop **starting** new Catch-up ticks **5 minutes** before `ends_at`.

## 5. Out of scope (v1)

- GPU / “Use GPU” toggle  
- Changing inbound `RATE_LIMIT_*` (protects BRIEFR’s own API)  
- OS sleep / scheduled power-off integration  
- New data sources or new enrichment algorithms  
- Analyst-facing controls  
- Making Catch-up survive process restart as still-active  

## 6. Product behavior

### 6.1 Operator UX (Admin → Scheduler)

Card **Catch-up mode** (operator mode only):

- Title: **Catch-up mode**
- Neutral description (exact product copy):

  > Catch-up uses more of this machine’s CPU, disk, and network to clear backlog while still respecting each provider’s rate limits. Interactive use may feel slower until Catch-up ends.

- Controls: duration presets **2h / 6h (default) / 8h**, optional custom end (shared `DateTimePicker`), **Start Catch-up**, **End early**
- Live status when ON: ends-at (local + UTC), elapsed, backlog summary (embeddings pending if available, API queue throttled/queued counts), list of sources currently rate-limited
- Four async states: loading / empty(off) / error(+ request-id) / data(on)

### 6.2 What Catch-up changes

| Lever | Polite (default) | Catch-up active |
|-------|------------------|-----------------|
| Embeddings per run | `EMBEDDINGS_MAX_PER_RUN` (default 2000) | `min(base × 2, 5000)` |
| Correlation precompute per run | `CORRELATION_PRECOMPUTE_MAX_PER_RUN` (default 500) | `min(base × 2, 2000)` when feature enabled |
| LLM headroom | provider `*_HEADROOM_PCT` (default 85) | effective **95** (still ≤ 100%; intervals recomputed) |
| Non-LLM source intervals | `get_source_pacing()` as today | **unchanged** (already at documented floors) |
| Job cadence | normal APScheduler intervals | Extra **Catch-up tick** every **5 minutes** kicks eligible backlog jobs if not locked |

### 6.3 Catch-up tick (eligible jobs)

Tick may invoke (via existing scheduler run functions / `_JOB_RUN_MAP` patterns — never duplicate business logic):

1. `embeddings_backfill` (when `EMBEDDINGS_ENABLED`)
2. Nightly correlation path’s precompute slice when `CORRELATION_PRECOMPUTE_ENABLED` (reuse existing helpers; do not invent a second engine)
3. Optional: already-queued outbound work needs no kick — `api_queue` drains whenever slots open; Catch-up’s LLM headroom change is enough for external LLM drain

Do **not** force NVD full sync or backup from Catch-up ticks.

### 6.4 State model

In-process module `backend/catchup_mode.py`:

```text
CatchupState:
  active: bool
  started_at: datetime | None   # UTC
  ends_at: datetime | None      # UTC
  duration_hours: float | None
  started_by: str | None        # audit actor label
  cleared_reason: str | None    # expired | ended_early | restart | None
```

- Primary truth: **in-memory** (fast for pacing hot path).
- On start/end/expire: write a small JSON blob to `sync_state` key `catchup_mode_last` for UI “last session / interrupted”.
- On process boot: memory = inactive; if `catchup_mode_last` said active with future `ends_at`, mark `cleared_reason=restart`.

### 6.5 API (admin-auth)

| Method | Path | Body / behavior |
|--------|------|-----------------|
| `GET` | `/api/admin/catchup` | Current state + derived `effective_*` + queue summary snippets |
| `POST` | `/api/admin/catchup/start` | `{ "duration_hours": 6 }` **or** `{ "ends_at": "<ISO-8601>" }`; reject if already active; max duration **24h** |
| `POST` | `/api/admin/catchup/stop` | End early; audit |

Audit actions: `catchup.start`, `catchup.stop`.

### 6.6 Safety / errors

- Start while active → `409` with clear detail.
- Invalid duration / ends_at in the past / >24h → `400`.
- Tick errors: log + continue; never leave Catch-up “stuck on” past `ends_at` (expire check on GET, tick, and pacing reads).

## 7. Neutral copy rationale

Laptop vs server differ only in thermal/noise expectations; product behavior is identical. One description avoids forked UX. Operators who stay at the keyboard still see the “may feel slower” warning.

## 8. Docs / follow-ons

- Update `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md`, `docs/HANDOVER.md` in the implementation PR(s).
- GPU optional acceleration: **parked** (separate design later).
- Optional later: persist active Catch-up across restart; OS shutdown handshake.

## 9. Acceptance (v1 done when)

- Operator can start 6h Catch-up from Admin Scheduler, see status, end early.
- While active: embeddings/correlation caps and LLM headroom match §6.2; non-LLM pacing unchanged; 429/Retry-After still pause sources.
- After expiry or stop: polite profile restored within one tick/request.
- Restart clears Catch-up; no orphaned “active forever”.
- Tests cover state machine, effective caps/headroom, API auth, and UI presentation helpers.
- No GPU code paths.
