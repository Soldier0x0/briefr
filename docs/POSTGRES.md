# PostgreSQL database (production)

**Install steps (Postgres + pgvector + linking `DATABASE_URL`):** start at [`SELF_HOST.md`](SELF_HOST.md) §2 (dev) or §3 (production). This document is the **deep reference** for DSN shape, backups, restore, dual-dialect tests, external Postgres, and pgvector cutover.

BRIEFR stores all intel data in **PostgreSQL**. Production runs Postgres **16** in Docker at `/opt/infra/postgres`; the BRIEFR app on the host connects via `DATABASE_URL` (published port `127.0.0.1:5432`).

Use a host `postgresql-client` whose **major version matches** the server (16 in production). The deploy scripts install `postgresql-client` and fall back across supported majors.

## Required configuration

In `backend/.env`:

```bash
DATABASE_URL=postgresql://briefr:YOUR_PASSWORD@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

Verify after restart:

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool | grep -E '"backend"|cve_count'
```

Expect `"backend": "postgresql"`.

## Infrastructure (`/opt/infra/postgres`)

Postgres runs outside the BRIEFR git tree:

```bash
cd /opt/infra/postgres
docker compose up -d
docker compose ps    # confirm healthy
```

BRIEFR only needs TCP access to the mapped port. Schema is applied by Alembic on backend startup (`alembic upgrade head` via `init_db()`).

**Logs and volume backups** are configured in the infra repo (compose logging driver, volume snapshots). BRIEFR handles **logical backups** via `pg_dump` on the host.

**pgvector requirement:** enabling `EMBEDDINGS_ENABLED=1` requires the `vector` extension. Use `pgvector/pgvector:pg16` for local, CI, and production Postgres 16; plain `postgres:16` images cannot run the embeddings migrations or pgvector ANN queries.

## Local development

**Persistent dev Postgres (port 5432)** — shares the default port with production-style setups; use when you want a named volume:

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d   # pgvector/pgvector:pg16 (local + prod major)
```

**Disposable test Postgres (port 5433, PG-002)** — recommended for the dual-DB pytest rule when `:5432` is already taken (production, compose stack, or cloud VM):

```bash
./scripts/postgres-dev.sh start   # briefr-pg-test on 127.0.0.1:5433 (image pgvector/pgvector:pg16)
# prints DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr

cd backend && DATABASE_URL="$(../scripts/postgres-dev.sh url)" BRIEFR_REQUIRE_POSTGRES=1 python3 -m pytest tests/ -q
```

If you previously started `briefr-pg-test` on plain `postgres:16-alpine`, recreate once so `vector` is available:

```bash
./scripts/postgres-dev.sh destroy && ./scripts/postgres-dev.sh start
```

`./scripts/verify-local.sh --full` auto-starts `briefr-pg-test` when `DATABASE_URL` is unset and compose on `:5432` is not running.

### Dual-dialect tests (SQLite default + Postgres CI)

- **Default pytest** (`cd backend && pytest tests/ -q`) uses the **SQLite** zero-config fallback. Production SQL is Postgres-native; parallel `_SQLITE` / `_PG` constants in `backend/db/` keep that suite green.
- **CI** also runs a **`test-postgres`** job (and local `--full` / `postgres-dev.sh`) against real Postgres — that is the production-dialect signal.
- **Ratchet:** `backend/tests/test_sql_dialect_pairs.py` requires every module-level `_PG` constant to have a same-file `_SQLITE` sibling or an explicit `# pg-only` marker, and caps the pair count at `ALLOWED_MAX` (may only stay equal or decrease without intentional bump). Testcontainers / Postgres-as-default CI remain a later follow-on (not this ratchet).

```bash
# backend/.env (either stack — pick one URL)
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr   # compose
# DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr  # disposable dev/CI
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

```bash
cd backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

With Postgres validated you may run multiple workers (`--workers 2`); connection pooling is via asyncpg.

## External Postgres (no bundled container)

When Postgres is already running (production `/opt/infra/postgres`, managed cloud DB, or a team-shared instance), **do not** start `deploy/docker-compose.postgres.yml`. Point BRIEFR at the server with `DATABASE_URL` only:

```bash
cp deploy/external-postgres.env.example backend/.env
# edit DATABASE_URL, then:
cd backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Requirements:

- Postgres **16** in production (match production major for `pg_dump` / restore); use a client matching the server you connect to
- Network reachability from the BRIEFR host to the DB port
- Alembic migrations run on backend startup (`init_db()`)

Verify: `curl -s http://127.0.0.1:8000/api/health` → `"backend": "postgresql"`.

## Architecture

| Layer | Technology |
|-------|------------|
| Runtime driver | **asyncpg** pool (`db/connection.py`) |
| Migrations | **Alembic** + **psycopg** (sync, migration-time) |
| SQL compatibility | `db/pg_adapt.py` adapts legacy router SQL at the Postgres connection boundary |
| Durable jobs | **Procrastinate** (`PROCRASTINATE_ENABLED=0` default). Schema applied by Alembic `028_procrastinate_schema` (official `schema.sql`). In-process worker starts from `main.py` lifespan when enabled. |
| Embeddings search | `embeddings` (`vector(384)`) + scheduler/auto-on-ingest writes with `content_hash`. Hybrid search and related CVEs prefer pgvector ANN on Postgres, with SQLite BLOB / legacy `cve_embeddings` fallback for dev and cold-index cases. Requires `pgvector/pgvector:pg16` when `EMBEDDINGS_ENABLED=1`. |

## Backups

`python -m backup run` and `deploy/briefr-backup.sh` create `briefr-*.tar.gz[.age]` archives containing:

