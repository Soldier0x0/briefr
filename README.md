
<p align="center">
  <img src="docs/assets/production-architecture.svg" alt="BRIEFR architecture" width="720"/>
</p>

<h1 align="center">BRIEFR</h1>
<p align="center"><strong>CVE Intelligence &amp; Threat Investigation for Security Analysts</strong></p>

<p align="center">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-blue.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.139-009688.svg">
  <img alt="React 19" src="https://img.shields.io/badge/React-19.2-61DAFB.svg?logo=react&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white">
  <img alt="Self-hosted" src="https://img.shields.io/badge/Self--hosted-yes-success.svg">
  <img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

<p align="center">
  <a href="#what-is-briefr">What is it</a> ·
  <a href="#features">Features</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#api-reference">API</a> ·
  <a href="#license">License</a>
</p>

BRIEFR is a self-hosted CVE intelligence dashboard for security analysts, small teams, and solo researchers. It aggregates NVD, CISA KEV, EPSS, MITRE ATT&CK, MITRE ATLAS, and optional threat-feed enrichment into one searchable UI — with IOC lookup, explainable correlation, detection-engineering helpers, and PDF export.

**Live demo:** [briefr.projectjupiter.in](https://briefr.projectjupiter.in)

BRIEFR is open-source software under the **Apache License 2.0** — clone it, self-host it, modify it, and use it commercially with attribution (see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)). You bring your own API keys for intel feeds (NVD, OTX, VirusTotal, and others). See [Contributing](CONTRIBUTING.md) if you want to send a PR.

---

## Screenshots

Committed UI screenshots are not in this tree yet. Maintainers can use [`docs/IMAGE_BRIEFS.md`](docs/IMAGE_BRIEFS.md) and `scripts/capture_readme_screenshots.mjs` to regenerate reader-facing captures when the app is running with seeded data.

---

## What is BRIEFR?

Every morning, analysts check NVD, CISA KEV, VirusTotal, and exploit trackers to answer one question: *what broke overnight and does it affect us?* BRIEFR automates that aggregation into a single self-hosted app. Built-in login with httpOnly session cookies; no third-party analytics — your database and API keys stay on your server.

Five main areas:

| URL tab | Header label | What it does |
|---------|--------------|--------------|
| `brief` | **BRIEF** | Morning brief action queue, Recharts panels, 90-day heatmap, OP/Threat-ranked tiles |
| `feed` | **FEED** | Paginated CVE list, stack filter/backfill banner, KEV deadlines, export, hybrid search |
| `ioc` | **IOC LOOKUP** | IP / hash / domain enrichment via VirusTotal, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus |
| `atlas` | **INCIDENTS & NEWS** | Security RSS feeds (5 sources) plus MITRE ATLAS incident narratives |
| `forge` | **FORGE** | ATT&CK navigator, threat scenarios, campaigns, backlog, hunt-pack library |

---

## Architecture, at a glance

