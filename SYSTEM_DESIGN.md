# BRIEFR System Design

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Version:** 1.1 (beta)  
**Last updated:** 2026-06-07  
**Source of truth:** `/workspace` codebase at commit audited for v1.1

---

## 1. Overview

BRIEFR is a CVE intelligence platform that ingests vulnerability data from NVD, CISA KEV, EPSS, and MITRE sources into a local SQLite database, enriches records with threat-context feeds (OTX, Sploitus, GreyNoise, OSV, CIRCL), and presents them through a React analyst UI with IOC lookup, risk scoring, correlation, and PDF export.

It is built for security analysts, small security teams, and solo researchers who need a single-pane view of what is exploitable, what is in KEV, and what matches their stack — without standing up a full SIEM or commercial threat-intel platform.

The core problem it solves is **analyst time**: aggregating scattered CVE metadata, exploitation signals, ATT&CK mapping, and IOC enrichment into one fast, dark-mode workflow that runs on a single server with optional API keys.

---

## 2. Architecture

### Four-layer model

```
Feed Ingestion  →  SQLite DB  →  FastAPI API  →  React UI
(scheduler.py)     (database.py)   (main.py)      (frontend/src)
```

### ASCII architecture diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│ NVD API      │ CISA KEV     │ EPSS CSV     │ MITRE STIX   │ ATLAS YAML     │
│ Sploitus     │ GreyNoise    │ VirusTotal   │ AbuseIPDB    │ OTX            │
│ OSV.dev      │ CIRCL        │ MalwareBazaar│ URLhaus      │ Groq/Anthropic │
│ GitHub API   │ RSS x6       │              │              │                │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │              │                │
       ▼              ▼              ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ APScheduler (scheduler.py) — 7 jobs                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. NVD incremental      → cves, sync_state, cve_change_history, feed_cache  │
