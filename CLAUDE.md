# CLAUDE.md — BRIEFR project instructions

BRIEFR is a self-hosted CVE intelligence and detection-engineering platform.
FastAPI backend (`backend/`), React 19 + Vite frontend (`frontend/`, plain
JSX/CSS + semantic tokens + Radix primitives per ADR-003; no Tailwind), **PostgreSQL required in production**.

This file is the rulebook; `docs/AGENT_METHODOLOGY.md` is the working method
behind it (orient → plan → design → implement → verify → self-review → record).
Apply both on every task.

## Commands

- Backend tests: `cd backend && pytest tests/ -q`
- Frontend build (must pass before any frontend change is done): `cd frontend && npm run build`
- Dev servers: `uvicorn main:app --port 8000` (from `backend/`); `npm run dev` (from `frontend/`, proxies `/api` → `:8000`)

## Environment (Windows) — read first, these caused real lost hours

- Bash cwd resets between calls: always use absolute paths
  (`/c/Users/harsh/Documents/briefr-main/backend`), never bare `cd backend`.
- Not on PATH: `sqlite3`, `psql`, `wmic`. Foreground `sleep` is blocked —
  for waits, run the command as a background task and act on its
  completion notification; never poll in a loop.
- Postgres test run (danger zone 1 "both ways"): `./scripts/postgres-dev.sh start`
  (container `briefr-pg-test` on port **5433**, avoids `:5432` conflicts) →
  `DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr python3 -m pytest tests/ -q`
  (from `backend/`). Persistent local stack: `docker compose -f deploy/docker-compose.postgres.yml up -d` on `:5432`.
- Dev servers only via `.claude/launch.json` / preview_start — raw Bash
  servers collide with other sessions' ports (8000/5173).
- Browser E2E against local SQLite: seed ≥10 CVEs or quiet the scheduler
  first, or login hits "database is locked".

## Agent guardrails — each of these stalled a real session

- Never merge a PR unless the current user message says to merge.
- Never edit `.claude/settings*.json` or widen your own permissions.
- Never print `.env` contents, password hashes, or tokens to stdout.
- Never kill processes you didn't start this session.
- Browser logins are the user's job — ask, never type credentials.
- A request with 3+ items (especially UI/design): write the list to a
  checklist file first and tick items off — verbal lists don't survive
  context compaction.

## Error investigation — RCA-first (mandatory)

When the user shows an error or you detect one: **investigate to root cause before
fixing.** Reproduce/verify → trace the failing path → fix the underlying class of bug
(not a band-aid) → add a regression test or gate when recurrence is plausible → note in
`HANDOVER.md` if runtime behavior changed. Symptom-only patches without RCA are not done.

## PR workflow

- After push, CI + a Gemini review bot run. Wait with
  `gh pr checks <n> --watch` as a background task, then
  `gh pr view <n> --comments`; triage Gemini findings (real vs noise)
  before applying fixes. Don't re-poll manually.
- `dependency-audit` and `gitleaks` CI jobs are known-red on every run —
  not merge blockers until fixed.

## Source of truth

- `docs/PRODUCT_STATUS.md` is the living truth — when any other doc disagrees with it or with the code, they win, not the older doc.
- `docs/archive/snapshots/CODEBASE_CONTEXT.md`, `docs/archive/snapshots/FOLDER_STRUCTURE_GUIDE.md`, `docs/archive/snapshots/APPLICATION_EXECUTION_MAP.md`, `docs/archive/snapshots/TECHNICAL_INVENTORY.md` are periodic snapshots and may lag the code — verify against source before relying on them.
- Historical specs live in `docs/archive/` — never edit or resurrect them.
- Recent decisions and session context: `docs/HANDOVER.md` (newest entry
  first). Current work queue: `docs/planning/SPRINT_2026-07.md`.

## Danger zones — read before editing

1. **SQL:** the `db/` package is **Postgres-native** (Post-B, 2026-07;
   `db/dialect.py` was deleted — do not reintroduce a translation layer).
   Write new SQL Postgres-native (using parallel `_SQLITE` / `_PG` constants
   where SQLite compatibility is required to keep the default test suite green).
   Production is Postgres-only
   (`BRIEFR_REQUIRE_POSTGRES=1`); SQLite survives **only** as the
   zero-config test/dev fallback in `db/connection.py` (`db/pg_adapt.py`
   adapts for it). Tests default to SQLite — a query can pass the default
   suite and still break production, so for any `db/`-layer change run the
   suite both ways: default, and with `DATABASE_URL` pointing at Postgres.
2. **Scheduler locks:** job `id=` strings in `scheduler.py` must stay in sync
   with the lock mapping used by `routers/admin/ (jobs.py `_JOB_RUN_MAP`)`.
3. **Migrations are forward-only** (Alembic). Never edit an applied migration;
   add a new one. Exception: a revision that **never stamped** on any environment
   (failed mid-upgrade under transactional DDL) may be corrected in place — as with
   quoting `"references"` in `035` (Postgres reserved word). Raw SQL column names
   must not use unquoted reserved identifiers; `test_alembic_revisions.py` scans
   for that class of bug. Prefer rename (`rule_references`) over quoting for new
   columns. Postgres-native tables still need a real Postgres apply path before
   merge (`verify-local --full` / CI) — SQLite skips cannot catch DDL syntax.
4. **Secrets in logs:** structured logging redacts extra fields matching
   `*_KEY/_TOKEN/_SECRET/_PASSWORD`. Never interpolate secrets into log
   message strings — redaction only covers `extra` fields.
5. **`deploy/` scripts run on a live production box.** Changes must stay
   additive per the compatibility promise in `docs/planning/ROADMAP.md` /
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
  (see `docs/PRODUCT.md` anti-references).
- Motion: 120–180ms ease-out, opacity/transform only,
  `prefers-reduced-motion` respected (global rule exists — keep it).
- Every status word, pill, or badge ships with a discoverable explanation
  (tooltip/legend) — `docs/PRODUCT.md` design principle 1.
- **Repo-wide UX standards (permanent):** admin UX review findings apply to the
  whole product, not admin-only. Follow `docs/design/design-system.md` §23 and
  `.cursor/rules/design-system.mdc` — soft accent focus/active tokens, shared
  `DateTimePicker`, dropdowns for discrete settings, "Reset to default" labels,
  uppercase wayfinding, health-vs-freshness callouts, job progress while LOCKED.

## Docs rules

- Runtime behavior changed → update `docs/PRODUCT_STATUS.md` and
  `docs/SYSTEM_DESIGN.md` in the same PR.
- Endpoints changed → update `docs/API_REFERENCE.md` in the same PR.
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
