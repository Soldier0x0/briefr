# WHAT — Project Overview

## What does this project do?

BRIEFR is a self-hosted CVE intelligence and threat-investigation dashboard for security analysts, small teams, and solo researchers. It aggregates vulnerability data from NVD, CISA KEV, FIRST EPSS, MITRE ATT&CK, MITRE ATLAS, and dozens of optional enrichment feeds into a single searchable dark-mode UI. Analysts use it to answer: *what broke overnight, is it exploitable, does it affect our stack, and what should we hunt for?*

The backend (`backend/`) is a **FastAPI** monolith that ingests feeds on a schedule (APScheduler), stores everything in **SQLite** (`backend/briefr.db`), and exposes a REST API under `/api/*`. The frontend (`frontend/`) is **React + Vite** with plain JSX/CSS (no component library). In development, Vite on `:5173` proxies `/api` → `:8000`. In production, **nginx** serves `frontend/dist` and reverse-proxies API calls to uvicorn.

Live demo: [briefr.projectjupiter.in](https://briefr.projectjupiter.in)

## Core problem it solves

Analysts normally bounce between NVD, CISA KEV, VirusTotal, exploit trackers, ATT&CK, and RSS news to triage overnight CVE activity. BRIEFR automates that aggregation into one fast workflow on a single server. Asset inventory is **never stored server-side** — only `POST /api/cves/match` receives CPE profiles for ephemeral scoring.

## Key features and capabilities

| Area | Capabilities |
|------|-------------|
| **BRIEF tab** | Morning brief action queue (`GET /api/brief`), KPI stats, 90-day heatmap, What Changed panel, analyst charts (KEV histogram, EPSS movers) |
| **FEED tab** | Paginated CVE list with stack/vendor/KEV/EPSS filters, CSV/XLSX export, sidebar KEV deadlines + top ATT&CK techniques |
| **IOC LOOKUP** | Multi-source IP/hash/domain enrichment (VirusTotal, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus) with 6h cache |
| **INCIDENTS & NEWS** | 6 RSS security feeds + MITRE ATLAS case studies via `GET /api/case-studies/feed` |
| **Forge tab** | Detection engineering MVP — ATT&CK coverage map, hunt pack generation (`/api/forge/*`, `/api/hunt-packs/*`) |
| **CVE detail drawer** | Live enrichment (Sploitus, GreyNoise, OTX, OSV, CIRCL), EPSS sparkline, momentum, correlation, detection rules, related CVEs, PDF export |
| **Investigation panel** | Session-only cross-tab pivots (CVE → IOC → related CVE) |
| **Risk scoring** | Client-side Risk Score v1.1b + server momentum; weights from `GET /api/config/risk` |
| **Correlation** | Three-level engine: shared OTX IPs, actor/sector match, temporal vendor anomalies |
| **Ops** | Integrity-checked SQLite backups (age-encrypted), webhook alerts (Discord/Telegram), rate limiting, circuit breakers |

## Tech stack

### Backend (`backend/requirements.txt`)

| Package | Version | Role |
|---------|---------|------|
| Python | 3.11+ (`.python-version` pins 3.13; CI uses 3.12) | Runtime |
| fastapi | 0.137.2 | HTTP API framework |
| uvicorn[standard] | 0.49.0 | ASGI server |
| httpx | 0.28.1 | Async HTTP (via `resilient_client.py`) |
| apscheduler | 3.11.2 | Scheduled ingest jobs |
| aiosqlite | 0.22.1 | Async SQLite |
| pydantic | 2.13.4 | Request/response models |
| pydantic-settings | 2.14.1 | Typed env config (`settings.py`) |
| python-dotenv | 1.2.2 | `.env` loading |
| PyYAML | 6.0.3 | MITRE ATLAS YAML parsing |
| openpyxl | 3.1.5 | Excel export support |
| pyrage | 1.3.0 | age encryption for backups |
| numpy | 2.4.6 | Embeddings math |

**Optional (not in requirements.txt):** `fastembed` — required only when `EMBEDDINGS_ENABLED=1`.

**Dev (`backend/requirements-dev.txt`):** pytest 9.1.0, playwright 1.52.0 (+ requirements.txt).

### Frontend (`frontend/package.json`)

| Package | Version | Role |
|---------|---------|------|
| react / react-dom | 19.2.7 | UI framework |
| react-router-dom | 7.18.0 | Routing (`/privacy`, `/terms`, main app) |
| vite | 8.0.16 | Dev server + bundler |
| @vitejs/plugin-react | 6.0.2 | JSX transform |
| chart.js | 4.5.1 | KEV histogram (lazy-loaded) |
| exceljs | 4.4.0 | XLSX export |
| jspdf | 4.2.1 | PDF reports |
| html2canvas | 1.4.1 | PDF screenshot capture |
| @fontsource/* | 5.2.x | Self-hosted fonts (no Google CDN at runtime) |
| playwright | 1.61.0 (dev) | Screenshot/smoke scripts |

---

# WHERE — Repository Structure

## Annotated directory tree

```
/workspace/
├── backend/                    # FastAPI Python backend — all server logic
│   ├── main.py                 # App entry: lifespan, middleware, router includes
│   ├── settings.py             # Pydantic BaseSettings (phase-1 env vars)
│   ├── dependencies.py         # Admin-key gate, audit writer
│   ├── database.py             # SQLite schema, migrations, all DB access (~2400 lines)
│   ├── scheduler.py            # APScheduler jobs, ingest locks, startup bootstrap
│   ├── resilient_client.py     # Shared httpx pool, retries, circuit breakers
│   ├── rate_limit.py           # Token-bucket rate limiting (IOC + refresh)
│   ├── structured_logging.py   # JSON/plain logging, request_id contextvar
│   ├── tracking.py             # api_usage counters + quota metadata
│   ├── pytest.ini              # pytest config
│   ├── requirements.txt        # Runtime deps
│   ├── requirements-dev.txt    # Test deps
│   ├── .env.example            # Env var template (copy to .env)
│   ├── briefr.db               # SQLite DB (gitignored, created at runtime)
│   ├── ai/                     # LLM executive summary (Groq → Anthropic → template)
│   ├── backup/                 # SQLite backup/restore manager (age encryption)
│   ├── brief/                  # Morning brief server-side aggregation
│   ├── correlation/            # Three-level CVE correlation engine
│   ├── detection/              # Sigma/Elastic rule search, SIEM queries, Sigma generator
│   ├── enrichment/             # CVE reference parsing, IOC lookup orchestration
│   ├── feeds/                  # External feed fetchers (NVD, KEV, EPSS, MITRE, OTX, RSS, …)
│   ├── matching/               # CPE-based asset exposure matching
│   ├── ml/                     # Optional embeddings + LLM product extraction
│   ├── routers/                # FastAPI route modules (split from main.py in V1.2)
│   ├── scoring/                # Server-side momentum calculation
│   ├── templates/              # Plain-English intel sentence templates
│   ├── webhooks/               # Discord/Telegram alert sender + KEV-on-stack alerts
│   ├── scripts/                # One-off CLI tools (e.g. backfill_poc.py)
│   └── tests/                  # pytest suite (~40 test files + fixtures/)
│
├── frontend/                   # React + Vite SPA
│   ├── index.html              # Vite HTML shell
│   ├── vite.config.js          # Dev proxy /api → :8000, port 5173
│   ├── package.json            # npm dependencies
│   └── src/
│       ├── main.jsx            # React root, AssetProfileProvider, risk weight prefetch
│       ├── App.jsx             # Tab shell, global state, drawer host, keyboard shortcuts
│       ├── App.css             # Layout/grid styles
│       ├── api.js              # Central fetch wrapper + all API client functions
│       ├── components/         # UI components (Feed, Drawer, IOC, Brief, Forge, …)
│       ├── context/            # InvestigationContext, AssetProfileContext
│       ├── hooks/              # useWatchlist, useModalLayer, useInactivityTimeout
│       ├── pages/              # PrivacyPage, TermsPage, LegalPage
│       ├── scoring/            # riskScore.js — client risk calculation
│       ├── utils/              # PDF export, drawer controller, filters, timezone, …
│       ├── config/             # assetCatalog.js, caseStudySources.js
│       └── theme/              # light-theme.css (NOT imported — dark mode only)
│
├── deploy/                     # Production Debian/systemd/nginx scripts
│   ├── setup.sh                # Initial server install → /opt/briefr
│   ├── briefr-update.sh        # Pull, build frontend, restart services
│   ├── briefr-backup.sh        # Manual/scheduled backup
│   ├── briefr-restore.sh       # List/restore archives
│   ├── check-backend.sh        # Health probe for monitoring
│   ├── smoke-intel.sh          # Post-deploy smoke checks
│   ├── nginx-briefr.conf       # nginx config (HTTPS)
│   ├── nginx-briefr-http.conf  # nginx config (HTTP)
│   ├── briefr-backend.service  # systemd unit for uvicorn
│   ├── briefr-backup.timer     # systemd timer (every 6h)
│   └── lib.sh                  # Shared deploy helpers
│
├── docs/                       # Contributor + ops documentation
│   ├── ONBOARDING.md           # Start here for developers
│   ├── ROADMAP.md              # Release index V1.2–V2.0
│   ├── OPERATIONS.md           # Backup, logs, deploy
│   ├── THREAT_MODEL.md         # Security design
│   ├── JUPITER_VISION.md       # Product vision / ecosystem
│   ├── HANDOVER.md             # Live execution state
│   ├── AGENT_IMPLEMENTATION_GUIDE.md
│   ├── LIGHT_THEME.md          # Unused light theme tokens
│   └── diagrams/               # Mermaid architecture + flow diagrams
│
├── scripts/                    # Repo-level utility scripts
│   ├── seed_screenshot_data.py # Seed 15 CVEs + warm RSS for UI work
│   ├── capture_readme_screenshots.mjs
│   ├── generate_system_design_pdf.mjs
│   └── generate_technical_inventory_xlsx.py
│
├── .github/
│   ├── workflows/backend-tests.yml  # CI: pytest, pip-audit, npm audit, Playwright smoke
│   └── dependabot.yml
│
├── AGENTS.md                   # Cursor Cloud agent instructions
├── README.md                   # Product overview + quick start
├── SYSTEM_DESIGN.md            # Architecture deep dive
├── API_REFERENCE.md            # Full endpoint catalog
├── APPLICATION_EXECUTION_MAP.md # Startup + request journey traces
├── FOLDER_STRUCTURE_GUIDE.md   # File-by-file map
├── TECHNICAL_INVENTORY.md      # Schema, scheduler jobs, feature matrix
├── Beta V1.2.md … V2.0.md      # Release roadmaps
└── LICENSE                     # Proprietary — all rights reserved
```

## Key files and what each one does

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app wiring: `lifespan()`, CORS, security headers, `X-Request-ID` middleware, router registration order |
| `backend/database.py` | `get_db()`, `init_db()`, all table DDL + inline migrations, upsert/query helpers |
| `backend/scheduler.py` | 13 scheduled jobs + startup tasks; per-source asyncio locks prevent concurrent runs |
| `backend/routers/cves.py` | Largest router: CVE list/detail/intel, stats, changes, export, KEV deadlines, asset match |
| `backend/routers/refresh.py` | Manual ingest triggers (`POST /api/refresh*`), admin-gated |
| `backend/enrichment/ioc.py` | Multi-source IOC lookup orchestration |
| `backend/feeds/nvd.py` | NVD API 2.0 fetch, parse, watermark-based incremental sync |
| `backend/correlation/engine.py` | Nightly + on-demand three-level correlation |
| `backend/scoring/risk.py` | `calculate_momentum()` + weight constants (authority for risk config) |
| `backend/brief/service.py` | `build_morning_brief()` — server-computed action queue |
| `backend/backup/manager.py` | WAL-safe backup, age encryption, startup auto-restore |
| `frontend/src/App.jsx` | Tab panels (`brief`, `feed`, `ioc`, `atlas`, `forge`), filters, drawer, shortcuts |
| `frontend/src/api.js` | All `fetch*` functions; 20s timeout via `AbortSignal.timeout` |
| `frontend/src/scoring/riskScore.js` | `calculateRiskScore()`, `fetchAndCacheRiskWeights()` |
| `frontend/src/utils/openCveDrawer.js` | `createCveDrawerController()` — stale-fetch guard on drawer close |

## Where to find things

| Concern | Location |
|---------|----------|
| **Config / env vars** | `backend/.env.example`, `backend/settings.py` (partial), inline `os.environ.get` elsewhere |
| **Backend entrypoint** | `backend/main.py` → `uvicorn main:app` |
| **Frontend entrypoint** | `frontend/src/main.jsx` → `frontend/index.html` |
| **Database schema** | `backend/database.py:init_db()` (lines 21–341); docs in `TECHNICAL_INVENTORY.md` §2 |
| **Routes / controllers** | `backend/routers/*.py` |
| **Feed ingest logic** | `backend/feeds/*.py`, orchestrated by `backend/scheduler.py` |
| **Pydantic models** | Inline in router files (e.g. `routers/cves.py`, `routers/ioc.py`) — no separate `models/` package |
| **Tests** | `backend/tests/test_*.py`, fixtures in `backend/tests/fixtures/` |
| **Utilities** | `frontend/src/utils/`, `backend/enrichment/`, `backend/matching/` |
| **CI/CD** | `.github/workflows/backend-tests.yml` |
| **Deploy** | `deploy/*.sh`, `deploy/briefr-backend.service` |

---

# WHY — Architecture & Design Decisions

## Why this architecture

**Monolithic FastAPI + SQLite + React SPA** on a single Debian server. Not microservices — the deployment target is one analyst or a small team on one box. SQLite with WAL mode handles read-heavy analyst traffic; APScheduler runs ingest inside the same process (no separate worker). This keeps ops simple: one systemd unit, one DB file, one nginx config.

Trade-off documented in README: **not designed for concurrent multi-tenant writes**. V2.0 roadmap mentions optional Postgres + Docker.

## Key design patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **Feed → DB → API → UI** four-layer model | `scheduler.py` → `database.py` → `routers/` → `frontend/src` | Separates slow network ingest from fast read path |
| **Router split (V1.2)** | `backend/routers/` | `main.py` was ~1400 lines; split preserves OpenAPI route order (snapshot-tested in `test_router_split.py`) |
| **Resilient HTTP client** | `resilient_client.py` | One pooled `httpx.AsyncClient` + per-source circuit breakers for ~15 external APIs |
| **Feed cache table** | `feed_cache` | TTL-based caching for RSS, CIRCL, correlation results, LLM extractions — avoids repeat network calls |
| **Per-job asyncio locks** | `scheduler.py` (`_nvd_lock`, `_kev_lock`, …) | Skip duplicate runs; expose `ingest_in_progress` on `/api/health` |
| **Tab panels stay mounted** | `App.jsx` uses `hidden` attribute | Preserves FEED scroll position and filter state across tab switches |
| **Drawer stale-fetch guard** | `createCveDrawerController()` | Closing drawer during load must not reopen when fetch completes |
| **Asset profile client-only** | `AssetProfileContext.jsx` + `localStorage` | Privacy: inventory never persisted server-side; only sent to `POST /api/cves/match` |
| **Risk weight single-sourcing** | `GET /api/config/risk` → `riskScore.js` | Backend `scoring/risk.py` is authority; frontend fetches once at startup with bundled fallback |
| **Token-bucket rate limiting** | `rate_limit.py` | In-memory per-IP buckets — sufficient because SQLite implies single uvicorn worker |
| **Structured logging** | `structured_logging.py` | JSON lines with `request_id`; `briefr.access` logger for every HTTP request |

## Non-obvious decisions

| Decision | Rationale |
|----------|-----------|
| **aiosqlite over SQLAlchemy** | Direct SQL in `database.py`; no ORM layer. Simpler for a single-file schema but `database.py` is large (~2400 lines). |
| **Plain JSX + CSS, no Tailwind/MUI** | Terminal aesthetic, full control, no component-library lock-in. |
| **Dark mode only** | `light-theme.css` exists but is not imported. |
| **Self-hosted fonts via @fontsource** | No runtime Google Fonts requests — privacy posture. |
| **`load_dotenv()` without override** | Process env vars (Cursor Secrets) win over `.env` placeholders. Restart backend after secret changes. |
| **cvelistV5 before NVD** | GitHub compare deltas can surface CVE JSON 5.x hours before NVD analysis completes. |
| **Vulnrichment gap-fill** | CISA Vulnrichment fills CVSS/CWE/CPE for NVD-unanalyzed CVEs additively — never overwrites official NVD data. |
| **Correlation is DB-only at request time** | External OTX data pre-cached by nightly job; on-demand correlation reads `correlation_*` tables + `feed_cache`. |
| **Snooze removed from UI** | Watchlist supports `pin` only in UI; legacy snooze rows cleared via `DELETE /api/watchlist/snoozes` on load. |
| **No app-level auth yet** | `BRIEFR_ADMIN_API_KEY` optionally gates `POST /api/refresh*` only. Built-in login planned before public release. |
| **Playwright smoke skips incident feed scheduler** | `PLAYWRIGHT_SMOKE=1` disables `incident_feed_refresh` job to avoid RSS network in CI. |

## Documented trade-offs and planned work

From `Beta V1.2.md`, `README.md`, `SYSTEM_DESIGN.md`:

- **`database.py` monolith** — planned pay-as-you-go extraction to `repositories/` (V1.2/V2.0); full layer waits for Postgres.
- **`services/` layer** — planned between routers and DB (`cve_service`, `enrichment_service`, `ioc_service`).
- **`settings.py` phase 1 only** — most env vars still read via `os.environ.get` at call time; migration in progress.
- **Risk weights** — ✅ partially solved via `GET /api/config/risk`; momentum signals still computed separately in Python and JS.
- **Single-user SQLite** — concurrent writes not supported; V2.0 targets optional Postgres.
- **No frontend unit tests** — UI validated manually or via Playwright scripts in `scripts/` and `test_playwright_smoke.py`.
- **No ESLint/ruff** — no lint config in repo.

---

# HOW — Core Flows & Logic

## How the app starts / boots up

```
uvicorn loads main:app
  → load_dotenv() + configure_logging()
  → lifespan() enters:
      1. backup.manager.ensure_db_or_restore()  — integrity check; auto-restore if corrupt
      2. database.init_db()                     — CREATE TABLE + inline migrations
      3. scheduler.start_scheduler()            — register 13 APScheduler jobs
      4. scheduler.maybe_run_on_startup():
           - If CVE count ≥ 10: strip auto-summaries, enrich KEV summaries
           - If CVE count < 10: asyncio.create_task(run_full_ingest_sync)
           - maybe_run_mitre_on_startup() if MITRE/ATLAS < 10 rows
           - create_task(run_epss_backfill)
           - create_task(run_exploit_sources_sync) if enabled
  → FastAPI ready — /api/* accepts traffic
```

On shutdown: `stop_scheduler()` → `close_client()` (httpx pool).

Frontend boot (`main.jsx`):
```
ReactDOM.createRoot → BrowserRouter → AssetProfileProvider → App
fetchAndCacheRiskWeights() — fire-and-forget from /api/config/risk
```

## Primary data flow

### Read path (analyst opens CVE)

```
Browser → Vite proxy /api/cves/{id}
  → cves_router.get_cve (routers/cves.py)
  → database.get_db() — read cves row
  → Parallel enrichment (asyncio):
       feeds.extended (Sploitus, CIRCL)
       feeds.otx.load_otx_pulses_for_cve
       feeds.osv.fetch_osv_by_cve
       greynoise_scans_for_cve
  → JSON response → DetailDrawer.jsx
  → Lazy sub-fetches: /sentences, /epss-history, /momentum, /correlation, /related, /detection
```

### Write/ingest path (scheduled NVD sync)

```
APScheduler → run_nvd_incremental_sync()
  → _nvd_lock (skip if locked)
  → database.resolve_nvd_sync_watermark()
  → feeds.nvd.fetch_nvd_cve_updates() via resilient_client
  → database.upsert_cves() + set_nvd_sync_watermark()
  → strip_auto_generated_summaries, backfill_display_fields, backfill_has_poc
  → feeds.extended.enrich_cves_extended() (Sploitus, CIRCL batch)
  → cve_change_history rows for field deltas
```

### IOC lookup path

```
IOCLookup.jsx → POST /api/ioc/lookup
  → rate_limit_ioc (token bucket)
  → database.get_ioc_cache (6h TTL; GreyNoise 1h)
  → enrichment/ioc.lookup_ioc() → VT, AbuseIPDB, GN, MB, UH, OTX
  → database.set_ioc_cache + tracking.record_api_call
  → IOCLookup renders per-source panels + quota from GET /api/usage/ioc
```

## Authentication / authorization flow

**No built-in app login.** Current controls:

| Mechanism | Scope | Implementation |
|-----------|-------|----------------|
| `BRIEFR_ADMIN_API_KEY` | `POST /api/refresh*` only | `dependencies.require_admin_key()` checks `X-BRIEFR-Admin-Key` header via `secrets.compare_digest` |
| Rate limiting | `POST /api/ioc/lookup`, `POST /api/refresh*` | `rate_limit.py` — 429 + `Retry-After` |
| CORS | All `/api/*` | `ALLOWED_ORIGINS` env var |
| Security headers | All responses | CSP, X-Frame-Options, etc. in `main.py` middleware |
| Audit log | Admin refresh actions | `dependencies.audit()` → `audit_log` table (not exposed via API yet) |

Future hook: `request.state.user_email` in `dependencies.audit()` — empty until login ships.

## Database schema overview

**26 tables** in SQLite (`backend/briefr.db`). All DDL in `database.py:init_db()`.

### Core CVE data

| Table | PK | Key columns | Relationships |
|-------|-----|-------------|---------------|
| `cves` | `cve_id` | cvss_score, severity, epss_score, is_kev, has_poc, affected_products, has_ai_context | Central entity — joined by most tables |
| `kev_deadlines` | `cve_id` | due_date, required_action, vendor_project | FK-like join on cve_id |
| `epss_history` | (cve_id, recorded_date) | score | Sparkline data for drawer |
| `cve_change_history` | id AUTO | field_name, old_value, new_value, detected_at | What Changed panel, brief EPSS movers |
| `cve_exploits` | id AUTO | cve_id, url, source, type | UNIQUE (cve_id, url) |

### MITRE / ATLAS

| Table | Purpose |
|-------|---------|
| `mitre_techniques` | ATT&CK technique metadata |
| `cve_technique_map` | CVE ↔ technique many-to-many |
| `mitre_groups` | Threat actor groups |
| `group_technique_map` | Group ↔ technique |
| `atlas_techniques` | MITRE ATLAS AI/ML techniques |
| `atlas_case_studies` | ATLAS incident narratives |
| `cve_atlas_map` | CVE ↔ ATLAS technique |

### Threat intel / correlation

| Table | Purpose |
|-------|---------|
| `otx_cve_pulses` | OTX campaign pulses per CVE |
| `otx_pulse_iocs` | IOCs within pulses (feeds infrastructure correlation) |
| `correlation_infrastructure` | CVE pairs sharing exploitation IPs |
| `correlation_actor` | Actor/sector matches per CVE |
| `correlation_temporal` | Vendor volume anomaly scores |
| `ioc_cache` | Cached IOC lookup results (6h) |
| `feed_cache` | Generic TTL cache (RSS, CIRCL, correlation, LLM, incident snapshot) |

### Ops / user state

| Table | Purpose |
|-------|---------|
| `sync_state` | Watermarks (NVD, cvelistV5 head SHA, EPSS backfill done, …) |
| `api_usage` | Per-service daily/monthly call counters |
| `audit_log` | Admin action audit trail |
| `watchlist` | Pin/snooze state (UI: pin only) |
| `webhook_alert_log` | Deduped KEV-on-stack + backup dead-man alerts |
| `hunt_packs` | Forge tab saved detection packs |
| `cve_embeddings` | Optional semantic similarity vectors |

**PRAGMA settings:** `journal_mode=WAL`, `busy_timeout=30000`, `foreign_keys=ON`.

## Five most important functions/classes

### 1. `init_db()` — `backend/database.py`

Creates all 26 tables, runs inline ALTER/migration loop (try/except per statement), normalizes `epss_score = 0.0 → NULL`. Called once at startup. There is no separate migration framework — schema evolution is additive DDL in the migration tuple.

### 2. `start_scheduler()` — `backend/scheduler.py:881`

Registers all APScheduler jobs with `max_instances=1, coalesce=True`. Jobs: NVD (hourly), KEV (15m), EPSS (6h), MITRE+ATLAS (weekly Sun), OTX nightly, incident feed (30m), exploit sources, embeddings backfill, LLM extraction, correlation nightly, vulnrichment (6h), cvelistV5 (30m), backup dead-man. Returns the scheduler instance stored in module-global `_scheduler`.

### 3. `get_cve()` — `backend/routers/cves.py`

Primary CVE detail endpoint. Reads DB row, orchestrates parallel live enrichment (Sploitus, GreyNoise, OTX, OSV, CIRCL), attaches MITRE/ATLAS techniques, KEV deadline, watchlist state, exploit list. Called by drawer on every CVE open. Validates `CVE-` prefix on sibling intel endpoints.

### 4. `build_morning_brief()` — `backend/brief/service.py:54`

Server-computed morning brief. Aggregates action queue sections from existing DB state only (no ingest): EPSS movers, new KEV entries, critical/high CVEs, stack matches, AI/ML alerts. Uses `_stack_match_clause` from cves router for stack filtering. Returns unified `action_queue` list consumed by `MorningBrief.jsx`.

### 5. `calculateRiskScore()` — `frontend/src/scoring/riskScore.js`

Client-side Risk Score v1.1b. Combines six weighted components (asset 0.35, KEV 0.25, EPSS 0.15, exploit 0.10, CVSS 0.10, momentum 0.05) using weights from `fetchAndCacheRiskWeights()` (cached at startup from `GET /api/config/risk`). Used in `CVECard.jsx` (momentum=0) and `DetailDrawer.jsx` (with live momentum from `GET /api/cves/{id}/momentum`).

---

# WHEN — State & Lifecycle

## When major components initialize

| Component | When | Trigger |
|-----------|------|---------|
| SQLite DB + schema | First `lifespan()` entry | Every backend start |
| DB auto-restore | Before `init_db()` if corrupt | `ensure_db_or_restore()` |
| APScheduler | After `init_db()` | `start_scheduler()` |
| Full NVD ingest | Startup if `< 10` CVEs | `maybe_run_on_startup()` |
| MITRE/ATLAS refresh | Startup if `< 10` technique rows | `maybe_run_mitre_on_startup()` |
| EPSS history backfill | Startup (one-shot) | `run_epss_backfill()` unless `sync_state.epss_backfill_done` |
| Incident feed snapshot | ~20s after boot + every 30m | `run_incident_feed_refresh()` |
| Risk weight cache | Frontend first load | `main.jsx` → `fetchAndCacheRiskWeights()` |
| Asset profile | Frontend first load | `AssetProfileContext` reads `localStorage` |
| Investigation thread | Session only | `InvestigationContext` — lost on refresh |
| httpx client pool | First outbound HTTP call | `resilient_client._get_client()` |
| Embeddings model | First scheduler run when enabled | `ml/embeddings.py` downloads ONNX to `EMBEDDINGS_CACHE_DIR` |

## Event-driven triggers and cron jobs

All jobs in `scheduler.py:start_scheduler()`. Default timezone: `SCHEDULER_TIMEZONE=Asia/Kolkata`.

| Job ID | Schedule | Function |
|--------|----------|----------|
| `nvd_incremental_sync` | Every `NVD_SYNC_INTERVAL_HOURS` (1h) | `run_nvd_incremental_sync` |
| `kev_metadata_sync` | Every `KEV_SYNC_INTERVAL_MINUTES` (15m) | `run_kev_sync` |
| `epss_score_sync` | Every `EPSS_SYNC_INTERVAL_HOURS` (6h) | `run_epss_sync` |
| `weekly_mitre_refresh` | Cron Sun `MITRE_REFRESH_HOUR:MINUTE` | `run_weekly_mitre_refresh` |
| `otx_nightly_correlation` | Cron daily in `OTX_CORRELATION_TIMEZONE` | `run_otx_nightly_sync` |
| `incident_feed_refresh` | Every `INCIDENT_FEED_REFRESH_MINUTES` (30m) | `run_incident_feed_refresh` |
| `exploit_sources_sync` | Every N hours (if `EXPLOIT_SOURCES_SYNC_ENABLED`) | `run_exploit_sources_sync` |
| `embeddings_backfill` | Every 6h (no-op unless `EMBEDDINGS_ENABLED=1`) | `run_embeddings_sync` |
| `llm_product_extraction` | Every 6h (no-op unless enabled + Groq key) | `run_llm_extraction_sync` |
| `nightly_correlation` | Cron daily in `CORRELATION_TIMEZONE` | `run_nightly_correlation` |
| `vulnrichment_snapshot_sync` | Every 6h | `run_vulnrichment_sync` |
| `cvelistv5_incremental_sync` | Every 30m | `run_cvelistv5_sync` |
| `backup_deadman_check` | Every `max(1, BACKUP_INTERVAL_HOURS // 2)` | `run_backup_deadman_check` |

**Startup one-shots (not scheduled):** `run_full_ingest_sync`, `run_epss_backfill`, `run_exploit_sources_sync` (if ≥10 CVEs).

**Manual triggers:** `POST /api/refresh`, `/api/refresh/nvd`, `/kev`, `/epss`, `/mitre` (admin-gated if key set).

**Webhook alerts (scheduler-side):** KEV-on-stack after KEV sync (`webhooks/alerts.py:process_kev_stack_alerts`); backup dead-man (`check_backup_deadman`).

**External systemd timer:** `briefr-backup.timer` every 6h → `deploy/briefr-backup.sh`.

## Deployment pipeline / CI-CD

### CI (`.github/workflows/backend-tests.yml`)

Triggers: push to `main`, all pull requests.

| Job | Steps |
|-----|-------|
| **test** | Python 3.12, `pip install -r requirements-dev.txt`, `cd backend && pytest tests/ -q` |
| **dependency-audit** | `pip-audit -r requirements.txt` + `npm ci && npm run audit:ci` (Node 24) |
| **playwright-smoke** | Build frontend, `PLAYWRIGHT_SMOKE=1 pytest tests/test_playwright_smoke.py -q` |

No frontend unit test job. No deploy job in CI — production deploy is manual via `deploy/briefr-update.sh`.

### Production deploy

```bash
bash deploy/setup.sh          # First-time: clone to /opt/briefr, venv, systemd, nginx
bash deploy/briefr-update.sh  # Pull, npm run build, restart briefr-backend + nginx
```

Install path: `/opt/briefr`. Backend venv: `/opt/briefr/venv`. Backups: `/var/lib/briefr/backups`.

## Environment-specific behavior

| Aspect | Development | Production |
|--------|-------------|------------|
| `BRIEFR_ENV` | `development` (default) | `production` — disables `/api/docs`, `/api/redoc`, `/api/openapi.json` |
| Frontend | Vite dev server `:5173`, HMR | nginx serves `frontend/dist` |
| `ALLOWED_ORIGINS` | `localhost:5173` etc. | Public URL (not `:5173`) |
| API keys | `.env` placeholders OK; many features empty without real keys | Real keys recommended |
| Env var precedence | Process env > `.env` (`load_dotenv()` no override) | Same |
| Backups | Optional: `BACKUP_DIR=./backups`, `python -m backup run` | `/var/lib/briefr/backups`, systemd timer |
| Embeddings cache | Default HF cache | systemd sets `/var/lib/briefr/models` (writable under ProtectSystem=strict) |
| Playwright smoke | N/A locally unless `PLAYWRIGHT_SMOKE=1` | CI only; disables incident feed scheduler |
| Single worker assumption | uvicorn `--reload` (dev) | Single uvicorn worker (rate limit buckets are in-memory) |

---

# CONTEXT FOR AI

## Things an AI assistant must know to not break this codebase

1. **Router registration order matters.** `main.py` includes routers in a specific sequence so `/api/cves/{cve_id}` matches after literal paths like `/api/cves/export`. Changing order breaks routing; `tests/test_router_split.py` snapshot-tests OpenAPI route list.

2. **Never store asset inventory server-side.** Only `POST /api/cves/match` receives CPE data. Asset profiles live in `localStorage` via `AssetProfileContext`.

3. **`database.py` is the single DB layer.** No SQLAlchemy. Add queries here or in the relevant feed module — do not introduce an ORM without explicit request.

4. **Env vars: process env wins over `.env`.** After changing secrets, restart the backend process (stale tmux/uvicorn won't pick them up).

5. **Dark mode only.** Do not import `frontend/src/theme/light-theme.css`.

6. **Tab panels use `hidden`, not conditional unmount.** In `App.jsx`, tab content stays mounted to preserve scroll/filter state.

7. **Snooze is legacy.** UI only exposes pin. App clears snoozes via `DELETE /api/watchlist/snoozes` on load.

8. **Risk weights: backend is authority.** Change weights in `backend/scoring/risk.py`; frontend fetches via `GET /api/config/risk`. Keep bundled fallback constants in `riskScore.js` in sync.

9. **Single SQLite writer.** Do not run multiple uvicorn workers — rate limit buckets and SQLite writes assume one process.

10. **Incident feed uses one DB connection.** `case_study_feed.py` must not open parallel connections (causes "database is locked").

11. **NVD 503s are transient.** Circuit breaker in `resilient_client.py` — not necessarily a bad API key.

12. **First boot is slow.** `< 10` CVEs triggers full ingest. Use `python scripts/seed_screenshot_data.py` for instant sample data.

13. **Proprietary license.** Do not assume OSS redistribution rights.

## Common gotchas

| Gotcha | Detail |
|--------|--------|
| Frontend `/api` 404 | Backend not running on `:8000` before `npm run dev` |
| Empty IOC results | Missing `VIRUSTOTAL_API_KEY` / `ABUSEIPDB_API_KEY` in env |
| GreyNoise empty | Weekly 50-call free tier; must opt in per lookup in UI |
| CORS errors | Add origin to `ALLOWED_ORIGINS` |
| `pytest` import errors | Must run from `backend/` directory |
| `database is locked` | Parallel SQLite connections; check `busy_timeout=30000` |
| Drawer reopens after close | Must use `createCveDrawerController` stale-fetch guard |
| OpenAPI docs in prod | Set `BRIEFR_ENV=production` |
| README vs package.json versions | README may lag; trust `requirements.txt` and `package.json` |
| EPSS score 0.0 | Normalized to NULL in `init_db()` — treat NULL as "no score" |
| `affected_products_source='llm'` | LLM-extracted products; official NVD CPE supersedes on next sync |

## Naming conventions

| Area | Convention |
|------|------------|
| Python files | `snake_case.py` |
| Python functions | `snake_case` |
| Python private | `_leading_underscore` |
| React components | `PascalCase.jsx` + co-located `PascalCase.css` |
| React hooks | `useCamelCase.js` |
| API routes | `/api/{resource}` lowercase, `{cve_id}` path params uppercase CVE IDs |
| DB tables | `snake_case` plural or descriptive (`cves`, `kev_deadlines`, `cve_change_history`) |
| DB columns | `snake_case` |
| Env vars | `SCREAMING_SNAKE_CASE` |
| Scheduler job IDs | `snake_case` descriptive (`nvd_incremental_sync`) |
| Feed cache keys | Colon-separated namespaces (`incident_rss:{source}`, `incident_feed:snapshot`) |
| Sync state keys | Plain strings in `sync_state.key` (`nvd_last_modified`, `cvelistv5_head_sha`, `epss_backfill_done`) |
| Frontend localStorage | `briefr_*` prefix (`briefr_timezone`, asset profile keys) |
| Custom events | `briefr-stack-change`, `briefr-profile-change`, `briefr-timezone-change` |

## Test strategy and how to run tests

**Backend only** — no frontend unit tests, no ESLint/ruff.

```bash
cd backend
source .venv/bin/activate   # or create venv first
pip install -r requirements-dev.txt
pytest tests/ -q            # matches CI
pytest tests/ -v              # verbose
pytest tests/test_cpe_matching.py -v  # single file
```

**Playwright smoke (optional, needs built frontend):**

```bash
cd frontend && npm ci && npm run build
cd ../backend
PLAYWRIGHT_SMOKE=1 pytest tests/test_playwright_smoke.py -q
```

**Frontend build check:**

```bash
cd frontend && npm run build
```

**Dependency audit (matches CI):**

```bash
pip-audit -r backend/requirements.txt
cd frontend && npm ci && npm run audit:ci
```

Key test files: `test_router_split.py` (route order), `test_rate_limit.py`, `test_resilient_client.py`, `test_incident_news.py`, `test_cpe_matching.py`, `test_risk_intelligence.py`, `test_backup_manager.py`, `test_exploit_sources.py`.

## How to add a new feature

### New API endpoint

1. **Choose router** — add to existing `backend/routers/{module}.py` or create new router file.
2. **Define handler** — use `APIRouter`, Pydantic models for request/response bodies.
3. **DB access** — add query helpers to `database.py` if needed.
4. **Register router** — `app.include_router()` in `main.py` at the correct position (literal routes before parameterized ones).
5. **Add test** — `backend/tests/test_{feature}.py`.
6. **Document** — update `API_REFERENCE.md` if public-facing.
7. **Frontend client** — add `fetch*` function in `frontend/src/api.js`.

Example pattern (existing code):

```python
# backend/routers/example.py
router = APIRouter()

@router.get("/api/example/{item_id}")
async def get_example(item_id: str):
    db = await get_db()
    try:
        # query
        ...
    finally:
        await db.close()
```

### New scheduled feed

1. Create fetcher in `backend/feeds/new_feed.py` using `resilient_client.resilient_get()`.
2. Add DB upsert helpers in `database.py`.
3. Register job in `scheduler.py:start_scheduler()` with asyncio lock + `max_instances=1`.
4. Add env vars to `.env.example`.
5. Write `backend/tests/test_new_feed.py` with fixtures in `tests/fixtures/`.

### New UI tab or panel

1. Create component in `frontend/src/components/NewFeature.jsx` + `.css`.
2. Add tab to `Header.jsx` nav and `App.jsx` tab panel (use `hidden` attribute pattern).
3. Add API calls to `frontend/src/api.js`.
4. Wire state in `App.jsx` or a dedicated context if cross-tab.

### New CVE list filter

1. Add query param handling in `backend/routers/cves.py` (`_build_cve_filters` / list endpoint).
2. Add filter field to `DEFAULT_FILTERS` in `App.jsx`.
3. Map filter → query param in `frontend/src/api.js:fetchCVEs()`.
4. Add UI control in `FilterBar.jsx`.

---

## Quick reference: all API endpoints

| Method | Path | Router file |
|--------|------|-------------|
| GET | `/api/health` | `health.py` |
| GET | `/api/version`, `/api/time` | `meta.py` |
| GET | `/api/usage`, `/api/usage/ioc` | `meta.py` |
| POST | `/api/ai/summary`, `/api/investigation/summary` | `meta.py` |
| GET | `/api/changes` | `cves.py` |
| GET | `/api/stats`, `/api/stats/timeline` | `cves.py` |
| GET | `/api/cves`, `/api/cves/export` | `cves.py` |
| POST | `/api/cves/match` | `cves.py` |
| GET | `/api/cves/{id}`, `/api/cves/{id}/sentences`, `/epss-history`, `/related` | `cves.py` |
| GET | `/api/cves/{id}/momentum`, `/detection`, `/correlation` | `cves.py` |
| GET | `/api/kev/deadlines`, `/api/techniques/top` | `cves.py` |
| POST | `/api/ioc/lookup` | `ioc.py` |
| GET | `/api/otx/pulses/{id}/iocs` | `ioc.py` |
| GET | `/api/atlas/techniques`, `/api/atlas/casestudies` | `atlas.py` |
| GET | `/api/case-studies/feed`, `/api/case-studies/news` | `atlas.py` |
| GET | `/api/brief` | `brief.py` |
| GET | `/api/config/risk` | `config.py` |
| GET/POST/DELETE | `/api/watchlist`, `/api/watchlist/{id}`, `/api/watchlist/snoozes` | `watchlist.py` |
| GET | `/api/forge/coverage` | `forge.py` |
| GET/POST | `/api/hunt-packs/{technique_id}`, `/api/hunt-packs/generate` | `forge.py` |
| POST | `/api/refresh`, `/api/refresh/nvd`, `/kev`, `/epss`, `/mitre` | `refresh.py` |

Interactive docs (dev only): `http://localhost:8000/api/docs`

---

## Related documentation (read order for deeper dives)

1. `docs/ONBOARDING.md` — developer quick start
2. `SYSTEM_DESIGN.md` — architecture diagrams and trade-offs
3. `APPLICATION_EXECUTION_MAP.md` — per-tab request journeys
4. `API_REFERENCE.md` — full param/response shapes
5. `TECHNICAL_INVENTORY.md` — schema columns, scheduler details, external API matrix
6. `FOLDER_STRUCTURE_GUIDE.md` — every file one-liner
7. `AGENTS.md` — Cursor Cloud environment caveats
