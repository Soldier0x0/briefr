# AGENTS.md

**Rulebook:** [`CLAUDE.md`](CLAUDE.md) is the single source for project rules, danger
zones, error-handling, UI conventions, PR workflow, and working style. Do **not**
duplicate those here — edit `CLAUDE.md` when rules change.

## Start here (all agents)

Read in this order before making changes:

1. [`CLAUDE.md`](CLAUDE.md) — rulebook
2. [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) — what is true in production
3. [`docs/HANDOVER.md`](docs/HANDOVER.md) — recent session context
4. [`docs/planning/SPRINT_2026-07.md`](docs/planning/SPRINT_2026-07.md) — work queue
5. **UI work:** [`docs/design/design-system.md`](docs/design/design-system.md) §23
6. [`docs/AGENT_METHODOLOGY.md`](docs/AGENT_METHODOLOGY.md) — working method

## Execution contract (Cursor agents)

When HANDOVER or SPRINT names a next task, **execute it immediately** — do not stop
at wave boundaries for approval. Merge gate: `./scripts/verify-local.sh` (green is
sufficient when GitHub Actions quota is exhausted). RCA-first, danger zones, and
review disposition: follow `CLAUDE.md`.

**Stop and ask only when:** missing secret/credential, destructive non-additive
deploy outside spec, or a spec contradiction that cannot be resolved from repo docs.

**Shared surfaces:** never parallelize M1, C-Evolve-3, H2, H4 (all touch DetailDrawer).

**Session resume:** pull main, read HANDOVER, continue the next unchecked item.

## Cursor Cloud specific instructions

BRIEFR is a self-hosted CVE intelligence dashboard: a **FastAPI (Python) backend** in `backend/`
and a **React + Vite frontend** in `frontend/`. See `README.md` and `docs/ONBOARDING.md` for the
full developer guide; this section only captures non-obvious cloud-environment caveats.

### Database (PostgreSQL)

Production uses **PostgreSQL 16** in Docker at `/opt/infra/postgres`. BRIEFR connects via
`DATABASE_URL` in `backend/.env` (host port `127.0.0.1:5432`).

```bash
DATABASE_URL=postgresql://briefr:PASSWORD@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

- Runtime: **asyncpg** pool; migrations: **Alembic**
- Backups: host `pg_dump` / `pg_restore` — install `postgresql-client-16` (or matching major)
- Verify: `curl -s http://127.0.0.1:8000/api/health` → `"backend": "postgresql"`
- See `docs/POSTGRES.md` for backups, restore, and troubleshooting
- Embeddings E1: Postgres image must be `pgvector/pgvector:pg16` (plain `postgres:16` lacks `vector`)

### Services and how to run them

The update script provisions the backend virtualenv (`backend/.venv`), installs Python and npm
dependencies, and ensures `backend/.env` exists (copied from `backend/.env.example`). On startup:

- **Postgres** (production): `cd /opt/infra/postgres && docker compose up -d`
- **Backend** (`:8000`): from `backend/`, `source .venv/bin/activate` then
  `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- **Frontend** (`:5173`): from `frontend/`, `npm run dev`. Vite proxies `/api` → `:8000`, so the
  backend must be running first or the UI shows `/api` 404s.

Local dev without production infra: `docker compose -f deploy/docker-compose.postgres.yml up -d`
(Postgres **16 + pgvector** — `pgvector/pgvector:pg16`). Production `/opt/infra/postgres`
uses the same major: cut over to `pgvector/pgvector:pg16` with embeddings E1 feature
deploy (backup + same volume); see `docs/POSTGRES.md`.

### Tests / build / lint

- **Local pre-merge gate:** from repo root, `./scripts/verify-local.sh` — mirrors CI jobs
  `test`, `dependency-audit`, frontend build, and **frontend unit tests** (`npm run test:unit`).
  Pass `--full` for Postgres pytest, gitleaks, and Playwright smoke when available.
  **Green local verify is sufficient to merge** when GitHub Actions quota is exhausted.
- Backend tests: from `backend/`, `pytest tests/ -q`.
- Frontend build: from `frontend/`, `npm run build`.
- Frontend unit tests: from `frontend/`, `npm run test:unit`.
- Frontend dependency audit: from `frontend/`, `npm run audit:ci` after `npm ci`.
- There is **no ESLint/ruff/flake8** lint config yet (Phase 1 W6). UI is also validated via
  Playwright (`scripts/` / `backend/tests/test_playwright_smoke.py`, gated behind `PLAYWRIGHT_SMOKE=1`).
- **Dark mode only** — light theme CSS exists under `frontend/src/theme/light-theme.css` but is not imported.
- **Tab state** — main nav tabs use `hidden` panels instead of unmounting so FEED scroll/filters survive tab switches.
- **Snooze removed from UI** — pin/watchlist remains; app clears legacy snooze rows on startup.

### Non-obvious caveats

- **No API keys are required to run the app.** `backend/.env` is seeded from `.env.example` with
  placeholder keys; the CVE feed, detail drawer, search, and Incidents/News (RSS) work without real
  keys. IOC lookups (VirusTotal/AbuseIPDB/GreyNoise) and AI PDF summaries stay empty until real keys
  are added.
- **API keys: env vars win over `backend/.env`.** Keys are read from the process environment first
  (Cursor injected Secrets — e.g. `NVD_API_KEY`, `VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY`,
  `GITHUB_TOKEN`); `main.py` calls `load_dotenv()` without `override`, so real env vars take
  precedence over the `.env` placeholders. If you add/change secrets mid-session, **restart the
  backend process** so it inherits them (a long-lived process — or a stale `tmux` server started
  before the secrets existed — will not pick them up).
- `NVD` (`services.nvd.nist.gov`) frequently returns transient `503`s independent of your key; the
  resilient client has a per-source circuit breaker, so retry later rather than assuming a bad key.
- **Empty feed on first boot:** if the `cves` table has fewer than 10 rows, the backend kicks off a
  full NVD→KEV→EPSS ingest on startup (needs network and is slow). To get realistic data instantly,
  run the seed script with `DATABASE_URL` set — `python scripts/seed_screenshot_data.py` from the
  repository root (the script `chdir`s into `backend/`). Re-running is safe (skips CVE seeding once
  10+ rows exist).
- `backend/.python-version` pins `3.13`, but CI and this environment use **Python 3.12**, which is
  fully supported (`requirements.txt` is 3.11+).
