<p align="center">
  <img src="docs/assets/screenshots/brief.png" alt="BRIEFR morning brief — prioritized CVE queue and heatmap" width="720"/>
</p>

<h1 align="center">BRIEFR</h1>
<p align="center"><strong>Self-hosted CVE intelligence for analysts who need answers, not another raw feed</strong></p>

<p align="center">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-blue.svg">
  <img alt="React 19" src="https://img.shields.io/badge/React-19.2-61DAFB.svg?logo=react&logoColor=white">
  <img alt="PostgreSQL 16" src="https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white">
  <img alt="Self-hosted" src="https://img.shields.io/badge/Self--hosted-yes-success.svg">
</p>

<p align="center">
  <a href="https://briefrdemo.projectjupiter.in">Live demo</a> ·
  <a href="https://docs.projectjupiter.in">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#screenshots">Screenshots</a>
</p>

---

## What is BRIEFR?

BRIEFR is a **self-hosted CVE intelligence dashboard**. It pulls public vulnerability and threat feeds into **your** PostgreSQL database, then gives you one dark-mode UI to work through them: morning brief, searchable feed, IOC lookup, investigation graph, advisories, and detection tooling.

You are not clicking through NVD on every page load. Schedulers sync upstream sources on a schedule; the UI reads what is already stored locally.

---

## Why BRIEFR?

- **Save time on triage** — Operational Priority (P1–P4), threat score, and stack relevance surface what matters first instead of a flat severity sort.
- **One place to work** — Brief, feed, drawer detail, IOC enrichment, stored-intel graph, and Forge hunt packs share the same session and watchlist.
- **Explainable scoring** — Rule-based prioritization and correlation; optional LLM narration at the edges, not a black-box risk number.
- **Detection output** — Sigma, SIEM snippets, and YARA from a local SigmaHQ mirror plus BRIEFR class templates tied to CWE/ATT&CK context.
- **Your data stays yours** — Self-hosted Postgres, Apache 2.0, no vendor SaaS lock-in.

---

## Who is it for?

- **SOC and vulnerability analysts** who need a daily queue and deep CVE context
- **Detection engineers** mapping CVEs to ATT&CK and exporting hunt content
- **Small security teams** who want one tool instead of five browser tabs and spreadsheets
- **Operators** who need Postgres backups, scheduler health, and API key management on their own infra

Not a scanner or ASM product — BRIEFR prioritizes **known CVEs** against your stack; it does not discover assets on your network.

---

## What you get

| Area | What it does |
|------|----------------|
| **BRIEF** | Morning queue — KEV due soon, EPSS movers, stack matches |
| **FEED** | Full CVE list, filters, hybrid search, export |
| **IOC LOOKUP** | VirusTotal, AbuseIPDB, GreyNoise, OTX, and more (with your API keys) |
| **INVESTIGATE** | Stored-intel graph — search CVE/IOC/technique, pan/zoom, expand hops |
| **ADVISORIES & INTEL** | Headlines, CISA advisories, MITRE ATLAS case studies |
| **FORGE** | MITRE ATT&CK coverage map and hunt pack generation |
| **Admin** | Feeds, backups, webhooks, AI ops, wallboard kiosk |

**Try without installing:** [briefrdemo.projectjupiter.in](https://briefrdemo.projectjupiter.in) — same analyst shell over fixture data.

---

## How data reaches you

1. **Ingest** — Background jobs sync NVD, CISA KEV, EPSS, MITRE, OTX, RSS, and other sources into PostgreSQL (respecting each provider’s rate limits).
2. **Store** — CVE rows, enrichment mirrors, correlation artifacts, and optional pgvector embeddings live in your database.
3. **Work** — The React UI reads from Postgres. IOC lookups and optional LLM tasks call outbound APIs only when you ask.
4. **Operate** — Admin surfaces show feed freshness, scheduler jobs, backups, and API key health.

For architecture depth, see [How it works](docs/HOW_IT_WORKS.md) and [System design](docs/SYSTEM_DESIGN.md).

---

## Quick start

**Local try-out** (PostgreSQL 16 + pgvector):

```bash
git clone https://github.com/Soldier0x0/briefr.git && cd briefr
docker compose -f deploy/docker-compose.postgres.yml up -d
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
# set DATABASE_URL=postgresql://briefr:briefr@127.0.0.1:5432/briefr in .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

Open the UI and complete first-run admin setup.

**Production path** — PostgreSQL 16 + **pgvector** (`pgvector/pgvector:pg16`), then the install script:

```bash
# After Postgres is running — see docs/SELF_HOST.md §3
bash deploy/briefr-install.sh
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

| Guide | Use when |
|-------|----------|
| [SELF_HOST.md](docs/SELF_HOST.md) | Full install — dev Postgres, production Debian/nginx, Docker notes |
| [POSTGRES.md](docs/POSTGRES.md) | Backups, restore, pgvector upgrade |
| [USE.md](docs/USE.md) | Analyst tabs and workflows |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Something broke |

Online docs: [docs.projectjupiter.in](https://docs.projectjupiter.in)

---

## Screenshots

From a self-hosted deployment (dark theme, BRIEFR accent `#e85533`).

<table>
<tr>
<td align="center"><img src="docs/assets/screenshots/brief.png" alt="BRIEF tab" width="360" /><br><sub>BRIEF</sub></td>
<td align="center"><img src="docs/assets/screenshots/feed.png" alt="FEED tab" width="360" /><br><sub>FEED</sub></td>
<td align="center"><img src="docs/assets/screenshots/detail-drawer.png" alt="CVE detail drawer" width="360" /><br><sub>CVE detail</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/assets/screenshots/investigate.png" alt="INVESTIGATE graph" width="360" /><br><sub>INVESTIGATE</sub></td>
<td align="center"><img src="docs/assets/screenshots/ioc-lookup.png" alt="IOC LOOKUP" width="360" /><br><sub>IOC LOOKUP</sub></td>
<td align="center"><img src="docs/assets/screenshots/advisories-intel.png" alt="Advisories and Intel" width="360" /><br><sub>Advisories &amp; Intel</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/assets/screenshots/forge.png" alt="FORGE MITRE coverage and hunt packs" width="360" /><br><sub>FORGE</sub></td>
<td align="center"><img src="docs/assets/screenshots/admin-analyst.png" alt="Admin analyst view" width="360" /><br><sub>Admin · Analyst</sub></td>
<td align="center"><img src="docs/assets/screenshots/admin-operator.png" alt="Admin operator view" width="360" /><br><sub>Admin · Operator</sub></td>
</tr>
</table>

---

## Documentation

| I want to… | Doc |
|------------|-----|
| Install | [SELF_HOST.md](docs/SELF_HOST.md) |
| Use the UI | [USE.md](docs/USE.md) |
| Fix a problem | [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| API contract | [API_REFERENCE.md](docs/API_REFERENCE.md) |
| What's shipped | [PRODUCT_STATUS.md](docs/PRODUCT_STATUS.md) |
| Contribute | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE). Security reports: [SECURITY.md](SECURITY.md).

Copyright © 2026 Sai Harsha Vardhan.