One FastAPI process, one database, a scheduler that does all the heavy lifting so the API stays fast. The picture at the top of this README is the real shape of it — for the full story (why it's built this way, not just what it is), see:

- [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) — the short version, with diagrams
- [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) — the reference architecture essay
- [docs.projectjupiter.in](https://docs.projectjupiter.in) — public docs portal (Pathways, guides, API reference)

---

## Features

**Vulnerability intelligence**
- NVD incremental ingest with CVSS v3.1, EPSS, CISA KEV, and change tracking
- CVE detail enrichment: Sploitus exploits, GreyNoise scans, OTX pulses, OSV packages, CIRCL references
- MITRE ATT&CK technique mapping and top-technique sidebar
- MITRE ATLAS AI/ML threat context (weekly refresh; per-CVE drawer + Incidents tab)
- 90-day publication timeline heatmap beside the **What changed** panel on wide screens (≥901px); stacked on narrower viewports
- Server-side **Risk Score v1.1b** plus split Threat Score / Environment Relevance / Operational Priority via `POST /api/cves/{cve_id}/risk`

**Threat investigation**
- Investigation panel with cross-tab pivots (CVE → IOC → ATLAS / Forge / related CVE)
- Explainable correlation engine (shared OTX infrastructure, actor/sector match, temporal vendor anomalies, campaign clustering) — no black-box ML score
- Detection tab and Forge: **local SigmaHQ Postgres index** (CVE-exact, DRL-1.1) with GitHub Sigma/Elastic fallback when the index is empty; generated Sigma hunt starters only when no community rule matches
- Asset profile wizard with CPE-based exposure matching (`POST /api/cves/match` only — inventory never stored server-side)

**IOC enrichment**
- Cached lookups (6 hours; GreyNoise 1 hour)
- Live API quota display per service
- Optional GreyNoise opt-in per lookup (weekly free-tier limit)

**Export & reporting**
- CSV and Excel export from the feed
- Single-CVE and bulk PDF reports (jsPDF + optional AI executive summary, always with a deterministic template fallback)
- Markdown copy from the detail drawer
- Timezone-aware timestamps

**User experience**
- Dark terminal aesthetic (semantic design tokens, Radix UI primitives — see ADR-003/ADR-005)
- Timezone selector (server-persisted per user)
- Keyboard shortcuts (`/`, `F`, `Esc`, `g d` digest, arrow keys in feed)
- Tab panels stay mounted when switching BRIEF / FEED / IOC / ATLAS / Forge (scroll and filter state preserved)
- CVE detail drawer slides over content, keeps drawer tabs mounted after visit, and syncs open state to `?cve=`
- Session-only investigation thread; stack filter persisted server-side

---

## Tech Stack

| Backend | Frontend |
|---------|----------|
| FastAPI 0.139 · Uvicorn 0.51 (single worker, by design) | React 19.2 · React Router 7.18 |
| httpx 0.28 · APScheduler 3.11 | Vite 8.1 |
| asyncpg 0.31 + psycopg 3.3 (Alembic migrations) | Radix UI primitives + semantic CSS tokens (no Tailwind) |
| Pydantic 2.13 · Procrastinate (durable jobs) | Recharts via shared `ChartShell` · TanStack Table |
| bcrypt + PyJWT (built-in auth) | jsPDF + html2canvas (client-side PDF) · write-excel-file |
| fastembed / ONNX (local CPU embeddings, optional) | `node:test` (unit) + Playwright (E2E) |

**Database:** PostgreSQL 16 in production (required); use a pgvector-enabled Postgres image for embeddings. SQLite is the zero-config dev/test fallback only — see [`docs/POSTGRES.md`](docs/POSTGRES.md).

> **Note — PostgreSQL vs SQLite**
>
> | | |
> |---|---|
> | **Why SQLite existed** | Early on, while BRIEFR was still a simple CVE reader during testing, I used SQLite — single file, zero setup. |
> | **Why I pivoted to Postgres** | As the tool matured (correlation, scheduled ingest, embeddings, overlapping API + scheduler traffic), parallel reads and writes became a bottleneck. **PostgreSQL 16 (+ pgvector)** is what I run in production. |
> | **What ships on `main` today** | Production expects Postgres. The repo still carries a **SQLite dev/test fallback** (omit `DATABASE_URL`) — on real Postgres hosts those paths are largely dormant. |
> | **Open PR [#752](https://github.com/Soldier0x0/briefr/pull/752)** | I have a draft to remove the SQLite fallback entirely. **It is not merged to `main`.** I will merge it only after I have validated it against existing Postgres installs — **nothing changes for production until then.** |

**LLM enrichment (all optional, all free/cheap-tier, none load-bearing):** Groq → Cerebras → OpenRouter → Gemini, in that fixed failover order. Every LLM-backed feature (PDF summaries, product extraction, detection-context artifacts) has a deterministic non-LLM fallback — BRIEFR is fully functional with zero LLM keys configured.

---

<details>
<summary><strong>Data Sources</strong> (click to expand — 19 external feeds)</summary>

BRIEFR incorporates publicly available intelligence from NVD, CISA KEV, FIRST EPSS, MITRE ATT&CK, MITRE ATLAS, OTX, VirusTotal, AbuseIPDB, GreyNoise, abuse.ch, and the additional feeds below. All trademarks, service marks, logos, and data rights remain the property of their respective owners.

| Source | Data | Refresh | API / trigger |
|--------|------|---------|---------------|
| NVD (NIST) | CVE records, CVSS, CPE | Every `NVD_SYNC_INTERVAL_HOURS` (default 1h) | `POST /api/refresh/nvd` |
| CISA KEV | Known exploited vulns + deadlines | Every `KEV_SYNC_INTERVAL_MINUTES` (default 15m) | `POST /api/refresh/kev` |
| FIRST EPSS | Exploit probability scores | Every `EPSS_SYNC_INTERVAL_HOURS` (default 6h) | `POST /api/refresh/epss` |
| cvelistV5 (MITRE/CVE Project) | CVE JSON 5.x records + ADP containers, often hours before NVD | Every `CVELISTV5_SYNC_INTERVAL_MINUTES` (default 30m) | Scheduler only (git-SHA watermark) |
| CISA Vulnrichment | SSVC / CVSS / CWE / CPE gap-fill before NVD analysis | Every `VULNRICHMENT_SYNC_INTERVAL_HOURS` (default 6h) | Scheduler only |
| MITRE ATT&CK | Techniques, groups, CVE mappings | Weekly (Sunday cron) | `POST /api/refresh/mitre` |
| MITRE ATLAS | AI/ML techniques + case studies | Weekly (with MITRE job) | `POST /api/refresh/mitre` |
| OTX (AlienVault) | Campaign pulses + IOCs | Nightly job + continuous budget-paced sync | `OTX_API_KEY` |
| SigmaHQ | Community Sigma rules (local Postgres mirror) | Weekly `sigmahq_index_sync` + Admin Force re-sync | optional `GITHUB_TOKEN` (rate limits) |
| ThreatFox (abuse.ch) | Bulk IOC mirror | Scheduler (7-day rolling window) | — |
| VirusTotal | IOC reputation | On demand (6h cache) | `POST /api/ioc/lookup` |
| AbuseIPDB | IP abuse score | On demand (6h cache) | `POST /api/ioc/lookup` |
| GreyNoise | IP classification + CVE scan context | On demand (opt-in) | IOC + CVE detail |
| abuse.ch (MalwareBazaar / URLhaus) | Hash / domain malware context | On demand | `ABUSECH_AUTH_KEY` |
| OSV.dev | Affected packages | On CVE detail view | — |
| Sploitus | Public exploits | On CVE detail / ingest enrichment | — |
| PoC-in-GitHub | GitHub PoC index (git-SHA watermark) | Scheduler (`exploit_sources_sync`) | `GITHUB_TOKEN` optional |
| ExploitDB / Metasploit / Nuclei | Public exploit + template indexes | Scheduler (`exploit_sources_sync`) | — |
| CIRCL (vulnerability.circl.lu) | Extended CVE references + CAPEC | On CVE detail / ingest (7d cache, 24h negative cache) | `CIRCL_API_KEY` optional |
| VulnCheck | Community KEV supplement | Scheduler | `VULNCHECK_API_KEY` optional |
| Groq / Cerebras / OpenRouter / Gemini | PDF executive summary, product extraction, detection-context artifacts | On demand / scheduler | see LLM keys below |
| GitHub | Sigma/Elastic community rule search; SigmaHQ tarball tip resolve | Detect tab + weekly SigmaHQ sync | `GITHUB_TOKEN` optional |
| RSS × 5 | Security news cards (The Hacker News, Krebs, Dark Reading, Schneier, CISA Advisories) | Snapshot every 30 min (`INCIDENT_FEED_REFRESH_MINUTES`) | `GET /api/case-studies/feed` |

</details>

---

## Getting Started

**Full step-by-step install (all paths):** [`docs/SELF_HOST.md`](docs/SELF_HOST.md) — authoritative; includes Postgres + pgvector linking, verification checklist, and where to look.

### Choose your install path

| Goal | Guide | Summary |
|------|-------|---------|
| **Try locally** (fastest) | [SELF_HOST §1](docs/SELF_HOST.md#1-quick-local-development-sqlite) | SQLite fallback — no Docker |
| **Develop with Postgres + pgvector** | [SELF_HOST §2](docs/SELF_HOST.md#2-local-development-with-postgresql--pgvector) | `docker compose -f deploy/docker-compose.postgres.yml up -d` + `DATABASE_URL` in `.env` |
| **Production server** | [SELF_HOST §3](docs/SELF_HOST.md#3-production-debian--systemd--nginx) | `deploy/setup.sh` + Postgres 16 (`pgvector/pgvector:pg16`) |
| **Postgres / backups / pgvector cutover** | [`docs/POSTGRES.md`](docs/POSTGRES.md) | Deep database ops |
| **Change the code** | [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | Tests, env vars, subsystems |

### Prerequisites

- Python 3.11+
- Node.js 18+
- **Production / serious dev:** PostgreSQL 16 with **pgvector** (`pgvector/pgvector:pg16` — plain `postgres:16` lacks the `vector` extension)
- Recommended API keys: [NVD](https://nvd.nist.gov/developers/request-an-api-key), [VirusTotal](https://www.virustotal.com/gui/join-us), [AbuseIPDB](https://www.abuseipdb.com/register)
- Optional: GreyNoise, OTX, Abuse.ch, Groq/Cerebras/OpenRouter/Gemini, GitHub token — see `backend/.env.example`

### Quick local install (SQLite)

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # optional API keys

uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
cd ../frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api → :8000
```

Open http://localhost:5173 → complete **first-run setup** to create the admin user.

### Postgres + pgvector (dev or production)

> **Use Postgres for production.** See the **PostgreSQL vs SQLite** table under [Tech Stack → Database](#tech-stack) for why I pivoted away from SQLite and why [PR #752](https://github.com/Soldier0x0/briefr/pull/752) (SQLite removal) is still open.

1. Start Postgres: `docker compose -f deploy/docker-compose.postgres.yml up -d` (image: `pgvector/pgvector:pg16`)
2. Link in `backend/.env`:

```bash
DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr
BRIEFR_REQUIRE_POSTGRES=1
```

3. Start backend — **Alembic migrations run automatically** on startup (`alembic upgrade head`)

Full linking steps, port `:5433` disposable Postgres, external DB, and embeddings flags: [`docs/SELF_HOST.md` §2](docs/SELF_HOST.md#2-local-development-with-postgresql--pgvector) and [`docs/POSTGRES.md`](docs/POSTGRES.md).

### Verify install

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

| Check | Dev (SQLite) | Dev / prod (Postgres) |
|-------|--------------|------------------------|
| `"backend"` | `"sqlite"` | `"postgresql"` |
| UI | `:5173` loads, setup or login | same |
| pgvector (optional) | n/a | `psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname='vector';"` |

On first start with fewer than 10 CVEs, the backend automatically runs a full ingest (NVD → KEV → EPSS). Optional seed: `python scripts/seed_screenshot_data.py`.

### Production deploy

```bash
bash deploy/setup.sh          # initial install (git clone) — internet-connected only
bash deploy/briefr-update.sh  # git pull + build + restart (legacy / dev boxes)
```

**Production zone** (no git pull — artifact/rsync): `briefr-install.sh` (first time) → `briefr-deploy.sh` (releases) → `briefr-service.sh` (restart). See [`docs/SELF_HOST.md` §3](docs/SELF_HOST.md#3-production-debian--systemd--nginx).

**Maintainer note (not a BRIEFR requirement):** For my own public demo I put edge access control in front of the host using [Cloudflare Zero Trust](https://www.cloudflare.com/products/zero-trust/) (free tier) with DNS on Cloudflare. That is a personal security choice for domain-fronted access — not part of the app, not required to run BRIEFR, and not the only way to expose a self-hosted instance. If your domain’s DNS is already on Cloudflare, it is one convenient option among many.

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

Requires `DATABASE_URL` and host `postgresql-client` (match your Postgres major — **16** in production; see [`docs/POSTGRES.md`](docs/POSTGRES.md)).

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

---

<details>
<summary><strong>Environment Variables</strong> (click to expand — full reference; see also <code>backend/.env.example</code>)</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL DSN — omit for a zero-config local SQLite fallback | SQLite dev fallback |
| `BRIEFR_REQUIRE_POSTGRES` | Refuse startup unless `DATABASE_URL` is a real `postgresql://` DSN (set `1` in production) | `0` |
| `DATABASE_POOL_SIZE` | asyncpg connection pool size | `10` |
| `JWT_SECRET` | Session signing secret — **required** in production, auto-generated in dev | — |
| `NVD_API_KEY` | NVD rate-limit key (recommended) | — |
| `VIRUSTOTAL_API_KEY` | IOC lookups | — |
| `ABUSEIPDB_API_KEY` | IP reputation | — |
| `GREYNOISE_API_KEY` | IP context (50/week free) | — |
| `ABUSECH_AUTH_KEY` | MalwareBazaar + URLhaus + ThreatFox | — |
| `OTX_API_KEY` | OTX pulses + correlation | — |
| `GITHUB_TOKEN` | SigmaHQ index sync + detection rule search + PoC-GitHub rate limit | — |
| `CIRCL_API_KEY` | vulnerability.circl.lu authenticated rate limits | — |
| `VULNCHECK_API_KEY` | VulnCheck community KEV supplement | — |
| `GROQ_API_KEY` | LLM chain, tried first (product extraction, detection-context, PDF summaries) | — |
| `CEREBRAS_API_KEY` | LLM chain, second | — |
| `OPENROUTER_API_KEY` | LLM chain, third (`:free` tier models) | — |
| `GEMINI_API_KEY` | LLM chain, last resort | — |
| `EMBEDDINGS_ENABLED` | Semantic "similar CVEs" via local CPU embeddings (`pip install fastembed`; off = shared-product heuristic) | `0` |
| `EMBEDDINGS_MODEL` | Local embedding model (ONNX, CPU-only) | `BAAI/bge-small-en-v1.5` |
| `EMBEDDINGS_PGVECTOR` | Store embeddings in Postgres pgvector when the extension exists | `1` |
| `LLM_PRODUCT_EXTRACTION_ENABLED` | Fill empty `affected_products` for NVD-unanalyzed CVEs via the LLM chain (provenance-marked, superseded by official CPE) | `0` |
| `DETECTION_CONTEXT_LLM_ENABLED` | LLM-based detection-artifact extraction (Nuclei-based extraction runs regardless, on by default) | `0` |
| `SIGMAHQ_INDEX_SYNC_ENABLED` | Weekly mirror of SigmaHQ rules into Postgres (`detection_rules*`) | `1` |
| `SIGMAHQ_INDEX_SYNC_INTERVAL_HOURS` | SigmaHQ sync cadence | `168` |
| `BRIEFR_ENV` | `production` disables Swagger/OpenAPI docs | `development` |
| `RATE_LIMIT_ENABLED` | Token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` + login | `1` |
| `RATE_LIMIT_IOC_PER_MINUTE` / `RATE_LIMIT_REFRESH_PER_MINUTE` | Per-client-IP budgets (429 + `Retry-After` over the limit) | `30` / `10` |
| `RATE_LIMIT_WALLBOARD_PER_MINUTE` | Per-client-IP budget for `GET /api/wallboard` | `60` |
| `BRIEFR_RATE_LIMIT_STORE` | `db` shares rate-limit buckets across workers via `sync_state` (only needed if you ever run more than 1 worker) | in-memory |
| `PROCRASTINATE_ENABLED` | Enable PostgreSQL-backed durable jobs for restart-safe outbound work | `0` |
| `WALLBOARD_TOKEN` | Optional read-only gate for `GET /api/wallboard` + `/wallboard` UI | — |
| `LOG_FORMAT` | `json` structured logs with `request_id`, or `plain` | `json` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `BACKUP_DIR` | Backup archive directory | `/var/lib/briefr/backups` |
| `BACKUP_RETENTION_COUNT` | Max `briefr-*.tar.gz[.age]` archives kept | `100` |
| `BACKUP_ENABLED` | Enable backups + startup auto-restore | `1` |
| `BACKUP_AGE_KEY_FILE` | age identity for archive encryption (outside `BACKUP_DIR`; `""` disables) | `/var/lib/briefr/keys/backup-age.key` if present |
| `BACKUP_INTERVAL_HOURS` | Expected backup cadence (dead-man alert threshold = 2× this) | `6` |
| `DISCORD_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` / `WEBHOOK_GENERIC_URL` | Alert destinations (KEV-on-stack, backup dead-man, etc.), all SSRF-protected | — |
| `BRIEFR_STACK_TERMS` | Comma-separated stack for server-side KEV-on-stack matching | — |
| `NVD_SYNC_INTERVAL_HOURS` / `KEV_SYNC_INTERVAL_MINUTES` / `EPSS_SYNC_INTERVAL_HOURS` | Feed sync cadences | `1` / `15` / `6` |
| `SCHEDULER_TIMEZONE` | APScheduler TZ | `Asia/Kolkata` |
| `MAX_CVES_PER_FETCH` | Cap per NVD sync | `2000` |

</details>

---

## API Reference

Full endpoint catalog: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)
Interactive docs: `http://localhost:8000/api/docs` (Swagger — **disable in production**)

<details>
<summary><strong>Core endpoints</strong> (click to expand)</summary>

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | CVE count, ingest status, next refresh times |
| `GET /api/stats` | Critical/high/KEV/patched/24h counts |
| `GET /api/stats/timeline` | Daily CVE publication heatmap (90-day) |
| `GET /api/changes` | Recent CVE field deltas (What changed panel + EPSS movers table) |
| `GET /api/cves` | Paginated CVE list (`page`, `limit` max **50**, filters, keyset pagination available) |
| `GET /api/cves/{cve_id}` | CVE detail + live enrichment |
| `GET /api/cves/{cve_id}/sentences` | Human-readable intel sentences (template-based, no LLM) |
| `GET /api/cves/{cve_id}/epss-history` | EPSS sparkline data (30 days) |
| `GET /api/cves/{cve_id}/momentum` | Momentum score + signals |
| `POST /api/cves/{cve_id}/risk` | Risk Score v1.1b + split Threat/Environment/Priority |
| `GET /api/cves/{cve_id}/correlation` | Campaign / infrastructure / actor / temporal correlation |
| `GET /api/correlation/clusters` | Stack-ranked campaign cluster list |
| `GET /api/cves/{cve_id}/detection` | Sigma, Elastic, SIEM queries, YARA |
| `GET /api/cves/{cve_id}/related` | Related CVEs (product heuristic; semantic similarity when `EMBEDDINGS_ENABLED=1`) |
| `GET /api/search/semantic` | Hybrid keyword + vector search across CVEs/techniques/campaigns |
| `POST /api/cves/match` | Asset CPE exposure scores |
| `POST /api/ioc/lookup` | IOC enrichment (ip, hash, domain) |
| `GET /api/kev/deadlines` | KEV remediation deadlines |
| `GET /api/techniques/top` | Top ATT&CK techniques by CVE count |
| `GET /api/atlas/techniques` / `GET /api/atlas/casestudies` | ATLAS techniques and case studies |
| `GET /api/case-studies/feed` | Combined RSS news + ATLAS case studies (Incidents tab) |
| `GET /api/brief` | Morning brief action queue |
| `POST /api/ai/summary` | AI executive summary (PDF export only; template fallback always available) |
| `GET /api/usage` / `GET /api/usage/ioc` | API quota counters |
| `GET /api/version` | Deployed version + commit (stamped at deploy) |

</details>

---

## Documentation

**Start here:** [`docs/index.md`](docs/index.md) — pick one guide, most people need exactly one.

| I want to… | Doc |
|------------|-----|
| **Install** (SQLite, Postgres+pgvector, production) | [`docs/SELF_HOST.md`](docs/SELF_HOST.md) |
| Postgres / pgvector / backups | [`docs/POSTGRES.md`](docs/POSTGRES.md) |
| Use the product | [`docs/USE.md`](docs/USE.md) |
| Fix a problem | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand internals (short version) | [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) |
| **Learn architecture (guided paths)** | [docs.projectjupiter.in](https://docs.projectjupiter.in) |
| Develop / contribute | [`docs/ONBOARDING.md`](docs/ONBOARDING.md) + [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| See what's actually shipped today | [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) |

Diagram prompts (maintainers): [`docs/IMAGE_BRIEFS.md`](docs/IMAGE_BRIEFS.md)

<details>
<summary>Regenerating diagrams, screenshots, and the technical inventory</summary>

Generate `SYSTEM_DESIGN.pdf` on demand — it is not committed (requires network for Mermaid CDN on first run):

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

Screenshots use **live RSS headlines** and a **seeded CVE database** so tabs show realistic data (not empty placeholders). The capture script preflights `/api/health` and `/api/case-studies/feed`, rejects `database is locked` feed errors, and requires CVE cards plus RSS news badges before writing images. It captures the **viewport only** (1440×900) so the BRIEF feed's infinite scroll does not produce an overly tall image, and **exits with code 1** on missing data, feed errors, or failed selectors (no silent blank captures).

Regenerate the technical inventory spreadsheet:

```bash
pip install openpyxl
python3 scripts/generate_technical_inventory_xlsx.py
```

Writes `TECHNICAL_INVENTORY.xlsx` locally (not committed) with auto-sized columns (minimum width 10).

</details>

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

BRIEFR collects no personal data beyond your self-hosted login account, uses httpOnly session cookies for authentication (no tracking cookies), and runs no analytics. Display and timezone preferences persist server-side per user when signed in (`/api/me/preferences`). IOC lookups are sent to configured third-party APIs; results are cached in your own database (6 hours for IOC, various TTLs for feed cache). See [`frontend/src/pages/PrivacyPage.jsx`](frontend/src/pages/PrivacyPage.jsx) or `/privacy` in the app.

---

## Known limitations

- Single-node PostgreSQL — not designed for concurrent multi-tenant writes at scale without connection pooling tuning
- Built-in app login with server sessions; admin/refresh routes require the `admin` role (the interim shared admin-key gate was removed early in the project's history)
- Runs as a single uvicorn worker by design — rate-limit token buckets are in-memory unless `BRIEFR_RATE_LIMIT_STORE=db` is set; don't raise the worker count without also enabling that
- Risk score v1.1b is computed server-side (`backend/scoring/risk.py`); weights for formula display only are fetched via `GET /api/config/risk`
- AI/ML alerts chip requires AI/ML keywords in your saved stack or asset profile `aiSystems`
- No official recommended CPU/RAM/disk sizing envelope is published yet — the architecture's design choices (CPU-only local embeddings, single worker, in-memory caches) point toward comfortable operation on a small VPS, but this hasn't been formally load-tested

---

## License

BRIEFR is licensed under the **Apache License, Version 2.0**. You may use, modify, and distribute the software (including commercially) provided you retain the license and [`NOTICE`](NOTICE) attribution. See [`LICENSE`](LICENSE) for the full text.

Copyright © 2026 Sai Harsha Vardhan.

Contributions are governed by [`CONTRIBUTING.md`](CONTRIBUTING.md). Security issues go to [`SECURITY.md`](SECURITY.md) — please don't open a public issue for a vulnerability.

---

<p align="left">
  <strong>Built by</strong> Sai Harsha Vardhan<br/>
  <a href="https://www.linkedin.com/in/sai-harsha-vardhan/">LinkedIn</a>
</p>