│ 2. KEV metadata         → kev_deadlines, cves.is_kev, summaries             │
│ 3. EPSS scores          → cves.epss_score, epss_history                     │
│ 4. MITRE+ATLAS weekly   → mitre_*, atlas_*, cve_*_map, has_ai_context       │
│ 5. OTX nightly          → otx_cve_pulses, otx_pulse_iocs, feed_cache        │
│ 6. Incident RSS (4h)    → feed_cache (incident_rss:*)                       │
│ 7. Correlation nightly  → correlation_*, feed_cache, otx_pulse_iocs         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SQLite (briefr.db) — 21 tables — see TECHNICAL_INVENTORY.md                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI (main.py) — /api/* — 1,344 lines, ~30 endpoints                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React + Vite (frontend/src)                                                 │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│ BRIEF tab        │ IOC LOOKUP tab   │ INCIDENTS tab    │ DetailDrawer       │
│ CVEFeed.jsx      │ IOCLookup.jsx    │ CaseStudies.jsx  │ (global overlay)   │
│ → GET /cves      │ → POST /ioc      │ → news + atlas   │ → 6+ sub-routes    │
│ CVECard.jsx      │                  │                  │                    │
│ StatsRow.jsx     │                  │                  │                    │
│ TimelineHeatmap  │                  │                  │                    │
│ Sidebar.jsx      │                  │                  │                    │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

Mermaid source: [`docs/diagrams/architecture.mermaid`](docs/diagrams/architecture.mermaid)

### DB tables → primary API readers

| Table(s) | Primary endpoints | Frontend consumers |
|---|---|---|
| `cves` | `GET /api/cves`, `GET /api/cves/{id}`, `GET /api/stats` | CVEFeed, CVECard, DetailDrawer, StatsRow, TimelineHeatmap |
| `kev_deadlines` | `GET /api/kev/deadlines`, embedded in CVE detail | Sidebar, DetailDrawer sentences |
| `epss_history` | `GET /api/cves/{id}/epss-history`, momentum | DetailDrawer EPSS sparkline |
| `mitre_techniques`, `cve_technique_map` | `GET /api/techniques/top`, CVE `techniques` field | Sidebar, DetailDrawer Intel tab |
| `atlas_*`, `cve_atlas_map` | `GET /api/atlas/*`, `GET /api/cves/{id}` (per-CVE fields) | DrawerAtlasSection, CaseStudies (global list) |
| `otx_*` | CVE detail, correlation, IOC lookup | DetailDrawer Intel tab, IOCLookup |
| `feed_cache`, `ioc_cache` | Internal — speeds enrichment | Transparent to UI |
| `correlation_*` | `GET /api/cves/{id}/correlation` | DetailDrawer correlation section |
| `cve_exploits` | Via Sploitus loader in CVE detail | DetailDrawer Intel tab |
| `cve_change_history` | `GET /api/changes` | — (API only) |
| `api_usage` | `GET /api/usage`, `GET /api/usage/ioc` | IOCLookup quota display |

---

## 3. Data Flow

### A. CVE lifecycle

1. **Ingest:** `scheduler.run_nvd_incremental_sync` → `feeds/nvd.py:fetch_nvd_cve_updates` (NVD REST 2.0, watermark in `sync_state`).
2. **Persist:** `database.upsert_cves` → `cves` table (`ON CONFLICT DO UPDATE`), optional `cve_change_history` rows.
3. **Post-process:** strip auto-summaries, backfill display fields, `enrich_cves_extended` (Sploitus/CIRCL).
4. **List:** `GET /api/cves` builds SQL from `_build_cve_filters`, paginates (`page`, `limit` max **50**).
5. **UI:** `CVEFeed.jsx:loadPage` → `fetchCVEs` → `CVECard.jsx` renders each row.

Sequence diagram: [`docs/diagrams/flow_cve_feed.mermaid`](docs/diagrams/flow_cve_feed.mermaid)

### B. CVE detail drill-down

1. **Card click:** `App.jsx:handleSelectCVE` sets list CVE, then `fetchCVE(cve_id)` → `GET /api/cves/{id}`.
2. **Server enrichment (serial awaits in handler):** Sploitus exploits, GreyNoise scans, OTX pulses, OSV packages, CIRCL merge (`main.py:912–971`).
3. **Drawer opens** with enriched CVE; parallel client fetches on `cve_id` change:
   - `GET /api/cves/{id}/sentences` (immediate)
   - `GET /api/cves/{id}/epss-history` (immediate)
   - `GET /api/cves/{id}/momentum` (immediate)
   - `GET /api/cves/{id}/correlation?sector=` (immediate)
4. **Lazy tab fetches:**
   - `GET /api/cves/{id}/related` — only when **Related** tab active
   - `GET /api/cves/{id}/detection` — only when **Detect** tab first opened
5. **OTX pulse IOCs:** loaded via CVE detail `otx_pulses`; pulse IOC drill-down uses `GET /api/otx/pulses/{id}/iocs`.

**ATLAS wiring:** `GET /api/cves/{id}` returns `has_ai_context`, `atlas_techniques`, and `atlas_case_studies` via `database.get_atlas_techniques_for_cve` / `get_atlas_case_studies_for_cve` for `DrawerAtlasSection.jsx`.

Sequence diagram: [`docs/diagrams/flow_cve_detail.mermaid`](docs/diagrams/flow_cve_detail.mermaid)

### C. IOC lookup

1. **Input:** `IOCLookup.jsx` validates type (`ip` | `hash` | `domain`), optional GreyNoise opt-in.
2. **API:** `POST /api/ioc/lookup` → `get_ioc_cache` (6h) or `enrichment/ioc.lookup_ioc`.
3. **Per-type enrichment (sequential within shared httpx client, not asyncio.gather):**
   - **IP:** VirusTotal → AbuseIPDB → (optional) GreyNoise → OTX
   - **Hash:** VirusTotal → MalwareBazaar
   - **Domain:** VirusTotal → URLhaus → OTX
4. **Cache write:** `set_ioc_cache` with `ON CONFLICT DO UPDATE`.
5. **UI:** per-source result cards and template sentences from `templates/intelligence.py`.

Sequence diagram: [`docs/diagrams/flow_ioc_lookup.mermaid`](docs/diagrams/flow_ioc_lookup.mermaid)

### D. Risk scoring (v1.1b)

**Client-side** (`frontend/src/scoring/riskScore.js:calculateRiskScore`):

| Component | Weight |
|---|---|
| Asset profile match | 0.35 |
| KEV status | 0.25 |
| EPSS | 0.15 |
| Exploit availability | 0.10 |
| CVSS | 0.10 |
| Momentum | 0.05 |

**Momentum** fetched lazily from `GET /api/cves/{id}/momentum` → `scoring/risk.py:calculate_momentum` (EPSS trend, OTX pulse recency, recent KEV, rapid exploitation signals). Cached in `momentumCache.js` for card arrows.

**Display:** `DetailDrawer.jsx` Overview tab — `RiskScoreBreakdown` (not Correlation tab). Cards use momentum `0` until drawer fetch updates cache.

**Duplication debt:** same weights/logic mirrored in `backend/scoring/risk.py` (server momentum only today).

---

## 4. Design Decisions & Trade-offs

### SQLite over PostgreSQL

- **Why:** Single-user beta, zero ops overhead, `aiosqlite` async support, `feed_cache` + `ioc_cache` adequate at current scale.
- **Trade-off:** No concurrent write safety, no horizontal scaling — acceptable for v1.1.

### APScheduler over Celery/Redis

- **Why:** No message broker; embedded in FastAPI process; sufficient for 7 jobs (`scheduler.py:start_scheduler`).
- **Trade-off:** Jobs lost on process restart (mitigated by `maybe_run_on_startup` bootstrap when CVE count &lt; 10); no distributed workers.

### Plain JSX + CSS over component library

- **Why:** Full control over dark terminal aesthetic; smaller bundle (`package.json` — React + Vite only).
- **Trade-off:** More custom CSS; no pre-built accessibility primitives.

### Client-side risk scoring

- **Why:** Zero API calls for score on cards; instant recalculation when asset profile changes.
- **Trade-off:** Weights duplicated in Python (`scoring/risk.py`) and JavaScript (`scoring/riskScore.js`) — v1.2 will serve single config.

### Monolithic `main.py` (intentional v1.1)

- **Why:** Single-developer velocity; no premature abstraction.
- **Trade-off:** 1,344 lines, ~10 responsibilities — v1.2 router + service split planned.

### Monolithic `database.py` (intentional v1.1)

- **Why:** Single-file DAL easy to audit; no ORM.
- **Trade-off:** 1,681 lines — v1.2 `repositories/` extraction planned.

---

## 5. System Design Principles Status

| Principle | v1.1 Status | v1.2 Plan |
|---|---|---|
| Separation of Concerns | PARTIAL | `services/` layer (cve, enrichment, ioc, detection) |
| Single Responsibility | PARTIAL | Router split; `DetailDrawer.jsx` (1,516 lines) component extraction |
| Repository Pattern | MISSING | `repositories/` from `database.py` |
| Dependency Injection | MISSING | FastAPI `Depends()` for DB + `settings.py` |
| Circuit Breaker | PARTIAL | `resilient_client.py` wrapper (NVD has retry only today) |
| Idempotency | PARTIAL | Upserts + scheduler locks; fix `cve_change_history` duplicate inserts |
| Caching Strategy | PARTIAL | `feed_cache`/`ioc_cache` exist; add React Query + stats cache |
| API Consistency | PARTIAL | v1.2 response envelope (`data` + `meta`) |
| Config Management | PARTIAL | `settings.py`; centralize weights and TTLs |
| Observability | PARTIAL | Plain logging; add request IDs + structured JSON |

---

## 6. External Dependencies Map

| Service | Used by | Data provided | Key env var | Free tier | Failure behaviour |
|---|---|---|---|---|---|
| NVD | `feeds/nvd.py`, scheduler | CVE records, CVSS, CPE | `NVD_API_KEY` (optional) | 50 req/30s with key | Sync aborts; logs error |
| CISA KEV | `feeds/kev.py` | KEV catalog JSON | — | Unrestricted | Returns `[]` |
| EPSS | `feeds/epss.py` | Exploit prediction scores | — | Unrestricted | Returns `{}` |
| MITRE STIX | `feeds/mitre.py` | Techniques, groups, CVE maps | — | Unrestricted | Weekly job fails; logs |
| ATLAS YAML | `feeds/atlas.py` | AI/ML techniques, case studies | `ATLAS_YAML_URL` | Unrestricted | Weekly job fails; logs |
| Sploitus | `feeds/extended.py` | Public exploits | — | Unpublished | `[]` / `None` |
| GreyNoise | `feeds/extended.py`, IOC | IP classification | `GREYNOISE_API_KEY` | 50/week | `[]` or unknown record |
| VirusTotal | `enrichment/ioc.py` | IP/hash/domain reputation | `VIRUSTOTAL_API_KEY` | 500/day | Empty VT fields |
| AbuseIPDB | `enrichment/ioc.py` | IP abuse score | `ABUSEIPDB_API_KEY` | 1000/day | Skipped if no key |
| OTX | `feeds/otx.py` | Pulses, IOCs | `OTX_API_KEY` | 10k/month | `[]`; nightly skipped if unset |
| OSV.dev | `feeds/osv.py` | Package affected versions | — | Unrestricted | `[]` |
| CIRCL | `feeds/extended.py` | Extra refs, CAPEC | — | Unrestricted | No merge |
| MalwareBazaar | `feeds/extended.py` | Hash metadata | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| URLhaus | `feeds/extended.py` | Domain malware URLs | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| Groq | `ai/summary.py` | Executive summary | `GROQ_API_KEY` | Console quota | Falls back to Anthropic/template |
| Anthropic | `ai/summary.py` | Executive summary | `ANTHROPIC_API_KEY` | Console quota | Falls back to template |
| GitHub | `detection/rule_sources.py` | Sigma/Elastic rule search | `GITHUB_TOKEN` (optional) | 60/hr anon | `[]` rules |
| RSS (6 sources) | `feeds/incident_news.py` | News cards | — | Per-feed | Per-source error in `errors[]` |

RSS sources defined in `feeds/incident_sources.py`: The Hacker News, Bleeping Computer, Krebs, Dark Reading, Schneier, CISA Advisories.

---

## 7. Known Limitations — v1.1 Beta

- **Single-user SQLite** — no concurrent write safety under heavy parallel writes.
- **No authentication** on any `/api/*` endpoint.
- **`POST /api/investigation/summary`** — legacy route; delegates to `generate_investigation_summary` → `generate_executive_summary`. Prefer `POST /api/ai/summary` for new clients.
- **Risk weights duplicated** in `backend/scoring/risk.py` and `frontend/src/scoring/riskScore.js`.
- **No circuit breakers** on external APIs (timeouts only).
- **`DetailDrawer.jsx` — 1,516 lines** — maintenance risk; v1.2 split planned.
- **No request ID tracking** across request lifecycle.
- **Dead code:** `frontend/src/utils/riskScore.js` (v1.1a, unused), `Phase2Block` in DetailDrawer (defined, never rendered), `AIThreats.jsx` (not imported).

---

## 8. v1.2 Refactor Roadmap

| Phase | Scope |
|---|---|
| **1** | `settings.py` + `dependencies.py` + split `main.py` into `routers/` |
| **2** | `services/cve_service.py`, `services/enrichment_service.py`, `services/ioc_service.py` |
| **3** | `repositories/` extracted from `database.py` (1,681 lines) |
| **4** | Frontend hooks (`useCVEFeed`, `useCveDrawerData`, `useIOCLookup`) + DetailDrawer component split |
| **5** | Structured logging, request IDs, API response envelope, shared HTTP resilience |

---

## Related documentation

- [`API_REFERENCE.md`](API_REFERENCE.md) — endpoint catalog
- [`TECHNICAL_INVENTORY.md`](TECHNICAL_INVENTORY.md) — schema, scheduler, stack
- [`APPLICATION_EXECUTION_MAP.md`](APPLICATION_EXECUTION_MAP.md) — startup and request journeys
- [`FOLDER_STRUCTURE_GUIDE.md`](FOLDER_STRUCTURE_GUIDE.md) — file-by-file map
- [`docs/diagrams/`](docs/diagrams/) — Mermaid diagrams (render in GitHub, VS Code, Notion)