- `briefr.pgdump` — `pg_dump --format=custom`
- `.env` + `manifest.json`
- Optional **age** encryption (`BACKUP_AGE_KEY_FILE`)

**Host requirements:**

```bash
sudo apt install postgresql-client-16    # match production Postgres major
# or: apt install postgresql-client        # when the meta package tracks your major
```

`briefr-update.sh` installs the client automatically when `DATABASE_URL` is set.

### Scheduled backups (production)

**Default:** APScheduler job `scheduled_backup` inside `briefr-backend.service`
(honours `BACKUP_INTERVAL_HOURS` and M-4 interval guard). Fresh installs from
`deploy/lib.sh` **disable** `briefr-pg-backup.timer` to avoid double archives.

Manual / break-glass backup:

```bash
sudo -u briefr bash /opt/briefr/deploy/briefr-pg-backup.sh manual
```

Legacy host timer (optional — **do not** run alongside in-app scheduled backups):

```bash
sudo cp /opt/briefr/deploy/briefr-pg-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now briefr-pg-backup.timer
```

### Restore

```bash
sudo bash /opt/briefr/deploy/briefr-restore.sh --force \
  /var/lib/briefr/backups/briefr-YYYYMMDDTHHMMSSZ.tar.gz.age
```

`DATABASE_URL` must be set. Restore uses `pg_restore --clean --if-exists`.

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool | grep cve_count
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | **Required.** `postgresql://user:pass@host:5432/dbname` |
| `BRIEFR_REQUIRE_POSTGRES` | Set `1` to refuse startup without Postgres |
| `DATABASE_POOL_SIZE` | asyncpg pool size (default `10`) |
| `DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS` | Wait for a free pool slot before HTTP 503 (default `10`) |
| `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` | **SQL statement** timeout on pooled connections (default `60`). Not for feed/API HTTP — each source has its own timeout in `feeds/`. Do not raise this to mask slow CIRCL/Sploitus/etc.; commit or close the connection before outbound source I/O (`db/txn_boundaries.py`). |
| `EMBEDDINGS_ENABLED` | Optional semantic retrieval toggle; requires `pgvector/pgvector:pg16` on Postgres |
| `EMBEDDINGS_AUTO_ON_INGEST` | When embeddings are enabled, warm vectors for new/updated CVEs after ingest (default `1`) |
| `BACKUP_DIR` | Archive directory (default `/var/lib/briefr/backups`) |
| `BACKUP_RETENTION_COUNT` | Max `briefr-*.tar.gz[.age]` archives |
| `BACKUP_AGE_KEY_FILE` | age identity for encryption (outside `BACKUP_DIR`) |

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `PostgreSQL pool is not initialized` | Backend lifespan failed — check `journalctl -u briefr-backend` |
| `relation "cves" does not exist` | Run `alembic upgrade head` from `backend/` or restart backend |
| `pg_dump: connection refused` | Docker Postgres down — `cd /opt/infra/postgres && docker compose up -d` |
| `pg_dump: server version mismatch` | Install matching client, e.g. `apt install postgresql-client-16` (production) |
| Timeline/charts empty but `cve_count` > 0 | Fixed in app — ensure `/api/stats/timeline` returns non-zero counts; hard-refresh browser |
| Empty feed on first boot | Fewer than 10 CVE rows triggers NVD ingest, or run `scripts/seed_screenshot_data.py` with `DATABASE_URL` set |
| `extension "vector" is not available` / Alembic 032 fails | Postgres image lacks pgvector — use `pgvector/pgvector:pg16` (same major as prod); recreate disposable containers after the image change |
| Job fails with `Database command timeout` during another feed’s CIRCL/HTTP | SQL `command_timeout` budget shared under lock wait — not that job’s HTTP timeout. Ensure writers commit/close before source I/O (`db/txn_boundaries.py`); do not raise `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` first |

## pgvector cutover (embeddings E1)

Embeddings ANN, hybrid search, and embeddings-backed related CVEs need the **`vector`** extension. Plain `postgres:*-alpine` images do **not** ship it.

| Env | Image |
|-----|--------|
| Local compose (`deploy/docker-compose.postgres.yml`) | `pgvector/pgvector:pg16` |
| Disposable / CI (`scripts/postgres-dev.sh`, GitHub `test-postgres`) | `pgvector/pgvector:pg16` |
| Production `/opt/infra/postgres` | Cut over to **`pgvector/pgvector:pg16`** with the E1 feature deploy (**stay on major 16** — do not jump to pg17 for this) |

**Production cutover sequence** (with feature deploy — do **not** run during design-only work):

1. Backup (`pg_dump` / existing backup job)
2. Stop container; set image to `pgvector/pgvector:pg16`; **same volume mounts**
3. Start; verify `SELECT version()`, CVE count
4. Backend startup runs Alembic → `CREATE EXTENSION IF NOT EXISTS vector` + `embeddings` table + migration of legacy `cve_embeddings`
5. Smoke: `/api/health`, feed, `GET /api/search/semantic`, related CVEs, and Admin → AI operations retrieval health

**Data loss risk:** wrong volume on recreate — backup + keep the same volume name. Extension install itself is non-destructive.

Verify extension after migrate:

```bash
psql "$DATABASE_URL" -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM embeddings;"
```

Legacy `cve_embeddings` remains as a read fallback for older rows/cold indexes; current writes target `embeddings` and current retrieval prefers pgvector ANN when available.

| Log | Location |
|-----|----------|
| BRIEFR backup runs | `${BACKUP_DIR}/logs/backup.log` — `BACKUP_LOG_MAX_BYTES` / `BACKUP_LOG_BACKUP_COUNT` |
| Postgres container | `/opt/infra/postgres` — compose / `docker logs` / volume log dir |
| BRIEFR backend | `journalctl -u briefr-backend` |
