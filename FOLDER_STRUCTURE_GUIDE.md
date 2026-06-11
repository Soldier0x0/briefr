# BRIEFR Folder Structure Guide

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

Every file in the repository with a one-line purpose. Tags:

- **[DEPRECATED]** — dead or superseded code
- **[KNOWN-ISSUE]** — documented runtime or wiring problem
- **[V1.2-SPLIT]** — flagged for v1.2 extraction/refactor

---

## Backend

| Path | Description |
|---|---|
| `backend/main.py` | FastAPI app wiring only: lifespan, CORS + security-header middleware, router includes (~130 lines; V1.2 router split complete) |
| `backend/settings.py` | Pydantic `BaseSettings` env config (phase 1: `BRIEFR_ENV`, `BRIEFR_ADMIN_API_KEY`, `ALLOWED_ORIGINS`) |
| `backend/dependencies.py` | Shared route dependencies: admin-key gate, audit-log writer |
| `backend/database.py` | **[V1.2-SPLIT]** SQLite schema, migrations, upserts, cache, MITRE/ATLAS/OTX persistence (1,681 lines) |
| `backend/scheduler.py` | APScheduler: 7 jobs, ingest locks, startup bootstrap, manual refresh entry points |
| `backend/tracking.py` | `api_usage` counters and quota metadata for `/api/usage` endpoints |
| `backend/requirements.txt` | Python dependencies (FastAPI, httpx, aiosqlite, APScheduler, PyYAML) |
| `backend/.env.example` | Environment variable template for API keys and scheduler tuning |
| `backend/.python-version` | Python version pin for local/pyenv |
| `backend/.gitignore` | Ignores `briefr.db`, `.env`, `__pycache__` |

### backend/routers/

| Path | Description |
|---|---|
| `backend/routers/__init__.py` | Package marker |
| `backend/routers/refresh.py` | Manual refresh endpoints (`POST /api/refresh*`), admin-gated + audited |
| `backend/routers/health.py` | `GET /api/health` + `format_time_in_tz` helper (also used by `/api/time` in `routers/meta.py`) |
| `backend/routers/atlas.py` | MITRE ATLAS + Case Studies endpoints (`/api/atlas/*`, `/api/case-studies/*`) |
| `backend/routers/ioc.py` | IOC lookup + OTX pulse IOCs (`POST /api/ioc/lookup`, `GET /api/otx/pulses/{id}/iocs`) |
| `backend/routers/cves.py` | CVE group: changes/stats/list/export/detail/momentum/detection/correlation + KEV deadlines, CVE filter SQL, enrichment orchestration |
| `backend/routers/meta.py` | Meta group: `/api/version`, `/api/time`, `/api/usage*`, AI/investigation summaries |

### backend/ai/

| Path | Description |
|---|---|
| `backend/ai/__init__.py` | Package marker |
| `backend/ai/summary.py` | Groq → Anthropic → template executive summary for PDF export |

### backend/correlation/

| Path | Description |
|---|---|
| `backend/correlation/__init__.py` | Package marker |
| `backend/correlation/engine.py` | Nightly + on-demand correlation (infra, actor, temporal); 6h feed_cache |

### backend/detection/

| Path | Description |
|---|---|
| `backend/detection/__init__.py` | Package marker |
| `backend/detection/rule_sources.py` | GitHub search for SigmaHQ and Elastic detection rules |
| `backend/detection/sigma_generator.py` | Template-based Sigma YAML when no community rules |
| `backend/detection/siem_queries.py` | Static SIEM query strings (Elastic, Splunk, Sentinel, QRadar) |

### backend/enrichment/

| Path | Description |
|---|---|
| `backend/enrichment/__init__.py` | Package marker |
| `backend/enrichment/cve.py` | CVE reference parsing helpers (MITRE technique, PoC detection) |
| `backend/enrichment/domain_validation.py` | Domain format validation for IOC lookup |
| `backend/enrichment/ioc.py` | Multi-source IOC lookup orchestration (VT, AbuseIPDB, etc.) |

### backend/feeds/

