# BRIEFR Application Execution Map

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

Runtime behaviour traced from source. File:function references match the codebase.

---

## 1. Startup Sequence

| Step | File | Function / action |
|---|---|---|
| 1 | `uvicorn` | Loads `main:app` |
| 2 | `main.py` | `lifespan()` context manager enters |
| 2a | `backup/manager.py` | `ensure_db_or_restore()` — integrity check; auto-restore from latest backup if corrupt |
| 3 | `database.py` | `init_db()` — `CREATE TABLE IF NOT EXISTS` for 21 tables (lines 20–277) |
| 4 | `database.py` | Inline migrations in `init_db()` loop (lines 280–304): ALTER columns, correlation tables, indexes |
| 5 | `database.py` | Normalize `epss_score = 0.0` → NULL (lines 314–317) |
| 6 | `scheduler.py` | `start_scheduler()` — register 7 jobs, `scheduler.start()` (lines 546–644) |
| 7 | `scheduler.py` | `maybe_run_on_startup()` (lines 432–459) |
| 7a | `database.py` | If CVE count ≥ 10: `strip_auto_generated_summaries`, `enrich_kev_summaries` |
| 7b | `scheduler.py` | If CVE count &lt; 10: `asyncio.create_task(run_full_ingest_sync)` |
| 8 | `scheduler.py` | `maybe_run_mitre_on_startup()` (lines 411–429) |
| 8a | `database.py` | `get_mitre_technique_count`, `get_atlas_technique_count` |
| 8b | `scheduler.py` | If either &lt; 10: `create_task(run_weekly_mitre_refresh)` |
| 9 | `main.py` | FastAPI app ready — all `/api/*` routes accept traffic |
| Shutdown | `scheduler.py` | `stop_scheduler()` on lifespan exit (line 82) |

**Note:** There is no separate `run_migrations()` function — migrations run inside `init_db()`.

Flowchart: [`docs/diagrams/startup.mermaid`](docs/diagrams/startup.mermaid)

---

## 2. Request Lifecycle

### A. User opens BRIEF tab

| Hop | File | Function | API |
|---|---|---|---|
| 1 | `main.jsx` | `ReactDOM.createRoot().render()` | — |
| 2 | `App.jsx` | `useEffect` → `fetchStats({ frameworks })` when AI stack/profile declared | `GET /api/stats?frameworks=` |
| 3 | `App.jsx` | `loadHealth()` + 60s interval | `GET /api/health?tz=` |
| 4 | `App.jsx` | Renders `MainApp` when `activeTab === 'feed'` | — |
| 5 | `StatsRow.jsx` | Displays stats prop | — |
| 6 | `TimelineHeatmap.jsx` | `fetchStatsTimeline(90)` | `GET /api/stats/timeline?days=90` |
| 7 | `CVEFeed.jsx` | `loadPage(1)` on mount / filter change | `GET /api/cves?...` |
| 8 | `Sidebar.jsx` | `fetchKEVDeadlines`, `fetchTopTechniques` | `GET /api/kev/deadlines`, `GET /api/techniques/top` |
| 9 | `CVECard.jsx` | Renders each CVE; `calculateRiskScore` with momentum 0 | — |

### B. User clicks CVE card — drawer data loads

| Hop | File | Function | API |
|---|---|---|---|
| 1 | `App.jsx` | `handleSelectCVE` → `setSelectedCVE(cve)` | — |
| 2 | `App.jsx` | `fetchCVE(cve_id)` | `GET /api/cves/{id}` |
| 3 | `main.py` | `get_cve` — DB read + Sploitus/GN/OTX/OSV/CIRCL | External feeds |
| 4 | `DetailDrawer.jsx` | Opens (`cve` prop set) | — |
| 5 | `DetailDrawer.jsx` | `useEffect` → `fetchCVESentences` | `GET /api/cves/{id}/sentences` |
| 6 | `DetailDrawer.jsx` | `useEffect` → `fetchCVEEpssHistory` | `GET /api/cves/{id}/epss-history` |
| 7 | `DetailDrawer.jsx` | `useEffect` → `fetchCVEMomentum` | `GET /api/cves/{id}/momentum` |
| 8 | `DetailDrawer.jsx` | `useEffect` → `fetchCVECorrelation` | `GET /api/cves/{id}/correlation` |
| 9 | `DetailDrawer.jsx` | `useMemo` → `calculateRiskScore` with momentum | Client only |
| 10 (lazy) | `DetailDrawer.jsx` | Related tab → `fetchCVERelated` | `GET /api/cves/{id}/related` |
| 11 (lazy) | `DetailDrawer.jsx` | Detect tab → `fetchCVEDetection` | `GET /api/cves/{id}/detection` |
| 12 | `DrawerAtlasSection.jsx` | Renders ATLAS techniques + case studies when `has_ai_context` | Data from `GET /api/cves/{id}` |

