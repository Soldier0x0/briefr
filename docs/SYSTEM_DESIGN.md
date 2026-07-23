# BRIEFR System Design

Copyright © 2026 Sai Harsha Vardhan. Licensed under the Business Source License 1.1 (`SPDX-License-Identifier: BUSL-1.1`); see the repository `LICENSE` for the full text.

**Version:** 1.5
**Last updated:** 2026-07-22
**Source of truth:** `/workspace` codebase and [`docs/PRODUCT_STATUS.md`](PRODUCT_STATUS.md). Archive snapshots are historical context only.

---

## 1. Overview

BRIEFR is a CVE intelligence platform that ingests vulnerability data from NVD, CISA KEV, EPSS, MITRE/ATLAS, Vulnrichment, cvelistV5, exploit indexes, CPE catalog data, RSS news, and optional threat-intel feeds into PostgreSQL, enriches records with scoring/correlation/retrieval context, and presents them through a React analyst UI with IOC lookup, Forge detection workflows, Admin operations, wallboard, and PDF export.

It is built for security analysts, small security teams, and solo researchers who need a single-pane view of what is exploitable, what is in KEV, and what matches their stack — without standing up a full SIEM or commercial threat-intel platform.

The core problem it solves is **analyst time**: aggregating scattered CVE metadata, exploitation signals, ATT&CK mapping, and IOC enrichment into one fast, dark-mode workflow that runs on a single server with optional API keys.

---

## 2. Architecture

### Four-layer model

```
Feed Ingestion  →  PostgreSQL  →  FastAPI API  →  React UI
(scheduler.py)     (asyncpg)      (main.py)      (frontend/src)
```

### ASCII architecture diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│ NVD API      │ CISA KEV     │ EPSS CSV     │ MITRE STIX   │ ATLAS YAML     │
│ Sploitus     │ GreyNoise    │ VirusTotal   │ AbuseIPDB    │ OTX            │
│ OSV.dev      │ CIRCL        │ MalwareBazaar│ URLhaus      │ Groq/Cerebras/ │
│ VulnCheck    │ ThreatFox    │              │              │ OpenRtr/Gemini │
│ GitHub API   │ RSS x5       │ NVD CPE API  │              │                │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │              │                │
       ▼              ▼              ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ APScheduler (scheduler.py) — 26 normal jobs + 3 registration-gated optional jobs │