| Path | Description |
|---|---|
| `backend/feeds/__init__.py` | Package marker |
| `backend/feeds/nvd.py` | NVD API 2.0 fetch, parse, retry on 429 |
| `backend/feeds/kev.py` | CISA KEV JSON fetch |
| `backend/feeds/epss.py` | EPSS bulk CSV and batch API fallback |
| `backend/feeds/mitre.py` | MITRE ATT&CK STIX + CTID CVE→technique mappings |
| `backend/feeds/atlas.py` | MITRE ATLAS YAML + case studies from GitHub |
| `backend/feeds/otx.py` | AlienVault OTX pulses, IOCs, nightly correlation |
| `backend/feeds/osv.py` | OSV.dev query by CVE alias |
| `backend/feeds/extended.py` | Sploitus, GreyNoise, MalwareBazaar, URLhaus, CIRCL |
| `backend/feeds/ai_context.py` | AI/ML keyword detection and ATLAS link heuristics |
| `backend/feeds/incident_sources.py` | RSS source config (6 feeds) |
| `backend/feeds/incident_news.py` | RSS fetch, parse, 30min feed_cache per source |

### backend/matching/

| Path | Description |
|---|---|
| `backend/matching/__init__.py` | Package marker |
| `backend/matching/cpe.py` | CPE version matching for asset profile POST `/api/cves/match` |

### backend/scoring/

| Path | Description |
|---|---|
| `backend/scoring/__init__.py` | Package marker |
| `backend/scoring/risk.py` | Server-side momentum calculation (`calculate_momentum`) |

### backend/templates/

| Path | Description |
|---|---|
| `backend/templates/__init__.py` | Package marker |
| `backend/templates/intelligence.py` | Plain-English sentence templates for CVE/IOC/GreyNoise/OTX |

### backend/scripts/

| Path | Description |
|---|---|
| `backend/scripts/backfill_poc.py` | CLI to backfill `has_poc` flags from references |

### backend/tests/

| Path | Description |
|---|---|
| `backend/tests/test_*.py` | Pytest unit tests for feeds, scoring, CPE, intelligence templates |
| `backend/tests/fixtures/otx_cve_44228_general.json` | OTX API response fixture |

---

## Frontend

| Path | Description |
|---|---|
| `frontend/index.html` | Vite HTML shell |
| `frontend/package.json` | React 18, Vite 5, jsPDF, exceljs dependencies |
| `frontend/package-lock.json` | Locked npm dependency tree |
| `frontend/vite.config.js` | Dev server port 5173, `/api` proxy to :8000 |
| `frontend/.gitignore` | Ignores `node_modules`, `dist` |

### frontend/src/

| Path | Description |
|---|---|
| `frontend/src/main.jsx` | React root; applies `briefr_theme` from localStorage |
| `frontend/src/App.jsx` | App shell, tabs, global state, DetailDrawer host |
| `frontend/src/App.css` | Layout and grid styles |
| `frontend/src/api.js` | Central `fetch` wrapper and all API client functions |

### frontend/src/components/

