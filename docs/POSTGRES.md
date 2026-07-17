# PostgreSQL database (production)

BRIEFR stores all intel data in **PostgreSQL**. Production runs Postgres **17** in Docker at `/opt/infra/postgres`; the BRIEFR app on the host connects via `DATABASE_URL` (published port `127.0.0.1:5432`).

Use a host `postgresql-client` whose **major version matches** the server (17 in production; local compose may differ — see below). The deploy scripts install `postgresql-client` and fall back across supported majors.

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

## Local development

**Persistent dev Postgres (port 5432)** — shares the default port with production-style setups; use when you want a named volume:

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d   # Postgres 16 image (local dev); production is 17
```

**Disposable test Postgres (port 5433, PG-002)** — recommended for the dual-DB pytest rule when `:5432` is already taken (production, compose stack, or cloud VM):

```bash
./scripts/postgres-dev.sh start   # container briefr-pg-test on 127.0.0.1:5433
# prints DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr

cd backend && DATABASE_URL="$(../scripts/postgres-dev.sh url)" BRIEFR_REQUIRE_POSTGRES=1 python3 -m pytest tests/ -q
```

`./scripts/verify-local.sh --full` auto-starts `briefr-pg-test` when `DATABASE_URL` is unset and compose on `:5432` is not running.

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

- Postgres **17** in production (match production major for `pg_dump` / restore); local dev compose image may lag — use a client matching the server you connect to
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
| Embeddings search | NumPy cosine (no pgvector required today) |

## Backups

`python -m backup run` and `deploy/briefr-backup.sh` create `briefr-*.tar.gz[.age]` archives containing:

- `briefr.pgdump` — `pg_dump --format=custom`
- `.env` + `manifest.json`
- Optional **age** encryption (`BACKUP_AGE_KEY_FILE`)

**Host requirements:**

```bash
sudo apt install postgresql-client-17    # match production Postgres major
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
| `BACKUP_DIR` | Archive directory (default `/var/lib/briefr/backups`) |
| `BACKUP_RETENTION_COUNT` | Max `briefr-*.tar.gz[.age]` archives |
| `BACKUP_AGE_KEY_FILE` | age identity for encryption (outside `BACKUP_DIR`) |

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `PostgreSQL pool is not initialized` | Backend lifespan failed — check `journalctl -u briefr-backend` |
| `relation "cves" does not exist` | Run `alembic upgrade head` from `backend/` or restart backend |
| `pg_dump: connection refused` | Docker Postgres down — `cd /opt/infra/postgres && docker compose up -d` |
| `pg_dump: server version mismatch` | Install matching client, e.g. `apt install postgresql-client-17` (production) |
| Timeline/charts empty but `cve_count` > 0 | Fixed in app — ensure `/api/stats/timeline` returns non-zero counts; hard-refresh browser |
| Empty feed on first boot | Fewer than 10 CVE rows triggers NVD ingest, or run `scripts/seed_screenshot_data.py` with `DATABASE_URL` set |

## Log rotation

| Log | Location |
|-----|----------|
| BRIEFR backup runs | `${BACKUP_DIR}/logs/backup.log` — `BACKUP_LOG_MAX_BYTES` / `BACKUP_LOG_BACKUP_COUNT` |
| Postgres container | `/opt/infra/postgres` — compose / `docker logs` / volume log dir |
| BRIEFR backend | `journalctl -u briefr-backend` |
