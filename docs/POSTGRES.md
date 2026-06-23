# PostgreSQL support (V2.0 foundation — beta)

BRIEFR defaults to **SQLite** (`DB_PATH=briefr.db`). PostgreSQL is **optional** and intended for deployments that need concurrent writers or multiple uvicorn workers.

## Quick start (local dev)

1. Start PostgreSQL:

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d
```

2. Point BRIEFR at Postgres in `backend/.env`:

```bash
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
# DB_PATH is ignored when DATABASE_URL is set
DATABASE_POOL_SIZE=10
```

3. Run the backend (from `backend/`):

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

On first boot, Alembic creates the schema (`alembic upgrade head` via `init_db()`).

With PostgreSQL validated in your environment you may increase workers:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

SQLite deployments must stay at **`--workers 1`**.

## Migrating existing SQLite data

**Always take a BRIEFR backup first** (Admin → Backups or `deploy/briefr-backup.sh`).

Recommended tool: [pgloader](https://pgloader.io/) — loads `briefr.db` into PostgreSQL while preserving rows.

Example `briefr.load` file:

```lisp
LOAD DATABASE
     FROM sqlite:///opt/briefr/backend/briefr.db
     INTO postgresql://briefr:briefr@127.0.0.1:5432/briefr

WITH include drop, create tables, create indexes, reset sequences

SET work_mem to '16MB', maintenance_work_mem to '128 MB';
```

```bash
pgloader briefr.load
```

Then set `DATABASE_URL`, restart the backend, and verify `/api/health` (`cve_count`, feeds).

**Rollback:** stop backend → restore `briefr.db` from your pre-migration tarball → remove `DATABASE_URL` → restart on SQLite.

## What works today (foundation)

| Area | SQLite | PostgreSQL |
|------|--------|------------|
| Schema bootstrap | `init_db()` | Alembic `001_initial` |
| CVE feed / ingest | ✅ | ✅ (beta — report issues) |
| IOC lookup | ✅ | ✅ |
| Admin pane | ✅ | ✅ (integrity check adapted) |
| File backups (`briefr.db` tarball) | ✅ | ❌ — use `pg_dump` instead |
| sqlite-vec embeddings accelerator | optional | ❌ — use NumPy fallback |
| CI default | ✅ | opt-in via `POSTGRES_TEST_URL` |

## Architecture notes

- Runtime driver: **asyncpg** connection pool (`db/connection.py`)
- Migrations: **Alembic** + **psycopg** (sync, migration-time only)
- SQL compatibility: `db/dialect.py` translates `?` placeholders, `datetime('now')`, `INSERT OR IGNORE`, and `PRAGMA` checks
- Remaining V2.0 work: `pg_dump` backup path, repository layer extraction, pgvector for embeddings, Docker Compose all-in-one

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | _(empty → SQLite via `DB_PATH`)_ | `postgresql://user:pass@host:5432/dbname` |
| `DB_PATH` | `briefr.db` | SQLite file when `DATABASE_URL` unset |
| `DATABASE_POOL_SIZE` | `10` | asyncpg pool size |
| `BRIEFR_REQUIRE_POSTGRES` | `0` | When `1`, refuse to start unless `DATABASE_URL` points at PostgreSQL |

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `PostgreSQL pool is not initialized` | `init_pool()` not run before `get_db()` — check app lifespan |
| `relation "cves" does not exist` | Migrations not applied — restart backend or run `alembic upgrade head` from `backend/` |
| SQL syntax error on Postgres | Report upstream — dialect adapter may need extending |
| Still see SQLite lock errors | You're still on SQLite — confirm `DATABASE_URL` is set and backend was restarted |
