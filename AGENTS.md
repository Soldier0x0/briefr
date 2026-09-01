# AGENTS.md

Cursor Cloud and automation agents: start here before changing BRIEFR.

## Read order

1. [`docs/CONTRIBUTOR_RULES.md`](docs/CONTRIBUTOR_RULES.md) — danger zones, UI, docs rules
2. [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) — production truth
3. [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — install, tests, env vars
4. **UI work:** [`docs/design/design-system.md`](docs/design/design-system.md) §23

Merge gate: `./scripts/verify-local.sh` (green is sufficient to merge when CI quota is exhausted).

## Cursor Cloud — quick notes

BRIEFR is FastAPI (`backend/`) + React/Vite (`frontend/`). See `README.md` and
[`docs/SELF_HOST.md`](docs/SELF_HOST.md) for the full guide.

### Database

Production uses PostgreSQL 16 + pgvector. `DATABASE_URL` (postgresql://) is required; there is no SQLite fallback.

```bash
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
```

`./scripts/verify-local.sh` requires a reachable Postgres (starts `deploy/docker-compose.postgres.yml` when Docker is available).

### Services

- Backend `:8000`: `cd backend && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- Frontend `:5173`: `cd frontend && npm run dev` (proxies `/api` → `:8000`)

### Tests / build

- `./scripts/verify-local.sh` — default merge gate
- `cd backend && pytest tests/ -q`
- `cd frontend && npm run build && npm run test:unit`

### Caveats

- API keys are optional for core CVE feed, search, and Incidents/News; IOC/AI need real keys.
- Env vars override `backend/.env`; restart backend after secret changes.
- Empty feed on first boot triggers slow NVD ingest; seed with `python scripts/seed_screenshot_data.py`.
