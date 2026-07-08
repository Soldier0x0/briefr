# Postgres-Native Conversion Plan (Post-B)

**Purpose:** self-contained execution plan for converting BRIEFR's backend from
SQLite-dialect-with-Postgres-translation to Postgres-native. Written so an
agent with no memory of prior sessions (e.g. Cursor Composer) can pick this up
cold. Read `CLAUDE.md` first (danger zone 1 covers this exact area).

**Status as of 2026-07-08:** Phase 0 complete (#318). F3 complete (#319).
Phase 1 in progress — `db/sync_state.py` converted (#320);
`db/watchlist.py` + `db/webhooks.py` converted (#322);
`db/cache_retention.py` converted (PR 3). **6 SQL modules
remain** (batched into ~4 PRs — see below). Phases 2–4 not started.

---

## Phase 0 — CI full-suite gate — **DONE** (#318)

`test-postgres` runs `pytest tests/ -q` (full suite, ~760 passed / ~8 skipped).
Logging ring-buffer fix merged in same PR (Alembic `fileConfig` gotcha #7).

---

## Gotchas discovered while building Phase 0 (read before touching code)

These cost real debugging time this session — don't rediscover them.

1. **asyncpg pools are bound to the event loop that created them.** A test
   using a shared `with TestClient(app) as client:` fixture (pool created
   during `__enter__`, bound to the TestClient's own portal thread/loop)
   cannot touch that pool from a fresh `asyncio.run()` call in the test
   body — that creates a *different* loop. Symptom:
   `RuntimeError: PostgreSQL pool is not initialized` even though the pool
   demonstrably exists. Fix: `client.portal.call(async_fn)` runs the
   coroutine on the TestClient's own loop instead of a new one.
2. **`PostgresConnection.execute_fetchall()` returns plain `dict`s**
   (`db/connection.py` — search `[dict(record) for record in records]`),
   **not** SQLite's `Row` objects. `row[0]` (positional) works on SQLite,
   throws `KeyError: 0` on Postgres. Every row access must be by column
   name (`row["col"]`), no exceptions.
3. **`init_pool()`/`close_pool()` are idempotent no-ops when already in the
   right state** (`if _pool is not None: return` / `if _pool is not None:
   ... else return`), and both are no-ops entirely on SQLite. This makes a
   `run_db_test(coro)` helper safe to sprinkle liberally in tests — see
   `backend/tests/conftest.py`.
4. **Alembic migrations must run via a standalone `asyncpg` connection**,
   never via the pool — binding the pool inside a migration
   `asyncio.run()` call ties it to a loop that's about to close. See
   `backend/tests/test_postgres_pool.py`'s `postgres_migrations` fixture
   for the reference pattern.
5. **Raw `sqlite3.connect()` / `aiosqlite.connect(db_path)` in test seed
   helpers is a silent Postgres-incompatibility trap.** If a helper
   connects directly to the SQLite file path instead of going through
   `get_db()`, it silently no-ops on Postgres (writes to an empty local
   file nobody reads) instead of erroring — much harder to spot than a
   crash. Any test seed helper must use `get_db()`, not a raw driver call,
   unless it's testing something genuinely SQLite-only (see next point).
6. **Some things are genuinely SQLite-only, not just unconverted** — don't
   try to "fix" these into portability, they need real Postgres-side
   design work:
   - `GET /api/admin/storage/export` streams a `VACUUM INTO`'d SQLite
     file. No Postgres equivalent exists yet (Postgres backups go through
     `deploy/briefr-pg-backup.sh`, a separate `pg_dump`-based script).
     This is a **product gap**, not a test gap — decide whether this
     endpoint gets a Postgres implementation (e.g. shell out to
     `pg_dump`) or gets hidden/disabled when `is_postgres()`.
   - Test helpers using `datetime('now', '-2 days')` (SQLite scalar
     function) or `PRAGMA table_info(...)` (SQLite introspection) are
     marked `_requires_sqlite` / skip-on-Postgres in the test files
     listed below. These are testing infrastructure, not app behavior —
     no product decision needed, just leave them skipped until Phase 3
     (dialect.py deletion) forces a rewrite.
     Files: `test_wallboard.py`, `test_embeddings.py`, `test_forge.py`,
     `test_watchlist.py`, `test_brief_endpoint.py`, `test_admin_storage.py`.
7. **Alembic `fileConfig` wipes BRIEFR logging handlers.** Collection-time
   `from main import app` calls `configure_logging()` (stderr JSON + ring
   buffer). Session `_postgres_schema_once` then runs Alembic, whose
   `env.py` calls `fileConfig` and replaces `root.handlers` with Alembic's
   console handler only — new logs reach stderr but not the ring buffer, so
   `test_admin_logs` / `test_structured_logging` fail late in the Postgres
   suite. Fix: re-`configure_logging()` after migrations in `conftest.py`,
   autouse `clear_log_buffer()` + `ensure_ring_buffer_attached()` per test,
   and `disable_existing_loggers=False` in `alembic/env.py`.

---

## Phase 1 — Convert `db/*.py` modules to Postgres-native SQL

**Rule (from `CLAUDE.md` danger zone 1):** all SQL today is written in
SQLite dialect with `?` placeholders, translated to Postgres at runtime by
`db/dialect.py`. This phase deletes that translation module-by-module by
rewriting each module's SQL to native Postgres (`$1`/`$2` placeholders,
Postgres-specific functions where useful) and removing its dependency on
`db/dialect.py`'s regex translation for that module's queries.

**PR sizing (agreed 2026-07-08):** default **one module = one PR = one
deploy** for rollback clarity. **Batch only small, independent modules**
(e.g. `watchlist` + `webhooks`). Keep **`cve.py` and `init.py` as solo PRs**
(highest blast radius).

### Conversion pattern (locked in #320)

Reference implementation: `backend/db/sync_state.py`.

1. Define parallel SQL constants: `_FOO_SQLITE` (`?`) and `_FOO_PG` (`$n`).
2. Pick SQL via connection type — **not** `is_postgres()` env lookup:
   `type(db).__name__ == "PostgresConnection"`.
3. Type hints: `DbConnection` from `db/types.py` (not `aiosqlite.Connection`).
4. `utcnow_str()` bound params are fine on both backends; prefer them over
   `datetime('now')` in SQL.
5. Add or extend module tests; run **full** `pytest tests/ -q` before merge.

### Module status

| # | Module | Lines | Status |
|---|--------|-------|--------|
| 1 | `db/types.py` | 27 | **Skip** — Protocol only, no SQL |
| 2 | `db/sync_state.py` | 82 | **Done** — #320 |
| 3–4 | `db/watchlist.py` + `db/webhooks.py` | 78 + 147 | **Done** — PR 2 |
| 5 | `db/cache_retention.py` | 191 | **Done** — PR 3 |
| 6 | `db/cache.py` | 303 | **Next PR** |
| 7 | `db/enrichment.py` | 430 | Pending |
| 8–9 | `db/metadata.py` + `db/correlation.py` | 478 + 489 | Pending (batched) |
| 10 | `db/cve.py` | 544 | Pending — **solo PR** |
| 11 | `db/init.py` | 627 | Pending — **solo PR, last** |

**~4 PRs remaining** in Phase 1 (down from 9 with batching).

### Legacy numbered list (same order)

1. `db/types.py` (27 lines) — **no SQL**; Protocol-only, no conversion needed.
2. `db/sync_state.py` (82 lines) — **converted** (#320).
3. `db/watchlist.py` (78 lines) — batch with #4.
4. `db/webhooks.py` (147 lines) — batch with #3.
5. `db/cache_retention.py` (191 lines)
6. `db/cache.py` (303 lines)
7. `db/enrichment.py` (430 lines)
8. `db/metadata.py` (478 lines)
9. `db/correlation.py` (489 lines)
10. `db/cve.py` (544 lines) — highest risk; solo PR.
11. `db/init.py` (627 lines) — last; enables Phase 3.

**Per-module checklist (apply to every PR in this phase):**

- [ ] Read the module's current SQL. Identify every `?` placeholder,
      every SQLite-specific function (`datetime()`, `julianday()`,
      `strftime()`, `PRAGMA`), every `INSERT OR REPLACE` /
      `ON CONFLICT` phrasing that differs between dialects.
- [ ] Rewrite to native Postgres syntax directly in this module —
      no more relying on `db/dialect.py`'s regex translation for this
      module's queries.
- [ ] Remove this module from whatever registers it with
      `db/dialect.py`'s translation path (check how `dialect.py` decides
      what to translate — likely all `PostgresConnection` calls, so this
      may require the connection layer to know which modules are
      "already native" — **read `db/dialect.py` and `db/connection.py`
      fully before starting this phase**, the exact mechanism isn't
      re-derived here, verify against current code).
- [ ] Run this module's tests on **both** SQLite and Postgres:
      ```
      cd backend && pytest tests/test_<module>*.py -q
      cd backend && DATABASE_URL="postgresql://briefr:briefr@127.0.0.1:5433/briefr" BRIEFR_REQUIRE_POSTGRES=1 JWT_SECRET=ci-test-jwt-secret-not-for-production pytest tests/test_<module>*.py -q
      ```
      (see "Local Postgres setup" below for how to stand up that
      container)
- [ ] Run the **full** suite on both dialects before merging — a module
      conversion can break callers in other modules that share tables.
- [ ] Update `docs/PRODUCT_STATUS.md` if this changes documented runtime
      behavior (per `CLAUDE.md` docs rules).

---

## Phase 2 — Unify exception handling

**After all modules in Phase 1 are converted:**

- Give the connection wrapper (`db/connection.py`) **one app-level
  exception type** that translates asyncpg errors (e.g. `DatabaseError`
  wrapping whatever asyncpg raises).
- Delete all `sqlite3.*` exception handling **outside** `db/` — these
  currently exist in (verify against current code, this list is from a
  2026-07 grep and may be stale):
  - `backend/backup/manager.py`
  - `backend/dependencies.py`
  - `backend/scheduler.py`
  - `backend/tracking.py`
- Rationale: the `audit()` bug fixed in Sprint A0 (catching
  `sqlite3.OperationalError` which never fires on Postgres, silently
  swallowing errors) is exactly the class of bug this phase prevents from
  recurring. The dialect layer's blast radius includes exception types,
  not just SQL syntax.

## Phase 3 — Delete `db/dialect.py`

Only after **every** module using it has been converted (Phase 1 complete)
and exception handling is unified (Phase 2 complete). At this point:

- Delete `db/dialect.py` entirely.
- Delete the SQLite code path from `db/connection.py`'s
  `get_connection()` if the product has fully moved to
  `BRIEFR_REQUIRE_POSTGRES=1` in all supported environments — **confirm
  this with the user first**, this is a bigger decision (drops SQLite
  support entirely) than the rest of this plan and isn't pre-approved.
- Resolve the 6 skip-marked test files listed in gotcha #6 — with
  `dialect.py` gone, `is_postgres()` may not even be meaningfully
  toggleable the same way, so those tests need redesigning, not just
  unskipping.

## Phase 4 — CI backup verification

Add a dump → restore → row-count round-trip to the CI Postgres job:
run `deploy/briefr-pg-backup.sh` then `deploy/briefr-restore.sh` against
the CI Postgres container, assert restored row counts match source for
the core tables (`cves`, `kev_deadlines`, at minimum). This was flagged
in the original Track B "After Track B" notes and in Sprint J2 — verify
it hasn't been done by some other track before starting.

---

## Local Postgres setup (for running the dialect verification commands above)

```bash
docker run -d --name briefr-pg-test \
  -e POSTGRES_USER=briefr -e POSTGRES_PASSWORD=briefr -e POSTGRES_DB=briefr \
  -p 5433:5432 postgres:16-alpine \
  -c fsync=off -c full_page_writes=off -c synchronous_commit=off
```

(`fsync=off` etc. are safe for this throwaway local test container only —
never use these flags on anything with real data. They avoid a severe
Docker-Desktop-on-Windows disk I/O bottleneck seen this session — a single
`TRUNCATE` took 8s+ with fsync on, <1s with it off.)

Port **5433**, not 5432 — on Windows, a native Postgres install may
already be listening on 5432; connecting to the wrong server produces a
confusing "password authentication failed" error that has nothing to do
with credentials. Verify with `Get-NetTCPConnection -LocalPort 5432` if
5433 seems unavailable for some reason.

---

## Known pre-existing test failures (not part of this work, do not "fix")

These 5 fail identically on unmodified `main`, on SQLite, with no
`DATABASE_URL` set — Windows-environment issues (file-permission bits,
`pg_dump` path detection), unrelated to the Postgres-native conversion:

- `test_backup_encryption.py::test_generate_age_key_permissions_and_format`
- `test_backup_encryption.py::test_generate_age_key_leaves_existing_parent_mode_alone`
- `test_backup_encryption.py::test_run_backup_produces_age_encrypted_archive`
- `test_backup_manager.py::test_run_backup_creates_verified_archive`
- `test_backup_postgres.py::test_pg_tool_prefers_highest_numeric_version`

One more test is timing-sensitive and occasionally flaky under system
load (confirmed pre-existing, reproduces on unmodified `main`), not a
dialect issue: `test_tracking.py::test_record_api_call_schedules_background_flush`.

If the full suite ever shows a failure **other than these 6**, treat it as
real and investigate — that's exactly the class of bug this whole gate
exists to catch (see the 5 real bugs found and fixed in PR #303's third
commit for what that investigation looks like in practice).
