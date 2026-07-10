# CLAUDE.md — BRIEFR project instructions

BRIEFR is a self-hosted CVE intelligence and detection-engineering platform.
FastAPI backend (`backend/`), React 19 + Vite frontend (`frontend/`, plain
JSX/CSS, no component library), **PostgreSQL required in production**.

## Commands

- Backend tests: `cd backend && pytest tests/ -q`
- Frontend build (must pass before any frontend change is done): `cd frontend && npm run build`
- Dev servers: `uvicorn main:app --port 8000` (from `backend/`); `npm run dev` (from `frontend/`, proxies `/api` → `:8000`)

## Source of truth

- `docs/PRODUCT_STATUS.md` is the living truth — when any other doc disagrees with it or with the code, they win, not the older doc.
- `CODEBASE_CONTEXT.md`, `FOLDER_STRUCTURE_GUIDE.md`, `APPLICATION_EXECUTION_MAP.md`, `TECHNICAL_INVENTORY.md` are periodic snapshots and may lag the code — verify against source before relying on them.
- Historical specs live in `docs/archive/` — never edit or resurrect them.
- Recent decisions and session context: `docs/HANDOVER.md` (newest entry
  first). Current work queue: `docs/SPRINT_2026-07.md`.

## Danger zones — read before editing

1. **SQL:** the `db/` package is **Postgres-native** (Post-B, 2026-07;
   `db/dialect.py` was deleted — do not reintroduce a translation layer).
   Write new SQL Postgres-native. Production is Postgres-only
   (`BRIEFR_REQUIRE_POSTGRES=1`); SQLite survives **only** as the
   zero-config test/dev fallback in `db/connection.py` (`db/pg_adapt.py`
   adapts for it). Tests default to SQLite — a query can pass the default
   suite and still break production, so for any `db/`-layer change run the
   suite both ways: default, and with `DATABASE_URL` pointing at Postgres.
2. **Scheduler locks:** job `id=` strings in `scheduler.py` must stay in sync
   with the lock mapping used by `routers/admin.py`.
3. **Migrations are forward-only** (Alembic). Never edit an applied migration;
   add a new one.
4. **Secrets in logs:** structured logging redacts extra fields matching
   `*_KEY/_TOKEN/_SECRET/_PASSWORD`. Never interpolate secrets into log
   message strings — redaction only covers `extra` fields.
5. **`deploy/` scripts run on a live production box.** Changes must stay
   additive per the compatibility promise in `docs/ROADMAP.md` /
   `docs/OPERATIONS.md`.
6. **Heavy work never runs on the request path.** ML, enrichment sweeps, and
   external syncs belong in `scheduler.py` jobs; request handlers do DB reads
   and cached lookups.

## Error-handling conventions

- Backend: raise `HTTPException` with a short, safe, actionable `detail` for
  expected 4xx cases. Let unexpected errors reach the global handler — it
  returns a generic 500 with `request_id` and logs the full traceback. Never
  put stack traces, SQL, file paths, or upstream API responses containing
  keys into `detail`.
- Frontend: surface the API `detail` string plus the `X-Request-ID` response
  header ("ref: <id>") so operators can grep the logs. Never render raw
  exception objects. Every async view needs designed loading / empty / error
  / data states.

## UI rules

- **Density over decoration. Do NOT add large side margins or center a
  narrow content column in a wide viewport.** Content fills the width with
  normal gutters (~24–32px). `max-width` is for prose paragraphs only —
  never for feeds, tables, or dashboards.
- Dark terminal aesthetic: mono labels, existing tokens in `App.css`. No
  gradients, no hero-marketing sections, no icon+heading+text card grids
  (see `PRODUCT.md` anti-references).
- Motion: 120–180ms ease-out, opacity/transform only,
  `prefers-reduced-motion` respected (global rule exists — keep it).
- Every status word, pill, or badge ships with a discoverable explanation
  (tooltip/legend) — `PRODUCT.md` design principle 1.

## Docs rules

- Runtime behavior changed → update `docs/PRODUCT_STATUS.md` and
  `SYSTEM_DESIGN.md` in the same PR.
- Endpoints changed → update `API_REFERENCE.md` in the same PR.
- Do not create new top-level docs; extend the existing set
  (`docs/DOCUMENTATION_PLAN.md` governs structure).

## Working style

- State assumptions explicitly; if multiple interpretations exist, ask
  before implementing.
- Minimum code that solves the problem — no speculative features,
  abstractions, or configurability that wasn't requested.
- Touch only what the task requires; match existing style; every changed
  line should trace to the request. Remove only orphans your own change
  created.
- Define verification before coding: run the relevant test files and
  `npm run build` before declaring done. For UI work, verify in the browser,
  not just the build.