Sequence: [`docs/diagrams/flow_cve_detail.mermaid`](docs/diagrams/flow_cve_detail.mermaid)

### B2. User clicks AI/ML alerts stat chip

| Hop | File | Function | API |
|---|---|---|---|
| 1 | `StatsRow.jsx` | Fifth chip visible when `showAiAlerts` and `ai_ml_alerts > 0` | — |
| 2 | `App.jsx` | `handleAiAlertsClick` → `setActiveTab('feed')` + filter state | — |
| 3 | `App.jsx` | Sets `ai_context_only`, `ai_profile_match`, `ai_profile` from asset profile / stack | — |
| 4 | `CVEFeed.jsx` | `loadPage(1)` on filter change | `GET /api/cves?frameworks=&ai_context_only=true` |
| 5 | `cveFilters.js` | Maps `ai_profile_match` → `frameworks` query param | — |

### F. User opens Incidents & News tab

| Hop | File | Function | API |
|---|---|---|---|
| 1 | `App.jsx` | `activeTab === 'incidents'` → renders `CaseStudies` | — |
| 2 | `CaseStudies.jsx` | `loadCaseStudyFeed()` on mount | `GET /api/case-studies/feed?atlas_limit=80` |
| 3 | `case_study_feed.py` | `fetch_combined_case_study_feed` — `asyncio.gather` RSS + ATLAS | `feeds/incident_news.py`, `database.get_atlas_case_studies` |
| 4 | `caseStudyFeed.js` | Session cache (5 min); `filterCaseStudyCards` for search | — |
| 5 | `CaseStudies.jsx` | Renders news + ATLAS cards; per-source errors in banner | — |

### C. User submits IOC lookup

| Hop | File | Function | API / service |
|---|---|---|---|
| 1 | `IOCLookup.jsx` | Form submit handler | — |
| 2 | `api.js` | `lookupIOC(value, type, {greynoise})` | `POST /api/ioc/lookup` |
| 3 | `main.py` | `ioc_lookup` | — |
| 4 | `database.py` | `get_ioc_cache` (6h) | `ioc_cache` |
| 5 | `enrichment/ioc.py` | `lookup_ioc` | VT, AbuseIPDB, GN, MB, UH, OTX |
| 6 | `database.py` | `set_ioc_cache` | `ioc_cache` |
| 7 | `IOCLookup.jsx` | Renders per-source panels | — |

Sequence: [`docs/diagrams/flow_ioc_lookup.mermaid`](docs/diagrams/flow_ioc_lookup.mermaid)

### D. Scheduled NVD sync fires

| Hop | File | Function |
|---|---|---|
| 1 | APScheduler | Triggers `run_nvd_incremental_sync` |
| 2 | `scheduler.py` | `_nvd_lock` — skip if already running |
| 3 | `database.py` | `resolve_nvd_sync_watermark` |
| 4 | `feeds/nvd.py` | `fetch_nvd_cve_updates` (retry on 429) |
| 5 | `database.py` | `upsert_cves`, `set_nvd_sync_watermark` |
| 6 | `database.py` | `strip_auto_generated_summaries`, `backfill_display_fields`, `backfill_has_poc` |
| 7 | `feeds/extended.py` | `enrich_cves_extended` (Sploitus, CIRCL) |
| 8 | `scheduler.py` | Log duration seconds |

Sequence: [`docs/diagrams/flow_nvd_sync.mermaid`](docs/diagrams/flow_nvd_sync.mermaid)

### E. User generates PDF report

| Hop | File | Function | API |
|---|---|---|---|
| 1 | `DetailDrawer.jsx` | `handlePdfConfirm` | — |
| 2 | `pdfReport.js` | `downloadSingleCvePdf` | — |
| 3 | `pdfAiSummary.js` | `loadPdfExecutiveSummary` | `POST /api/ai/summary` |
| 4 | `ai/summary.py` | `generate_executive_summary` → Groq/Anthropic/template | External AI |
| 5 | `pdfReport.js` | jsPDF layout + optional html2canvas sparkline | — |
| 6 | Browser | File download | — |

Sequence: [`docs/diagrams/flow_pdf_report.mermaid`](docs/diagrams/flow_pdf_report.mermaid)