| Path | Description |
|---|---|
| `frontend/src/components/Header.jsx` | Logo, BRIEF/IOC/INCIDENTS tabs, theme, timezone, profile |
| `frontend/src/components/Hero.jsx` | Tech stack input; persists to localStorage |
| `frontend/src/components/StatsRow.jsx` | Severity/KEV stat chips from `GET /api/stats` |
| `frontend/src/components/TimelineHeatmap.jsx` | 90-day CVE publication heatmap |
| `frontend/src/components/CVEFeed.jsx` | Infinite-scroll CVE list, bulk export |
| `frontend/src/components/CVECard.jsx` | Single CVE row with risk badge and EPSS sparkline |
| `frontend/src/components/FilterBar.jsx` | Severity, KEV, PoC, EPSS, technique filters |
| `frontend/src/components/Sidebar.jsx` | KEV deadlines and top ATT&CK techniques |
| `frontend/src/components/DetailDrawer.jsx` | **[V1.2-SPLIT]** CVE detail drawer (~1,500 lines) |
| `frontend/src/components/DrawerAtlasSection.jsx` | ATLAS techniques/case studies block (fed by `GET /api/cves/{id}`) |
| `frontend/src/components/IOCLookup.jsx` | **[V1.2-SPLIT]** IOC lookup UI (1,168 lines) |
| `frontend/src/components/CaseStudies.jsx` | Incidents & News tab — RSS + ATLAS cards |
| `frontend/src/components/InvestigationPanel.jsx` | Investigation thread sidebar |
| `frontend/src/components/DigestModal.jsx` | Multi-CVE digest modal |
| `frontend/src/components/PdfExportModal.jsx` | Analyst name prompt for PDF export |
| `frontend/src/components/AssetWizard.jsx` | Asset profile setup wizard |
| `frontend/src/components/AssetProfileManage.jsx` | Profile view/edit UI |
| `frontend/src/components/AssetWarning.jsx` | Banner when profile affects risk display |
| `frontend/src/components/AboutModal.jsx` | About / version modal |
| `frontend/src/components/ShortcutsPanel.jsx` | Keyboard shortcut reference |
| `frontend/src/components/SessionLockOverlay.jsx` | Inactivity session lock UI |
| `frontend/src/components/ScrollToTop.jsx` | Scroll-to-top control |
| `frontend/src/components/*.css` | Co-located styles per component |

### frontend/src/context/

| Path | Description |
|---|---|
| `frontend/src/context/AssetProfileContext.jsx` | Asset profile state, CPE match scores, wizard flow |
| `frontend/src/context/InvestigationContext.jsx` | Investigation items, cross-tab navigation |

### frontend/src/hooks/

| Path | Description |
|---|---|
| `frontend/src/hooks/useInactivityTimeout.js` | Session inactivity detection |

### frontend/src/pages/

| Path | Description |
|---|---|
| `frontend/src/pages/PrivacyPage.jsx` | Privacy policy (localStorage disclosure) |
| `frontend/src/pages/TermsPage.jsx` | Terms of use |
| `frontend/src/pages/LegalPage.css` | Shared legal page styles |

### frontend/src/config/

| Path | Description |
|---|---|
| `frontend/src/config/assetCatalog.js` | Vendor/product catalog for asset wizard |
| `frontend/src/config/caseStudySources.js` | ATLAS YAML fallback URL for client-side merge |

### frontend/src/scoring/

| Path | Description |
|---|---|
| `frontend/src/scoring/riskScore.js` | **Active** client-side risk score v1.1b (6 components) |

### frontend/src/utils/

| Path | Description |
|---|---|
| `frontend/src/utils/aiAssets.js` | AI/ML framework detection for alerts stat + drawer |
| `backend/feeds/case_study_feed.py` | Combined RSS + ATLAS loader for `/api/case-studies/feed` (single DB connection) |
| `backend/backup/` | SQLite backup manager CLI (`python -m backup`) |
| `frontend/src/utils/cveFilters.js` | Stack localStorage key and filter param mapping |
| `frontend/src/utils/cveAge.js` | CVE age display helpers |
| `frontend/src/utils/timezone.js` | Timezone list, formatting, localStorage persistence |
| `frontend/src/utils/epssSparkline.js` | EPSS mini-chart data for CVECard |
| `frontend/src/utils/momentumCache.js` | Module-level momentum score cache for cards |
| `frontend/src/utils/caseStudyFeed.js` | Merges RSS + ATLAS case study cards |
| `frontend/src/utils/pdfReport.js` | jsPDF single/bulk CVE report generation |
| `frontend/src/utils/pdfAiSummary.js` | Wrapper for `POST /api/ai/summary` on PDF export |
| `frontend/src/utils/investigationPdf.js` | Investigation thread PDF export |
| `frontend/src/utils/report.js` | Markdown report builder for clipboard export |
| `frontend/src/utils/exportCsv.js` | CVE list CSV export |
| `frontend/src/utils/exportXlsx.js` | CVE list Excel export (exceljs) |
| `frontend/src/utils/heatmapGrid.js` | Timeline heatmap grid layout |
| `frontend/src/utils/displayText.js` | Text truncation/display helpers |
| `frontend/src/utils/domainValidation.js` | Client-side domain validation (mirrors backend) |
| `frontend/src/utils/aiAssets.js` | AI/ML asset profile matching helpers |
| `frontend/src/utils/assetProfileIo.js` | Import/export asset profile JSON files |
| `frontend/src/utils/extractIndicatorsFromCve.js` | Pull IOCs from CVE OTX/GreyNoise fields |
| `frontend/src/utils/investigationActors.js` | Actor extraction for investigation PDF |

