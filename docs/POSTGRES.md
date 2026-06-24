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
| File backups (`briefr.db` tarball) | ✅ | ✅ (`pg_dump` custom format in same `briefr-*.tar.gz[.age]` archives) |
| sqlite-vec embeddings accelerator | optional | ❌ — use NumPy fallback |
| CI default | ✅ | opt-in via `POSTGRES_TEST_URL` |

## Architecture notes

- Runtime driver: **asyncpg** connection pool (`db/connection.py`)
- Migrations: **Alembic** + **psycopg** (sync, migration-time only)
- SQL compatibility: `db/dialect.py` translates `?` placeholders, `datetime('now')`, `INSERT OR IGNORE`, and `PRAGMA` checks
- Remaining V2.0 work: repository layer extraction, pgvector for embeddings, Docker Compose all-in-one

## Postgres-only production

When `DATABASE_URL` points at PostgreSQL, `DB_PATH` / `briefr.db` are **ignored** at runtime. To lock this in:

```bash
DATABASE_URL=postgresql://briefr:YOUR_PASSWORD@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
```

After verifying `/api/health` shows `"backend": "postgresql"`, you may archive the old SQLite file:

```bash
sudo systemctl stop briefr-backend
sudo mv /opt/briefr/backend/briefr.db /var/lib/briefr/backups/briefr.db.retired
sudo systemctl start briefr-backend
```

## Backups on PostgreSQL

`python -m backup run` (and `deploy/briefr-backup.sh`) **auto-detect** the backend:

| Backend | Archive contents | Tool |
|---------|------------------|------|
| SQLite | `briefr.db` + `.env` + `manifest.json` | `sqlite3` online backup |
| PostgreSQL | `briefr.pgdump` + `.env` + `manifest.json` | `pg_dump --format=custom` |

Requirements for Postgres backups:

- `postgresql-client` on the host (`pg_dump`, `pg_restore`)
- `DATABASE_URL` in `backend/.env` (same DSN the app uses)
- Existing backup settings still apply: `BACKUP_DIR`, `BACKUP_RETENTION_COUNT`, `BACKUP_AGE_KEY_FILE`, log rotation env vars

### systemd timer (production)

Use the dedicated Postgres timer (same 6h cadence as SQLite):

```bash
sudo cp /opt/briefr/deploy/briefr-pg-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now briefr-backup.timer   # if migrating from SQLite
sudo systemctl enable --now briefr-pg-backup.timer
```

Or keep `briefr-backup.timer` — both invoke the same `python -m backup run` path.

Manual backup:

```bash
sudo -u briefr bash /opt/briefr/deploy/briefr-backup.sh manual
```

### Restore PostgreSQL

```bash
sudo bash /opt/briefr/deploy/briefr-restore.sh --force /var/lib/briefr/backups/briefr-YYYYMMDDTHHMMSSZ.tar.gz.age
```

`DATABASE_URL` must be set in `.env`. The backend is stopped automatically; `pg_restore --clean --if-exists` loads `briefr.pgdump` from the archive.

Verify after restore:

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool | grep cve_count
```

### PostgreSQL server logs

BRIEFR backup run logs still go to `${BACKUP_DIR}/logs/backup.log` (size rotation via `BACKUP_LOG_MAX_BYTES`). PostgreSQL server logs are managed separately (Debian: `/etc/postgresql/*/main/postgresql.conf` + `/etc/logrotate.d/postgresql-common`).

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
