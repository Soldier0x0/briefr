# Self-host BRIEFR

One guide for installing and running BRIEFR on your server.

---

## At a glance

![Production architecture](assets/production-architecture.svg)

| Piece | What |
|-------|------|
| App | FastAPI `:8000` + React static via nginx |
| Database | **PostgreSQL 16** required; use `pgvector/pgvector:pg16` when embeddings are enabled |
| Code | `/opt/briefr` |
| Backups | `/var/lib/briefr/backups` |

---

## Quick start (development)

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd ../frontend && npm install && npm run dev
```

Open http://localhost:5173. First visit → complete **setup** to create the admin user.

**Sample data:** `python scripts/seed_screenshot_data.py` from repo root.

**Postgres locally:** `docker compose -f deploy/docker-compose.postgres.yml up -d`

---

## Production

```bash
bash deploy/setup.sh
bash deploy/briefr-update.sh
```

| Checklist | Setting |
|-----------|---------|
| Database | `DATABASE_URL=postgresql://...` |
| Require Postgres | `BRIEFR_REQUIRE_POSTGRES=1` |
| CORS | `ALLOWED_ORIGINS` = your public URL |
| Rate limits | `RATE_LIMIT_ENABLED=1` |
| Swagger off | `BRIEFR_ENV=production` |
| Static wallboard | optional `WALLBOARD_TOKEN` |

Optional edge: Cloudflare Tunnel + Zero Trust OTP. It is separate from BRIEFR's app login.

Full ops detail: [`OPERATIONS.md`](OPERATIONS.md) · Postgres: [`POSTGRES.md`](POSTGRES.md)

---

## Updates & backups

```bash
bash /opt/briefr/deploy/briefr-update.sh
bash /opt/briefr/deploy/briefr-restore.sh --list
```

Backups run every **6h** plus before each update. Archives are age-encrypted when `/var/lib/briefr/keys/backup-age.key` exists.

---

## Key environment flags

Do not copy every `.env.example` line blindly. Set the operating shape first:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL DSN; required in production |
| `BRIEFR_REQUIRE_POSTGRES` | Refuse startup without Postgres |
| `PROCRASTINATE_ENABLED` | Durable Postgres-backed jobs panel / retryable work |
| `EMBEDDINGS_ENABLED` | Local CPU semantic search / related-CVE similarity |
| `EMBEDDINGS_PGVECTOR` | Store embeddings in pgvector when Postgres has the extension |
| `BRIEFR_RATE_LIMIT_STORE` | Set `db` only if sharing buckets across workers |
| `RATE_LIMIT_ENABLED` | Inbound token buckets for IOC/refresh/login/wallboard |
| `NVD_API_KEY` | Recommended for ingest pacing |
| `OTX_API_KEY` | Pulses, campaigns, correlation |
| `BACKUP_DIR` | Default `/var/lib/briefr/backups` |

Full reference: `backend/.env.example` · API catalog: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## Something wrong?

Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