├─────────────────────────────────────────────────────────────────────────────┤
│ Ingest: nvd_incremental_sync, kev_metadata_sync, epss_score_sync,           │
│ weekly_mitre_refresh, vulnrichment_snapshot_sync, cvelistv5_incremental_sync│
│ Intel: otx_nightly_correlation, otx_continuous_sync*, threatfox_sync,       │
│ vulncheck_kev_sync, ioc_retro_match, exploit_sources_sync*                  │
│ Detection/retrieval: nightly_correlation, embeddings_backfill,              │
│ detection_context_sync, detection_context_llm*, kev_backlog_reconcile       │
│ Product/stack: llm_product_extraction, catchup_tick, cpe_catalog_sync       │
│ Ops: incident_feed_refresh, scheduled_backup, backup_deadman_check,         │
│ watchlist_monitor_alerts, api_key_health_check, session_cleanup,            │
│ cache_retention_cleanup, resource_metrics_sample, atlas_version_check       │
│ Startup one-shots: full ingest when cves <10; deferred summary, EPSS        │
│ history, exploit-source, and MITRE/ATLAS maintenance when data is sparse    │
│ * registered only when the corresponding feature flag is enabled             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL 16 + asyncpg pool; SQLite is only the zero-config test/dev fallback│
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI (main.py + routers/) — session-gated /api/* router packages         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React + Vite (frontend/src)                                                 │
├──────────────┬──────────────┬──────────────┬──────────────┬───────────────┤
│ BRIEF tab    │ FEED tab     │ IOC LOOKUP   │ INCIDENTS    │ Forge tab     │ Admin/Security │ DetailDrawer │
│ MorningBrief │ CVEFeed.jsx  │ IOCLookup    │ CaseStudies  │ Forge.jsx     │ Posture       │ (overlay)    │
│ BriefCharts  │ CVECard.jsx  │              │              │               │               │
│ WhatChanged  │ FilterBar    │              │              │               │               │
│ TimelineHeat │ + Sidebar    │              │              │               │               │
│ StatsRow     │              │              │              │               │               │
│ Hero stack   │              │              │              │               │               │
└──────────────┴──────────────┴──────────────┴──────────────┴───────────────┘
```

Mermaid sources: master graph [`docs/diagrams/system-graph.mermaid`](diagrams/system-graph.mermaid) · component view [`docs/diagrams/architecture.mermaid`](diagrams/architecture.mermaid)

### DB tables → primary API readers

| Table(s) | Primary endpoints | Frontend consumers |
|---|---|---|
| `cves` | `GET /api/cves`, `GET /api/cves/{id}`, `GET /api/cves/{id}/drawer`, `GET /api/stats`, `GET /api/brief`, `GET /api/search/semantic` | CVEFeed, CVECard, DetailDrawer, StatsRow (BRIEF tab), TimelineHeatmap (BRIEF tab), MorningBrief, FEED hybrid results |
| `kev_deadlines` | `GET /api/kev/deadlines`, `kev_due_date` on list/export/detail, `GET /api/brief` | Sidebar (urgent sort), CVECard due chip, DetailDrawer sentences, MorningBrief |
| `epss_history` | `GET /api/cves/{id}/epss-history`, momentum | DetailDrawer EPSS sparkline |
| `mitre_techniques`, `cve_technique_map` | `GET /api/techniques/top`, CVE `techniques` field | Sidebar, DetailDrawer Intel tab |
| `atlas_*`, `cve_atlas_map` | `GET /api/atlas/*`, `GET /api/cves/{id}` (per-CVE fields) | DrawerAtlasSection, CaseStudies (global list) |
| `otx_*` | CVE detail, correlation, IOC lookup | DetailDrawer Intel tab, IOCLookup |
| `feed_cache`, `ioc_cache` | Internal — snapshot/TTL cache; `GET /api/usage/ioc` for IOC usage aggregate | Transparent to UI except IOC quota display |
| `correlation_*` | `GET /api/cves/{id}/correlation`, drawer bundle, `GET /api/correlation/clusters` | DetailDrawer correlation section, Forge campaigns, wallboard |
| `cve_exploits` | Via Sploitus loader in CVE detail | DetailDrawer Intel tab |
| `cve_change_history` | `GET /api/changes`, `GET /api/brief` (EPSS movers) | WhatChangedPanel (BRIEF tab), MorningBrief |
| `api_usage`, `api_call_events` | `GET /api/usage/ioc`, `GET /api/admin/api-usage/metering` | IOCLookup quota display, Admin API keys metering |
| `audit_log` | Written by `POST /api/refresh*`, backup/restore, all admin actions | `GET /api/admin/audit-log` |
| `hunt_packs` (+ `mitre_techniques`, `cve_technique_map`) | `GET /api/forge/coverage`, `GET /api/hunt-packs/{technique_id}`, `POST /api/hunt-packs/generate` | Forge tab (coverage map + hunt pack panel) |
| `watchlist` | `GET/POST/DELETE /api/watchlist`, `DELETE /api/watchlist/snoozes`; join on `GET /api/cves` for sort/filter | CVECard + DetailDrawer pin; WATCHLIST feed filter; monitor alerts |
| `ioc_watchlist`, `threatfox_iocs` | `GET/POST/DELETE /api/ioc/watchlist`; scheduler `threatfox_sync`, `ioc_retro_match` | IOCLookup watchlist panel |
| `embeddings`, `cve_embeddings` | `GET /api/search/semantic`, `GET /api/cves/{id}/related`, `GET /api/admin/retrieval/health` | FEED hybrid search, Related tab, Admin AI Operations |
| `software_catalog`, `stack_backfill_*` | `GET /api/stack/catalog/suggest`, `GET /api/stack/coverage`, `POST /api/stack/backfill/agree`, `GET/POST /api/stack/backfill/{run_id}` | Asset wizard typeahead, FEED stack coverage/backfill banner |
| `procrastinate_jobs` | `GET /api/admin/jobs/outbound`, `POST /api/admin/jobs/outbound/ping` | Admin Scheduler durable outbound jobs panel |
| `api_key_health:*` feed cache, `resource_metrics`, `user_notifications` | `GET/POST /api/admin/api-keys/health*`, `GET /api/admin/resources`, `/api/me/notifications/*` | Admin API key health, Resources page, notification bells |
| `scoring/threat.py` + `environment.py` + `priority.py` + `ssvc.py` + `POST /api/cves/{id}/risk` | ADR-002 Threat / Environment / Operational Priority + W4 SSVC annotation (backend sole engine) | `DetailDrawer` via `fetchCVERisk()` — display-only |
| `scoring/risk.py` | Legacy v1.1b blend returned as `legacy_risk_v11b` only | Formula display helpers in `riskScore.js` |
| `scoring/risk.py` constants | `GET /api/config/risk` — v1.1b weights, no DB | `riskScore.js` weight prefetch (startup) |

### Primary endpoint surface

| Area | Live endpoints |
|---|---|
| CVE/feed | `GET /api/cves`, `GET /api/cves/export`, `GET /api/cves/{id}`, `GET /api/cves/{id}/drawer`, `POST /api/cves/{id}/risk`, `GET /api/cves/{id}/detection`, `GET /api/cves/{id}/correlation`, `GET /api/cves/{id}/related`, `POST /api/cves/match` |
| Search/retrieval | `GET /api/search/semantic` (`mode=hybrid` default; keyword fallback; stack/severity/KEV filters) and `GET /api/admin/retrieval/health` |
| Analyst shell | `GET /api/brief`, `GET /api/stats*`, `GET /api/changes`, `GET /api/kev/deadlines`, `GET /api/case-studies/feed`, `GET /api/wallboard` |
| Forge/detection | `GET /api/forge/coverage`, `GET/POST/DELETE /api/hunt-packs*`, `GET/POST /api/detection-backlog*`, `POST /api/proof/run` |
| Stack | `GET/PUT /api/me/stack`, `GET /api/stack/catalog/suggest`, `GET /api/stack/coverage`, `POST /api/stack/backfill/agree`, `GET/POST /api/stack/backfill/{run_id}` |
| Admin | `routers/admin/` package under `/api/admin`: diagnostics, storage/db explorer/resources, scheduler/catch-up/outbound jobs, API key health/metering, config, webhooks, feed health, AI operations, database, audit/logs, notifications, data ops |

---

### Risk score (ADR-002 + legacy v1.1b) — backend canonical

`POST /api/cves/{cve_id}/risk` is the **sole engine** for displayed Threat,
Environment, and Operational Priority (ADR-002). Threat is asset-independent;
CISA `is_kev` applies a Threat floor of 80; VulnCheck-only exploitation does
**not** get that floor. Environment never folds phantom points into Threat.
Legacy v1.1b blend remains on the response as `legacy_risk_v11b` until a later
deprecation PR.

**EPSS → OP (W3):** after the base Threat×Environment table, OP may escalate one
band when Threat is HIGH/MED, EPSS ≥ 0.5, and Environment ≥ POSSIBLE; rising EPSS
(momentum `epss_rising`) may escalate base P3→P2 under the same env gate. These
rules are additive, never change Threat, and never de-escalate KEV/CRIT P1.
Missing EPSS counts as 0. See ADR-002 addendum.

**SSVC annotation (W4):** `POST /risk` also returns `ssvc`
(`scoring/ssvc.py`, version `ssvc-annotation-1.0`) with
`outcome` ∈ {Act, Attend, Track*, Track}, `factors`, and explainability `path`.
Mapped from Threat/KEV/exploit (exploitation), CVSS (technical impact), and
Environment tier (+ optional profile `internet_facing` / `criticality` when
present). SSVC does **not** change Threat or replace Operational Priority.
Documentation crosswalk (OP primary): **P1↔Act, P2↔Attend, P3↔Track*, P4↔Track**.
Overview shows a small SSVC chip beside the OP band when `riskScore.ssvc` is present.
Vulnrichment CISA SSVC in the drawer remains a separate ingested section.

**Exposure / criticality flags (W5):** optional My Stack profile fields
`internet_facing` (bool), `criticality`
(`MISSION_CRITICAL`|`IMPORTANT`|`SUPPORTING`), and optional
`privileged_service` / `ot_safety` (bool) affect **OP and/or SSVC only** —
never Threat. Absent flags preserve pre-W5 bands. OP rule (version
`operational-priority-1.2`): CISA KEV path (Threat CRIT or `is_kev`) +
`internet_facing=True` + Environment ≠ `NO_MATCH` → prefer P1 when the
working band would otherwise be P2 (e.g. CRIT×POSSIBLE/WEAK). SSVC
`mission_prevalence` already consumes `internet_facing` / `criticality`
when set. Asset wizard Environment step exposes these as optional scoring
controls (distinct from qualitative `environment.internetFacing` /
`environment.criticality` labels).

Optional `profile` / `assets` in the POST body personalise Environment (CPE
match via `matching/cpe.py`, fuzzy graduation via `scoring/asset_match.py`).
Momentum is computed server-side in the same request via `calculate_momentum()`.

`GET /api/config/risk` still exposes weight constants for the drawer's formula
display (`score × weight × 100 = points`). `frontend/src/scoring/riskScore.js`
prefetches weights at startup and provides **UI helpers only** (colors, hero
summary text, correlation OP merge, SSVC display) — it does **not** recompute Threat or
v1.1b totals for displayed numbers (W2 / F1.3).

The Overview tab presents DESCRIPTION first, then a twin-grid row with the
Operational Priority hero beside the full Environment Relevance panel, followed
by WHY THIS MATTERS, SEVERITY CONTEXT (CVSS), KEY EXPLOITATION SIGNALS,
EXPLOITATION, AFFECTED PRODUCTS/CWE, REMEDIATION, REFERENCES, and enrichment
sections (CAPEC, SSVC, OSV).

**Correlation escalation (temporary FE merge):** when the drawer loads
correlation after `/risk`, `applyCorrelationEscalationToRiskScore` may bump
Operational Priority one band (P3→P2 / P2→P1) using the same rules as
`derive_operational_priority(..., corr_escalation=True)`. This client merge is
**temporary** until `/risk` (or the drawer bundle) applies correlation
server-side; Threat is never modified by correlation.

| Component (legacy v1.1b only) | Weight |
|---|---|
| Asset profile match | 0.35 |
| KEV status | 0.25 |
| EPSS | 0.15 |
| Exploit availability | 0.10 |
| CVSS | 0.10 |
| Momentum | 0.05 |

KEV component raw score uses CISA KEV recency tiers when `is_kev`; when not on
CISA KEV, `is_vulncheck_exploited` (VulnCheck sync) contributes **0.72** — below
full KEV tiers but above zero. That raw feeds Threat additive math; the **80
floor applies only for CISA KEV**.

**Momentum (card arrows):** `GET /api/cves/{id}/momentum` remains available for
the momentum tab/signals; cached in `momentumCache.js` for CVECard arrows after
drawer open.

**Display:** `DetailDrawer` Overview tab fetches `POST /api/cves/{id}/risk` when
the CVE or asset profile changes and renders `threat` / `environment` /
`operational_priority` / `ssvc` from that response.

### A. CVE lifecycle

1. **Ingest:** `scheduler.run_nvd_incremental_sync` → `feeds/nvd.py:fetch_nvd_cve_updates` (NVD REST 2.0, watermark in `sync_state`).
2. **Persist:** `database.upsert_cves` → `cves` table (`ON CONFLICT DO UPDATE`), optional `cve_change_history` rows. Ingest batches upserts via `executemany` in 500-row chunks (`db/cve.py`).
3. **Post-process (DB only):** strip auto-summaries, backfill display fields / PoC flags, **commit and close** the ingest connection. Source HTTP must not share this write transaction (see §4 “SQL vs source I/O”).
4. **Extended enrich (best-effort):** fresh connection → `enrich_cves_extended` (Sploitus/CIRCL) with commit-before-HTTP (`db/txn_boundaries.commit_before_source_io`) and per-lookup commits; optional embeddings ingest tail on another fresh connection. Watermark already advanced — enrich failure does not roll back upserts.
5. **List:** `GET /api/cves` builds SQL from `_build_cve_filters`, paginates (`page`, `limit` max **50**). `CVE_SELECT` uses a `LEFT JOIN kev_deadlines` (no correlated KEV subquery). `total` is cached 45s per filter set (`read_cache.py`). Postgres search benefits from Alembic `012_cve_trgm_search` GIN indexes on description/summary/affected_products.
6. **UI:** `CVEFeed.jsx:loadPage` → `fetchCVEs` → `CVECard.jsx` renders each row. Scroll “Showing X–Y” is tracked by leaf component `FeedVisibleRange.jsx` (rAF-throttled) so scrolling does not re-render the card list (`React.memo` on `CVECard`).

Sequence diagram: [`docs/diagrams/flow_cve_feed.mermaid`](diagrams/flow_cve_feed.mermaid)

### B. CVE detail drill-down

1. **Card click:** `App.jsx:handleSelectCVE` sets list CVE, then `fetchCVE(cve_id)` → `GET /api/cves/{id}`.
2. **Server path:** `_load_cve_detail_from_db` reads core rows and releases the pool connection; Sploitus, OTX, OSV, and CIRCL enrich via `asyncio.gather` with short-lived connections per task (`routers/cves/detail.py:get_cve`). GreyNoise remains on-demand only (`GET /api/cves/{id}/greynoise-scans`).
3. **Drawer opens** with enriched CVE; client fetches:
   - `POST /api/cves/{id}/risk` (immediate — canonical Threat / Environment / OP / SSVC; optional profile body)
   - `GET /api/cves/{id}/drawer?sector=` (immediate bundle for sentences, EPSS history, related CVEs, correlation, momentum, and related news). Each bundle sub-fetch uses its own DB connection so asyncpg calls can run in parallel.
4. **Lazy tab fetches / on-demand pivots:**
   - `GET /api/cves/{id}/related` — only when **Related** tab active
   - `GET /api/cves/{id}/detection` — only when **Detect** tab first opened
   - `GET /api/cves/{id}/greynoise-scans` — only when the GreyNoise action is triggered
5. **OTX pulse IOCs:** loaded via CVE detail `otx_pulses`; pulse IOC drill-down uses `GET /api/otx/pulses/{id}/iocs`.

**ATLAS wiring:** `GET /api/cves/{id}` returns `has_ai_context`, `atlas_techniques`, and `atlas_case_studies` via `database.get_atlas_techniques_for_cve` / `get_atlas_case_studies_for_cve` for `DrawerAtlasSection.jsx`.

Sequence diagram: [`docs/diagrams/flow_cve_detail.mermaid`](diagrams/flow_cve_detail.mermaid)

### C. IOC lookup

1. **Input:** `IOCLookup.jsx` validates type (`ip` | `hash` | `domain`), optional GreyNoise opt-in.
2. **API:** `POST /api/ioc/lookup` → `get_ioc_cache` (6h) or `enrichment/ioc.lookup_ioc`.
3. **Per-type enrichment (sequential within shared httpx client, not asyncio.gather):**
   - **IP:** VirusTotal → AbuseIPDB → (optional) GreyNoise → OTX
   - **Hash:** VirusTotal → MalwareBazaar
   - **Domain:** VirusTotal → URLhaus → OTX
4. **Cache write:** `set_ioc_cache` with `ON CONFLICT DO UPDATE`.
5. **UI:** per-source result cards and template sentences from `templates/intelligence.py`.

Sequence diagram: [`docs/diagrams/flow_ioc_lookup.mermaid`](diagrams/flow_ioc_lookup.mermaid)

### C2. IOC watchlist + retro-match (V1.5 Phase 5)

1. **UI:** `IOCLookup.jsx` watchlist panel — signed-in users save IPs/hashes/domains with optional labels via `POST /api/ioc/watchlist`; list/remove via `GET` / `DELETE`.
2. **ThreatFox mirror:** `threatfox_sync` (interval, default 24h) fetches the Abuse.ch ThreatFox export when `ABUSECH_AUTH_KEY` is set → `threatfox_iocs` local mirror (`feeds/threatfox.py`, `db/threatfox.py`).
3. **Retro-match:** `ioc_retro_match` (nightly cron, default 04:00) joins `ioc_watchlist` against local `otx_pulse_iocs` and `threatfox_iocs` (`ioc/retro_match.py`) — no outbound IOC enrichment on the match path.
4. **Alerts:** matches dispatch optional `ioc_watchlist_hit` webhooks (dedupe `{user_id}:{ioc_value}:{source}`).

### D. Risk scoring (ADR-002)

See **Risk score (ADR-002 + legacy v1.1b) — backend canonical** above. Implementation:
`backend/scoring/threat.py`, `backend/scoring/environment.py`, `backend/scoring/priority.py`,
`backend/scoring/ssvc.py`, `backend/scoring/risk.py`, `backend/scoring/asset_match.py`,
`POST /api/cves/{cve_id}/risk` in `routers/cves/intel.py`.

### E. Incidents & News feed (snapshot-served)

1. **UI:** `CaseStudies.jsx` calls `loadCaseStudyFeed()` → `GET /api/case-studies/feed?atlas_limit=80`.
2. **Client cache:** `caseStudyFeed.js` holds a 5-minute session cache; a `meta.warming` response (snapshot still being built) is never pinned in that cache.
3. **Scheduler builds, API reads:** `run_incident_feed_refresh` (every `INCIDENT_FEED_REFRESH_MINUTES`, default 30; first run ~20s after boot) calls `case_study_feed.build_incident_feed_snapshot()`:
   - `fetch_all_incident_news_parallel(db)` — 5 RSS sources fetched concurrently via `asyncio.gather` (network only); cache reads/writes stay bounded through the shared DB adapter (30 min `feed_cache` per source)
   - `_load_atlas_cards(db)` — ATLAS case studies from `atlas_case_studies` table
   - Combined result persisted to `feed_cache` under `incident_feed:snapshot` with `generated_at`
4. **Request path:** `get_incident_feed()` is a pure snapshot read (<50ms warm). A cold miss never blocks — it schedules a background build and returns `meta.warming=true` with empty data.
5. **Meta:** responses include `meta.refreshed_at`, `meta.stale` (older than 2× refresh interval), `meta.warming`. `/api/health` exposes `feeds.incidents.last_refresh` + `stale`.
6. **Merge:** Cards sorted by `publishedAt` descending; per-source errors collected in `errors[]` without failing the whole feed. Cache-write contention (e.g. during bootstrap ingest) degrades gracefully — parsed items are kept in the snapshot and persisted on the next cycle.
7. **Editorial filter:** `incident_news.py` excludes non-security RSS items by title pattern (e.g. Dark Reading **"Name That Toon"** contest). Filter applies on parse and when serving cached rows; malformed cache entries are skipped defensively.

Flowchart: [`docs/diagrams/startup.mermaid`](diagrams/startup.mermaid) (scheduler registration) · Client journey: [`docs/archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) §2.C

### F2. Analyst Brief charts (Recharts, V1.5)

1. **UI:** `BriefCharts.jsx` on the BRIEF tab (below the morning brief, above the heatmap / What changed row). Chart panels lazy-load Recharts through BRIEFR's shared `ChartShell`; Chart.js has been removed from the runtime dependency set.
2. **Panels (2):**
   - **Top KEV vendors** — `GET /api/stats/top-vendors` → Recharts horizontal bar chart with an adjacent accessible data table.
   - **Top EPSS movers** — `GET /api/changes?field=epss_score&since_hours=168&limit=50` → compact table (CVE ID, dim severity dot, 7-day EPSS sparkline from `GET /api/cves/{id}/epss-history`, delta badge). Row click opens the CVE drawer via `onSelectCVE`.
3. **Refresh:** parallel fetch on mount + 5-minute poll (`POLL_MS`); per-CVE EPSS history fetched when movers list changes; cancellation guards on unmount.
4. **Theming:** charts use semantic design tokens via shared UI chart helpers and respect reduced motion through the global motion system.
5. **Layout:** two-column grid at ≥1100px; stacks to one column on narrower viewports.
6. **Severity hierarchy (feed + sidebar):** CVE cards and sidebar KEV rows use left accent bars driven by KEV due-date urgency (full `--red` only for overdue / due today / due tomorrow). CVSS, EPSS%, PoC, and published-age metadata use neutral/dim chip styling so they do not compete with real urgency signals. Shared description truncation: `CveDescriptionClamp.jsx` (used by `CVECard` and `MorningBrief` action-queue rows).

### F2b. BRIEF vs FEED tab layout (V1.3)

1. **BRIEF tab (landing):** `Hero.jsx` (serif headline + stack bar + BRIEF apply), `StatsRow.jsx` (four KPI tiles + optional AI/ML alerts), unified `MorningBrief.jsx` action queue (single list from `action_queue` with reason/due-window filter chips; `CveDescriptionClamp` per row; KEV histogram bucket clicks set client-side due-window filter), `BriefCharts.jsx`, then side-by-side `TimelineHeatmap.jsx` + `WhatChangedPanel.jsx` (≥901px).
2. **FEED tab:** Compact utility chrome only — `FilterBar.jsx` (`CVE FEED // {total}` line + stack input row + quick filters/search) and paginated `CVEFeed.jsx` with `Sidebar.jsx` (KEV deadlines + top techniques unchanged). No Hero, StatsRow, or TimelineHeatmap on FEED.
3. **Action queue filters:** Client-side only — chips filter `reasons[]` on the already-fetched `action_queue`; KEV histogram `onBucketClick` applies a UTC `kev_due_date` window on the same list (no extra API call).

### F. Forge — detection coverage + hunt packs (V1.3 MVP)

1. **UI:** `Forge.jsx` (FORGE tab) loads `GET /api/forge/coverage` on mount; the
   optional "MY STACK ONLY" toggle re-fetches with the saved stack from
   Postgres `user_preferences.stack_terms` (Feed tab, per login user). Optional
   operator override: `BRIEFR_STACK_TERMS` in admin config. Legacy
   `briefr_stack` localStorage migrates to the API on first login (Wave 2 PR 4).
2. **Coverage map (`routers/forge.py`):** one grouped query over
   `cve_technique_map ⋈ cves` (stack filter as a subselect on `cves`) +
   `hunt_packs` counts + `mitre_techniques` metadata. Status per technique:
   `yours` (saved pack exists) → `community` (bundled template library covers
   the technique — `detection/sigma_generator.py` + `detection/siem_queries.py`)
   → `gap`. Entirely local: no outbound HTTP, no caching layer needed.
3. **Technique click:** `GET /api/hunt-packs/{technique_id}` returns technique
   metadata, saved packs, the template SIEM baseline, log patterns, and up to
   20 linked CVEs (KEV first, then EPSS, then recency).
4. **CVE inventory + generate pack:** Hunt-pack detail UI leads with the
   linked-CVE inventory (`linked_cves` + `linked_cve_total`, truncated
   descriptions). **Generate pack** is a secondary action on a linked CVE →
   `POST /api/hunt-packs/generate` builds the Sigma rule + SIEM queries from
   the template library, derives priority from KEV/CVSS/EPSS, and upserts into
   `hunt_packs` (`UNIQUE(technique_id, cve_id)` — idempotent regeneration).
   The UI refetches coverage so the technique flips to `yours`.
5. **Boundary:** SigmaHQ community rules are mirrored into Postgres by
   `sigmahq_index_sync` and served CVE-exact from the local index on Detect
   (`find_sigma_rules`) and Forge generate (index YAML when present). Live
   GitHub Sigma search is fallback only when the index is empty; Elastic
   search remains GitHub-backed on Detect. **V1.5 rule proof
   bench** (`POST /api/proof/run`, Forge hunt pack panel) validates saved Sigma
   rules against pasted log lines — file-based, no live SIEM. **V1.5 KEV detection
   backlog** (`GET /api/detection-backlog`, Forge Backlog tab) surfaces stack-matched
   KEV CVEs whose ATT&CK techniques are coverage gaps; rows are created on KEV sync
   and weekly reconcile; optional `kev_backlog` webhook. **V1.5 IOC watchlist**
   (`GET/POST/DELETE /api/ioc/watchlist`, IOC tab panel) persists per-user IOCs;
   nightly retro-match vs OTX + ThreatFox mirrors; optional `ioc_watchlist_hit`
   webhook. **VulnCheck exploited tier** (`vulncheck_kev_sync` when
   `VULNCHECK_API_KEY` set) sets `cves.is_vulncheck_exploited` for risk v1.1b KEV
   component scoring below CISA KEV. HyperDX provisioning
   remains out of scope.
6. **Forge redesign FR-1/FR-2 (2026-07, `docs/planning/specs/forge-redesign.md`):**
   `Forge.jsx` (~1090 lines) split into a thin shell + view components under
   `frontend/src/components/forge/` (`CoverageView`, `ScenariosView`,
   `CampaignsView`, `BacklogView`, `LibraryView`, `HuntPackRail`, `shared`) —
   behavior-preserving move, same fetch logic and endpoints per view.
   - **Shell layout:** three panels — left nav (220px, five views + coverage
     counts + MY STACK ONLY toggle) / center workspace (one view at a time) /
     persistent Hunt Pack rail (320px). The rail mounts once at the shell
     level and renders whichever technique is selected regardless of which
     view set the selection — fixes the pre-FR-2 gap where Campaigns/Backlog
     had no rail and a generated pack's result was invisible.
   - **URL state:** Analyst shell owns `?tab=brief|feed|ioc|atlas|forge`
     (`shellUrlState.js` / `selectAppTab`). Forge adds
     `?view=coverage|scenarios|campaigns|backlog|library` +
     `&technique=`/`&pack=`, two-way via `useSearchParams` (`Forge.jsx`
     `writeUrl`) — every view/selection change rewrites the URL
    with `pushContext` for intentional navigation, and a `searchParams`
    effect mirrors browser back/forward into state. Hygiene cleanup
    (`replaceHygiene`) is reserved for stale params. Admin sidebar owns
    `?p=` the same way (clicks push history; first-paint/stale cleanup
    replaces). Legacy Forge
     links with `view=` and no `tab=` still resolve to the Forge tab.
   - **Hunt Pack Library (FR-1 backend, FR-2 frontend):** `LibraryView.jsx`
     is an `AdminDataGrid` (`pages/admin/shared/AdminDataGrid.jsx`) over
     `GET /api/hunt-packs` (technique/priority/KEV/title filters, 250ms
     debounce) with delete (`DELETE /api/hunt-packs/{id}`, `ConfirmModal`,
     hard delete + `audit_log` entry from FR-1) and a JSON export (client-side
     blob download of the pack's Sigma/SIEM/log-pattern content — no PDF
     dependency; PDF export via `utils/huntPackPdf.js` is FR-3 scope). Row
     click opens the pack in the persistent rail by `technique_id`. `list_hunt_packs`
     gained an additive `LEFT JOIN cves` (wrapped around the existing
     filtered/paginated subquery, so the original WHERE/params are untouched)
     to surface `is_kev` for the Library's KEV column — the FR-1 endpoint had
     shipped without it even though forge-redesign.md §3.1 specified it.
   - `AdminDataGrid` gained optional `onRowClick`/`activeRowKey` props
     (backward-compatible, default `null`) for the Library's row-click-to-open
     behavior; no other `AdminDataGrid` caller is affected.
   - **Responsive:** mirrors `threat-modeling-security-architecture.md` §3.1 —
     rail pinned ≥1280px, slide-in overlay with backdrop + `Escape`-to-close
     960–1279px, left nav collapses to a horizontal wrap ≤959px.
7. **Forge redesign FR-3 (2026-07, live-data enrichment + PDF export):**
   closes the `forge-redesign.md` program (FR-1→FR-3 all shipped).
   - **Case-study cross-links:** MITRE ATLAS (`atlas_case_studies`,
     `atlas_techniques`) and MITRE ATT&CK Enterprise (`mitre_techniques`,
     Forge's own taxonomy) are separate technique ID spaces — a case study's
     `techniques` list is ATLAS IDs, not ATT&CK ones. The only shared key is
     the CVE, so `db/metadata.py::get_case_study_counts_by_technique` /
     `get_case_studies_for_technique` join `atlas_case_studies.cve_ids`
     (JSON) against `cve_technique_map.cve_id` in Python — the ATLAS table
     is MITRE's small bundled dataset, not a live feed, so this avoids an
     N+1 across every coverage-map technique. `GET /api/forge/coverage`
     gains `case_study_count` per technique (Coverage map chip); `GET
     /api/hunt-packs/{technique_id}` gains a `case_studies` array (Hunt Pack
     rail section) — both additive, no schema change.
   - **KEV backlog notifications:** `detection/backlog.py`'s
     `process_new_kev_backlog` / `reconcile_kev_backlog` (both scheduler-only
     — CLAUDE.md danger zone 6, never on the request path) call
     `notifications/emit.py::emit_kev_backlog_notification` for each newly
     created backlog row, one `user_notifications` insert per active analyst
     (`entity_type="kev_backlog"`, `dedupe_key=f"kev_backlog:{cve_id}:
     {technique_id}"`). `NotificationBell.jsx` deep-links `kev_backlog`
     clicks to `/?tab=forge&view=backlog` (legacy `?view=backlog` still works).
   - **CWE/EPSS:** `list_hunt_packs` (Library) and `get_hunt_pack` (rail)
     extend their existing `cves` join/query to also select `cwe_ids`,
     `cvss_score`, `epss_score` — no new query, same columns the
     pack-generate flow already reads. Library grid gained CWE/EPSS columns;
     the rail's saved-pack header shows the same line.
   - **PDF export:** `utils/huntPackPdf.js` mirrors `pdfReport.js`'s jsPDF
     pattern (lazy `import('jspdf')`, `exportCommon.js` layout constants/
     branding, local `drawSection`/`drawCodeBlock`/footer helpers — not
     extracted into a shared module, matching `pdfReport.js`'s own choice
     not to share those with `investigationPdf.js`). Renders technique,
     Sigma rule, SIEM queries, log patterns, notes, CVE/KEV/CWE/EPSS badges,
     and related case studies (when known) with the BRIEFR branding footer.
     Wired from both `LibraryView.jsx` (row EXPORT PDF — supersedes the FR-2
     JSON-blob placeholder) and `HuntPackRail.jsx` (per-pack EXPORT PDF,
     which additionally has technique name/tactic and case studies loaded).

### F. Watchlist — pin + monitor alerts (V1.5)

Signed-in users keep their pinned CVEs in `watchlist`; legacy snooze data is cleaned up by the UI.

1. **Persistence:** `watchlist` table (`cve_id`, `state`, `snooze_until`, `created_at`) retained for migration compatibility; the live UI exposes pin/watchlist only.
2. **API:** `GET/POST/DELETE /api/watchlist` (`routers/watchlist.py`). POST validates the CVE exists; snooze default is 7 days (`snooze_days` 1–365).
3. **Feed behaviour (`GET /api/cves`):** `LEFT JOIN` active watchlist rows. Pinned CVEs sort first. `watchlist_only=true` returns watchlist rows for the feed quick filter.
4. **UI:** `useWatchlist` hook loads pins on mount and clears legacy snoozes via `DELETE /api/watchlist/snoozes`. Pin on `CVECard` and `DetailDrawer`; **WATCHLIST** quick-filter chip. Mutations bump a version counter so `CVEFeed` refetches without a full page reload. No `localStorage`. Snooze controls were removed from the UI (API retained for migration).
5. **Monitor alerts:** `watchlist_monitor_alerts` checks pinned CVEs hourly for KEV / EPSS / PoC changes and emits optional `watchlist_alert` webhooks.

### H. Security posture — corpus + Admin shell + live sections (TM-0→TM-6)

1. **Corpus (TM-1, extended TM-3/TM-4/TM-5):** `backend/security_architecture/corpus/` — versioned YAML, `origin: generated | curated | live` per record. Generated files (`components.yaml`, `api_inventory.yaml`, `scheduler_jobs.yaml`, `db_tables.yaml`, `self_stack.yaml`, and TM-4's `graphs/architecture.json`) are emitted by `scripts/generate_security_corpus.py` from live route/scheduler/schema/dependency-manifest introspection and drift-tested in CI (`test_security_architecture_corpus.py::test_committed_corpus_has_no_drift`, plus TM-4's `test_committed_architecture_graph_has_no_drift`). `self_stack.yaml` (TM-3, spec §4.5) holds one record per dependency term parsed from `backend/requirements.txt` and `frontend/package.json`, plus declared runtime components (`postgresql`, `nginx`) — a new dependency changes this file and fails the drift check until regenerated. `graphs/architecture.json` (TM-4) holds nodes for every component/job/table already in the other generated files (no parallel node list to hand-sync — a corpus test asserts the node id set equals that union exactly) plus `component -> table` `references_table` edges, derived by regexing each router source file for table names appearing directly after a SQL keyword (`FROM`/`JOIN`/`INTO`/`UPDATE`/`DELETE FROM`) — anchored to real SQL syntax so a table named e.g. `users` can't spuriously match an unrelated identifier or comment elsewhere in the file. No x/y layout ships in this file: presentation isn't a code fact, so it doesn't belong in a drift-checked generated artifact — `ArchitectureGraphSection.jsx` computes a deterministic cluster+index grid layout at render time. Curated files: `controls.yaml` got its first real security-review seed in TM-3 (10 controls); TM-4 seeded `trust_boundaries.yaml` with its first 2 real boundaries (Browser→API→Database, BRIEFR→external services), each linking `related_ids` to real generated component/table ids and TM-3's curated controls. TM-5 seeded `security_decisions.yaml` (2 records mapping the two real ADRs in `docs/decisions/` — `decision`/`alternatives`/`tradeoffs`/`consequences` drawn directly from each ADR's own sections, not invented), `abuse_cases.yaml` (6 entries, each `current_protection` field citing real code as evidence — webhook SSRF, webhook replay, rate-limit bypass, SQL injection, log secret leakage, plus one honestly-open `broken-authorization-single-tier-session` finding with no mitigating control), and `reviews.yaml` (3 curated review-pass records documenting the program's own TM-3/TM-4/TM-5 security-review passes). `risks.yaml` stays intentionally empty — no real risk-register judgment pass has happened; the Risk Register's only non-empty content is `live` self-stack rows. `corpus_loader.py` validates required fields, `origin`, and cross-file `related_ids` at load time (mtime-cached); `security_architecture/graphs.py` separately loads/caches `graphs/architecture.json` (JSON, not YAML — different schema shape, not an entity-record list). `live` rows (self-stack risk-register entries, and TM-5's `reviews` section audit-log events) are never stored in a file — computed at read time by `security_architecture/merge.py` and merged into `/section/{risks,reviews}` responses.
2. **Staleness decay (TM-5, spec §4.1):** `security_architecture/merge.py::annotate_stale` adds a `stale: boolean` field to every row returned by `/section/{id}` — `true` for curated records whose `review_date` is more than `STALE_WINDOW_DAYS` (90) in the past; always `false` for generated/live rows (they carry no review-date judgment call). This one function is the single source of truth for three consumers that must never disagree: the frontend STALE badge (`RiskRegisterSection.jsx`, `DecisionsSection.jsx`, `AbuseCasesSection.jsx`, `ReviewHistorySection.jsx`), the Overview "Controls Active" ratio (`merge.py::controls_active_ratio` excludes stale controls from both numerator and denominator — the module's one real percentage a curated record feeds, spec §5.1), and the risk-register PDF export's "contains N stale records" footer disclaimer (`utils/securityArchitecturePdf.js`). `GET /stale` (new TM-5 endpoint) lists every stale curated record across every section, tagged with its `section`/`type`, for the Overview "Stale Records" tile drill-through.
3. **API (`routers/security_architecture.py`):** the API still lives at `/api/security-architecture/*`. `GET /manifest` returns the corpus version + `sections[]` (the nav source of truth; includes `mitre_attack`, which has no corpus file — it's served entirely from live DB data). `GET /overview` returns raw counts plus a `tiles[]` array — every tile value is a `len()`, exact field match, or a visible ratio over corpus/live rows (no scoring, spec's "no arithmetic invented" rule), each carrying a `section`/`filter` drill target; TM-3 adds `mitre_detection_coverage` and `self_cve_exposure` tiles, TM-4 adds `unreviewed_endpoints`, TM-5 adds `stale_records` and turns `controls` into the "Controls Active" ratio. `GET /mitre` reuses `routers.forge.build_coverage_map`; `GET /threat-scenarios` wraps `threat_model.scenarios.build_threat_scenarios`; `GET /graph/architecture`, `GET /graph/attack-surface`, `GET /context/{node_id}`, `GET /section/{id}`, `GET /stale`, `GET /search`, and `GET /frameworks/{id}` back the Admin Security posture page.
4. **UI (`frontend/src/pages/admin/SecurityPosturePage.jsx`):** Security posture is under Admin at `/admin?p=securityposture`; `securityposture` is also allowlisted for analyst read-only access. The old top-level ARCH header tab was removed. Legacy `/security-architecture` URLs redirect to Admin Security posture and preserve known `section`, `node`, and filter params. The page keeps the corpus shell sections, graph context rail, global search, PDF export, and TM-6 framework workspaces, with all state round-tripped through `?section=&type=&status=&severity=&origin=&node=`.
5. **PDF export (TM-5, spec §5.16):** `utils/securityArchitecturePdf.js` follows the existing jsPDF pattern exactly (`utils/huntPackPdf.js`/`pdfReport.js` — lazy `import('jspdf')`, shared `exportCommon.js` branding constants, local page-layout helpers; no new dependency). Three exports: Overview posture snapshot (every tile verbatim, no client-side arithmetic), Risk Register (the exact rows currently in view), and a selected Threat Scenario. Every export's footer carries the corpus version, generated timestamp, and — when any included row's `stale` flag is `true` — an explicit "Contains N stale records" disclaimer, so a PDF is never more confident than the screen it came from.
6. **MITRE matrix scope narrowing (TM-3, documented deviation):** spec §5.6 names an `AttackNavigatorMatrix` with 5 coverage layers (Detection/Correlation/YARA/Threat feed/AI). Only Detection has a live data source in this codebase. TM-3 ships a dense grouped-by-tactic list with the one real layer rather than fabricate the other four.
7. **Framework workspaces (TM-6) — the user's own threat surface, not BRIEFR's.** `security_architecture/frameworks/` adds four analyst-facing workspaces — `cwe`, `owasp`, `capec`, `stride` — served entirely from live DB data via `GET /frameworks/{id}` (no corpus file, like `mitre_attack`). This deliberately reframes spec §4.5: instead of "BRIEFR watches BRIEFR" (self-stack), the frameworks describe whatever the operator is defending. A **Scope** selector (`all` | `stack` | `watchlist` | `kev`, + `severity`) resolves to a bounded live query over the ingested `cves` corpus (`frameworks/scope.py`) — `stack` reuses `routers.cves._stack_match_clause` against the caller's saved stack (soft-resolved from the `briefr_at` cookie) or an explicit `?stack=` override, reporting `unavailable`+`reason` rather than a silent whole-corpus fallback when neither exists. All four workspaces are projections of one live aggregation — the CWE weakness classes in `cves.cwe_ids` across that scope (`frameworks/aggregate.py`): CWE is direct; OWASP Top 10 2021, CAPEC (MITRE CWE→CAPEC), and STRIDE (documented heuristic) are reference-mapping projections of the same CWEs (`frameworks/reference.py`, standard published mappings kept as versioned code, not curated corpus). Counting is distinct-CVE per category (never CWE-occurrence sums that double-count an advisory); CWEs with no mapping surface in an explicit `unmapped` bucket so the parts reconcile with the whole; every row ships `example_cves` (KEV/EPSS-prioritised) as its drill-through, and the response reports `sample_size` vs `total_in_scope` so a capped aggregation is visibly capped (CLAUDE.md danger zone 6 — bounded, request-path-safe). **UI:** hosted inside Admin → Security posture (`SecurityPosturePage.jsx`, PM-4a), a FRAMEWORKS subtab group after the operator posture sections, each rendered by the shared `FrameworkSection.jsx` with the Scope bar; example CVEs open the CVE drawer in a new tab. The self-referential posture material (self-stack exposure, control active-flags, and future ASVS/NIST CSF control-backed verification) stays operator/self-monitoring scope, distinct from these analyst threat frameworks.
8. **Program complete at TM-5; TM-6 framework workspaces (CWE/OWASP/CAPEC/STRIDE) shipped:** risk register, decision records, review history, abuse cases, global search, and PDF export (spec `threat-modeling-security-architecture.md` §8 TM-5) close the committed program (TM-0→TM-5, 5 PRs, 11 sections). TM-6 ships the four live-data-backed framework workspaces above; NIST CSF / ASVS (operator control-backed self-assessment) and a scheduled self-monitoring/remediation job remain follow-up work. TM-4 also documented one spec staleness in `manifest.yaml`'s notes: spec §2.2's navigation catalog uses kebab-case section ids (`system-architecture`, `trust-boundaries`, `attack-surface`); code has used snake_case since TM-1 and kept that convention rather than rewriting the established ids.

### G. ML assist — embeddings + LLM product extraction (V1.3, env-gated)

Both features follow the ML placement rules (`docs/planning/ROADMAP.md`): env-gated, CPU-only, scheduler-side only, deterministic fallback, tool fully functional with ML disabled. **Both are off by default.**

**Similar CVEs via embeddings (`EMBEDDINGS_ENABLED=1`):**

1. **Scheduler writes:** `embeddings_backfill` (every `EMBEDDINGS_SYNC_INTERVAL_HOURS`, default 6h) embeds **rich CVE text** (description + summary + products + CWEs, capped) with a local ONNX model (`ml/embeddings.py`, fastembed, `EMBEDDINGS_MODEL=BAAI/bge-small-en-v1.5`). **E2 dual-write:** L2-normalized float32 vectors go to multi-entity `embeddings` (`vector(384)` on Postgres / BLOB on SQLite) with `content_hash = sha256(text + '\\n' + model)`, and still to legacy `cve_embeddings` for one-release read-fallback. Rows with E1 `migrated:` placeholders are re-selected until re-embedded (capped at `EMBEDDINGS_MAX_PER_RUN`). `EMBEDDINGS_PGVECTOR=0` skips the `embeddings` table write. Inference runs in a worker thread; `fastembed` is optional — if missing, the job logs one warning and skips. Model cache: `EMBEDDINGS_CACHE_DIR` (production `/var/lib/briefr/models`).
2. **pgvector foundation (E1):** Alembic `032` requires a pgvector-capable Postgres image (`pgvector/pgvector:pg16`), installs `CREATE EXTENSION vector`, creates `embeddings` + HNSW, and copies existing BLOBs (`content_hash` placeholder `migrated:…`).
3. **Request path — related (E3):** `GET /api/cves/{id}/related` does **no model inference**. Prefers ANN / cosine on `embeddings` (pgvector on Postgres; BLOB scan on SQLite), then legacy `cve_embeddings` NumPy, then product heuristic. `meta.method` is `embeddings` or `product_heuristic`.
4. **Request path — search (E3):** `GET /api/search/semantic` (`mode=hybrid|keyword|semantic`). Keyword always available. Hybrid merges keyword + vector via weighted RRF with query-shape rules (CVE-id → keyword-first; short → keyword-heavy; long → vector-heavier). Free-text semantic may embed **one** query string when `EMBEDDINGS_ENABLED=1` (design §7.1); cold/disabled → `keyword_fallback`.
5. **Deterministic fallback:** embeddings disabled, target CVE not embedded yet, or zero hits → related serves the shared-product heuristic; search stays keyword-capable. Embedding hits carry additive `similarity` where applicable.

**LLM product extraction (`LLM_PRODUCT_EXTRACTION_ENABLED=1` + any LLM provider key):**

1. `llm_product_extraction` (every `LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS`, default 6h) selects CVEs with **no CPE data and empty `affected_products`** (NVD-unanalyzed), up to `LLM_PRODUCT_EXTRACTION_MAX_PER_RUN` per run. With `PROCRASTINATE_ENABLED=1`, APScheduler only enqueues durable task `jobs:llm_product_extraction`; otherwise it keeps the inline scheduler behavior. Admin Run/Retry uses the same durable task when available, with `trigger="manual"` and elevated priority.
2. LLM calls go through the router/provider pacing chain; extracted `{vendor, product, version_range}` entries are normalized to the existing `vendor:product` format.
3. **Write guard + provenance:** products are written only while the field is still empty, and the row is marked `affected_products_source='llm'`. A later NVD sync with official CPE data supersedes the LLM products and clears the marker; an NVD sync that still carries no CPE data does **not** wipe them (upsert CASE rules in `database.py`).
4. **Negative caching + durable retry:** every completed extraction (including ones that found no products) is recorded in `feed_cache` (`llm_products:<id>`, 7-day window) so the same CVE never costs quota twice. Errors are **not** cached. Retryable task-level timeouts re-defer with `queueing_lock="llm_product_extraction"` and bounded delays from `jobs/retry_policy.py`; non-retryable or exhausted failures fail the durable job.

---

## 4. Design Decisions & Trade-offs

### Resilient outbound HTTP (`resilient_client.py`)

All scheduler-driven intel sources (NVD, KEV, EPSS, MITRE, ATLAS, OSV, 5× RSS, CPE catalog, and optional exploit/intel feeds) share one pooled `httpx.AsyncClient` with:

- **Retries:** transport errors and retryable statuses (5xx, 429 with `Retry-After` respect) retried with exponential backoff.
- **Circuit breaker per source:** `CIRCUIT_FAILURE_THRESHOLD` consecutive failures (default 3) open the circuit for `CIRCUIT_COOLDOWN_SECONDS` (default 60); calls fail fast with `CircuitOpenError` so one dead source cannot stall a sync cycle. Plain 4xx responses do not trip the circuit (the source is reachable).
- **Health registry:** `/api/health` → `feeds.sources` exposes `last_success`, `last_failure`, `last_error`, `consecutive_failures`, `circuit_open` per source.
- **NVD exception:** keeps its bespoke 429/key-rejection retry logic but uses the pooled client and reports into the same health registry.
- **Quota-billed sources** (VirusTotal, AbuseIPDB, GreyNoise) use `retries=0` — a failed call is never retried automatically, so quota cannot be burned by the retry loop. Circuit breakers still apply.
- **CIRCL negative caching:** failed/missing lookups are cached for 24h (`circl_miss:*` keys) so a rate-limited upstream is not re-hammered with the same IDs on every sync cycle.
- **SQL vs source I/O:** `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` (default 60) is an asyncpg **SQL statement** budget only. Feed/API HTTP timeouts stay per-source in `feeds/` (CIRCL ~25s, Sploitus ~30s, ThreatFox ~120s, …). Scheduler paths commit or close before outbound source I/O (`db/txn_boundaries.commit_before_source_io`) so slow CIRCL/Sploitus cannot hold `cves` locks and burn concurrent writers (VulnCheck/KEV/EPSS) into `Database command timeout`. Do not raise the global SQL timeout to paper over slow APIs.

All outbound modules are migrated: scheduler feeds (NVD, KEV, EPSS, MITRE, ATLAS, RSS) and on-demand enrichment (`enrichment/ioc.py`, `feeds/extended.py` — Sploitus/GreyNoise/MalwareBazaar/URLhaus/CIRCL, `feeds/otx.py`, `feeds/osv.py`).

### Audit log + auth direction (V1.2 decision, 2026-06-11)

- **Audit:** `audit_log` table (actor, action, target, timestamp plus metadata where available) is written by manual `POST /api/refresh*` calls, backup/restore, admin actions, webhook tests, correlation feedback, and storage/data ops. Admin exposes it at `GET /api/admin/audit-log` with filters and target masking.
- **Auth direction:** BRIEFR ships built-in app login (shipped). Admin and **ingest** `POST /api/refresh*` routes require an `admin` role session. **`POST /api/auth/refresh`** is available to any signed-in user and rejects sessions past `sessions.expires_at` or with token reuse (revokes all user sessions). The legacy shared admin-key header was removed in Sprint A0.
- **Frontend refresh dedupe (#731):** `frontend/src/api.js` keeps a module-level in-flight `refreshAccessToken()` promise so concurrent 401 handlers share one rotation. `AuthContext` bootstrap calls `fetchMe()` only (`request()` already refreshes on 401) — never a bare `fetch('/api/auth/refresh')`, which raced retries and tripped reuse detection (sticky BRIEF “Not authenticated” while the header still showed the user). Residual: multi-tab concurrent refresh can still hit reuse detection by design.

### Rate limiting + structured logging (V1.2 §5.5)

- **Rate limiting:** token buckets (`rate_limit.py`) protect abuse-prone routes — `POST /api/ioc/lookup`, refresh/admin/auth paths, DB explorer, and `GET /api/wallboard`. Keyed per trusted client identity; capacity = the per-minute rate, continuous refill. Over the limit → `429` with `Retry-After` (whole seconds). Defaults include `RATE_LIMIT_IOC_PER_MINUTE=30`, `RATE_LIMIT_REFRESH_PER_MINUTE=10`, `RATE_LIMIT_WALLBOARD_PER_MINUTE=60`; `RATE_LIMIT_ENABLED=0` disables. Multi-worker installs can use `BRIEFR_RATE_LIMIT_STORE=db` so buckets are stored in `sync_state` instead of per-process memory.
- **Wallboard (V1.4 Theme 4):** `GET /api/wallboard` (`wallboard/service.py`) aggregates read-only tiles (KEV-on-stack count, 24h brief highlights, top risk CVEs ranked by **Operational Priority then Threat** — not legacy v1.1b total — ingest health subset, Forge gap summary, incident headline ticker) into one `feed_cache` payload (~45s TTL). Top-risk items expose `threat_score`, `op_band`, and `risk_score` (alias of Threat for backward compatibility). Optional `WALLBOARD_TOKEN` read-only gate (`X-BRIEFR-Wallboard-Token` header only — Sprint A7 dropped `?token=`, which leaked into access logs). Frontend `/wallboard` is chromeless — 3×2 grid, 90s poll, rotating tile focus, scrolling ticker. No admin routes, secrets, or write actions exposed.
- **Rate-limit client identity (anti-spoofing):** forwarded headers are honoured only when the socket peer is a loopback proxy (nginx/cloudflared proxy_pass from 127.0.0.1 — `deploy/nginx-briefr*.conf`); direct connections are keyed by socket address, so a spoofed header cannot mint fresh buckets. Behind the tunnel the order is `CF-Connecting-IP` (overwritten at the Cloudflare edge), then the **rightmost non-loopback** `X-Forwarded-For` hop (nginx appends `$remote_addr`; leftmost hops are client-controlled), then `X-Real-IP`. Bucket storage is bounded: idle buckets are pruned, and a flood of distinct keys past a hard cap evicts least-recently-seen buckets (bounded memory beats a remotely triggerable OOM). Residual risk: a LAN host talking to nginx directly can still forge headers — accepted for a typical self-hosted, single-operator deployment; revisit if BRIEFR is ever deployed with untrusted hosts on the same LAN as the reverse proxy.
- **Structured logging:** `structured_logging.py` emits one JSON object per line on stderr (journald-friendly): `ts`, `level`, `logger`, `message`, `request_id`, plus any `extra={...}` fields. A `request_context` middleware (outermost) assigns each request an ID (honours a well-formed incoming `X-Request-ID`, else generates one), returns it in the `X-Request-ID` response header, and logs a `briefr.access` line per request (`method`, `path`, `status`, `duration_ms`, `client`). uvicorn's startup/error loggers are rerouted through the same JSON handler; uvicorn's own access log is disabled in JSON mode (the `briefr.access` line replaces it — it carries the request ID). Unhandled exceptions are logged by the middleware itself (with `request_id`, `exc_info` and the request metadata) before the contextvar resets, then re-raised. `LOG_FORMAT=plain` restores the previous human-readable format.
- **Production posture self-check (Sprint A6):** `settings.production_posture_warnings()` reports every unsafe flag in the current config — `RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, `WALLBOARD_TOKEN` unset. `main.py` startup logs one warning per entry when `BRIEFR_ENV=production`; `GET /api/admin/security` returns the same list (`posture_warnings`) plus `environment`, and the admin Security panel renders each as an amber callout.
- **Admin log viewer (V1.4 Theme 3):** the same `structured_logging` module attaches a fixed-size in-process ring buffer (`_RingBufferHandler`, capacity 500) to the root logger. Every `INFO+` record is mirrored into the buffer with a derived `category` field (`Application`, `Scheduler`, `Backup`, `Webhooks`, `Security`) and secret-like `extra` keys redacted. `GET /api/admin/logs` (admin-gated, refresh rate-limited) tails the buffer with `level`, `logger`, `request_id`, and `category` filters — no shelling out to journald. The admin pane **Application logs** page surfaces the tail with level/category/logger/request_id filters, auto-refresh, and NDJSON export.

### Backup archive encryption (`age`, V1.2)

- **What:** backup archives (Postgres dump or dev SQLite fallback + `.env` with all API keys + manifest) are encrypted to the age format (X25519, via `pyrage` — interoperable with the `age` CLI) and named `briefr-*.tar.gz.age`. The identity file is `BACKUP_AGE_KEY_FILE` (production default `/var/lib/briefr/keys/backup-age.key`, generated by `deploy/briefr-backup.sh` / `python -m backup keygen` on first run, mode 0600).
- **Key placement:** `backup/manager.py` **refuses to encrypt when the key sits inside `BACKUP_DIR`** — the point is that a stolen archive copy is useless without a file that never travels with it. The key stays readable by the `briefr` service user so restore (`briefr-restore.sh`) and **startup auto-restore** (`ensure_db_or_restore`) decrypt transparently; pre-encryption `.tar.gz` archives keep restoring as before.
- **Scope honesty:** this protects **off-site / at-rest archive copies only** (rclone/S3, stolen disks, leaked archive directories). A compromised host or service user can read the key — see `docs/archive/THREAT_MODEL.md` § Scope of backup encryption.
- **Opt-out:** `BACKUP_AGE_KEY_FILE=""` forces plaintext archives; dev machines without the default key file are unchanged.

### Push notifications (V1.3 Theme 8 → V1.4 engine)

- **Engine:** `webhooks/engine.py` dispatches events (`kev_alert`, `backup_failure`, `health`, `watchlist_alert`, `kev_backlog`, `ioc_watchlist_hit`) to one or more **destinations** loaded from env vars and the `webhook_destinations` table. Env seeds are upserted on startup (`sync_env_destinations_to_db`); per-destination `enabled` and `event_types` can be overridden via admin API.
- **Built-in destinations:** Discord (`DISCORD_WEBHOOK_URL`), Telegram (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`), optional generic HTTPS POST (`WEBHOOK_GENERIC_URL`). Each channel can be independently enabled/disabled (`*_WEBHOOK_ENABLED`) and subscribed to event types (`*_WEBHOOK_EVENTS`).
- **Transport:** outbound webhook HTTP uses `webhooks/ssrf.py` — **https only**, DNS resolve + block private/reserved ranges (RFC1918, RFC 6598 CGNAT `100.64.0.0/10`, 127.0.0.0/8, ::1, 169.254.0.0/16, 0.0.0.0, unique-local IPv6), connect to resolved IP with original `Host` header (DNS-rebinding safe), **no redirect following**, 10s timeout, no internal API keys on outbound headers. Failures recorded via `resilient_client` health (`webhook.{destination_id}`).
- **Dedupe:** `webhook_alert_log` stores one row per `(event_type, target)`; `webhook_delivery_log` records every delivery attempt (destination, status, error).
- **KEV-on-stack:** after each `kev_metadata_sync`, newly flagged KEV CVEs matching `BRIEFR_STACK_TERMS` dispatch `kev_alert` (deduped per CVE).
- **IOC watchlist hits:** after each `ioc_retro_match`, local OTX/ThreatFox mirror matches dispatch `ioc_watchlist_hit` (deduped per user/value/source).
- **Backup dead-man:** `backup_deadman_check` dispatches `backup_failure` when the newest archive is older than `2 × BACKUP_INTERVAL_HOURS`. Clears dedupe when a fresh backup appears.
- **Admin:** `GET /api/admin/webhooks/destinations`, `PATCH /api/admin/webhooks/destinations/{id}`, `GET /api/admin/webhooks/delivery-log`, `GET /api/admin/webhooks/log` (dedupe log).

### PostgreSQL first; SQLite only as test/dev fallback

- **Why:** Production requires `DATABASE_URL` and normally `BRIEFR_REQUIRE_POSTGRES=1`. Runtime uses an asyncpg pool, Alembic migrations, pgvector embeddings, db-backed rate-limit buckets, resource metrics, durable Procrastinate jobs, API metering, and Postgres backup/restore smoke tests.
- **Pool timeouts:** `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` is SQL-only; source HTTP timeouts live per feed. See resilient-client § “SQL vs source I/O” and `docs/POSTGRES.md`.
- **Compatibility:** SQLite remains as the zero-config local/test fallback through `db/connection.py` + `db/pg_adapt.py`, not as a production architecture choice.
- **Trade-off:** New persistence features are written Postgres-first. Where the default test suite needs SQLite support, the adapter or explicit `_SQLITE` / `_PG` query variants keep tests honest without reintroducing a dialect layer.

### APScheduler + Procrastinate over Celery/Redis

- **Why:** APScheduler remains the embedded cadence owner for recurring ingest/ops jobs; Procrastinate adds a Postgres-backed durable queue only where restart-safe retry is needed.
- **Trade-off:** APScheduler jobs still run in one scheduler owner process (`BRIEFR_SCHEDULER_ENABLED=1`). Durable work is intentionally narrow today: `jobs:health_ping`, `jobs:stack_backfill`, and `jobs:llm_product_extraction`.

### Background-job ownership registry (idempotency SSOT — audit F2.2 / IDEM-C)

Two background-job systems coexist. **Durable execution is owned by exactly one system**, in a
**disjoint namespace** (APScheduler ids never carry the `jobs:` prefix), so a job can never
be registered in both as `jobs:*` — asserted by `tests/test_job_ownership_registry.py`.
APScheduler may keep a bare-name tick that only enqueues a durable task. At-least-once
delivery means each durable task must be idempotent; the table records the guarantee.

| System | Owner / entrypoint | Jobs | Idempotency mechanism |
|--------|--------------------|------|-----------------------|
| **APScheduler** (in-process) | `scheduler.py:start_scheduler`; gated by `BRIEFR_SCHEDULER_ENABLED` (single owner across replicas) | 26 normal recurring jobs in non-smoke startup + 3 registration-gated optional jobs (`otx_continuous_sync`, `exploit_sources_sync`, `detection_context_llm`). `llm_product_extraction` becomes an enqueue tick when Procrastinate is enabled. | `max_instances=1` + `coalesce=True` per job; per-job `asyncio.Lock` (`scheduler_locks._LOCKS`); manual `/api/refresh*` shares the same locks |
| **Procrastinate** (durable queue) | `jobs/app.py` + `jobs/worker.py:start_inprocess_worker`; gated by `PROCRASTINATE_ENABLED`, Postgres-only | `jobs:health_ping`, `jobs:stack_backfill`, `jobs:llm_product_extraction` (`jobs/tasks.py`) | `stack_backfill`: per-run `queueing_lock` on defer (IDEM-B) + atomic `claim_run_running` run gate (IDEM-A); NVD rate-limit deferrals self-schedule the same task 180s later when the durable app is available. `llm_product_extraction`: singleton `queueing_lock` on scheduler defer/retry/manual Run + pool-scoped extraction (`db=None`) + bounded retry delays for retryable timeouts |

Because `claim_run_running` (IDEM-A) makes stack-backfill execution exactly-once regardless of
how many kicks reach it, an overlap of the durable job and the in-process fallback across a
`PROCRASTINATE_ENABLED` flag flip cannot double-run a run — it is contained at execution, and
duplicate *enqueues* are rejected by the `queueing_lock` (IDEM-B). New durable tasks must add a
row here with their idempotency key before merge.

### Plain JSX + CSS + BRIEFR-styled Radix primitives

- **Why:** The app keeps plain React/Vite and tokenized CSS for the dark terminal identity, while shared BRIEFR components wrap approved Radix primitives (`Checkbox`, `Switch`, `Select`, `Tabs`, `Dialog`, `DropdownMenu`, `Slider`) and composites (`Badge`, `EmptyState`, `StatCard`, `Card`, `Pill`, `Toast`, `ChartShell`).
- **Trade-off:** Component behavior comes from sanctioned headless primitives, but visual language stays in repo-owned CSS and semantic tokens.

### Backend-canonical risk scoring

- **Why:** One reproducible score for drawer, brief, exports, and future alerts; no Python/JS drift.
- **Trade-off:** `POST /api/cves/{id}/risk` on drawer open (and on profile change); cards show momentum arrows only until drawer warms cache.

### Router packages

- **Status:** `main.py` is app wiring, lifespan, middleware, and router registration. Endpoints live in `routers/` and package splits (`routers/cves/`, `routers/admin/`, `security_architecture/routers/`), with registration order preserved by tests so literal CVE routes keep matching before `/api/cves/{id}`.

### Database access layer

- **Status:** Persistence is still SQL-first rather than ORM-based, but shared behavior has moved into `db/` modules for connection/pool handling, Postgres adaptation, embeddings, correlation, resource metrics, API metering, software catalog, stack backfill, cache retention, notifications, and explorer allowlists. `database.py` remains the compatibility facade for older callers while new code should prefer narrower `db/*` helpers.

---

## 5. System Design Principles Status

| Principle | v1.5 Status | Notes |
|---|---|---|
| Separation of Concerns | MOSTLY SHIPPED | Router packages, `services/`, `db/`, scoring modules, AI, jobs, detection, and security posture are split by responsibility. |
| Single Responsibility | IMPROVED | `DetailDrawer` and Forge were split into feature components; drawer panels stay mounted via `hidden` after first visit. |
| Repository Pattern | PARTIAL | SQL remains explicit; new storage work generally lands in scoped `db/*` modules while `database.py` acts as a compatibility facade. |
| Dependency Injection | PARTIAL | Auth/admin/session dependencies are centralized; DB acquisition still uses shared helper functions rather than FastAPI-injected repositories. |
| Circuit Breaker | SHIPPED | `resilient_client.py` handles pooled HTTP, retry, per-source health, and circuit state; API key health probes do not mutate real source circuits. |
| Idempotency | SHIPPED/PARTIAL | Upserts, scheduler locks, graceful shutdown, Procrastinate `queueing_lock`, stack-backfill `claim_run_running`, and webhook dedupe are in place; each new durable job must declare its idempotency row. |
| Caching Strategy | SHIPPED/PARTIAL | `feed_cache`, `ioc_cache`, count cache, correlation snapshots, incident snapshots, detection context, retrieval health, and cache retention jobs are live. |
| API Consistency | PARTIAL | Newer endpoints use `data`/`meta` or `ok` shapes; older endpoints preserve backward-compatible payloads. |
| Config Management | SHIPPED/PARTIAL | `settings.py`, admin config schema, DB-backed `app_settings`, secret encryption, apply strategies, and scheduler reschedule are live. |
| Observability | PARTIAL | ✅ Shipped — JSON structured logs with `request_id` (`structured_logging.py`), `X-Request-ID` on every response, token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*`; admin log viewer (`GET /api/admin/logs`, 500-line ring buffer); **resource utilization** — `resource_metrics` table + `resource_metrics_sample` scheduler job (60s, `psutil` + `pg_stat_database`), admin **Resources** page (`GET /api/admin/resources`) |

---

## 6. External Dependencies Map

| Service | Used by | Data provided | Key env var | Free tier | Failure behaviour |
|---|---|---|---|---|---|
| NVD | `feeds/nvd.py`, scheduler | CVE records, CVSS, CPE | `NVD_API_KEY` (optional) | 50 req/30s with key | Sync aborts; logs error |
| CISA KEV | `feeds/kev.py` | KEV catalog JSON | — | Unrestricted | Returns `[]` |
| EPSS | `feeds/epss.py` | Exploit prediction scores | — | Unrestricted | Returns `{}` |
| MITRE STIX | `feeds/mitre.py` | Techniques, groups, CVE maps | — | Unrestricted | Weekly job fails; logs |
| ATLAS YAML | `feeds/atlas.py` | AI/ML techniques, case studies | `ATLAS_YAML_URL` | Unrestricted | Weekly job fails; logs |
| Sploitus | `feeds/extended.py` | Public exploits (on-demand) | — | Unpublished | `[]` / `None` |
| PoC-in-GitHub | `feeds/poc_github.py`, scheduler | GitHub PoC index | `GITHUB_TOKEN` optional | GitHub API limits | Skip; prior rows retained |
| ExploitDB | `feeds/exploitdb.py`, scheduler | Public exploits CSV | — | Unrestricted | Skip; prior snapshot retained |
| Metasploit | `feeds/metasploit_modules.py`, scheduler | MSF exploit modules | — | Unrestricted | Skip; prior snapshot retained |
| Nuclei | `feeds/nuclei_index.py`, scheduler | CVE template index | — | Unrestricted | Skip; prior snapshot retained |
| GreyNoise | `feeds/extended.py`, IOC | IP classification | `GREYNOISE_API_KEY` | 50/week | `[]` or unknown record |
| VirusTotal | `enrichment/ioc.py` | IP/hash/domain reputation | `VIRUSTOTAL_API_KEY` | 500/day | Empty VT fields |
| AbuseIPDB | `enrichment/ioc.py` | IP abuse score | `ABUSEIPDB_API_KEY` | 1000/day | Skipped if no key |
| OTX | `feeds/otx.py` | Pulses, IOCs | `OTX_API_KEY` | 10k/month | `[]`; nightly skipped if unset |
| OSV.dev | `feeds/osv.py` | Package affected versions | — | Unrestricted | `[]` |
| CIRCL (vulnerability.circl.lu) | `feeds/extended.py` | Extra refs, CAPEC (CVE 5.x records) | `CIRCL_API_KEY` optional (`X-API-KEY`) | Rate-limited; 7d hit cache + 24h negative cache | No merge |
| MalwareBazaar | `feeds/extended.py` | Hash metadata | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| URLhaus | `feeds/extended.py` | Domain malware URLs | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| ThreatFox | `feeds/threatfox.py`, scheduler | IOC mirror for retro-match | `ABUSECH_AUTH_KEY` | Fair use | Skip sync; prior rows retained |
| VulnCheck KEV | `feeds/vulncheck_kev.py`, scheduler | Exploited-in-the-wild tier | `VULNCHECK_API_KEY` | API key required | Job no-op; flags unchanged |
| Groq → Cerebras → OpenRouter → Gemini | `ai/llm_router.py`, `ai/summary.py`, `ml/product_extraction.py`, `detection/context_llm_sync.py` | Fixed-order failover chain: executive summary, LLM product extraction, detection-context artifacts; Program E Task 2 adds admin replay flows backed by stored failure payloads (`GET /api/admin/ai/operations/{operation_id}/payload`, `POST .../{operation_id}/retry`) with replay provenance (`context_type="replay"`, `context_id=<original operation_id>`) and circuit-open guard (`409` unless `force=true`) | `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `OPENROUTER_API_KEY` / `GEMINI_API_KEY` | Per-provider RPM/TPM pacing (`ai/llm_pacing.py`) | Falls through to the next provider, then to a deterministic template/heuristic — no Anthropic/Claude integration exists in this codebase |
| GitHub | `detection/rule_sources.py` | Sigma/Elastic rule search | `GITHUB_TOKEN` (optional) | 60/hr anon | `[]` rules |
| RSS (5 sources) | `feeds/incident_news.py` | News cards (editorial titles filtered) | — | Per-feed | Per-source error in `errors[]` |
| CISA Vulnrichment | `feeds/vulnrichment.py` | CISA ADP CVSS / CWE / CPE gap-fill | `GITHUB_TOKEN` (optional) | 60/hr anon GitHub API | Log error; skip run |
| cvelistV5 | `feeds/cvelistv5.py` | CVE JSON 5.x + ADP (pre-NVD) | `GITHUB_TOKEN` (optional) | 60/hr anon GitHub API | Log error; watermark retained |

### Scheduler intel enrichment (V1.3)

Two repo-based feeds run **only on the scheduler** (never on the request path):

1. **Vulnrichment** (`vulnrichment_snapshot_sync`) — lists `cisagov/vulnrichment` tree each run (snapshot, no watermark), fetches JSON for CVE rows still missing NVD analysis fields (`cvss_score`, `severity`, `cwe_ids`), and merges additively. Official NVD ingest later supersedes CISA ADP values because NVD upserts overwrite `cvss_score` / `severity` / `cwe_ids`.
2. **cvelistV5** (`cvelistv5_incremental_sync`) — compares `sync_state.cvelistv5_head_sha` against `main` via GitHub compare API, fetches only changed `cves/**/CVE-*.json` paths, parses CNA-first CVE 5.x records, and merges additively (or inserts new CVE rows). First boot seeds the watermark from commits in the last `CVELISTV5_INITIAL_SINCE_DAYS` (default 7).

Health for both appears under `GET /api/health` → `feeds.sources.vulnrichment` and `feeds.sources.cvelistv5`.

**Rejected CVEs:** NVD `vulnStatus: Rejected` and cvelistV5 `cveMetadata.state: REJECTED` records are **not upserted**. Each NVD sync also runs `purge_legacy_rejected_cves` (rows whose description starts with `Rejected reason:`) and deletes any reject IDs seen in the current feed batch. cvelistV5 deltas delete matching rows when a file flips to `REJECTED`.

RSS sources defined in `feeds/incident_sources.py`: The Hacker News, Krebs on Security, Dark Reading, Schneier on Security, CISA Advisories. Non-security editorial items (e.g. Dark Reading cartoon contests) are excluded via `EXCLUDED_NEWS_TITLE_PATTERNS` in `incident_news.py`.

---

## 7. Known Limitations — v1.5

- **SQLite is not a production target.** It remains only for zero-config dev/tests; production should run PostgreSQL 16 and pgvector when embeddings are enabled.
- **`POST /api/investigation/summary`** is a legacy route; it delegates to `generate_investigation_summary` → `generate_executive_summary`. Prefer `POST /api/ai/summary` for new clients.
- **Durable jobs are intentionally narrow.** Procrastinate covers health ping, stack backfill, and LLM product extraction; most recurring cadence remains APScheduler-owned.
- **Embeddings are retrieval-only.** Hybrid search and related CVEs use pgvector/embedding fallback when enabled; there is no RAG workflow.
- **Full V2.0 platform compose is not shipped.** Postgres compose exists; production still relies on the documented self-host deployment pieces.

### CI — frontend smoke

GitHub Actions job **`playwright-smoke`** in `.github/workflows/backend-tests.yml` runs `tests/test_playwright_smoke.py` with `PLAYWRIGHT_SMOKE=1`: seeds SQLite via `scripts/seed_screenshot_data.py`, builds the incident-feed snapshot, serves the production Vite bundle (`vite preview` with `/api` proxy), and asserts five Chromium interactions — BRIEF CVE cards render, quick-filter click scroll-anchors to the feed (regression for feed UX), CVE drawer open/close restores focus, IOC tab accepts input, Incidents tab renders cards. The default PR pytest job skips these tests (no browser required).

---

## 8. Current roadmap references

Near-future engineering and product intent lives in [`docs/planning/SPRINT_2026-07.md`](planning/SPRINT_2026-07.md), [`docs/planning/BACKLOG.md`](planning/BACKLOG.md), and active specs under [`docs/planning/specs/`](planning/specs/). Historical beta docs remain in `docs/archive/` and are not current system truth.

---

## Related documentation

- [`docs/ONBOARDING.md`](ONBOARDING.md) — contributor entry point, local dev, tests, troubleshooting
- [`API_REFERENCE.md`](API_REFERENCE.md) — endpoint catalog
- [`docs/archive/snapshots/TECHNICAL_INVENTORY.md`](archive/snapshots/TECHNICAL_INVENTORY.md) — schema, scheduler, stack
- [`docs/archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) — startup and request journeys
- [`docs/archive/snapshots/FOLDER_STRUCTURE_GUIDE.md`](archive/snapshots/FOLDER_STRUCTURE_GUIDE.md) — file-by-file map
- [`docs/diagrams/`](diagrams/) — Mermaid diagrams (render in GitHub, VS Code, Notion). Master: [`system-graph.mermaid`](diagrams/system-graph.mermaid). Flows: CVE feed/detail, IOC lookup, NVD sync, PDF export, error handling (`flow_error_handling.mermaid`), startup, schema ERD.
