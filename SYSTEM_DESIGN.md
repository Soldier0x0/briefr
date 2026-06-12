# BRIEFR System Design

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Version:** 1.1 (beta)  
**Last updated:** 2026-06-08  
**Source of truth:** `/workspace` codebase — see [`Beta V1.2.md`](Beta%20V1.2.md) for near-future roadmap

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
│ FastAPI (main.py + routers/) — /api/* — ~30 endpoints                       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React + Vite (frontend/src)                                                 │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│ BRIEF tab        │ IOC LOOKUP tab   │ INCIDENTS tab    │ DetailDrawer       │
│ CVEFeed.jsx      │ IOCLookup.jsx    │ CaseStudies.jsx  │ (global overlay)   │
│ → GET /cves      │ → POST /ioc      │ → combined feed  │ → 6+ sub-routes    │
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
| `audit_log` | Written by `POST /api/refresh*` and backup/restore (admin UI reads in V1.4) | — (not exposed yet) |

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
2. **Server enrichment (serial awaits in handler):** Sploitus exploits, GreyNoise scans, OTX pulses, OSV packages, CIRCL merge (`routers/cves.py:get_cve`).
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

### E. Incidents & News feed (snapshot-served)

1. **UI:** `CaseStudies.jsx` calls `loadCaseStudyFeed()` → `GET /api/case-studies/feed?atlas_limit=80`.
2. **Client cache:** `caseStudyFeed.js` holds a 5-minute session cache; a `meta.warming` response (snapshot still being built) is never pinned in that cache.
3. **Scheduler builds, API reads:** `run_incident_feed_refresh` (every `INCIDENT_FEED_REFRESH_MINUTES`, default 30; first run ~20s after boot) calls `case_study_feed.build_incident_feed_snapshot()`:
   - `fetch_all_incident_news_parallel(db)` — 6 RSS sources fetched concurrently via `asyncio.gather` (network only); cache reads/writes stay sequential on **one** SQLite connection (30 min `feed_cache` per source)
   - `_load_atlas_cards(db)` — ATLAS case studies from `atlas_case_studies` table
   - Combined result persisted to `feed_cache` under `incident_feed:snapshot` with `generated_at`
4. **Request path:** `get_incident_feed()` is a pure snapshot read (<50ms warm). A cold miss never blocks — it schedules a background build and returns `meta.warming=true` with empty data.
5. **Meta:** responses include `meta.refreshed_at`, `meta.stale` (older than 2× refresh interval), `meta.warming`. `/api/health` exposes `feeds.incidents.last_refresh` + `stale`.
6. **Merge:** Cards sorted by `publishedAt` descending; per-source errors collected in `errors[]` without failing the whole feed. Cache-write contention (e.g. during bootstrap ingest) degrades gracefully — parsed items are kept in the snapshot and persisted on the next cycle.
7. **Editorial filter:** `incident_news.py` excludes non-security RSS items by title pattern (e.g. Dark Reading **"Name That Toon"** contest). Filter applies on parse and when serving cached rows; malformed cache entries are skipped defensively.

Flowchart: [`docs/diagrams/startup.mermaid`](docs/diagrams/startup.mermaid) (scheduler registration) · Client journey: [`APPLICATION_EXECUTION_MAP.md`](APPLICATION_EXECUTION_MAP.md) §2.C

---

## 4. Design Decisions & Trade-offs

### Resilient outbound HTTP (`resilient_client.py`)

All scheduler-driven intel sources (NVD, KEV, EPSS, MITRE, ATLAS, OSV, 6× RSS) share one pooled `httpx.AsyncClient` with:

- **Retries:** transport errors and retryable statuses (5xx, 429 with `Retry-After` respect) retried with exponential backoff.
- **Circuit breaker per source:** `CIRCUIT_FAILURE_THRESHOLD` consecutive failures (default 3) open the circuit for `CIRCUIT_COOLDOWN_SECONDS` (default 60); calls fail fast with `CircuitOpenError` so one dead source cannot stall a sync cycle. Plain 4xx responses do not trip the circuit (the source is reachable).
- **Health registry:** `/api/health` → `feeds.sources` exposes `last_success`, `last_failure`, `last_error`, `consecutive_failures`, `circuit_open` per source.
- **NVD exception:** keeps its bespoke 429/key-rejection retry logic but uses the pooled client and reports into the same health registry.
- **Quota-billed sources** (VirusTotal, AbuseIPDB, GreyNoise) use `retries=0` — a failed call is never retried automatically, so quota cannot be burned by the retry loop. Circuit breakers still apply.
- **CIRCL negative caching:** failed/missing lookups are cached for 24h (`circl_miss:*` keys) so a rate-limited upstream is not re-hammered with the same IDs on every sync cycle.

All outbound modules are migrated: scheduler feeds (NVD, KEV, EPSS, MITRE, ATLAS, RSS) and on-demand enrichment (`enrichment/ioc.py`, `feeds/extended.py` — Sploitus/GreyNoise/MalwareBazaar/URLhaus/CIRCL, `feeds/otx.py`, `feeds/osv.py`).

### Audit log + auth direction (V1.2 decision, 2026-06-11)

- **Audit:** `audit_log` table (actor, action, target, timestamp) written by manual `POST /api/refresh*` calls and by backup runs/restores (`backup/manager.py`, actor = `system`, sync + best-effort so a locked DB never fails a backup or admin action). Admin pane reads it in V1.4.
- **Auth direction:** BRIEFR ships as a self-hosted platform with a **built-in app login** before public release (not enterprise SSO / edge-auth based). Until then the beta runs on a trusted private network; `BRIEFR_ADMIN_API_KEY` optionally gates refresh routes. `audit_log.actor` stays empty for request-driven actions until login lands (`request.state.user_email` is the wiring hook). A Cloudflare-Access JWT middleware was prototyped and dropped — see `docs/ROADMAP.md` amendments.

### SQLite over PostgreSQL

- **Why:** Single-user beta, zero ops overhead, `aiosqlite` async support, `feed_cache` + `ioc_cache` adequate at current scale.
- **Mitigations (v1.1):** `PRAGMA journal_mode=WAL`, `busy_timeout=30000`, and `connect(timeout=30)` in `database.get_db()`. Combined Incidents feed loads RSS + ATLAS on a **single connection** (`case_study_feed.py`) to avoid `database is locked` under concurrent scheduler writes.
- **Trade-off:** No horizontal scaling or multi-writer safety — acceptable for v1.1 single-server deploys.

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
- **Trade-off:** Resolved in v1.2 — router split complete: `main.py` is app wiring only (~130 lines); endpoints live in `routers/` (refresh, health, atlas, ioc, cves, meta) with `settings.py` + `dependencies.py`. Routers are included in the pre-split registration order (snapshot-tested) so the OpenAPI spec is unchanged.

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
| Circuit Breaker | MISSING | `resilient_client.py` planned Beta V1.2 (NVD has retry only today) |
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
| CIRCL (vulnerability.circl.lu) | `feeds/extended.py` | Extra refs, CAPEC (CVE 5.x records) | `CIRCL_API_KEY` optional (`X-API-KEY`) | Rate-limited; 7d hit cache + 24h negative cache | No merge |
| MalwareBazaar | `feeds/extended.py` | Hash metadata | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| URLhaus | `feeds/extended.py` | Domain malware URLs | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| Groq | `ai/summary.py` | Executive summary | `GROQ_API_KEY` | Console quota | Falls back to Anthropic/template |
| Anthropic | `ai/summary.py` | Executive summary | `ANTHROPIC_API_KEY` | Console quota | Falls back to template |
| GitHub | `detection/rule_sources.py` | Sigma/Elastic rule search | `GITHUB_TOKEN` (optional) | 60/hr anon | `[]` rules |
| RSS (6 sources) | `feeds/incident_news.py` | News cards (editorial titles filtered) | — | Per-feed | Per-source error in `errors[]` |

RSS sources defined in `feeds/incident_sources.py`: The Hacker News, Bleeping Computer, Krebs, Dark Reading, Schneier, CISA Advisories. Non-security editorial items (e.g. Dark Reading cartoon contests) are excluded via `EXCLUDED_NEWS_TITLE_PATTERNS` in `incident_news.py`.

---

## 7. Known Limitations — v1.1 Beta

- **Single-user SQLite** — no concurrent write safety under heavy parallel writes.
- **No app-level authentication yet** — built-in app login ships before the public self-hosted release; the beta instance runs on a trusted private network with an optional `X-BRIEFR-Admin-Key` gate on `POST /api/refresh*`.
- **`POST /api/investigation/summary`** — legacy route; delegates to `generate_investigation_summary` → `generate_executive_summary`. Prefer `POST /api/ai/summary` for new clients.
- **Risk weights duplicated** in `backend/scoring/risk.py` and `frontend/src/scoring/riskScore.js` — shared config planned for Beta V1.2.
- **No circuit breakers** on external APIs (timeouts only).
- **`DetailDrawer.jsx` — ~1,500 lines** — maintenance risk; v1.2 split planned.
- **No request ID tracking** across request lifecycle.

---

## 8. Beta V1.2 roadmap

Near-future engineering and product intent lives in **[`Beta V1.2.md`](Beta%20V1.2.md)** — themes include router split, `services/` layer, `resilient_client.py`, shared risk config, frontend hooks, auth, and E2E CI. Update that document when V1.2 phases ship.

---

## Related documentation

- [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — contributor entry point, local dev, tests, troubleshooting
- [`Beta V1.2.md`](Beta%20V1.2.md) — roadmap and planned work
- [`API_REFERENCE.md`](API_REFERENCE.md) — endpoint catalog
- [`TECHNICAL_INVENTORY.md`](TECHNICAL_INVENTORY.md) — schema, scheduler, stack
- [`APPLICATION_EXECUTION_MAP.md`](APPLICATION_EXECUTION_MAP.md) — startup and request journeys
- [`FOLDER_STRUCTURE_GUIDE.md`](FOLDER_STRUCTURE_GUIDE.md) — file-by-file map
- [`docs/diagrams/`](docs/diagrams/) — Mermaid diagrams (render in GitHub, VS Code, Notion)
