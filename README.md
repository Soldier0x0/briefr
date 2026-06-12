
# BRIEFR
### CVE Intelligence & Threat Investigation for Security Analysts

![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![React 18](https://img.shields.io/badge/React-18.3-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green.svg)

BRIEFR is a self-hosted CVE intelligence dashboard for security analysts, small teams, and solo researchers. It aggregates NVD, CISA KEV, EPSS, MITRE ATT&CK, MITRE ATLAS, and optional threat-feed enrichment into one searchable UI — with IOC lookup, correlation, detection engineering helpers, and PDF export.

**Live demo:** [briefr.projectjupiter.in](https://briefr.projectjupiter.in)

---

## Screenshots

### BRIEF — CVE feed, heatmap, KEV sidebar

![BRIEF tab — CVE intelligence feed](screenshots/brief.png)

### IOC LOOKUP — multi-source indicator enrichment

![IOC Lookup tab](screenshots/ioc-lookup.png)

### INCIDENTS & NEWS — RSS security news + MITRE ATLAS case studies

![Incidents and News tab](screenshots/incidents-news.png)

---

## What is BRIEFR?

Every morning, analysts check NVD, CISA KEV, VirusTotal, and exploit trackers to answer one question: *what broke overnight and does it affect us?* BRIEFR automates that aggregation into a single self-hosted app. No account, no cookies, no analytics — your SQLite database and API keys stay on your server.

Three main tabs:

| Tab | What it does |
|-----|----------------|
| **BRIEF** | Paginated CVE feed with CVSS, EPSS, KEV flags, stack filtering, timeline heatmap, detail drawer |
| **IOC LOOKUP** | IP / hash / domain enrichment via VirusTotal, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus |
| **INCIDENTS & NEWS** | Security RSS feeds (6 sources) plus MITRE ATLAS incident narratives |

---

## Features

**Vulnerability intelligence**
- NVD incremental ingest with CVSS v3.1, EPSS, CISA KEV, and change tracking
- CVE detail enrichment: Sploitus exploits, GreyNoise scans, OTX pulses, OSV packages, CIRCL references
- MITRE ATT&CK technique mapping and top-technique sidebar
- MITRE ATLAS AI/ML threat context (weekly refresh; per-CVE drawer + Incidents tab)
- 90-day publication timeline heatmap
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
- Dark mode default with light mode toggle
- Timezone selector (stored in `localStorage`)
- Keyboard shortcuts (`/`, `F`, `Esc`, `g d` digest, arrow keys in feed)
- Session-only investigation thread; stack filter persisted locally

---

## Tech Stack

| Backend | Frontend |
|---------|----------|
| FastAPI 0.136.3 | React 18.3.1 |
| Uvicorn 0.48.0 | React Router 7.16.0 |
| httpx 0.28.1 | Vite 5.4.1 |
| APScheduler 3.11.2 | ExcelJS 4.4.0 |
| aiosqlite 0.22.1 | jsPDF 4.2.1 + html2canvas |
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
| CIRCL (vulnerability.circl.lu) | Extended CVE references + CAPEC | On CVE detail / ingest (7d cache, 24h negative cache) | `CIRCL_API_KEY` optional |
| Groq / Anthropic | PDF executive summary | On PDF export only | `POST /api/ai/summary` |
| GitHub | Sigma + Elastic rule search | On Detect tab open | `GITHUB_TOKEN` optional |
| RSS × 6 | Security news cards | Snapshot every 30 min (`INCIDENT_FEED_REFRESH_MINUTES`) | `GET /api/case-studies/feed` |

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

BRIEFR backs up the SQLite database and `.env` to **`/var/lib/briefr/backups`** (outside the git tree):

| Mechanism | Schedule | Notes |
|-----------|----------|-------|
| `briefr-backup.timer` | Every **6 hours** | systemd oneshot; integrity-checked before write |
| `briefr-update.sh` | Before each deploy | Labelled `pre-update` in the manifest |
| Startup | On backend boot | If `briefr.db` fails `PRAGMA integrity_check`, restores the newest valid archive |

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

Recent field changes: `GET /api/changes?since_hours=24`

Check coverage:

```bash
sqlite3 backend/briefr.db \
  "SELECT COUNT(*) AS total, SUM(epss_score IS NOT NULL) AS with_epss FROM cves;"
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
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | PDF AI summary | — |
| `GITHUB_TOKEN` | Detection rule search rate limit | — |
| `CIRCL_API_KEY` | vulnerability.circl.lu authenticated rate limits | — |
| `BRIEFR_ENV` | `production` disables Swagger/OpenAPI docs | `development` |
| `BRIEFR_ADMIN_API_KEY` | Optional `X-BRIEFR-Admin-Key` gate for `POST /api/refresh*` | — |
| `RATE_LIMIT_ENABLED` | Token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` | `1` |
| `RATE_LIMIT_IOC_PER_MINUTE` / `RATE_LIMIT_REFRESH_PER_MINUTE` | Per-client-IP budgets (429 + `Retry-After` over the limit) | `30` / `10` |
| `LOG_FORMAT` | `json` structured logs with `request_id`, or `plain` | `json` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `DB_PATH` | SQLite file | `briefr.db` |
| `BACKUP_DIR` | Backup archive directory | `/var/lib/briefr/backups` |
| `BACKUP_RETENTION_COUNT` | Max `briefr-*.tar.gz[.age]` archives kept | `100` |
| `BACKUP_ENABLED` | Enable backups + startup auto-restore | `1` |
| `BACKUP_AGE_KEY_FILE` | age identity for archive encryption (outside `BACKUP_DIR`; `""` disables) | `/var/lib/briefr/keys/backup-age.key` if present |
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
| `GET /api/stats/timeline` | Daily CVE publication heatmap data |
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

| Document | Contents |
|----------|----------|
| [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | **Start here** — reading order, local dev, tests, env vars, troubleshooting |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | **Release index** — V1.2 foundation through V2.0 platform |
| [`docs/JUPITER_VISION.md`](docs/JUPITER_VISION.md) | Jupiter project vision, beast pillars, optional ClickStack |
| [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) | Architecture, data flows, design decisions |
| [`Beta V1.2.md`](Beta%20V1.2.md) | Current release — refactor, auth, resilience |
| [`Beta V1.3.md`](Beta%20V1.3.md) | Analyst beast — brief, charts, Forge MVP |
| [`Beta V1.4.md`](Beta%20V1.4.md) | Operator beast — admin pane, webhooks, wallboard |
| [`Beta V1.5.md`](Beta%20V1.5.md) | Threat model UI, rule proof, KEV backlog |
| [`Beta V2.0.md`](Beta%20V2.0.md) | Docker, optional Postgres, multi-user readiness |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Backup, logs, container seams, deploy compatibility |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Application threat model (security design) |
| [`API_REFERENCE.md`](API_REFERENCE.md) | Every endpoint with params and response shapes |
| [`TECHNICAL_INVENTORY.md`](TECHNICAL_INVENTORY.md) | Schema, scheduler jobs, external APIs, feature matrix |
| [`APPLICATION_EXECUTION_MAP.md`](APPLICATION_EXECUTION_MAP.md) | Startup sequence and request journeys |
| [`FOLDER_STRUCTURE_GUIDE.md`](FOLDER_STRUCTURE_GUIDE.md) | File-by-file map with deprecation tags |
| [`docs/diagrams/`](docs/diagrams/) | Mermaid architecture and flow diagrams |
| [`SYSTEM_DESIGN.pdf`](SYSTEM_DESIGN.pdf) | Printable system design (generated from markdown) |

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

BRIEFR collects no personal data, uses no cookies, and runs no analytics. Tech stack and timezone preferences are stored in your browser's `localStorage` only. IOC lookups are sent to configured third-party APIs; results are cached in your server's SQLite database (6 hours for IOC, various TTLs for feed cache). See [`frontend/src/pages/PrivacyPage.jsx`](frontend/src/pages/PrivacyPage.jsx) or `/privacy` in the app.

---

## Known limitations (v1.1 beta)

- Single-user SQLite — not designed for concurrent multi-tenant writes
- No app-level authentication yet — built-in app login ships before the public self-hosted release; until then `BRIEFR_ADMIN_API_KEY` optionally gates `POST /api/refresh*`
- Risk weights duplicated in Python (`backend/scoring/risk.py`) and JavaScript (`frontend/src/scoring/riskScore.js`) — shared config planned for Beta V1.2
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
