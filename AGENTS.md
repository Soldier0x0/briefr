# AGENTS.md

## Start here (all agents)

Read in this order before making changes:
1. [`CLAUDE.md`](CLAUDE.md) — project rules, danger zones, error-handling and UI conventions
2. [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) — what is true in production (wins over stale docs)
3. [`docs/HANDOVER.md`](docs/HANDOVER.md) — recent session context: what changed, why, decisions made
4. [`docs/planning/SPRINT_2026-07.md`](docs/planning/SPRINT_2026-07.md) — current work queue with acceptance criteria
5. **UI work:** [`docs/design/design-system.md`](docs/design/design-system.md) §23 (repo-wide UX standards —
   applies to analyst + admin + all surfaces; enforced by `.cursor/rules/design-system.mdc`)

## Execution contract (autonomous loop — mandatory)

When HANDOVER or SPRINT names a next task, **execute it immediately**. Do not stop at
wave/track boundaries for approval. Do not end a turn with “say the word” or optional
next steps when the next item is already defined.

### Automated inline review disposition (mandatory)

Before merging or recommending merge of a PR:

1. Inspect all available inline review threads on the PR.
2. Inspect Gemini and other automated reviewer inline comments.
3. Validate every substantive finding against the PR HEAD (not mergeable status alone).
4. Fix or technically disposition every substantive finding (fix, false positive, obsolete, duplicate).
5. Do not assume mergeable means review complete.
6. Do not assume an outdated thread means fixed — trace the code on HEAD.
7. If an asynchronous reviewer is configured and review is still pending, do not auto-merge immediately.

Use `./scripts/verify-local.sh` as the local merge gate when GitHub Actions quota is unavailable.

**Per-PR loop (repeat until backlog empty):**

1. Read HANDOVER (newest) + SPRINT unchecked items + relevant ADR/spec.
2. Branch `cursor/<task>-64e9` off fresh `origin/main`.
3. Implement (minimum diff; `CLAUDE.md` danger zones; match existing style).
4. **`./scripts/verify-local.sh`** — green required (GitHub Actions quota may be
   exhausted; local green is the merge gate). Use `--full` when Postgres/tools exist.
5. Push → open PR → **wait ~1–2 min** → read `gemini-code-assist[bot]` (and other)
   review comments → fix on same branch → push → re-verify locally.
6. **Merge** when local CI is green and actionable review is addressed.
7. Update HANDOVER + tick SPRINT + runtime docs (`PRODUCT_STATUS`, `API_REFERENCE`, etc.).

**Scope (unless the maintainer narrows it):** all sprint checkboxes, then activated
parked work (Track I Phase 3, correlation 4–5, monitor/alerts, L Wave 4, operator
settings in DB, V1.5 tail). **Excluded:** STIX 2.1 export, V2.0 platform release.

**Stop and ask only when:** missing secret/credential, destructive non-additive deploy
outside spec, or a spec contradiction that cannot be resolved from repo docs.

**Shared surfaces:** never parallelize M1, C-Evolve-3, H2, H4 (all touch DetailDrawer).

**Session resume:** if context limits interrupt the loop, pull main, read HANDOVER,
continue the next unchecked item — do not restart from scratch or ask for permission.

## Cursor Cloud specific instructions

BRIEFR is a self-hosted CVE intelligence dashboard: a **FastAPI (Python) backend** in `backend/`
and a **React + Vite frontend** in `frontend/`. See `README.md` and `docs/ONBOARDING.md` for the
full developer guide; this section only captures non-obvious cloud-environment caveats.

### Database (PostgreSQL)

Production uses **PostgreSQL 17** in Docker at `/opt/infra/postgres`. BRIEFR connects via
`DATABASE_URL` in `backend/.env` (host port `127.0.0.1:5432`).

```bash
DATABASE_URL=postgresql://briefr:PASSWORD@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
DATABASE_POOL_SIZE=10
```

- Runtime: **asyncpg** pool; migrations: **Alembic**
- Backups: host `pg_dump` / `pg_restore` — install `postgresql-client-17` (or matching major)
- Verify: `curl -s http://127.0.0.1:8000/api/health` → `"backend": "postgresql"`
- See `docs/POSTGRES.md` for backups, restore, and troubleshooting

### Services and how to run them

The update script provisions the backend virtualenv (`backend/.venv`), installs Python and npm
dependencies, and ensures `backend/.env` exists (copied from `backend/.env.example`). On startup:

- **Postgres** (production): `cd /opt/infra/postgres && docker compose up -d`
- **Backend** (`:8000`): from `backend/`, `source .venv/bin/activate` then
  `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- **Frontend** (`:5173`): from `frontend/`, `npm run dev`. Vite proxies `/api` → `:8000`, so the
  backend must be running first or the UI shows `/api` 404s.

Local dev without production infra: `docker compose -f deploy/docker-compose.postgres.yml up -d`
(Postgres 16 image for local dev; production is 17).

### Tests / build / lint

- **Local pre-merge gate (use when GitHub Actions is unavailable):** from repo root,
  `./scripts/verify-local.sh` — mirrors CI jobs `test`, `dependency-audit`, and the
  frontend build step. Pass `--full` to also run Postgres pytest, gitleaks, and Playwright
  smoke when those tools/DB are available. **Green local verify is sufficient to merge**;
  do not block on GitHub Actions when the org has hit its monthly free-tier limit.
- Backend tests: from `backend/`, `pytest tests/ -q` (matches CI in
  `.github/workflows/backend-tests.yml`). Run from `backend/` — tests prepend the parent to `sys.path`.
- Frontend build: from `frontend/`, `npm run build`.
- Frontend dependency audit (matches CI): from `frontend/`, `npm run audit:ci` after `npm ci`.
- There is **no lint config** (no ESLint/ruff/flake8) and **no frontend unit test suite**; UI is
 validated manually or via the Playwright scripts in `scripts/` / `backend/tests/test_playwright_smoke.py`
 (gated behind `PLAYWRIGHT_SMOKE=1`).
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
