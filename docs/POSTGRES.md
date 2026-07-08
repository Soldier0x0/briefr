# PostgreSQL database (production)

BRIEFR stores all intel data in **PostgreSQL**. Production runs Postgres **16** in Docker at `/opt/infra/postgres`; the BRIEFR app on the host connects via `DATABASE_URL` (published port `127.0.0.1:5432`).

Use a host `postgresql-client` whose **major version matches** the container (16 today; 17+ when you upgrade Postgres). The deploy scripts install `postgresql-client` and fall back across supported majors.

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

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d   # Postgres 16
```

```bash
# backend/.env
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

```bash
cd backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

With Postgres validated you may run multiple workers (`--workers 2`); connection pooling is via asyncpg.

## Architecture

| Layer | Technology |
|-------|------------|
| Runtime driver | **asyncpg** pool (`db/connection.py`) |
| Migrations | **Alembic** + **psycopg** (sync, migration-time) |
| SQL compatibility | `db/pg_adapt.py` adapts legacy router SQL at the Postgres connection boundary |
| Embeddings search | NumPy cosine (no pgvector required today) |

## Backups

`python -m backup run` and `deploy/briefr-backup.sh` create `briefr-*.tar.gz[.age]` archives containing:

- `briefr.pgdump` — `pg_dump --format=custom`
- `.env` + `manifest.json`
- Optional **age** encryption (`BACKUP_AGE_KEY_FILE`)

**Host requirements:**

```bash
sudo apt install postgresql-client-16    # match your Postgres major
# or: apt install postgresql-client        # when the meta package tracks your major
```

`briefr-update.sh` installs the client automatically when `DATABASE_URL` is set.

### systemd timer (production)

```bash
sudo cp /opt/briefr/deploy/briefr-pg-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now briefr-pg-backup.timer
```

Manual backup:

```bash
sudo -u briefr bash /opt/briefr/deploy/briefr-backup.sh manual
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
| `pg_dump: server version mismatch` | Install matching client, e.g. `apt install postgresql-client-16` |
| Timeline/charts empty but `cve_count` > 0 | Fixed in app — ensure `/api/stats/timeline` returns non-zero counts; hard-refresh browser |
| Empty feed on first boot | Fewer than 10 CVE rows triggers NVD ingest, or run `scripts/seed_screenshot_data.py` with `DATABASE_URL` set |

## Log rotation

| Log | Location |
|-----|----------|
| BRIEFR backup runs | `${BACKUP_DIR}/logs/backup.log` — `BACKUP_LOG_MAX_BYTES` / `BACKUP_LOG_BACKUP_COUNT` |
| Postgres container | `/opt/infra/postgres` — compose / `docker logs` / volume log dir |
| BRIEFR backend | `journalctl -u briefr-backend` |
