# AGENTS.md

## Cursor Cloud specific instructions

BRIEFR is a self-hosted CVE intelligence dashboard: a **FastAPI (Python) backend** in `backend/`
and a **React + Vite frontend** in `frontend/`. See `README.md` and `docs/ONBOARDING.md` for the
full developer guide; this section only captures non-obvious cloud-environment caveats.

### Services and how to run them

The update script provisions the backend virtualenv (`backend/.venv`), installs Python and npm
dependencies, and ensures `backend/.env` exists (copied from `backend/.env.example`). On startup:

- **Backend** (`:8000`): from `backend/`, `source .venv/bin/activate` then
  `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- **Frontend** (`:5173`): from `frontend/`, `npm run dev`. Vite proxies `/api` → `:8000`, so the
  backend must be running first or the UI shows `/api` 404s.

### Tests / build / lint

- Backend tests: from `backend/`, `pytest tests/ -q` (matches CI in
  `.github/workflows/backend-tests.yml`). Run from `backend/` — tests prepend the parent to `sys.path`.
- Frontend build: from `frontend/`, `npm run build`.
- Frontend dependency audit (matches CI): from `frontend/`, `npm run audit:ci` after `npm ci`.
- There is **no lint config** (no ESLint/ruff/flake8) and **no frontend unit test suite**; UI is
  validated manually or via the Playwright scripts in `scripts/` / `backend/tests/test_playwright_smoke.py`
  (gated behind `PLAYWRIGHT_SMOKE=1`).

### Non-obvious caveats

- **No API keys are required to run the app.** `backend/.env` is seeded from `.env.example` with
  placeholder keys; the CVE feed, detail drawer, search, and Incidents/News (RSS) work without real
  keys. IOC lookups (VirusTotal/AbuseIPDB/GreyNoise) and AI PDF summaries stay empty until real keys
  are added to `backend/.env`.
- **Empty feed on first boot:** if the `cves` table has fewer than 10 rows, the backend kicks off a
  full NVD→KEV→EPSS ingest on startup (needs network and is slow). To get realistic data instantly,
  run the seed script with an activated backend venv — `python ../scripts/seed_screenshot_data.py`
  from `backend/`, or `python scripts/seed_screenshot_data.py` from the repository root (the script
  `chdir`s into `backend/` itself). It seeds 15 sample CVEs and warms the RSS incident feed.
  Re-running is safe (skips CVE seeding once 10+ rows exist).
- The SQLite DB lives at `backend/briefr.db` (gitignored). Deleting it resets state; the next backend
  start re-triggers the bootstrap ingest.
- `backend/.python-version` pins `3.13`, but CI and this environment use **Python 3.12**, which is
  fully supported (`requirements.txt` is 3.11+).
