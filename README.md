
# BRIEFR
### Free CVE Intelligence & Threat Investigation for Security Analysts

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: Live](https://img.shields.io/badge/Status-Live-green.svg)
![Made with: Python + React](https://img.shields.io/badge/Made%20with-Python%20%2B%20React-informational)
![AI-Powered](https://img.shields.io/badge/AI%20Powered-Groq%20%26%20Anthropic-blueviolet)

![BRIEFR Dashboard](screenshots/dashboard.png)

---

## What is BRIEFR?

BRIEFR is a free, self-hosted CVE intelligence dashboard that aggregates NVD, CISA KEV, EPSS, OSV, MITRE ATT&CK, and threat intelligence data into one powerful searchable feed. It combines real-time vulnerability data with AI-powered threat investigation capabilities, built for security analysts and defenders who need fast intelligence without enterprise tooling or sign-up friction.

## Why I built this

Every morning, security analysts manually check NVD, CISA KEV, VirusTotal, and Exploit-DB just to answer one question — what broke overnight and does it affect us? Enterprise tools like Vulncheck solve this but cost thousands of dollars per year. BRIEFR does the same thing, free, with no account, no tracking, and no noise—plus adds AI-driven threat investigation and MITRE ATT&CK mapping.

## Features

**Vulnerability Intelligence:**
- Real-time CVE feed from NVD with CVSS v3.1 and EPSS scoring
- CISA KEV integration with remediation deadline tracking
- MITRE ATT&CK technique mapping and case study integration
- Extended threat intelligence (GreyNoise scans, Sploitus exploits, CIRCL data)
- Timeline heatmap for CVE publication trends
- Risk scoring engine with asset-based contextualization

**Threat Investigation:**
- AI-powered threat analysis and executive summaries (Groq/Anthropic)
- IOC enrichment with VirusTotal and AbuseIPDB lookups (IP, hash, domain)
- Threat actor correlation and IOC tracking
- Linked CVE investigation chains
- PDF report generation with AI summaries

**Search & Filtering:**
- Stack-based relevance filtering (match tech stack to affected products)
- AI profile filtering (filter CVEs by affected AI frameworks)
- Technique-based filtering by MITRE ATT&CK
- EPSS score ranges, severity levels, KEV-only, PoC-only filters
- Full-text CVE ID, vendor, and description search

**Data Export & Reporting:**
- Bulk select and copy CVEs as Markdown/JSON
- CVE digest export for filtered views
- PDF report generation with AI summaries
- Excel and CSV export
- Timezone-aware timestamps on all reports

**User Experience:**
- Dark and light mode
- Timezone selector with local timestamps
- Keyboard shortcuts for navigation (/, F, Esc, arrows, Enter)
- No account required. No cookies. No tracking.
- Fully responsive design

## Tech Stack

| Backend | Frontend |
|---------|----------|
| FastAPI 0.136+ | React 18.3+ |
| Uvicorn | React Router 7+ |
| httpx | Vite 5+ |
| APScheduler | ExcelJS |
| aiosqlite | jsPDF, html2canvas |
| Pydantic 2+ | |
| python-dotenv | |
| PyYAML | |

## Data Sources

| Source | Data | Refresh | Endpoints |
|--------|------|---------|-----------|
| NVD/NIST | CVE details + CVSS | Hourly incremental (`lastMod` watermark) | `/api/refresh/nvd` |
| CISA KEV | Known exploited vulns | Every 15 minutes | `/api/refresh/kev` |
| EPSS (FIRST.org) | Exploit probability | Every 6 hours | `/api/refresh/epss` |
| MITRE ATT&CK | CVE→technique mappings + case studies | Weekly | `/api/refresh/mitre` |
| OSV.dev | Open source package vulns | On CVE detail view | — |
| VirusTotal | IOC enrichment (hash, domain, IP) | On demand (6h cache) | `/api/ioc/lookup` |
| AbuseIPDB | IP reputation | On demand (6h cache) | `/api/ioc/lookup` |
| GreyNoise | Scans for CVE | On demand | — |
| Sploitus | Public exploits | On demand | — |
| CIRCL CVE | Extended CVE data | On demand | — |

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

## API Reference

### CVE Data

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service health, CVE count, last refresh times |
| `GET /api/time` | Server UTC and local time |
| `GET /api/stats` | Severity and KEV summary counts |
| `GET /api/cves` | Paginated, filterable CVE list (supports `?severity=`, `?stack=`, `?search=`, etc.) |
| `GET /api/cves/{cve_id}` | Single CVE detail with OSV packages, techniques, and related CVEs |
| `GET /api/changes` | Recent CVSS/EPSS/KEV/PoC changes |

### Risk Intelligence & Scoring

| Endpoint | Description |
|----------|-------------|
| `GET /api/cves/{cve_id}/score` | BRIEFR Risk Score v1.1a with optional `?assets=` JSON array |
| `GET /api/cves/{cve_id}/sentences` | Humanized intelligence sentences (severity, epss, kev, exploit, patch, ai_context) |
| `GET /api/kev/deadlines` | CISA KEV entries with remediation due dates |

### Threat Investigation

| Endpoint | Description |
|----------|-------------|
| `POST /api/ioc/lookup` | IOC enrichment (ip, hash, domain) via VirusTotal + AbuseIPDB |
| `GET /api/ai-profiles/{ai_profile}/alerts` | AI ML profile alerts (frameworks like PyTorch, TensorFlow, etc.) |
| `GET /api/investigation/related` | Get related CVEs and IOCs for an investigation |

### MITRE ATT&CK Integration

| Endpoint | Description |
|----------|-------------|
| `GET /api/techniques/top` | Top ATT&CK techniques by mapped CVE count |
| `GET /api/cves/{cve_id}/techniques` | Techniques mapped to a single CVE |
| `GET /api/atlas/techniques` | Grouped techniques with case studies |
| `GET /api/atlas/case-studies` | MITRE ATT&CK case studies |
| `GET /api/atlas/case-studies/{cve_id}` | Case studies for a specific CVE |
| `POST /api/refresh/mitre` | Refresh MITRE ATT&CK Enterprise STIX + CVE mappings (weekly auto) |

### Refresh & Admin

| Endpoint | Description |
|----------|-------------|
| `POST /api/refresh` | Full ingest (NVD + KEV + EPSS + MITRE); runs automatically on scheduler |
| `POST /api/refresh/nvd` | NVD incremental sync only |
| `POST /api/refresh/kev` | CISA KEV metadata only |
| `POST /api/refresh/epss` | EPSS scores only |
| `GET /api/usage` | External API usage counters (NVD, VT, AbuseIPDB calls) |

**Interactive API docs:** `/api/docs` (Swagger UI)

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
