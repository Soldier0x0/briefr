# BRIEFR Contributor Onboarding

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Purpose:** Single entry point for developers who want to understand BRIEFR, run it locally, and navigate the codebase. Use this before diving into individual reference documents.

---

## 1. Recommended reading order

Read in this sequence the first time through. Skim what you already know; stop and run commands where indicated.

| Step | Document | Why |
|------|----------|-----|
| 1 | [`README.md`](../README.md) | Product scope, features, quick start |
| 2 | [`SYSTEM_DESIGN.md`](../SYSTEM_DESIGN.md) | Architecture, data flows, trade-offs |
| 3 | [`docs/diagrams/`](../docs/diagrams/) | Visual architecture + sequence diagrams (open `.mermaid` in GitHub or VS Code) |
| 4 | [`APPLICATION_EXECUTION_MAP.md`](../APPLICATION_EXECUTION_MAP.md) | Startup order and per-tab request journeys |
| 5 | [`API_REFERENCE.md`](../API_REFERENCE.md) | Endpoint params and response shapes |
| 6 | [`FOLDER_STRUCTURE_GUIDE.md`](../FOLDER_STRUCTURE_GUIDE.md) | File-by-file map — use when you need the exact module to edit |
| 6b | [`CODEBASE_CONTEXT.md`](../CODEBASE_CONTEXT.md) | Consolidated codebase reference (WHAT/WHERE/WHY/HOW/WHEN + AI guardrails) |
| 7 | [`TECHNICAL_INVENTORY.md`](../TECHNICAL_INVENTORY.md) | Schema (26 tables), scheduler jobs, feature matrix |
| 8 | [`docs/ROADMAP.md`](ROADMAP.md) | Release index (V1.2–V2.0) and product positioning |
| 9 | [`Beta V1.2.md`](../Beta%20V1.2.md) | Current release — foundation and hardening |
| 10 | [`docs/JUPITER_VISION.md`](JUPITER_VISION.md) | Jupiter ecosystem and beast identity (optional sidecars) |
| 11 | Source + tests | `backend/tests/` and the files named in the execution map |

**Printable architecture:** [`SYSTEM_DESIGN.pdf`](../SYSTEM_DESIGN.pdf) — regenerate with `node scripts/generate_system_design_pdf.mjs` after editing `SYSTEM_DESIGN.md`.

---

## 2. Local development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