---

## 3. Error Propagation Map

| Journey | Failure point | User sees | Logged? | Auto-retry? |
|---|---|---|---|---|
| BRIEF feed load | `GET /api/cves` network/5xx | CVEFeed error banner | Browser console | User refresh |
| BRIEF feed load | Empty DB | Empty list | — | Startup ingest if &lt;10 CVEs |
| CVE detail | Sploitus/GN/OTX/OSV/CIRCL fail | Empty section in drawer | `logger.error` in `main.py` | No |
| CVE detail | `fetchCVE` 404 | Drawer with minimal CVE id | — | No |
| Drawer sentences | `/sentences` fail | Section empty | — | No |
| Drawer momentum | `/momentum` fail | Score without momentum (silent) | — | No |
| IOC lookup | VT 429 / no key | Partial result, `sources_missing` | `logger.warning` | No |
| IOC lookup | All sources fail | Error field in result | Yes | No |
| NVD sync | NVD 429 | Sync continues after backoff | `logger.warning` | Yes (5× in nvd.py) |
| NVD sync | Exception mid-run | Prior data intact | `logger.error` | Next scheduler tick |
| PDF AI summary | Groq+Anthropic fail | Template summary text | `logger.warning` | No (template fallback) |
| Investigation summary | AI provider fail | Template fallback text | `logger.warning` | No (template fallback) |
| Incidents feed | RSS or ATLAS partial fail | Cards from successful sources + `errors[]` | Per-source in response | Client retries on tab revisit |
| AI/ML alerts | No frameworks in profile/stack | Chip hidden (`ai_ml_alerts` = 0) | — | No |

---

## 4. State Management Map

| Feature | State location | Persistence |
|---|---|---|
| CVE feed list | `CVEFeed.jsx` `useState` (cves, page, filters) | Session only |
| Selected CVE / drawer | `App.jsx` `selectedCVE` | Session only |
| Filters | `App.jsx` `filters` + `Hero` stack | `localStorage` stack via `cveFilters.js` |
| Asset profile | `AssetProfileContext.jsx` | Session + file import/export (not server) |
| CPE match scores | `AssetProfileContext` from `POST /api/cves/match` | Session only |
| Investigation thread | `InvestigationContext.jsx` | Session only |
| IOC lookup result | `IOCLookup.jsx` `useState` | Session; server `ioc_cache` 6h |
| IOC history | `IOCLookup.jsx` `useState` | Session only (no localStorage) |
| Momentum cache | `momentumCache.js` module Map | Session until reload |
| Theme | `Header.jsx` + `main.jsx` | `localStorage` `briefr_theme` |
| Timezone | `Header.jsx` + `timezone.js` | `localStorage` `briefr_timezone` |
| Last visit marker | `CVEFeed.jsx` | `localStorage` `briefr_last_visit` |
| Active tab | `App.jsx` `activeTab` | Session only |
| Case study cards | `caseStudyFeed.js` module cache | 5 min session cache; `GET /api/case-studies/feed` loads RSS + ATLAS in parallel |
| AI/ML alert count | `App.jsx` `stats` | Refreshed on stack/profile change via `briefr-profile-change` event |

---

## 5. Scheduler Execution Timeline

Defaults from `backend/.env.example`. Scheduler TZ: `Asia/Kolkata` (`SCHEDULER_TIMEZONE`).  
OTX and Correlation jobs use their own timezone env vars (default IST).

```
24h timeline (Asia/Kolkata defaults)
──────────────────────────────────────────────────────────────────
00:00        │ EPSS may run (every 6h: 00,06,12,18)
00:00–24:00  │ NVD incremental every 1h (████ recurring)
00:00–24:00  │ KEV sync every 15m (█ recurring)
00:00–24:00  │ Incident RSS refresh every 4h (██ recurring)
01:00        │ ████ Nightly correlation (CORRELATION_HOUR=1 IST)
02:00        │ ████ OTX nightly correlation (OTX_CORRELATION_HOUR=2 IST)
02:00 Sun    │ ████ Weekly MITRE+ATLAS (MITRE_REFRESH_HOUR=2 sched TZ)
──────────────────────────────────────────────────────────────────
```

**Overlap protection:** `_nvd_lock`, `_kev_lock`, `_epss_lock`, `_mitre_refresh_lock`, `_otx_lock`, `_correlation_lock` — concurrent duplicate runs log warning and return `False`.

**Startup catch-up:** If `cves` count &lt; 10, full ingest runs once in background regardless of schedule.
