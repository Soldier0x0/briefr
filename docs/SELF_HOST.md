# Self-host BRIEFR

**Authoritative install guide.** Pick one path below — you do not need to read every section.

| I want to… | Go to |
|------------|-------|
| Try BRIEFR locally in 5 minutes | [§1 Quick dev (SQLite)](#1-quick-local-development-sqlite) |
| Develop or test with real Postgres + pgvector | [§2 Postgres dev](#2-local-development-with-postgresql--pgvector) |
| Run on a production Debian server | [§3 Production](#3-production-debian--systemd--nginx) |
| Deep Postgres / backup / pgvector cutover | [`POSTGRES.md`](POSTGRES.md) |
| Day-2 ops (updates, smoke, scheduler) | [`OPERATIONS.md`](OPERATIONS.md) |
| Something broke after install | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |

---

## At a glance

![Production architecture](assets/production-architecture.svg)

| Piece | What |
|-------|------|
| App | FastAPI `:8000` + React static via nginx (production) or Vite `:5173` (dev) |
| Database | **PostgreSQL 16** required in production; use **`pgvector/pgvector:pg16`** when embeddings or SigmaHQ index are enabled |
| Code (production) | `/opt/briefr` |
| Backups (production) | `/var/lib/briefr/backups` |
| Schema | Alembic migrations run automatically on backend startup (`init_db()` → `alembic upgrade head`) |

---

## 1. Quick local development (SQLite)

**Use when:** you want to evaluate BRIEFR with zero database setup.  
**Not for production** — SQLite is a dev/test fallback only.

### Prerequisites

- Python 3.11+
- Node.js 22.22+ (required by `react-router` 8.x pinned in the frontend)
- Git

### Steps

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # optional API keys — app works without them
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

In a second terminal:

```bash
cd briefr/frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api → :8000
```

1. Open http://localhost:5173
2. Complete **first-run setup** to create the admin user (shown when no users exist)
3. Optional sample data: `python scripts/seed_screenshot_data.py` from repo root

### Verify

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

| Check | Expected |
|-------|----------|
| `"backend"` | `"sqlite"` |
| `"cve_count"` | `0` on first boot, then grows (auto-ingest if &lt; 10 CVEs) |
| UI loads | Login/setup screen at `:5173` |

**Bare cloud VM note:** if `.env` contains a placeholder Postgres URL and nothing listens on `:5432`, startup fails. Clear it: `DATABASE_URL=""` and `BRIEFR_REQUIRE_POSTGRES=0` in `backend/.env`.

---

## 2. Local development with PostgreSQL + pgvector

**Use when:** you want production-like behaviour locally (migrations, pgvector, dual-dialect tests, embeddings, SigmaHQ index).

**Not for production.** This path uses the Vite dev server (`npm run dev` on `:5173`). For a permanent install with PostgreSQL and nginx serving a built SPA, use [§3 Production](#3-production-debian--systemd--nginx) — `briefr-install.sh` / `setup.sh` runs `npm run build` and systemd + nginx handle the UI.

### Prerequisites

- Everything in §1, plus **Docker** (or an existing Postgres 16 server with the `vector` extension)

### Step 1 — Start Postgres (pgvector image)

From the repo root:

```bash
docker compose -f deploy/docker-compose.postgres.yml up -d
```

This runs **`pgvector/pgvector:pg16`** on `127.0.0.1:5432` (user/db/password: `briefr` / `briefr` / `briefr`).

**Port 5432 already in use?** Use the disposable test container on **:5433**:

```bash
./scripts/postgres-dev.sh start
# prints DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5433/briefr
```

**Already have Postgres elsewhere?** Skip compose; set `DATABASE_URL` to your server — see [`POSTGRES.md` § External Postgres](POSTGRES.md#external-postgres-no-bundled-container).

### Step 2 — Link the app to the database

Edit `backend/.env`:

```bash
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

Use port **5433** if you started `postgres-dev.sh` instead of compose.

### Step 3 — Start backend and frontend

```bash
cd backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd frontend && npm run dev
```

On first backend start, **Alembic applies all migrations** (including `vector` extension and embeddings tables when the image supports it).

### Step 4 — Verify database link

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

| Check | Expected |
|-------|----------|
| `"backend"` | `"postgresql"` |
| `"cve_count"` | number (ingest or seed script) |
| pgvector (optional) | `psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname='vector';"` → one row |

### Step 5 — First-run setup and optional data

1. Open http://localhost:5173 → create admin user
2. Optional: `python scripts/seed_screenshot_data.py` (with `DATABASE_URL` set)
3. Optional embeddings: `EMBEDDINGS_ENABLED=1` in `.env` (requires `pip install fastembed` and pgvector image above)

### Step 6 — Optional feature flags (dev)

| Variable | When to set |
|----------|-------------|
| `EMBEDDINGS_PGVECTOR` | `1` (default) — store vectors in Postgres when extension exists |
| `SIGMAHQ_INDEX_SYNC_ENABLED` | `1` (default) — weekly SigmaHQ mirror; **first sync is manual**: Admin → Feed health → SigmaHQ → Sync |
| `OTX_API_KEY` | Pulses / correlation (optional) |
| `NVD_API_KEY` | Recommended for ingest rate limits |

Full list: `backend/.env.example` and [README environment table](../README.md).

---

## 3. Production (Debian + systemd + nginx)

**Use when:** installing BRIEFR on a server you operate.

### Choose your production path

| Environment | First install | Apply new release | Start / stop / restart |
|-------------|---------------|-------------------|-------------------------|
| **Production zone** (no outbound git; artifact/rsync) | `bash deploy/briefr-install.sh` | `bash deploy/briefr-deploy.sh` | `bash deploy/briefr-service.sh restart` |
| **Internet-connected** (git pull OK) | `bash deploy/setup.sh` | `bash deploy/briefr-update.sh` *(legacy)* | `bash deploy/briefr-service.sh restart` |

**Production zone workflow:** copy or extract the release to `/opt/briefr`, edit `backend/.env`, then `briefr-install.sh` once. Later releases: replace the tree (or rsync delta), then `briefr-deploy.sh`. Day-to-day restarts after `.env` changes: `briefr-service.sh` — no build, no git.

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Debian 11 / 12 / 13 (or compatible) | `deploy/setup.sh` targets Debian |
| PostgreSQL **16** with **pgvector** | Production: Docker at `/opt/infra/postgres` with image `pgvector/pgvector:pg16` — see [`POSTGRES.md`](POSTGRES.md) |
| DNS / TLS (optional) | nginx serves the app; many operators add Cloudflare Tunnel or reverse proxy |
| API keys (recommended) | At minimum `NVD_API_KEY`; see `backend/.env.example` |

### Step 1 — Provision PostgreSQL

Postgres runs **outside** the BRIEFR git tree. Production layout:

```bash
cd /opt/infra/postgres
docker compose up -d
docker compose ps    # confirm healthy
```

Image must be **`pgvector/pgvector:pg16`** (plain `postgres:16` cannot run embeddings migrations).

Create the database/user to match your DSN, or use the defaults from your infra compose file.

Detail: [`POSTGRES.md` § Infrastructure](POSTGRES.md#infrastructure-optinfrapostgres) and [§ pgvector cutover](POSTGRES.md#pgvector-cutover-embeddings-e1).

### Step 2 — Install the application

**Production zone** (artifact already on disk at `/opt/briefr` — no `git pull`):

```bash
# As root — creates venv, .env template, builds frontend, systemd + nginx
bash /opt/briefr/deploy/briefr-install.sh
```

**Internet-connected** (clone from GitHub):

```bash
bash deploy/setup.sh
```

`setup.sh` installs Python, clones to `/opt/briefr`, creates the venv, then runs `briefr-update.sh`.

### Step 3 — Configure `backend/.env`

On the server: `/opt/briefr/backend/.env`

**Minimum production shape:**

```bash
DATABASE_URL=postgresql://briefr:YOUR_PASSWORD@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
JWT_SECRET=<openssl rand -hex 32>
BRIEFR_ENV=production
ALLOWED_ORIGINS=https://your-public-hostname.example
RATE_LIMIT_ENABLED=1
```

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | **Required** — TCP to Postgres |
| `BRIEFR_REQUIRE_POSTGRES` | **Required** — refuse SQLite fallback |
| `JWT_SECRET` | **Required** in production — session signing |
| `ALLOWED_ORIGINS` | Your public URL (not `:5173`) |
| `NVD_API_KEY` | Strongly recommended |
| `EMBEDDINGS_ENABLED` | Optional semantic search (`fastembed` in venv) |
| `EMBEDDINGS_PGVECTOR` | `1` when using pgvector image |
| `GITHUB_TOKEN` | Optional — SigmaHQ sync + detection search rate limits |

Template: `backend/.env.example` · encrypted admin secrets: [`OPERATIONS.md` § ADR-006](OPERATIONS.md).

### Step 4 — Deploy / restart

**New release** (production zone — local tree, no git):

```bash
bash /opt/briefr/deploy/briefr-deploy.sh
```

**New release** (internet-connected — git pull + rollback):

```bash
bash /opt/briefr/deploy/briefr-update.sh
```

**Restart only** (after `.env` or config change — no pip/build/migrate):

```bash
bash /opt/briefr/deploy/briefr-service.sh restart
# or: start | stop | status | health
```

### Step 5 — Verify production install

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
systemctl status briefr-backend
```

| Check | Expected |
|-------|----------|
| `"backend"` | `"postgresql"` |
| `briefr-backend` | `active (running)` |
| Public URL | UI loads over nginx (not Vite) |
| First visit | Setup wizard if no users exist |

Post-deploy smoke (optional, needs seeded CVE data):

```bash
bash /opt/briefr/deploy/smoke-intel.sh
```

### Step 6 — Post-install operator tasks

| Task | Where |
|------|-------|
| Create admin (if not done in UI) | First browser visit, or `POST /api/auth/setup` |
| SigmaHQ rules (empty until synced) | Admin → Feed health → SigmaHQ → **Sync** |
| Feed ingest | Automatic scheduler; or `POST /api/refresh` |
| Backups | Automatic every 6h + pre-update; archives in `/var/lib/briefr/backups` |
| Ongoing updates | `bash /opt/briefr/deploy/briefr-update.sh` |

---

## After install: verification checklist

Use this table regardless of path:

| What to check | Command / location | Good sign |
|---------------|-------------------|-----------|
| Backend up | `curl -s http://127.0.0.1:8000/api/health` | HTTP 200, JSON with `cve_count` |
| Database backend | same JSON → `"backend"` | `"postgresql"` (prod/dev PG) or `"sqlite"` (§1 only) |
| UI | Browser → app URL | Login or setup screen |
| Migrations applied | Backend logs / restart once | No `relation "cves" does not exist` |
| pgvector (if embeddings) | `psql "$DATABASE_URL" -c "\\dx vector"` | `vector` extension listed |
| CVE data | health `cve_count` or FEED tab | &gt; 0 after ingest or seed script |
| SigmaHQ (Detect tab) | Admin → Feed health | Row shows last sync after manual Sync |
| Backups (production) | `ls /var/lib/briefr/backups` | `briefr-*.tar.gz` or `.age` archives |

---

## Where to look for what

| I need… | Document | Path / command |
|---------|----------|----------------|
| Install steps (this page) | `docs/SELF_HOST.md` | You are here |
| Postgres DSN, pgvector, backups, restore | `docs/POSTGRES.md` | `backend/.env` → `DATABASE_URL` |
| Updates, smoke tests, scheduler, webhooks | `docs/OPERATIONS.md` | `/opt/briefr/deploy/briefr-update.sh` |
| Symptom → fix | `docs/TROUBLESHOOTING.md` | — |
| Developer workflow / tests | `docs/ONBOARDING.md` | `./scripts/verify-local.sh` |
| API keys template | `backend/.env.example` | copy to `backend/.env` |
| Compose Postgres (dev) | `deploy/docker-compose.postgres.yml` | `docker compose -f deploy/docker-compose.postgres.yml up -d` |
| Disposable Postgres (CI / :5433) | `scripts/postgres-dev.sh` | `./scripts/postgres-dev.sh start` |
| External Postgres env stub | `deploy/external-postgres.env.example` | — |
| Production install script | `deploy/setup.sh` (git) or `deploy/briefr-install.sh` (artifact) |
| Production deploy (local tree) | `deploy/briefr-deploy.sh` |
| Production deploy (git pull) | `deploy/briefr-update.sh` |
| Service control | `deploy/briefr-service.sh` | run once as root |
| Health / logs (production) | `journalctl -u briefr-backend` | `deploy/check-backend.sh` |

---

## Updates & backups

```bash
bash /opt/briefr/deploy/briefr-update.sh
bash /opt/briefr/deploy/briefr-restore.sh --list
```

Backups run every **6 hours** (in-app scheduler) plus before each update. Archives are age-encrypted when `/var/lib/briefr/keys/backup-age.key` exists.

Restore detail: [README § Backups](../README.md) and [`POSTGRES.md` § Restore](POSTGRES.md#restore).

---

## Key environment flags

Do not copy every `.env.example` line blindly. Set the operating shape first:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL DSN; required in production |
| `BRIEFR_REQUIRE_POSTGRES` | Refuse startup without Postgres (`1` in production) |
| `JWT_SECRET` | Session signing — **required** when `BRIEFR_ENV=production` |
| `EMBEDDINGS_ENABLED` | Local CPU semantic search / related-CVE similarity |
| `EMBEDDINGS_PGVECTOR` | Store embeddings in pgvector when Postgres has the extension |
| `PROCRASTINATE_ENABLED` | Durable Postgres-backed jobs panel / retryable work |
| `SIGMAHQ_INDEX_SYNC_ENABLED` | Weekly SigmaHQ mirror into `detection_rules*` |
| `BRIEFR_RATE_LIMIT_STORE` | Set `db` only if sharing buckets across workers |
| `RATE_LIMIT_ENABLED` | Inbound token buckets for IOC/refresh/login/wallboard |
| `NVD_API_KEY` | Recommended for ingest pacing |
| `OTX_API_KEY` | Pulses, campaigns, correlation |
| `BACKUP_DIR` | Default `/var/lib/briefr/backups` |

Full reference: `backend/.env.example` · API catalog: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## Something wrong?

Read [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — symptom → fix table, no prerequisites.