Recommended API keys for full functionality: NVD, VirusTotal, AbuseIPDB. See [Environment variables](#4-environment-variables) for the full list.

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # add keys as needed

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- SQLite database: `backend/briefr.db` (or `DB_PATH` from `.env`)
- Interactive API docs: http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/health

**First boot:** If fewer than 10 CVEs exist, the scheduler triggers a full ingest (NVD → KEV → EPSS). With 10+ CVEs, incremental jobs maintain freshness.

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 — Vite proxies /api → :8000
```

### Seed data for UI work

Populate CVE rows and warm RSS caches without waiting for a full NVD sync:

```bash
# backend running on :8000 (or script opens its own DB connection)
python3 scripts/seed_screenshot_data.py
```

Useful when testing the Incidents tab, README screenshots, or an empty local database.

### Frontend UI conventions (2026-06)

| Area | Behaviour |
|------|-----------|
| **Theme** | Dark mode only — no light toggle |
| **Tabs** | BRIEF / FEED / IOC / Forge panels stay mounted (`hidden` attribute) so scroll and filter state persist when switching tabs |
| **Feed filters** | Sticky toolbar: title + exports → stack bar → CVE search → quick chips. **Common vendors** scroll below the sticky block (not inside it) |
| **CVE drawer** | Slides over full-width content; `createCveDrawerController` ignores stale fetches after close; loading overlay shows “Calculating latest metrics…” |
| **Watchlist** | Pin only in UI; legacy snoozes cleared on load via `DELETE /api/watchlist/snoozes` |
| **Analyst charts** | `TimeWindowPicker` — preset windows (6h–90d) or custom datetime range |
| **Morning brief** | `action_queue` includes `description`; reason chips and metrics are color-coded |

Key files: `FilterBar.jsx`, `MorningBrief.jsx`, `BriefCharts.jsx`, `TimeWindowPicker.jsx`, `utils/openCveDrawer.js`.

---

## 3. Running tests

Backend tests use **pytest** (same as CI).

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

CI runs `pytest tests/ -q` via [`.github/workflows/backend-tests.yml`](../.github/workflows/backend-tests.yml).

| Test file | Covers |
|-----------|--------|
| `test_incident_news.py` | RSS parsing, editorial title filter, malformed cache rows |
| `test_case_study_feed.py` | Combined RSS + ATLAS feed on single DB connection |
| `test_ai_alerts_and_feed.py` | AI/ML alerts stat chip, combined feed endpoint |
| `test_cve_detail_atlas.py` | ATLAS fields on CVE detail |
| `test_cpe_matching.py` | Asset profile CPE matching |
| `test_intelligence.py` | Template sentences |
| `test_risk_intelligence.py` | Momentum / risk scoring |
| `test_backup_manager.py` | Backup integrity and restore |
| `test_backup_encryption.py` | age-encrypted archives: keygen, round-trip, auto-restore |
| `test_investigation_summary.py` | Investigation / AI summary endpoints |
| `test_exploit_sources.py` | PoC-in-GitHub, ExploitDB, Metasploit, Nuclei parsers + DB merge |
| Others | OTX, EPSS, MITRE feeds, domain validation, exploit refs |

There is no frontend unit test suite today; UI changes are validated manually or via Playwright scripts in `scripts/`.

---

## 4. Environment variables

Full template: [`backend/.env.example`](../backend/.env.example). Copy to `backend/.env` and adjust.

### API keys (enrichment)

| Variable | Required | Purpose |
|----------|----------|---------|
| `NVD_API_KEY` | Recommended | NVD rate limits (50 req/30s with key) |
| `VIRUSTOTAL_API_KEY` | Recommended | IOC lookups (500/day free) |
| `ABUSEIPDB_API_KEY` | Recommended | IP abuse score (1000/day free) |
| `GREYNOISE_API_KEY` | Optional | IP classification (50/week free; opt-in per lookup) |
| `ABUSECH_AUTH_KEY` | Optional | MalwareBazaar + URLhaus |
| `OTX_API_KEY` | Optional | OTX pulses + nightly correlation (10k/month) |
| `GROQ_API_KEY` | Optional | PDF executive summary (primary; Groq model `llama-3.1-8b-instant`) |
| `ANTHROPIC_API_KEY` | Optional | PDF executive summary (fallback) |
| `GITHUB_TOKEN` | Optional | Detection rule search + PoC-in-GitHub sync rate limit (5000/hr vs 60/hr) |
| `CIRCL_API_KEY` | Optional | vulnerability.circl.lu authenticated rate limits (free signup) |

### Database and backups

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_PATH` | `briefr.db` | SQLite file path |
| `BACKUP_DIR` | `/var/lib/briefr/backups` | Integrity-checked archive directory |
| `BACKUP_RETENTION_COUNT` | `100` | Max archives kept (~25 days at 6h intervals) |
| `BACKUP_ENABLED` | `1` | Set `0` to disable backups and startup auto-restore |
| `BACKUP_AGE_KEY_FILE` | `/var/lib/briefr/keys/backup-age.key` (when present) | age identity for archive encryption; must live outside `BACKUP_DIR`; `""` disables |
| `BACKUP_LOG_MAX_BYTES` | `5242880` | Rotating backup log size |
| `BACKUP_LOG_BACKUP_COUNT` | `5` | Gzipped backup log generations |
| `BACKUP_INTERVAL_HOURS` | `6` | Expected backup cadence; dead-man alert fires after 2× with no successful archive |

### Webhook alerts (V1.3)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISCORD_WEBHOOK_URL` | — | Discord incoming webhook URL (optional) |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token (optional; requires `TELEGRAM_CHAT_ID`) |
| `TELEGRAM_CHAT_ID` | — | Telegram destination chat/channel ID |
| `BRIEFR_STACK_TERMS` | — | Comma-separated products/CVE IDs for KEV-on-stack server matching |

Configure **one or both** channels. Alerts are scheduler-side only (KEV-on-stack after each KEV sync; backup dead-man check). No admin UI until V1.4.

### Scheduler intervals

| Variable | Default | Purpose |
|----------|---------|---------|
| `NVD_SYNC_INTERVAL_HOURS` | `1` | NVD incremental cadence |
| `KEV_SYNC_INTERVAL_MINUTES` | `15` | CISA KEV sync |
| `EPSS_SYNC_INTERVAL_HOURS` | `6` | EPSS score refresh |
| `INCIDENT_FEED_REFRESH_MINUTES` | `30` | Incidents & News snapshot rebuild |
| `VULNRICHMENT_SYNC_INTERVAL_HOURS` | `6` | CISA Vulnrichment snapshot (gap-fill CVSS/CWE/CPE) |
| `VULNRICHMENT_BRANCH` | `develop` | cisagov/vulnrichment git branch |
| `CVELISTV5_SYNC_INTERVAL_MINUTES` | `30` | cvelistV5 incremental sync (GitHub compare deltas) |
| `CVELISTV5_BRANCH` | `main` | CVEProject/cvelistV5 git branch |
| `CVELISTV5_INITIAL_SINCE_DAYS` | `7` | First-run bootstrap window when no `cvelistv5_head_sha` watermark |
| `CIRCUIT_FAILURE_THRESHOLD` | `3` | Consecutive failures before a source circuit opens |
| `CIRCUIT_COOLDOWN_SECONDS` | `60` | Circuit-open cooldown before retrying a source |
| `NVD_SYNC_OVERLAP_MINUTES` | `15` | Watermark overlap window |
| `SCHEDULER_TIMEZONE` | `Asia/Kolkata` | APScheduler timezone |
| `MITRE_REFRESH_HOUR` / `MITRE_REFRESH_MINUTE` | `2` / `0` | Weekly MITRE + ATLAS (Sunday) |
| `CORRELATION_HOUR` / `CORRELATION_TIMEZONE` | `1` / `Asia/Kolkata` | Nightly correlation engine |
| `OTX_CORRELATION_HOUR` / `OTX_CORRELATION_TIMEZONE` | `2` / `Asia/Kolkata` | OTX nightly job (skipped if no `OTX_API_KEY`) |
| `CACHE_REFRESH_HOUR` / `CACHE_REFRESH_MINUTE` | `6` / `0` | Feed cache maintenance |

### Ingest tuning

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAX_CVES_PER_FETCH` | `2000` | Cap per NVD sync batch |
| `NVD_DAYS_BACK` | `14` | Initial lookback window |
| `KEV_CROSS_FETCH_NVD` | `1` | Fetch missing KEV CVEs from NVD by ID |
| `ATLAS_YAML_URL` | mitre-atlas/atlas-data | ATLAS YAML source override |
| `MITRE_CVE_MAPPINGS_JSON_URL` | — | Custom CVE→ATT&CK JSON (optional) |

### App behaviour

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALLOWED_ORIGINS` | localhost dev URLs | CORS origins (comma-separated) |
| `DEFAULT_TIMEZONE` | `Asia/Kolkata` | Health / time display default |
| `BRIEFR_ENV` | `development` | `production` disables Swagger/OpenAPI docs |
| `BRIEFR_ADMIN_API_KEY` | — | Optional `X-BRIEFR-Admin-Key` gate for `POST /api/refresh*` (interim until built-in app login ships) |
| `RATE_LIMIT_ENABLED` | `1` | Token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` (429 + `Retry-After`) |
| `RATE_LIMIT_IOC_PER_MINUTE` | `30` | Per-client-IP budget for `POST /api/ioc/lookup` |
| `RATE_LIMIT_REFRESH_PER_MINUTE` | `10` | Per-client-IP budget shared by all `POST /api/refresh*` routes |
| `LOG_FORMAT` | `json` | `json` = structured lines with `request_id`; `plain` = legacy human-readable format |

### ML assist (V1.3 — disabled by default, CPU-only, scheduler-side)

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDINGS_ENABLED` | `0` | Semantic "similar CVEs" on `GET /api/cves/{id}/related`. Requires the optional `fastembed` package (`pip install fastembed`). Off → shared-product heuristic; the tool is fully functional without it |
| `EMBEDDINGS_MODEL` | `BAAI/bge-small-en-v1.5` | Local ONNX embedding model (downloaded on first scheduler run) |
| `EMBEDDINGS_CACHE_DIR` | fastembed default | Model download/cache directory — must be writable by the service user. The production systemd unit sets `/var/lib/briefr/models` and adds it to `ReadWritePaths` (the default home-dir HuggingFace cache fails with EROFS under `ProtectSystem=strict`) |
| `EMBEDDINGS_SYNC_INTERVAL_HOURS` | `6` | Embeddings backfill job cadence |
| `EMBEDDINGS_MAX_PER_RUN` | `2000` | CVEs embedded per backfill run (bounds CPU per cycle) |
| `LLM_PRODUCT_EXTRACTION_ENABLED` | `0` | Fill empty `affected_products` for NVD-unanalyzed CVEs from description text via Groq. Requires `GROQ_API_KEY`. Writes only while the field is empty, marks `affected_products_source='llm'`; official CPE supersedes |
| `LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS` | `6` | Extraction job cadence |
| `LLM_PRODUCT_EXTRACTION_MAX_PER_RUN` | `25` | Groq calls per run (2s throttle; completed extractions negative-cached for 7 days, errors retried next run) |

---

## 5. Production deploy (overview)

BRIEFR targets a single Debian server with **systemd + nginx**. Install path: `/opt/briefr`.

| Script | Purpose |
|--------|---------|
| [`deploy/setup.sh`](../deploy/setup.sh) | Initial install: Python, clone repo, venv, then production deploy |
| [`deploy/briefr-update.sh`](../deploy/briefr-update.sh) | Pull, build frontend, restart backend + nginx |
| [`deploy/briefr-backup.sh`](../deploy/briefr-backup.sh) | Manual or scheduled integrity-checked backup |
| [`deploy/briefr-restore.sh`](../deploy/briefr-restore.sh) | List or restore archives |
| [`deploy/check-backend.sh`](../deploy/check-backend.sh) | Health probe for monitoring |
| [`deploy/smoke-intel.sh`](../deploy/smoke-intel.sh) | Post-deploy smoke checks |

**systemd units:** `briefr-backend.service`, `briefr-backup.timer` (every 6h). Scheduled ingest (NVD, KEV, EPSS, MITRE+ATLAS, exploit sources, backup dead-man) runs inside the backend — no separate refresh scripts needed.

**Production notes:**
- Set `ALLOWED_ORIGINS` to your public URL (not `:5173`).
- nginx serves `frontend/dist`; Vite dev server is not used.
- Backups land in `/var/lib/briefr/backups` outside the git tree.
- On startup, corrupt `briefr.db` triggers auto-restore from the newest valid archive.

See [README.md § Backups and restore](../README.md) for restore commands.

---

## 6. Key subsystems (where to look)

| If you are working on… | Start here |
|----------------------|------------|
| CVE list / filters | `backend/routers/cves.py` (`_build_cve_filters`), `frontend/src/components/CVEFeed.jsx` |
| CVE detail drawer | `frontend/src/components/DetailDrawer.jsx`, `GET /api/cves/{id}` in `routers/cves.py` |
| IOC lookup | `backend/enrichment/ioc.py`, `frontend/src/components/IOCLookup.jsx` |
| Incidents & News tab | `backend/feeds/case_study_feed.py`, `incident_news.py`, `CaseStudies.jsx` |
| Risk score | `frontend/src/scoring/riskScore.js`, `backend/scoring/risk.py` |
| Correlation | `backend/correlation/engine.py` |
| Detection rules | `backend/detection/` |
| Scheduled ingest | `backend/scheduler.py`, `backend/feeds/` |
| Database schema | `backend/database.py` (`init_db`), `TECHNICAL_INVENTORY.md` §2 |
| PDF export | `frontend/src/utils/pdfReport.js`, `backend/ai/summary.py` |
| Morning brief | `frontend/src/components/MorningBrief.jsx` (unified `action_queue` list + filter chips) |
| Analyst charts | `frontend/src/components/BriefCharts.jsx` (KEV histogram + EPSS movers table), `CveDescriptionClamp.jsx`, `chart.js` (lazy chunk for histogram only) |
| FEED stack filter | `frontend/src/components/FilterBar.jsx` (`STACK //` row — replaces Hero stack on FEED tab) |
| Backups | `backend/backup/manager.py`, `deploy/briefr-backup.sh` |

---

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Incidents tab shows `database is locked` | Parallel SQLite connections on RSS + ATLAS load | Ensure `case_study_feed.py` uses one connection; check `get_db()` sets `busy_timeout=30000` and `timeout=30` |
| Empty CVE feed on first run | Ingest still running or no network | Wait for bootstrap ingest; check `GET /api/health` `cve_count` |
| IOC lookup returns empty VT/AbuseIPDB | Missing API keys | Add keys to `.env`; restart backend |
| CORS errors in browser | Origin not allowed | Add your URL to `ALLOWED_ORIGINS` |
| GreyNoise always empty | No key or weekly quota exhausted | Set `GREYNOISE_API_KEY`; opt in per lookup |
| OTX pulses missing | No `OTX_API_KEY` | Key required for nightly correlation and pulse data |
| RSS shows contest/promo headlines | Editorial filter gap | Add pattern to `EXCLUDED_NEWS_TITLE_PATTERNS` in `incident_news.py` |
| `pytest` import errors | Wrong working directory | Run from `backend/` (tests prepend parent to `sys.path`) |
| Frontend `/api` 404 in dev | Backend not running | Start uvicorn on `:8000` before `npm run dev` |
| Production 502 | Backend down or nginx misconfigured | `systemctl status briefr-backend`; `deploy/check-backend.sh` |
| DB corruption after crash | Unclean shutdown | `briefr-restore.sh` or startup auto-restore |

### Useful diagnostics

```bash
# Health and CVE count
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool

# Combined incidents feed (RSS + ATLAS)
curl -s 'http://127.0.0.1:8000/api/case-studies/feed?atlas_limit=10' | python3 -m json.tool

# SQLite row counts
sqlite3 backend/briefr.db "SELECT COUNT(*) FROM cves;"

# Manual ingest chain
curl -X POST http://127.0.0.1:8000/api/refresh
```

---

## 8. Regenerating derived docs

| Output | Command |
|--------|---------|
| `SYSTEM_DESIGN.pdf` | `cd frontend && npm install && node ../scripts/generate_system_design_pdf.mjs` |
| `TECHNICAL_INVENTORY.xlsx` | `python3 scripts/generate_technical_inventory_xlsx.py` |
| README screenshots | `python3 scripts/seed_screenshot_data.py` then `node scripts/capture_readme_screenshots.mjs` |

Update the source markdown in the same PR when you change behaviour those artifacts describe.

---

## Related documentation

- [`CODEBASE_CONTEXT.md`](../CODEBASE_CONTEXT.md) — consolidated codebase reference (architecture, flows, AI guardrails)
- [`SYSTEM_DESIGN.md`](../SYSTEM_DESIGN.md) — architecture deep dive
- [`API_REFERENCE.md`](../API_REFERENCE.md) — endpoint catalog
- [`APPLICATION_EXECUTION_MAP.md`](../APPLICATION_EXECUTION_MAP.md) — runtime traces
- [`FOLDER_STRUCTURE_GUIDE.md`](../FOLDER_STRUCTURE_GUIDE.md) — every file in the repo
