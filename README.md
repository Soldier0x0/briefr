# BRIEFR
### Free CVE Intelligence for Security Analysts

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: Live](https://img.shields.io/badge/Status-Live-green.svg)
![Made with: Python + React](https://img.shields.io/badge/Made%20with-Python%20%2B%20React-informational)

![BRIEFR Dashboard](screenshots/dashboard.png)

---

## What is BRIEFR?

BRIEFR is a free CVE intelligence dashboard that aggregates NVD, CISA KEV, EPSS, and OSV data into one searchable feed. It is built for security analysts and defenders who need a fast morning brief without enterprise tooling or sign-up friction.

## Why I built this

Every morning, security analysts manually check NVD, CISA KEV, VirusTotal, and Exploit-DB just to answer one question — what broke overnight and does it affect us? Enterprise tools like Vulncheck solve this but cost thousands of dollars per year. BRIEFR does the same thing, free, with no account, no tracking, and no noise.

## Features

- Daily CVE feed from NVD with CVSS and EPSS scoring
- CISA KEV integration with remediation deadline tracking
- IOC enrichment — IP, hash, and domain lookup via VirusTotal and AbuseIPDB
- Stack-based relevance filtering for your technology stack
- Bulk select and copy CVEs as a Markdown report
- CVE digest export for the current filtered view
- Dark and light mode
- Timezone selector with local timestamps on reports
- Keyboard shortcuts for search, filters, and card navigation
- No account required. No cookies. No tracking.

## Tech Stack

| Backend | Frontend |
|---------|----------|
| FastAPI | React 18 |
| Uvicorn | React Router |
| httpx | Vite |
| APScheduler | |
| aiosqlite | |
| Pydantic | |
| python-dotenv | |

## Data Sources

| Source | Data | Refresh |
|--------|------|---------|
| NVD/NIST | CVE details + CVSS | Hourly incremental (`lastMod` watermark) |
| CISA KEV | Known exploited vulns | Every 15 minutes |
| EPSS (FIRST.org) | Exploit probability | Every 6 hours |
| OSV.dev | Open source package vulns | On CVE detail view |
| VirusTotal | IOC enrichment | On demand |
| AbuseIPDB | IP reputation | On demand |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Free API keys: [NVD](https://nvd.nist.gov/developers/request-an-api-key), [VirusTotal](https://www.virustotal.com/gui/join-us), [AbuseIPDB](https://www.abuseipdb.com/register)

### Installation

```bash
git clone https://github.com/Soldier0x0/briefr.git /opt/briefr
cd /opt/briefr/backend
python3.11 -m venv ../venv
../venv/bin/pip install -r requirements.txt
cp .env.example .env   # add your API keys

../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
cd /opt/briefr/frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api to :8000
```

Production deploy: `npm run build`, then serve `frontend/dist` behind nginx. See `deploy/setup.sh` for systemd install on Debian.

### Update EPSS scores (database)

After `git pull`, refresh EPSS from the FIRST daily feed without re-fetching all CVEs from NVD:

```bash
bash /opt/briefr/deploy/refresh-epss.sh
```

Or trigger a full ingest (NVD, then KEV, then EPSS — same as cold start):

```bash
curl -X POST http://127.0.0.1:8000/api/refresh
journalctl -u briefr-backend -f
```

Individual pipelines (no full NVD+KEV+EPSS chain):

```bash
curl -X POST http://127.0.0.1:8000/api/refresh/nvd
curl -X POST http://127.0.0.1:8000/api/refresh/kev
curl -X POST http://127.0.0.1:8000/api/refresh/epss
```

Recent CVSS / EPSS / KEV / PoC changes: `GET /api/changes?since_hours=24`

Check coverage:

```bash
sqlite3 /opt/briefr/backend/briefr.db \
  "SELECT COUNT(*) AS total, SUM(epss_score IS NOT NULL) AS with_epss FROM cves;"
```

### Production deploy (nginx, not Vite)

After initial `deploy/setup.sh`, every update (frontend + backend) is one command as **root**:

```bash
bash /opt/briefr/deploy/briefr-update.sh
```

This script:

- Pulls `main` from GitHub
- Updates Python and npm dependencies
- Runs `npm run build` → `/opt/briefr/frontend/dist`
- Installs/refreshes the nginx site (`deploy/nginx-briefr-http.conf` or HTTPS if certbot certs exist)
- **Stops and disables** `briefr-frontend` (Vite on 5173)
- Restarts `briefr-backend` and reloads nginx

Set `ALLOWED_ORIGINS` in `backend/.env` to your public URL (e.g. `http://192.168.1.50`, `https://projectjupiter.in`) — not `:5173`.

Force HTTPS config: `USE_TLS=1 bash /opt/briefr/deploy/briefr-update.sh` (requires Let's Encrypt certs for `projectjupiter.in`).

`setup-nginx-production.sh` is an alias for the same update script.

### Environment Variables

| Variable | Description | Where to get it |
|----------|-------------|-----------------|
| `NVD_API_KEY` | NVD API rate-limit key | [NVD API key request](https://nvd.nist.gov/developers/request-an-api-key) |
| `VIRUSTOTAL_API_KEY` | IOC hash/domain lookups | [VirusTotal](https://www.virustotal.com/gui/join-us) |
| `ABUSEIPDB_API_KEY` | IP reputation for IOC lookup | [AbuseIPDB](https://www.abuseipdb.com/register) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | Your frontend URL(s) |
| `NVD_SYNC_INTERVAL_HOURS` | NVD incremental sync interval | Default `1` |
| `KEV_SYNC_INTERVAL_MINUTES` | CISA KEV metadata sync | Default `15` |
| `EPSS_SYNC_INTERVAL_HOURS` | EPSS score sync | Default `6` |
| `NVD_SYNC_OVERLAP_MINUTES` | Watermark overlap for NVD | Default `15` |
| `CACHE_REFRESH_HOUR` | Weekly MITRE job hour (IST) | Default `6` |
| `CACHE_REFRESH_MINUTE` | Legacy; see MITRE weekly cron | Default `0` |
| `MAX_CVES_PER_FETCH` | Cap per NVD sync | Default `2000` |
| `DEFAULT_TIMEZONE` | Server display timezone | Default `Asia/Kolkata` |
| `DB_PATH` | SQLite database file | Default `briefr.db` in backend dir |

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service health, CVE count, last refresh time |
| `GET /api/time` | Server UTC and local time |
| `GET /api/stats` | Severity and KEV summary counts |
| `GET /api/cves` | Paginated, filterable CVE list |
| `GET /api/cves/{cve_id}` | Single CVE detail with OSV packages |
| `POST /api/ioc/lookup` | IOC enrichment (ip, hash, domain) |
| `POST /api/refresh` | Full ingest (NVD + KEV + EPSS); schedulers run automatically |
| `POST /api/refresh/nvd` | NVD incremental only |
| `POST /api/refresh/kev` | CISA KEV metadata only |
| `POST /api/refresh/epss` | EPSS scores only |
| `GET /api/changes` | Recent CVSS / EPSS / KEV / PoC field changes |
| `GET /api/kev/deadlines` | CISA KEV entries with due dates |
| `GET /api/usage` | External API usage counters |

Interactive docs: `/api/docs` (Swagger).

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `F` | Cycle filters (KEV → Critical → PoC → all) |
| `Esc` | Close drawer, digest, or About modal |
| `↑` `↓` | Navigate CVE cards |
| `Enter` | Open highlighted CVE |

## Privacy

BRIEFR collects no personal data, uses no cookies, and runs no analytics. IOC lookups are sent to VirusTotal and AbuseIPDB — results cached locally for 6 hours. See the full Privacy Policy at [projectjupiter.in/privacy](https://projectjupiter.in/privacy).

## License

MIT License — free to self-host, fork, and modify. Attribution appreciated.

---

<p align="left">
  <strong>Built by</strong> Sai Harsha Vardhan<br/>
  <a href="https://www.linkedin.com/in/sai-harsha-vardhan/">LinkedIn</a>
</p>