---

## Configuration & Environment

| Path | Description |
|---|---|
| `backend/.env.example` | All backend env vars documented |
| `deploy/nginx-briefr.conf` | Production nginx TLS reverse proxy |
| `deploy/nginx-briefr-http.conf` | HTTP-only nginx config |
| `deploy/briefr-backend.service` | systemd unit for uvicorn |
| `deploy/briefr-frontend.service` | systemd unit for Vite preview/static |
| `deploy/briefr.target` | systemd target grouping both services |
| `deploy/setup.sh` | Initial server setup script |
| `deploy/setup-nginx-production.sh` | nginx + TLS setup |
| `deploy/briefr-update.sh` | Pull and restart services |
| `deploy/check-backend.sh` | Health check script |
| `deploy/smoke-intel.sh` | Smoke test intel endpoints |
| `deploy/refresh-*.sh` | Manual MITRE/EPSS/ATLAS refresh helpers |
| `deploy/backfill-poc.sh` | Runs `backfill_poc.py` |
| `deploy/fix-permissions.sh` | File permission fix for deploy user |
| `.github/workflows/backend-tests.yml` | CI: pytest on push |

---

## Documentation

| Path | Description |
|---|---|
| `README.md` | Project overview and quick start |
| `docs/ONBOARDING.md` | Contributor entry point: reading order, local dev, tests, env vars, deploy overview, troubleshooting |
| `SYSTEM_DESIGN.md` | Architecture, data flows, design decisions |
| `SYSTEM_DESIGN.pdf` | PDF export of system design (generated) |
| `API_REFERENCE.md` | Human-readable endpoint catalog |
| `TECHNICAL_INVENTORY.md` | Stack, schema, scheduler, feature matrix |
| `TECHNICAL_INVENTORY.xlsx` | Spreadsheet export of inventory tables |
| `APPLICATION_EXECUTION_MAP.md` | Startup sequence and request journeys |
| `FOLDER_STRUCTURE_GUIDE.md` | This file |
| `docs/diagrams/*.mermaid` | Mermaid diagrams (architecture, flows, schema, startup) |
| `screenshots/brief.png` | README screenshot — BRIEF tab CVE feed |
| `screenshots/ioc-lookup.png` | README screenshot — IOC LOOKUP tab |
| `screenshots/incidents-news.png` | README screenshot — INCIDENTS & NEWS tab |
| `LICENSE` | Proprietary license (Sai Harsha Vardhan, all rights reserved) |

---

## Scripts

| Path | Description |
|---|---|
| `scripts/seed_screenshot_data.py` | Seeds sample CVE rows + warms RSS cache before README screenshot capture |
| `scripts/capture_readme_screenshots.mjs` | Playwright capture of README tab screenshots; preflights API health/feeds; exits non-zero on empty data or feed errors |
| `deploy/briefr-backup.sh` | Integrity-checked SQLite + `.env` backup; retention pruning |
| `deploy/briefr-restore.sh` | Restore newest or specified archive; stops/starts backend |
| `deploy/briefr-backup.service` / `.timer` | systemd oneshot + 6h timer → `/var/lib/briefr/backups` |
| `backend/backup/manager.py` | Backup core: integrity_check, online backup, restore, log rotation |
| `scripts/generate_technical_inventory_xlsx.py` | Regenerates `TECHNICAL_INVENTORY.xlsx` from structured data (min column width 10) |
| `scripts/generate_system_design_pdf.mjs` | Renders `SYSTEM_DESIGN.pdf` from markdown with Playwright (tables + Mermaid diagrams) |
| `backend/scripts/backfill_poc.py` | Backfill `has_poc` from NVD references |
| `deploy/*.sh` | Deployment and maintenance shell scripts |
