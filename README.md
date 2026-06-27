
# BRIEFR
### CVE Intelligence & Threat Investigation for Security Analysts

![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![React 19](https://img.shields.io/badge/React-19.2-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.137-green.svg)

BRIEFR is a self-hosted CVE intelligence dashboard for security analysts, small teams, and solo researchers. It aggregates NVD, CISA KEV, EPSS, MITRE ATT&CK, MITRE ATLAS, and optional threat-feed enrichment into one searchable UI — with IOC lookup, correlation, detection engineering helpers, and PDF export.

**Live demo:** [briefr.projectjupiter.in](https://briefr.projectjupiter.in)

---

## Screenshots

### BRIEF — morning brief, charts, heatmap

![BRIEF tab — morning brief action queue](screenshots/brief.png)

### IOC LOOKUP — multi-source indicator enrichment

![IOC Lookup tab](screenshots/ioc-lookup.png)

### INCIDENTS & NEWS — RSS security news + MITRE ATLAS case studies

![Incidents and News tab](screenshots/incidents-news.png)

---

## What is BRIEFR?

Every morning, analysts check NVD, CISA KEV, VirusTotal, and exploit trackers to answer one question: *what broke overnight and does it affect us?* BRIEFR automates that aggregation into a single self-hosted app. No account, no cookies, no analytics — your PostgreSQL database and API keys stay on your server.

Three main tabs:

| Tab | What it does |
|-----|----------------|
| **BRIEF** | Morning brief action queue, analyst charts, 90-day heatmap, Hero + KPI stats |
| **FEED** | Full paginated CVE list with FilterBar stack field, sidebar KEV deadlines |
| **IOC LOOKUP** | IP / hash / domain enrichment via VirusTotal, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus |
| **INCIDENTS & NEWS** | Security RSS feeds (6 sources) plus MITRE ATLAS incident narratives |

---

## Features

**Vulnerability intelligence**
- NVD incremental ingest with CVSS v3.1, EPSS, CISA KEV, and change tracking
- CVE detail enrichment: Sploitus exploits, GreyNoise scans, OTX pulses, OSV packages, CIRCL references
- MITRE ATT&CK technique mapping and top-technique sidebar
- MITRE ATLAS AI/ML threat context (weekly refresh; per-CVE drawer + Incidents tab)
- 90-day publication timeline heatmap beside the **What changed** panel on wide screens (≥901px); stacked on narrower viewports
- Client-side **Risk Score v1.1b** (asset, KEV, EPSS, exploit, CVSS, momentum)

**Threat investigation**
- Investigation panel with cross-tab pivots (CVE → IOC → related CVE)
- Three-level correlation engine (shared OTX IPs, actor/sector match, temporal vendor anomalies)
- Detection tab: SigmaHQ + Elastic community rules, generated Sigma fallback, SIEM quick queries
- Asset profile wizard with CPE-based exposure matching (`POST /api/cves/match` only — inventory never stored server-side)

**IOC enrichment**
- Cached lookups (6 hours; GreyNoise 1 hour)
- Live API quota display per service
- Optional GreyNoise opt-in per lookup (weekly free-tier limit)

**Export & reporting**
- CSV and Excel export from the feed
- Single-CVE and bulk PDF reports (jsPDF + optional AI executive summary)
- Markdown copy from the detail drawer
- Timezone-aware timestamps

**User experience**
- Dark mode only (terminal aesthetic)
- Timezone selector (stored in `localStorage`)
- Keyboard shortcuts (`/`, `F`, `Esc`, `g d` digest, arrow keys in feed)
- Tab panels stay mounted when switching BRIEF / FEED / IOC / Forge (scroll and filter state preserved)
- CVE detail drawer slides over content; closing during load does not reopen when fetch completes
- Session-only investigation thread; stack filter persisted locally
- Feed: prominent stack bar, CVE keyword search, quick filters below search, common vendor chips (non-sticky)

---

## Tech Stack

| Backend | Frontend |
|---------|----------|
| FastAPI 0.137.2 | React 19.2.7 |
| Uvicorn 0.49.0 | React Router 7.18.0 |
| httpx 0.28.1 | Vite 8.0.16 |
| APScheduler 3.11.2 | ExcelJS 4.4.0 |
| asyncpg 0.30.0 + psycopg 3.2.6 (Alembic) | jsPDF 4.2.1 + html2canvas |
| Pydantic 2.13.4 | Plain JSX + CSS (no component library) |
| python-dotenv, PyYAML | |

---

## Data Sources

BRIEFR incorporates publicly available intelligence from NVD, CISA KEV, FIRST EPSS, MITRE ATT&CK, MITRE ATLAS, OTX, VirusTotal, AbuseIPDB, GreyNoise, abuse.ch, and the additional feeds below. All trademarks, service marks, logos, and data rights remain the property of their respective owners.

| Source | Data | Refresh | API / trigger |
|--------|------|---------|---------------|
| NVD (NIST) | CVE records, CVSS, CPE | Every `NVD_SYNC_INTERVAL_HOURS` (default 1h) | `POST /api/refresh/nvd` |
| CISA KEV | Known exploited vulns + deadlines | Every `KEV_SYNC_INTERVAL_MINUTES` (default 15m) | `POST /api/refresh/kev` |
| FIRST EPSS | Exploit probability scores | Every `EPSS_SYNC_INTERVAL_HOURS` (default 6h) | `POST /api/refresh/epss` |
| MITRE ATT&CK | Techniques, groups, CVE mappings | Weekly (Sunday cron) | `POST /api/refresh/mitre` |
| MITRE ATLAS | AI/ML techniques + case studies | Weekly (with MITRE job) | `POST /api/refresh/mitre` |
| OTX (AlienVault) | Campaign pulses + IOCs | Nightly job + on demand | `OTX_API_KEY` |
| VirusTotal | IOC reputation | On demand (6h cache) | `POST /api/ioc/lookup` |
| AbuseIPDB | IP abuse score | On demand (6h cache) | `POST /api/ioc/lookup` |
| GreyNoise | IP classification + CVE scan context | On demand | IOC + CVE detail |
| abuse.ch (MalwareBazaar / URLhaus) | Hash / domain malware context | On demand | `ABUSECH_AUTH_KEY` |
| OSV.dev | Affected packages | On CVE detail view | — |
| Sploitus | Public exploits | On CVE detail / ingest enrichment | — |
| PoC-in-GitHub | GitHub PoC index | Scheduler (`exploit_sources_sync`) | `GITHUB_TOKEN` optional |
| ExploitDB | Public exploit CSV | Scheduler (`exploit_sources_sync`) | — |
| Metasploit | MSF exploit modules | Scheduler (`exploit_sources_sync`) | — |
| Nuclei | CVE template index | Scheduler (`exploit_sources_sync`) | — |
| CIRCL (vulnerability.circl.lu) | Extended CVE references + CAPEC | On CVE detail / ingest (7d cache, 24h negative cache) | `CIRCL_API_KEY` optional |
| Groq / Anthropic | PDF executive summary | On PDF export only | `POST /api/ai/summary` |
| GitHub | Sigma + Elastic rule search | On Detect tab open | `GITHUB_TOKEN` optional |
| RSS × 6 | Security news cards | Snapshot every 30 min (`INCIDENT_FEED_REFRESH_MINUTES`) | `GET /api/case-studies/feed` |
| CISA Vulnrichment | SSVC / CVSS / CWE / CPE gap-fill before NVD analysis | Every `VULNRICHMENT_SYNC_INTERVAL_HOURS` (default 6h) | Scheduler only |
| cvelistV5 | CVE JSON 5.x records + ADP containers (hours before NVD) | Every `CVELISTV5_SYNC_INTERVAL_MINUTES` (default 30m) | Scheduler only (`sync_state.cvelistv5_head_sha`) |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Recommended API keys: [NVD](https://nvd.nist.gov/developers/request-an-api-key), [VirusTotal](https://www.virustotal.com/gui/join-us), [AbuseIPDB](https://www.abuseipdb.com/register)
- Optional: GreyNoise, OTX, Abuse.ch, Groq/Anthropic, GitHub token — see `backend/.env.example`

### Development install

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate   # or use system Python 3.11+
pip install -r requirements-dev.txt
cp .env.example .env   # add your API keys

uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
cd ../frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api → :8000
```

On first start with fewer than 10 CVEs, the backend automatically runs a full ingest (NVD → KEV → EPSS). With 10+ CVEs, incremental schedulers maintain freshness.

### Production deploy

```bash
bash deploy/setup.sh          # initial Debian/systemd + nginx setup
bash deploy/briefr-update.sh  # pull, build frontend, restart backend + nginx
```

Set `ALLOWED_ORIGINS` in `backend/.env` to your public URL (not `:5173`). Production serves `frontend/dist` via nginx; the Vite dev server is not used.

If the same server is also used for post-deploy test verification, opt in to dev/test dependencies during the update:

```bash
BRIEFR_INSTALL_DEV_DEPS=1 bash deploy/briefr-update.sh
cd /opt/briefr/backend && /opt/briefr/venv/bin/pytest tests/ -q
```

### Backups and restore

BRIEFR backs up the PostgreSQL database (`pg_dump`) and `.env` to **`/var/lib/briefr/backups`** (outside the git tree):

| Mechanism | Schedule | Notes |
|-----------|----------|-------|
| `briefr-pg-backup.timer` | Every **6 hours** | systemd oneshot; `pg_dump` custom format (`briefr.pgdump` in archive) |
| `briefr-update.sh` | Before each deploy | Labelled `pre-update` in the manifest |
| Startup | On backend boot | If the database is unreachable or corrupt, restores the newest valid archive |

Requires `DATABASE_URL` and host `postgresql-client` (match your Postgres major — **16** in production; see `docs/POSTGRES.md`).

Defaults: keep the **newest 100** archives; rotate `backups/logs/backup.log` at 5 MB (5 gzipped generations).

Archives are **age-encrypted** (`briefr-*.tar.gz.age`) when a key exists at `/var/lib/briefr/keys/backup-age.key` — `deploy/briefr-backup.sh` generates it on first run (key lives outside `BACKUP_DIR`; restore and startup auto-restore decrypt transparently). Set `BACKUP_AGE_KEY_FILE` to use another path, or `BACKUP_AGE_KEY_FILE=""` for plaintext archives. **Copy the key somewhere safe — off-site archive copies are useless without it.**

```bash
# Manual backup
bash /opt/briefr/deploy/briefr-backup.sh manual

# List archives
bash /opt/briefr/deploy/briefr-restore.sh --list

# Restore newest valid backup (stops backend, replaces DB + .env from archive)
bash /opt/briefr/deploy/briefr-restore.sh

# Restore a specific archive (plaintext or encrypted)
bash /opt/briefr/deploy/briefr-restore.sh /var/lib/briefr/backups/briefr-20260608T120000Z.tar.gz.age
```

Development (optional): set `BACKUP_DIR=./backups` in `backend/.env`, then `python -m backup run`.

### Manual refresh

```bash
curl -X POST http://127.0.0.1:8000/api/refresh        # NVD + KEV + EPSS chain
curl -X POST http://127.0.0.1:8000/api/refresh/nvd
curl -X POST http://127.0.0.1:8000/api/refresh/kev
curl -X POST http://127.0.0.1:8000/api/refresh/epss
curl -X POST http://127.0.0.1:8000/api/refresh/mitre  # ATT&CK + ATLAS
```

Recent field changes: `GET /api/changes?since_hours=24` (BRIEF tab **What changed** panel — CVSS/EPSS/KEV/PoC deltas with 24h/48h/7d filters)

Check coverage:

```bash
psql "$DATABASE_URL" -c \
  "SELECT COUNT(*) AS total, COUNT(epss_score) AS with_epss FROM cves;"
```

---

## Environment Variables

See `backend/.env.example` for the full list. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `NVD_API_KEY` | NVD rate-limit key (recommended) | — |
| `VIRUSTOTAL_API_KEY` | IOC lookups | — |
| `ABUSEIPDB_API_KEY` | IP reputation | — |
| `GREYNOISE_API_KEY` | IP context (50/week free) | — |
| `ABUSECH_AUTH_KEY` | MalwareBazaar + URLhaus | — |
| `OTX_API_KEY` | OTX pulses + correlation | — |
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | PDF AI summary (Groq uses `llama-3.1-8b-instant`) | — |
| `GITHUB_TOKEN` | Detection rule search rate limit | — |
| `CIRCL_API_KEY` | vulnerability.circl.lu authenticated rate limits | — |
| `BRIEFR_ENV` | `production` disables Swagger/OpenAPI docs | `development` |
| `BRIEFR_ADMIN_API_KEY` | Optional `X-BRIEFR-Admin-Key` gate for `POST /api/refresh*` | — |
| `RATE_LIMIT_ENABLED` | Token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` | `1` |
| `RATE_LIMIT_IOC_PER_MINUTE` / `RATE_LIMIT_REFRESH_PER_MINUTE` | Per-client-IP budgets (429 + `Retry-After` over the limit) | `30` / `10` |
| `RATE_LIMIT_WALLBOARD_PER_MINUTE` | Per-client-IP budget for `GET /api/wallboard` | `60` |
| `WALLBOARD_TOKEN` | Optional read-only gate for `GET /api/wallboard` + `/wallboard` UI (`X-BRIEFR-Wallboard-Token`) | — |
| `LOG_FORMAT` | `json` structured logs with `request_id`, or `plain` | `json` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `DATABASE_URL` | PostgreSQL DSN (**required**) | `postgresql://briefr:briefr@127.0.0.1:5432/briefr` |
| `BRIEFR_REQUIRE_POSTGRES` | Refuse startup without Postgres | `1` |
| `DATABASE_POOL_SIZE` | asyncpg connection pool size | `10` |
| `BACKUP_DIR` | Backup archive directory | `/var/lib/briefr/backups` |
| `BACKUP_RETENTION_COUNT` | Max `briefr-*.tar.gz[.age]` archives kept | `100` |
| `BACKUP_ENABLED` | Enable backups + startup auto-restore | `1` |
| `BACKUP_AGE_KEY_FILE` | age identity for archive encryption (outside `BACKUP_DIR`; `""` disables) | `/var/lib/briefr/keys/backup-age.key` if present |
| `BACKUP_INTERVAL_HOURS` | Expected backup cadence (dead-man alert threshold = 2× this) | `6` |
| `DISCORD_WEBHOOK_URL` | Discord incoming webhook for scheduler alerts | — |
| `DISCORD_WEBHOOK_ENABLED` / `DISCORD_WEBHOOK_EVENTS` | Discord destination toggle + event filter | `1` / all events |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram bot alerts (both required to enable) | — |
| `TELEGRAM_WEBHOOK_ENABLED` / `TELEGRAM_WEBHOOK_EVENTS` | Telegram destination toggle + event filter | `1` / all events |
| `WEBHOOK_GENERIC_URL` | Generic HTTPS POST webhook (SSRF-protected) | — |
| `WEBHOOK_GENERIC_ENABLED` / `WEBHOOK_GENERIC_EVENTS` / `WEBHOOK_GENERIC_LABEL` | Generic destination toggle, events, label | `1` / all / `Generic HTTPS` |
| `BRIEFR_STACK_TERMS` | Comma-separated stack for server-side KEV-on-stack matching | — |
| `NVD_SYNC_INTERVAL_HOURS` | NVD incremental cadence | `1` |
| `KEV_SYNC_INTERVAL_MINUTES` | KEV sync cadence | `15` |
| `EPSS_SYNC_INTERVAL_HOURS` | EPSS sync cadence | `6` |
| `INCIDENT_FEED_REFRESH_MINUTES` | Incidents & News snapshot rebuild cadence | `30` |
| `SCHEDULER_TIMEZONE` | APScheduler TZ | `Asia/Kolkata` |
| `CORRELATION_HOUR` / `CORRELATION_TIMEZONE` | Nightly correlation job | `1` / `Asia/Kolkata` |
| `OTX_CORRELATION_HOUR` / `OTX_CORRELATION_TIMEZONE` | OTX nightly job | `2` / `Asia/Kolkata` |
| `MITRE_REFRESH_HOUR` | Weekly MITRE+ATLAS (Sunday) | `2` |
| `MAX_CVES_PER_FETCH` | Cap per NVD sync | `2000` |
| `DEFAULT_TIMEZONE` | Health/time display | `Asia/Kolkata` |
| `EMBEDDINGS_ENABLED` | Semantic "similar CVEs" via local embeddings (needs `pip install fastembed`; off = shared-product heuristic) | `0` |
| `EMBEDDINGS_MODEL` | Local CPU embedding model (ONNX) | `BAAI/bge-small-en-v1.5` |
| `EMBEDDINGS_CACHE_DIR` | Writable model cache dir (systemd unit sets `/var/lib/briefr/models`; home-dir HF cache is read-only under `ProtectSystem=strict`) | fastembed default |
| `EMBEDDINGS_SYNC_INTERVAL_HOURS` / `EMBEDDINGS_MAX_PER_RUN` | Embeddings backfill cadence / per-run cap | `6` / `2000` |
| `LLM_PRODUCT_EXTRACTION_ENABLED` | Fill empty `affected_products` for NVD-unanalyzed CVEs via Groq (requires `GROQ_API_KEY`; provenance-marked, superseded by official CPE) | `0` |
| `LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS` / `LLM_PRODUCT_EXTRACTION_MAX_PER_RUN` | Extraction job cadence / Groq calls per run | `6` / `25` |

---

## API Reference

Full endpoint catalog: [`API_REFERENCE.md`](API_REFERENCE.md)  
Interactive docs: `http://localhost:8000/api/docs` (Swagger — **disable in production**)

### Core endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | CVE count, ingest status, next refresh times |
| `GET /api/stats` | Critical/high/KEV/patched/24h counts |
| `GET /api/stats/timeline` | Daily CVE publication heatmap (90-day `TimelineHeatmap.jsx`) |
| `GET /api/changes` | Recent CVE field deltas (What changed panel + EPSS movers table) |
| `GET /api/cves` | Paginated CVE list (`page`, `limit` max **50**, filters) |
| `GET /api/cves/{cve_id}` | CVE detail + live enrichment |
| `GET /api/cves/{cve_id}/sentences` | Human-readable intel sentences |
| `GET /api/cves/{cve_id}/epss-history` | EPSS sparkline data (30 days) |
| `GET /api/cves/{cve_id}/momentum` | Momentum score + signals |
| `GET /api/cves/{cve_id}/correlation` | Infrastructure / actor / temporal correlation |
| `GET /api/cves/{cve_id}/detection` | Sigma, Elastic, SIEM queries |
| `GET /api/cves/{cve_id}/related` | Related CVEs (same-product heuristic; semantic similarity when `EMBEDDINGS_ENABLED=1`) |
| `POST /api/cves/match` | Asset CPE exposure scores |
| `POST /api/ioc/lookup` | IOC enrichment (ip, hash, domain) |
| `GET /api/kev/deadlines` | KEV remediation deadlines |
| `GET /api/techniques/top` | Top ATT&CK techniques by CVE count |
| `GET /api/atlas/techniques` | ATLAS techniques grouped by tactic |
| `GET /api/atlas/casestudies` | ATLAS case studies |
| `GET /api/case-studies/feed` | Combined RSS news + ATLAS case studies (Incidents tab) |
| `GET /api/case-studies/news` | RSS news only |
| `POST /api/ai/summary` | AI executive summary (PDF export only) |
| `GET /api/usage` / `GET /api/usage/ioc` | API quota counters |
| `GET /api/version` | Deployed version + commit (stamped at deploy) |

**Note:** `POST /api/investigation/summary` is a legacy alias for the investigation PDF summary pipeline; prefer `POST /api/ai/summary` for new integrations.

---

## Documentation

**Start here:** [`docs/index.md`](docs/index.md) — four guides, pick one.

| I want to… | Doc |
|------------|-----|
| Self-host | [`docs/SELF_HOST.md`](docs/SELF_HOST.md) |
| Use the product | [`docs/USE.md`](docs/USE.md) |
| Fix a problem | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand internals | [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) |
| Develop | [`docs/ONBOARDING.md`](docs/ONBOARDING.md) |

Diagram prompts (maintainers): [`docs/IMAGE_BRIEFS.md`](docs/IMAGE_BRIEFS.md)

Regenerate `SYSTEM_DESIGN.pdf` (requires network for Mermaid CDN on first run):

```bash
cd frontend && npm install
node ../scripts/generate_system_design_pdf.mjs
```

Regenerate screenshots (backend on `:8000`, frontend on `:5173`):

```bash
# 1) Seed sample CVE rows and warm RSS caches (skip CVE seed when 10+ rows exist)
python3 scripts/seed_screenshot_data.py

# 2) Start backend + frontend, then capture (requires network for live RSS)
cd frontend && npm install playwright --save-dev
npx playwright install chromium
node ../scripts/capture_readme_screenshots.mjs
```

Screenshots use **live RSS headlines** and a **seeded CVE database** so tabs show realistic data (not empty placeholders). The capture script preflights `/api/health` and `/api/case-studies/feed`, rejects `database is locked` feed errors, and requires CVE cards plus RSS news badges before writing images.

It captures the **viewport only** (1440×900) so the BRIEF feed’s infinite scroll does not produce an overly tall image. **Exits with code 1** on missing data, feed errors, or failed selectors (no silent blank captures).

Regenerate the technical inventory spreadsheet:

```bash
pip install openpyxl
python3 scripts/generate_technical_inventory_xlsx.py
```

Writes `TECHNICAL_INVENTORY.xlsx` with auto-sized columns (minimum width 10).

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus CVE search |
| `F` | Cycle filters (KEV → Critical → PoC → all) |
| `g` then `d` | Open digest for selected CVEs |
| `Esc` | Close drawer, digest, or About modal |
| `↑` `↓` | Navigate CVE cards |
| `Enter` | Open highlighted CVE |
| `C` | Copy CVE markdown (drawer open) |

---

## Privacy

BRIEFR collects no personal data, uses no cookies, and runs no analytics. Tech stack and timezone preferences are stored in your browser's `localStorage` only. IOC lookups are sent to configured third-party APIs; results are cached in your PostgreSQL database (6 hours for IOC, various TTLs for feed cache). See [`frontend/src/pages/PrivacyPage.jsx`](frontend/src/pages/PrivacyPage.jsx) or `/privacy` in the app.

---

## Known limitations (v1.1 beta)

- Single-node PostgreSQL — not designed for concurrent multi-tenant writes at scale without connection pooling tuning
- No app-level authentication yet — built-in app login ships before the public self-hosted release; until then `BRIEFR_ADMIN_API_KEY` optionally gates `POST /api/refresh*`
- Risk score v1.1b is computed server-side via `POST /api/cves/{cve_id}/risk` (`backend/scoring/risk.py`); weights for formula display are fetched at startup via `GET /api/config/risk` (`frontend/src/scoring/riskScore.js`)
- AI/ML alerts chip requires AI/ML keywords in your saved stack or asset profile `aiSystems`

---

## License

BRIEFR is currently proprietary software.

Copyright © 2026 Sai Harsha Vardhan.

All rights reserved.

Source code is not licensed for redistribution, modification, or commercial use. See [`LICENSE`](LICENSE).

---

<p align="left">
  <strong>Built by</strong> Sai Harsha Vardhan<br/>
  <a href="https://www.linkedin.com/in/sai-harsha-vardhan/">LinkedIn</a>
</p>
