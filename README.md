
<p align="center">
  <img src="docs/assets/production-architecture.svg" alt="BRIEFR architecture" width="720"/>
</p>

<h1 align="center">BRIEFR</h1>
<p align="center"><strong>Self-hosted CVE intelligence for security analysts</strong></p>

<p align="center">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-blue.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.139-009688.svg">
  <img alt="React 19" src="https://img.shields.io/badge/React-19.2-61DAFB.svg?logo=react&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white">
  <img alt="Self-hosted" src="https://img.shields.io/badge/Self--hosted-yes-success.svg">
</p>

<p align="center">
  <a href="#screenshots">Screenshots</a> ·
  <a href="#what-it-does">What it does</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#license">License</a>
</p>

BRIEFR aggregates NVD, CISA KEV, EPSS, MITRE ATT&CK/ATLAS, and optional threat feeds into one searchable UI — IOC lookup, explainable correlation, detection helpers, and PDF export. Apache 2.0: clone, self-host, modify, and use commercially with attribution ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)). Bring your own API keys for upstream feeds.

**Example instance:** https://briefr.projectjupiter.in

---

## Screenshots

PostgreSQL-backed instance (July 2026 reference data). Regenerate: [`scripts/capture_readme_screenshots.mjs`](scripts/capture_readme_screenshots.mjs) — see [`docs/IMAGE_BRIEFS.md`](docs/IMAGE_BRIEFS.md).

| BRIEF | FEED | CVE detail |
|-------|------|------------|
| ![BRIEF tab](docs/assets/screenshots/brief.png) | ![FEED tab](docs/assets/screenshots/feed.png) | ![CVE drawer](docs/assets/screenshots/detail-drawer.png) |

| IOC lookup | Incidents & news | Admin |
|------------|------------------|-------|
| ![IOC LOOKUP](docs/assets/screenshots/ioc-lookup.png) | ![Incidents & News](docs/assets/screenshots/incidents-news.png) | ![Admin Security](docs/assets/screenshots/admin-security.png) |

---

## What it does

| Tab | Label | Purpose |
|-----|-------|---------|
| `brief` | **BRIEF** | Morning queue, charts, heatmap, what changed |
| `feed` | **FEED** | CVE list, stack filter, KEV deadlines, hybrid search, export |
| `ioc` | **IOC LOOKUP** | IP / hash / domain enrichment |
| `atlas` | **INCIDENTS & NEWS** | Security RSS + MITRE ATLAS narratives |
| `forge` | **FORGE** | ATT&CK navigator, scenarios, campaigns, hunt packs |

**Highlights:** incremental NVD ingest · KEV/EPSS/CVSS · explainable OTX correlation · local SigmaHQ index · semantic search (optional embeddings) · built-in login · no third-party analytics.

**Stack:** FastAPI · React 19 · PostgreSQL 16 (+ pgvector for embeddings) · APScheduler. Production requires Postgres; SQLite remains a zero-config dev/test fallback until [PR #752](https://github.com/Soldier0x0/briefr/pull/752) lands.

---

## Getting started

**Install paths (SQLite, Postgres+pgvector, production):** [`docs/SELF_HOST.md`](docs/SELF_HOST.md)

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

Open http://localhost:5173 → first-run setup creates the admin user.

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

| Path | When |
|------|------|
| [SELF_HOST §2](docs/SELF_HOST.md#2-local-development-with-postgresql--pgvector) | Postgres + pgvector dev |
| [SELF_HOST §3](docs/SELF_HOST.md#3-production-debian--systemd--nginx) | Production Debian deploy |
| [POSTGRES.md](docs/POSTGRES.md) | Backups, restore, pgvector |
| [ONBOARDING.md](docs/ONBOARDING.md) | Development and tests |

Optional seed data: `python scripts/seed_screenshot_data.py` from repo root.

---

## Documentation

| I want to… | Doc |
|------------|-----|
| Install | [`docs/SELF_HOST.md`](docs/SELF_HOST.md) |
| Use the UI | [`docs/USE.md`](docs/USE.md) |
| Fix a problem | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand internals | [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) · [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) |
| Browse online | https://docs.projectjupiter.in |
| API contract | [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) |
| What's shipped | [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) |
| Contribute | [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/ONBOARDING.md`](docs/ONBOARDING.md) |

Index: [`docs/index.md`](docs/index.md)

---

## API

Full catalog: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md). Interactive Swagger at `http://localhost:8000/api/docs` (disable in production via `BRIEFR_ENV=production`).

Environment variables: `backend/.env.example`

---

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md). Security reports: [`SECURITY.md`](SECURITY.md) (no public issues for vulnerabilities).

Copyright © 2026 Sai Harsha Vardhan.
