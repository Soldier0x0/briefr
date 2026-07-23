# BRIEFR Contributor Onboarding

Copyright © 2026 Sai Harsha Vardhan. Licensed under the Business Source License 1.1 (`SPDX-License-Identifier: BUSL-1.1`); see the repository `LICENSE` for the full text.

**Purpose:** Entry point for developers changing the code.

| If you want to… | Start here |
|-----------------|------------|
| **Install** BRIEFR (any path) | [`SELF_HOST.md`](SELF_HOST.md) — authoritative step-by-step |
| **Use** or **self-host** without changing code | [`index.md`](index.md) → SELF_HOST or USE |
| **Change the code** | Continue below |

---

## 1. Recommended reading order

| Step | Document | Why |
|------|----------|-----|
| 1 | [`index.md`](index.md) + [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) | Quick product context (5 min) |
| 2 | [`README.md`](../README.md) | Features and local quick start |
| 3 | [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) | Architecture and trade-offs |
| 4 | [`API_REFERENCE.md`](API_REFERENCE.md) | Endpoints when you touch the API |
| 5 | [`archive/snapshots/CODEBASE_CONTEXT.md`](archive/snapshots/CODEBASE_CONTEXT.md) | Module map + AI guardrails |
| 6 | Source + tests | `backend/tests/` and files named in [`archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) |

**Deep reference when needed:** [`archive/snapshots/FOLDER_STRUCTURE_GUIDE.md`](archive/snapshots/FOLDER_STRUCTURE_GUIDE.md), [`archive/snapshots/TECHNICAL_INVENTORY.md`](archive/snapshots/TECHNICAL_INVENTORY.md), [`OPERATIONS.md`](OPERATIONS.md), [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md).

**Historical planning:** [`archive/`](archive/) (beta specs, agent notes — not required reading).

**Printable architecture:** generate `SYSTEM_DESIGN.pdf` with `node scripts/generate_system_design_pdf.mjs` (not committed).

---

## 2. Local development

**Install paths (SQLite vs Postgres+pgvector vs production):** [`SELF_HOST.md`](SELF_HOST.md). This section assumes you are developing against the repo.

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

- PostgreSQL via `DATABASE_URL` in `backend/.env` — full steps: [`SELF_HOST.md` §2](SELF_HOST.md#2-local-development-with-postgresql--pgvector) (`docker compose -f deploy/docker-compose.postgres.yml up -d` on **:5432**, or disposable `./scripts/postgres-dev.sh start` on **:5433** — see `docs/POSTGRES.md`)
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

### Frontend UI conventions (2026-07)

| Area | Behaviour |
|------|-----------|
| **Theme** | Dark mode only — no light toggle |
| **Tabs** | BRIEF / FEED / IOC / Forge panels stay mounted (`hidden` attribute) so scroll and filter state persist when switching tabs |
| **Feed filters** | Sticky toolbar: title + exports → stack bar → CVE search → quick chips. **Common vendors** scroll below the sticky block (not inside it) |
| **CVE drawer** | Slides over full-width content; `createCveDrawerController` ignores stale fetches after close; loading overlay shows “Calculating latest metrics…” |
| **Watchlist** | Pin only in UI; legacy snoozes cleared on load via `DELETE /api/watchlist/snoozes` |
| **Analyst charts** | `TimeWindowPicker` — preset windows (6h–90d) or custom datetime range |
| **Morning brief** | `action_queue` includes `description`; reason chips and metrics are color-coded |
| **Design system** | Use semantic CSS tokens from `frontend/src/styles/tokens.css`; Radix primitives are preferred for checkboxes, radios, selects, switches, tabs, dialogs, popovers, and tooltips |

Key files: `FilterBar.jsx`, `MorningBrief.jsx`, `BriefCharts.jsx`, `TimeWindowPicker.jsx`, `utils/openCveDrawer.js`.

---

## 3. Running tests

Use the local merge gate when possible:

```bash
./scripts/verify-local.sh
```

That mirrors the core CI checks (backend pytest, frontend build, dependency audit, frontend unit tests). Use `./scripts/verify-local.sh --full` when Postgres, gitleaks, and Playwright smoke are available.

Backend tests use **pytest**:

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

Frontend validation:

```bash
cd frontend
npm run build
npm run test:unit
```

UI changes should also be checked in the browser or with the Playwright smoke path when the change affects interaction.

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
| `GROQ_API_KEY` | Optional | LLM chain, tried first (default model `openai/gpt-oss-20b`; PDF summaries use the larger `openai/gpt-oss-120b`) |
| `CEREBRAS_API_KEY` | Optional | LLM chain, second |
| `OPENROUTER_API_KEY` | Optional | LLM chain, third (`:free` tier models) |
| `GEMINI_API_KEY` | Optional | LLM chain, last resort |
| `GITHUB_TOKEN` | Optional | Detection rule search + PoC-in-GitHub sync rate limit (5000/hr vs 60/hr) |
| `CIRCL_API_KEY` | Optional | vulnerability.circl.lu authenticated rate limits (free signup) |

All four LLM keys are optional and gate a fixed failover chain (Groq → Cerebras → OpenRouter → Gemini) for PDF executive summaries, product extraction, and detection-context artifact extraction — every one of those features has a deterministic non-LLM fallback, so BRIEFR is fully functional with none of them set. No client anywhere in this codebase calls the Anthropic API — an `ANTHROPIC_API_KEY` admin config field is still defined (vestigial from before it was removed from the chain) but nothing reads it to make a request.

### Database and backups

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | PostgreSQL DSN (`postgresql://user:pass@host:5432/dbname`); omit **or** set empty (`DATABASE_URL=""`) for zero-config local SQLite. If `.env` has a placeholder Postgres DSN and nothing listens on `:5432`, startup fails with `ConnectionRefusedError` — clear the URL and set `BRIEFR_REQUIRE_POSTGRES=0` (cloud/bare VM; see `AGENTS.md`) |
| `BRIEFR_REQUIRE_POSTGRES` | `0` | Set `1` to refuse startup unless `DATABASE_URL` is a real Postgres connection (recommended in production). Use `0` with empty `DATABASE_URL` for SQLite-only cloud/dev boxes without Docker |
| `DATABASE_POOL_SIZE` | `10` | asyncpg pool size |
| `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` | `60` | SQL statement timeout only — not feed HTTP; see [POSTGRES.md](POSTGRES.md) |
| `BACKUP_DIR` | `/var/lib/briefr/backups` | Integrity-checked archive directory |
| `BACKUP_RETENTION_COUNT` | `100` | Max archives kept (~25 days at 6h intervals) |
| `BACKUP_ENABLED` | `1` | Set `0` to disable backups and startup auto-restore |
| `BACKUP_AGE_KEY_FILE` | `/var/lib/briefr/keys/backup-age.key` (when present) | age identity for archive encryption; must live outside `BACKUP_DIR`; `""` disables |
| `BACKUP_LOG_MAX_BYTES` | `5242880` | Rotating backup log size |
| `BACKUP_LOG_BACKUP_COUNT` | `5` | Gzipped backup log generations |
| `BACKUP_INTERVAL_HOURS` | `6` | Expected backup cadence; dead-man alert fires after 2× with no successful archive |

### Webhook alerts (V1.3 → V1.4 engine)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISCORD_WEBHOOK_URL` | — | Discord incoming webhook URL (optional) |
| `DISCORD_WEBHOOK_ENABLED` | `1` | Enable/disable Discord destination |
| `DISCORD_WEBHOOK_EVENTS` | all | Comma-separated: `kev_alert`, `backup_failure`, `health` |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token (optional; requires `TELEGRAM_CHAT_ID`) |
| `TELEGRAM_CHAT_ID` | — | Telegram destination chat/channel ID |
| `TELEGRAM_WEBHOOK_ENABLED` | `1` | Enable/disable Telegram destination |
| `TELEGRAM_WEBHOOK_EVENTS` | all | Comma-separated event subscriptions |
| `WEBHOOK_GENERIC_URL` | — | Generic HTTPS POST webhook (SSRF-protected) |
| `WEBHOOK_GENERIC_ENABLED` | `1` | Enable/disable generic destination |
| `WEBHOOK_GENERIC_EVENTS` | all | Comma-separated event subscriptions |
| `WEBHOOK_GENERIC_LABEL` | `Generic HTTPS` | Admin display label |
| `BRIEFR_STACK_TERMS` | — | Comma-separated products/CVE IDs for KEV-on-stack server matching |

Configure **one or more** destinations. Alerts are scheduler-side (`kev_alert` after KEV sync; `backup_failure` from dead-man check). Per-destination enable/event subscriptions can be overridden via `PATCH /api/admin/webhooks/destinations/{id}`.

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
| `CACHE_REFRESH_HOUR` / `CACHE_REFRESH_MINUTE` | `6` / `0` | Unused — no scheduler job; kept for env compatibility |

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
| `RATE_LIMIT_ENABLED` | `1` | Token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` (429 + `Retry-After`) |
| `RATE_LIMIT_IOC_PER_MINUTE` | `30` | Per-client-IP budget for `POST /api/ioc/lookup` |
| `RATE_LIMIT_REFRESH_PER_MINUTE` | `10` | Per-client-IP budget shared by all `POST /api/refresh*` routes |
| `RATE_LIMIT_WALLBOARD_PER_MINUTE` | `60` | Per-client-IP budget for `GET /api/wallboard` (kiosk poll) |
| `WALLBOARD_TOKEN` | — | Optional read-only gate for wallboard (`X-BRIEFR-Wallboard-Token` header); unset = open |
| `LOG_FORMAT` | `json` | `json` = structured lines with `request_id`; `plain` = legacy human-readable format |

### ML assist (V1.3 — disabled by default, CPU-only, scheduler-side)

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDINGS_ENABLED` | `0` | Semantic "similar CVEs" on `GET /api/cves/{id}/related`. Requires the optional `fastembed` package (`pip install fastembed`). Off → shared-product heuristic; the tool is fully functional without it |
| `EMBEDDINGS_MODEL` | `BAAI/bge-small-en-v1.5` | Local ONNX embedding model (downloaded on first scheduler run) |
| `EMBEDDINGS_CACHE_DIR` | fastembed default | Model download/cache directory — must be writable by the service user. The production systemd unit sets `/var/lib/briefr/models` and adds it to `ReadWritePaths` (the default home-dir HuggingFace cache fails with EROFS under `ProtectSystem=strict`) |
| `EMBEDDINGS_SYNC_INTERVAL_HOURS` | `6` | Embeddings backfill job cadence |
| `EMBEDDINGS_MAX_PER_RUN` | `2000` | CVEs embedded per backfill run (bounds CPU per cycle) |
| `LLM_PRODUCT_EXTRACTION_ENABLED` | `0` | Fill empty `affected_products` for NVD-unanalyzed CVEs through the multi-provider LLM router (Groq → Cerebras → OpenRouter → Gemini; any configured provider key is enough). Writes only while the field is empty, marks `affected_products_source='llm'`; official CPE supersedes |
| `LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS` | `6` | Extraction job cadence |
| `LLM_PRODUCT_EXTRACTION_MAX_PER_RUN` | `10` | CVEs processed per run (provider throttling/circuits apply; completed extractions negative-cached for 7 days, errors retried next run) |

### Recent opt-in features

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROCRASTINATE_ENABLED` | `0` | Postgres-backed durable queue for selected outbound/admin-triggered jobs (`health_ping`, LLM product extraction, stack backfill) |
| `API_CALL_EVENTS_ENABLED` | `1` | Record outbound HTTP attempts into `api_call_events` for Admin API metering |
| `CPE_CATALOG_SYNC_ENABLED` | `0` | Scheduler sync of the NVD CPE dictionary into `software_catalog` for stack autocomplete |
| `STACK_BACKFILL_ENABLED` | `0` | Enable user-approved Tier A NVD keyword backfill for shallow My Stack products |
| `EMBEDDINGS_AUTO_ON_INGEST` | `1` | When embeddings are enabled, embed newly ingested/updated CVEs immediately after ingest (capped by `EMBEDDINGS_INGEST_MAX_PER_RUN`) |
| `BRIEFR_RATE_LIMIT_STORE` | unset | Set `db` for shared token buckets across multiple uvicorn workers |
| `BRIEFR_SCHEDULER_ENABLED` | `1` | Set `0` on API-only workers; keep one scheduler owner enabled |

---

## 5. Production deploy (overview)

**Full production install checklist:** [`SELF_HOST.md` §3](SELF_HOST.md#3-production-debian--systemd--nginx). This section is a developer-oriented summary; operators should use SELF_HOST + OPERATIONS.

BRIEFR targets a single Debian server with **systemd + nginx**. Install path: `/opt/briefr`.

| Script | Purpose |
|--------|---------|
| [`deploy/setup.sh`](../deploy/setup.sh) | Initial install: Python, clone repo, venv, then production deploy |
| [`deploy/briefr-update.sh`](../deploy/briefr-update.sh) | Pull, build frontend, restart backend + nginx |
| [`deploy/briefr-backup.sh`](../deploy/briefr-backup.sh) | Manual or scheduled PostgreSQL backup (`pg_dump`) |
| [`deploy/briefr-pg-backup.sh`](../deploy/briefr-pg-backup.sh) | systemd entry point (`briefr-pg-backup.timer`) |
| [`deploy/briefr-restore.sh`](../deploy/briefr-restore.sh) | List or restore archives |
| [`deploy/check-backend.sh`](../deploy/check-backend.sh) | Health probe for monitoring |
| [`deploy/smoke-intel.sh`](../deploy/smoke-intel.sh) | Post-deploy smoke checks |

**systemd units:** `briefr-backend.service`, `briefr-pg-backup.timer` (every 6h). Scheduled ingest (NVD, KEV, EPSS, MITRE+ATLAS, exploit sources, backup dead-man) runs inside the backend — no separate refresh scripts needed.

**Production notes:**
- Set `DATABASE_URL` and `BRIEFR_REQUIRE_POSTGRES=1` in `backend/.env` (see `docs/POSTGRES.md`).
- Set `ALLOWED_ORIGINS` to your public URL (not `:5173`).
- nginx serves `frontend/dist`; Vite dev server is not used.
- Backups land in `/var/lib/briefr/backups` outside the git tree.
- Install `postgresql-client-16` (or matching major) on the host for `pg_dump` / `pg_restore`.

See [README.md § Backups and restore](../README.md) and [`docs/POSTGRES.md`](POSTGRES.md) for restore commands.

---

## 6. Key subsystems (where to look)

| If you are working on… | Start here |
|----------------------|------------|
| CVE list / filters | `backend/routers/cves/` (`_build_cve_filters`), `frontend/src/components/CVEFeed.jsx` |
| CVE detail drawer | `frontend/src/components/DetailDrawer/`, `GET /api/cves/{id}` in `routers/cves/` |
| IOC lookup | `backend/enrichment/ioc.py`, `frontend/src/components/IOCLookup.jsx` |
| Incidents & News tab | `backend/feeds/case_study_feed.py`, `incident_news.py`, `CaseStudies.jsx` |
| Risk score | `backend/scoring/risk.py`, `backend/scoring/asset_match.py`, `POST /api/cves/{id}/risk`; UI in `frontend/src/scoring/riskScore.js` |
| Correlation | `backend/correlation/engine.py` |
| Detection rules | `backend/detection/` (`sigmahq_index.py`, `rule_sources.py`, `composer.py`) |
| SigmaHQ local index | `backend/detection/sigmahq_index.py`, scheduler `sigmahq_index_sync`, Admin Feed health |
| Scheduled ingest | `backend/scheduler.py`, `backend/feeds/` |
| Database schema / SQL adaptation | `backend/database.py` (`init_db`), `backend/db/pg_adapt.py` (legacy SQLite-shaped SQL adapted at the Postgres connection boundary), [`archive/snapshots/TECHNICAL_INVENTORY.md`](archive/snapshots/TECHNICAL_INVENTORY.md) §2 |
| PDF export | `frontend/src/utils/pdfReport.js`, `backend/ai/summary.py` |
| Morning brief | `frontend/src/components/MorningBrief.jsx` (unified `action_queue` list + filter chips) |
| Analyst charts | `frontend/src/components/BriefCharts.jsx` (activity/KEV/vendor views + EPSS movers table), `CveDescriptionClamp.jsx`, `frontend/src/components/briefVendorChartRecharts.jsx`, `frontend/src/utils/rechartsTheme.js` |
| FEED stack filter | `frontend/src/components/FilterBar.jsx` (`STACK //` row — replaces Hero stack on FEED tab) |
| Backups | `backend/backup/manager.py`, `deploy/briefr-backup.sh` |

---

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Incidents tab slow or errors on feed load | Postgres connection pool exhausted or DB unreachable | Check `GET /api/health`; verify Docker Postgres at `/opt/infra/postgres`; review `journalctl -u briefr-backend` |
| Empty CVE feed on first run | Ingest still running or no network | Wait for bootstrap ingest; check `GET /api/health` `cve_count` |
| IOC lookup returns empty VT/AbuseIPDB | Missing API keys | Add keys to `.env`; restart backend |
| CORS errors in browser | Origin not allowed | Add your URL to `ALLOWED_ORIGINS` |
| GreyNoise always empty | No key or weekly quota exhausted | Set `GREYNOISE_API_KEY`; opt in per lookup |
| OTX pulses missing | No `OTX_API_KEY` or upstream OTX outage | Key required for live refresh; cached `otx_cve_pulses` served on 5xx when present. Post-deploy smoke may fail during OTX outages — retry `deploy/smoke-intel.sh` or use `BRIEFR_STRICT_SMOKE=0` |
| Detect shows no Sigma rules | SigmaHQ index never synced | Admin → Feed health → SigmaHQ → Sync (Alembic `035` creates empty tables only) |
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

# PostgreSQL row counts (DATABASE_URL in backend/.env)
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM cves;"

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

- [`archive/snapshots/CODEBASE_CONTEXT.md`](archive/snapshots/CODEBASE_CONTEXT.md) — consolidated codebase reference (architecture, flows, AI guardrails)
- [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) — architecture deep dive
- [`API_REFERENCE.md`](API_REFERENCE.md) — endpoint catalog
- [`archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) — runtime traces
- [`archive/snapshots/FOLDER_STRUCTURE_GUIDE.md`](archive/snapshots/FOLDER_STRUCTURE_GUIDE.md) — every file in the repo
