# BRIEFR System Design

Copyright © 2026 Sai Harsha Vardhan. Licensed under the GNU Affero General Public License v3.0 or later (`SPDX-License-Identifier: AGPL-3.0-or-later`); see the repository `LICENSE` for the full text.

**Version:** 1.1 (beta)  
**Last updated:** 2026-06-19  
**Source of truth:** `/workspace` codebase — see [`docs/archive/snapshots/CODEBASE_CONTEXT.md`](archive/snapshots/CODEBASE_CONTEXT.md) for a consolidated snapshot and [`docs/planning/ROADMAP.md`](planning/ROADMAP.md) for release index

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
│ APScheduler (scheduler.py) — 16 recurring jobs (+ opt-in gates) + startup one-shots │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. NVD incremental      → cves, sync_state, cve_change_history, feed_cache  │
│ 2. KEV metadata         → kev_deadlines, cves.is_kev, webhook_alert_log       │
│ 3. EPSS scores          → cves.epss_score, epss_history                     │
│ 4. MITRE+ATLAS weekly   → mitre_*, atlas_*, cve_*_map, has_ai_context       │
│ 5. OTX nightly          → otx_cve_pulses, otx_pulse_iocs, feed_cache        │
│ 6. Incident feed (30m)  → feed_cache (incident_rss:*, incident_feed:snapshot)│
│ 7. Correlation nightly  → correlation_*, feed_cache, otx_pulse_iocs         │
│ 8. Vulnrichment (6h)    → cves (additive CVSS/CWE/CPE)                      │
│ 9. cvelistV5 delta (30m)→ cves, sync_state.cvelistv5_head_sha               │
│ 10. Embeddings backfill → cve_embeddings (no-op unless EMBEDDINGS_ENABLED)  │
│ 11. LLM product extract → cves.affected_products(+_source), feed_cache      │
│ 12. Exploit sources (opt-in) → cve_exploits, cves.has_poc                   │
│ 13. Backup dead-man     → webhook_alert_log (when webhooks configured)      │
│ 14. ThreatFox mirror    → threatfox_iocs (ABUSECH_AUTH_KEY)                 │
│ 15. VulnCheck KEV tier  → cves.is_vulncheck_exploited (VULNCHECK_API_KEY)   │
│ 16. IOC retro-match     → ioc_watchlist_hit webhooks (OTX + ThreatFox join)   │
│ (startup one-shot) EPSS history backfill → epss_history, sync_state marker  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL — see docs/archive/snapshots/TECHNICAL_INVENTORY.md              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI (main.py + routers/) — /api/* — ~43 route handlers                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React + Vite (frontend/src)                                                 │
├──────────────┬──────────────┬──────────────┬──────────────┬───────────────┤
│ BRIEF tab    │ FEED tab     │ IOC LOOKUP   │ INCIDENTS    │ Forge tab     │ DetailDrawer  │
│ MorningBrief │ CVEFeed.jsx  │ IOCLookup    │ CaseStudies  │ Forge.jsx     │ (overlay)     │
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
| `cves` | `GET /api/cves`, `GET /api/cves/{id}`, `GET /api/stats`, `GET /api/brief` | CVEFeed, CVECard, DetailDrawer, StatsRow (BRIEF tab), TimelineHeatmap (BRIEF tab), MorningBrief |
| `kev_deadlines` | `GET /api/kev/deadlines`, `kev_due_date` on list/export/detail, `GET /api/brief` | Sidebar (urgent sort), CVECard due chip, DetailDrawer sentences, MorningBrief |
| `epss_history` | `GET /api/cves/{id}/epss-history`, momentum | DetailDrawer EPSS sparkline |
| `mitre_techniques`, `cve_technique_map` | `GET /api/techniques/top`, CVE `techniques` field | Sidebar, DetailDrawer Intel tab |
| `atlas_*`, `cve_atlas_map` | `GET /api/atlas/*`, `GET /api/cves/{id}` (per-CVE fields) | DrawerAtlasSection, CaseStudies (global list) |
| `otx_*` | CVE detail, correlation, IOC lookup | DetailDrawer Intel tab, IOCLookup |
| `feed_cache`, `ioc_cache` | Internal — speeds enrichment | Transparent to UI |
| `correlation_*` | `GET /api/cves/{id}/correlation` | DetailDrawer correlation section |
| `cve_exploits` | Via Sploitus loader in CVE detail | DetailDrawer Intel tab |
| `cve_change_history` | `GET /api/changes`, `GET /api/brief` (EPSS movers) | WhatChangedPanel (BRIEF tab), MorningBrief |
| `api_usage` | `GET /api/usage`, `GET /api/usage/ioc` | IOCLookup quota display |
| `audit_log` | Written by `POST /api/refresh*`, backup/restore, all admin actions | `GET /api/admin/audit-log` |
| `hunt_packs` (+ `mitre_techniques`, `cve_technique_map`) | `GET /api/forge/coverage`, `GET /api/hunt-packs/{technique_id}`, `POST /api/hunt-packs/generate` | Forge tab (coverage map + hunt pack panel) |
| `watchlist` | `GET/POST/DELETE /api/watchlist`, `DELETE /api/watchlist/snoozes`; join on `GET /api/cves` for sort/filter | CVECard + DetailDrawer pin; WATCHLIST feed filter |
| `ioc_watchlist`, `threatfox_iocs` | `GET/POST/DELETE /api/ioc/watchlist`; scheduler `threatfox_sync`, `ioc_retro_match` | IOCLookup watchlist panel |
| `scoring/risk.py` + `POST /api/cves/{id}/risk` | Canonical Risk Score v1.1b | `DetailDrawer.jsx` via `fetchCVERisk()` |
| `scoring/risk.py` constants | `GET /api/config/risk` — v1.1b weights, no DB | `riskScore.js` formula display (startup prefetch) |

---

### Risk score (v1.1b) — backend canonical

`POST /api/cves/{cve_id}/risk` computes the full explainable score in
`backend/scoring/risk.py:calculate_risk_score()`. Optional `profile` / `assets`
in the POST body personalise the asset component (CPE match via
`matching/cpe.py`, fuzzy graduation via `scoring/asset_match.py`). Momentum is
computed server-side in the same request via `calculate_momentum()`.

`GET /api/config/risk` still exposes weight constants for the drawer's formula
display (`score × weight × 100 = points`). `frontend/src/scoring/riskScore.js`
prefetches weights at startup and provides UI helpers only (colors, hero
summary text) — it does **not** compute scores.

| Component | Weight |
|---|---|
| Asset profile match | 0.35 |
| KEV status | 0.25 |
| EPSS | 0.15 |
| Exploit availability | 0.10 |
| CVSS | 0.10 |
| Momentum | 0.05 |

KEV component raw score uses CISA KEV recency tiers when `is_kev`; when not on
CISA KEV, `is_vulncheck_exploited` (VulnCheck sync) contributes **0.72** — below
full KEV tiers but above zero.

**Momentum (card arrows):** `GET /api/cves/{id}/momentum` remains available for
the momentum tab/signals; cached in `momentumCache.js` for CVECard arrows after
drawer open.

**Display:** `DetailDrawer.jsx` Overview tab — `RiskScoreBreakdown` fetches
`POST /api/cves/{id}/risk` when the CVE or asset profile changes.

### A. CVE lifecycle

1. **Ingest:** `scheduler.run_nvd_incremental_sync` → `feeds/nvd.py:fetch_nvd_cve_updates` (NVD REST 2.0, watermark in `sync_state`).
2. **Persist:** `database.upsert_cves` → `cves` table (`ON CONFLICT DO UPDATE`), optional `cve_change_history` rows. Ingest batches upserts via `executemany` in 500-row chunks (`db/cve.py`).
3. **Post-process:** strip auto-summaries, backfill display fields, `enrich_cves_extended` (Sploitus/CIRCL).
4. **List:** `GET /api/cves` builds SQL from `_build_cve_filters`, paginates (`page`, `limit` max **50**). `CVE_SELECT` uses a `LEFT JOIN kev_deadlines` (no correlated KEV subquery). `total` is cached 45s per filter set (`read_cache.py`). Postgres search benefits from Alembic `012_cve_trgm_search` GIN indexes on description/summary/affected_products.
5. **UI:** `CVEFeed.jsx:loadPage` → `fetchCVEs` → `CVECard.jsx` renders each row. Scroll “Showing X–Y” is tracked by leaf component `FeedVisibleRange.jsx` (rAF-throttled) so scrolling does not re-render the card list (`React.memo` on `CVECard`).

Sequence diagram: [`docs/diagrams/flow_cve_feed.mermaid`](diagrams/flow_cve_feed.mermaid)

### B. CVE detail drill-down

1. **Card click:** `App.jsx:handleSelectCVE` sets list CVE, then `fetchCVE(cve_id)` → `GET /api/cves/{id}`.
2. **Server path:** `_load_cve_detail_from_db` reads core rows and releases the pool connection; Sploitus, OTX, OSV, and CIRCL enrich via `asyncio.gather` with short-lived connections per task (`routers/cves.py:get_cve`). GreyNoise remains on-demand only (`GET /api/cves/{id}/greynoise-scans`).
3. **Drawer opens** with enriched CVE; parallel client fetches on `cve_id` change:
   - `POST /api/cves/{id}/risk` (immediate — canonical score; optional profile body)
   - `GET /api/cves/{id}/sentences` (immediate)
   - `GET /api/cves/{id}/epss-history` (immediate)
   - `GET /api/cves/{id}/momentum` (immediate — signals tab + card cache)
   - `GET /api/cves/{id}/correlation?sector=` (immediate)
4. **Lazy tab fetches:**
   - `GET /api/cves/{id}/related` — only when **Related** tab active
   - `GET /api/cves/{id}/detection` — only when **Detect** tab first opened
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

### D. Risk scoring (v1.1b)

See **Risk score (v1.1b) — backend canonical** above. Implementation:
`backend/scoring/risk.py`, `backend/scoring/asset_match.py`,
`POST /api/cves/{cve_id}/risk` in `routers/cves.py`.

### E. Incidents & News feed (snapshot-served)

1. **UI:** `CaseStudies.jsx` calls `loadCaseStudyFeed()` → `GET /api/case-studies/feed?atlas_limit=80`.
2. **Client cache:** `caseStudyFeed.js` holds a 5-minute session cache; a `meta.warming` response (snapshot still being built) is never pinned in that cache.
3. **Scheduler builds, API reads:** `run_incident_feed_refresh` (every `INCIDENT_FEED_REFRESH_MINUTES`, default 30; first run ~20s after boot) calls `case_study_feed.build_incident_feed_snapshot()`:
   - `fetch_all_incident_news_parallel(db)` — 5 RSS sources fetched concurrently via `asyncio.gather` (network only); cache reads/writes stay sequential on **one** SQLite connection (30 min `feed_cache` per source)
   - `_load_atlas_cards(db)` — ATLAS case studies from `atlas_case_studies` table
   - Combined result persisted to `feed_cache` under `incident_feed:snapshot` with `generated_at`
4. **Request path:** `get_incident_feed()` is a pure snapshot read (<50ms warm). A cold miss never blocks — it schedules a background build and returns `meta.warming=true` with empty data.
5. **Meta:** responses include `meta.refreshed_at`, `meta.stale` (older than 2× refresh interval), `meta.warming`. `/api/health` exposes `feeds.incidents.last_refresh` + `stale`.
6. **Merge:** Cards sorted by `publishedAt` descending; per-source errors collected in `errors[]` without failing the whole feed. Cache-write contention (e.g. during bootstrap ingest) degrades gracefully — parsed items are kept in the snapshot and persisted on the next cycle.
7. **Editorial filter:** `incident_news.py` excludes non-security RSS items by title pattern (e.g. Dark Reading **"Name That Toon"** contest). Filter applies on parse and when serving cached rows; malformed cache entries are skipped defensively.

Flowchart: [`docs/diagrams/startup.mermaid`](diagrams/startup.mermaid) (scheduler registration) · Client journey: [`docs/archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) §2.C

### F2. Analyst Brief charts (Chart.js, V1.3)

1. **UI:** `BriefCharts.jsx` on the BRIEF tab (below the morning brief, above the heatmap / What changed row). The component is `React.lazy`-loaded; `chart.js` is dynamically imported into a separate Vite chunk (`chart-*.js`) so the main bundle stays lean and CSP `script-src 'self'` is satisfied without a CDN.
2. **Panels (2):**
   - **KEV due-date histogram** — `GET /api/kev/deadlines?sort=urgent` → Chart.js bar chart bucketed Overdue / 0–7d / 8–14d / 15–30d / 31d+ with escalating colours (`--red` → `--amber` → neutral). Bars are clickable; `onBucketClick` receives `{ bucket, start, end }` UTC date range (callback prop only — filter wiring deferred).
   - **Top EPSS movers** — `GET /api/changes?field=epss_score&since_hours=168&limit=50` → compact table (CVE ID, dim severity dot, 7-day EPSS sparkline from `GET /api/cves/{id}/epss-history`, delta badge). Row click opens the CVE drawer via `onSelectCVE`.
3. **Refresh:** parallel fetch on mount + 5-minute poll (`POLL_MS`); per-CVE EPSS history fetched when movers list changes; cancellation guards on unmount.
4. **Theming:** Chart.js fonts/colours read from CSS variables (`readChartTheme()` in `chartLoader.js`); `prefers-reduced-motion: reduce` disables animation (`duration: 0`).
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
4. **Generate pack:** "GENERATE PACK" on a linked CVE → `POST
   /api/hunt-packs/generate` builds the Sigma rule + SIEM queries from the
   template library, derives priority from KEV/CVSS/EPSS, and upserts into
   `hunt_packs` (`UNIQUE(technique_id, cve_id)` — idempotent regeneration).
   The UI refetches coverage so the technique flips to `yours`.
5. **Boundary:** community-rule *search* (SigmaHQ/Elastic over GitHub) stays on
   `GET /api/cves/{cve_id}/detection` (drawer Detect tab). **V1.5 rule proof
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
     (`{ replace: true }`), and a `searchParams` effect mirrors browser
     back/forward into state. Admin sidebar owns `?p=` the same way (writes
     on click; page-scoped filters clear when `p` changes). Legacy Forge
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

### F. Watchlist — pin / snooze (V1.3)

Single-user instance: `watchlist` rows are not keyed by identity until built-in app login ships.

1. **Persistence:** `watchlist` table (`cve_id` PRIMARY KEY, `state` `pin`|`snooze`, `snooze_until`, `created_at`). Idempotent forward migration in `database.py:init_db`.
2. **API:** `GET/POST/DELETE /api/watchlist` (`routers/watchlist.py`). POST validates the CVE exists; snooze default is 7 days (`snooze_days` 1–365).
3. **Feed behaviour (`GET /api/cves`):** `LEFT JOIN` active watchlist rows. Pinned CVEs sort first. Active snoozes (`datetime(snooze_until) > datetime('now')`) are excluded from the default feed. `watchlist_only=true` returns only watchlist rows (pins + active snoozes) so analysts can review snoozed items.
4. **UI:** `useWatchlist` hook loads pins on mount and clears legacy snoozes via `DELETE /api/watchlist/snoozes`. Pin on `CVECard` and `DetailDrawer`; **WATCHLIST** quick-filter chip. Mutations bump a version counter so `CVEFeed` refetches without a full page reload. No `localStorage`. Snooze controls were removed from the UI (API retained for migration).

### H. Security Architecture — corpus + shell + live sections (TM-0→TM-5) + framework workspaces (TM-6)

1. **Corpus (TM-1, extended TM-3/TM-4/TM-5):** `backend/security_architecture/corpus/` — versioned YAML, `origin: generated | curated | live` per record. Generated files (`components.yaml`, `api_inventory.yaml`, `scheduler_jobs.yaml`, `db_tables.yaml`, `self_stack.yaml`, and TM-4's `graphs/architecture.json`) are emitted by `scripts/generate_security_corpus.py` from live route/scheduler/schema/dependency-manifest introspection and drift-tested in CI (`test_security_architecture_corpus.py::test_committed_corpus_has_no_drift`, plus TM-4's `test_committed_architecture_graph_has_no_drift`). `self_stack.yaml` (TM-3, spec §4.5) holds one record per dependency term parsed from `backend/requirements.txt` and `frontend/package.json`, plus declared runtime components (`postgresql`, `nginx`) — a new dependency changes this file and fails the drift check until regenerated. `graphs/architecture.json` (TM-4) holds nodes for every component/job/table already in the other generated files (no parallel node list to hand-sync — a corpus test asserts the node id set equals that union exactly) plus `component -> table` `references_table` edges, derived by regexing each router source file for table names appearing directly after a SQL keyword (`FROM`/`JOIN`/`INTO`/`UPDATE`/`DELETE FROM`) — anchored to real SQL syntax so a table named e.g. `users` can't spuriously match an unrelated identifier or comment elsewhere in the file. No x/y layout ships in this file: presentation isn't a code fact, so it doesn't belong in a drift-checked generated artifact — `ArchitectureGraphSection.jsx` computes a deterministic cluster+index grid layout at render time. Curated files: `controls.yaml` got its first real security-review seed in TM-3 (10 controls); TM-4 seeded `trust_boundaries.yaml` with its first 2 real boundaries (Browser→API→Database, BRIEFR→external services), each linking `related_ids` to real generated component/table ids and TM-3's curated controls. TM-5 seeded `security_decisions.yaml` (2 records mapping the two real ADRs in `docs/decisions/` — `decision`/`alternatives`/`tradeoffs`/`consequences` drawn directly from each ADR's own sections, not invented), `abuse_cases.yaml` (6 entries, each `current_protection` field citing real code as evidence — webhook SSRF, webhook replay, rate-limit bypass, SQL injection, log secret leakage, plus one honestly-open `broken-authorization-single-tier-session` finding with no mitigating control), and `reviews.yaml` (3 curated review-pass records documenting the program's own TM-3/TM-4/TM-5 security-review passes). `risks.yaml` stays intentionally empty — no real risk-register judgment pass has happened; the Risk Register's only non-empty content is `live` self-stack rows. `corpus_loader.py` validates required fields, `origin`, and cross-file `related_ids` at load time (mtime-cached); `security_architecture/graphs.py` separately loads/caches `graphs/architecture.json` (JSON, not YAML — different schema shape, not an entity-record list). `live` rows (self-stack risk-register entries, and TM-5's `reviews` section audit-log events) are never stored in a file — computed at read time by `security_architecture/merge.py` and merged into `/section/{risks,reviews}` responses.
2. **Staleness decay (TM-5, spec §4.1):** `security_architecture/merge.py::annotate_stale` adds a `stale: boolean` field to every row returned by `/section/{id}` — `true` for curated records whose `review_date` is more than `STALE_WINDOW_DAYS` (90) in the past; always `false` for generated/live rows (they carry no review-date judgment call). This one function is the single source of truth for three consumers that must never disagree: the frontend STALE badge (`RiskRegisterSection.jsx`, `DecisionsSection.jsx`, `AbuseCasesSection.jsx`, `ReviewHistorySection.jsx`), the Overview "Controls Active" ratio (`merge.py::controls_active_ratio` excludes stale controls from both numerator and denominator — the module's one real percentage a curated record feeds, spec §5.1), and the risk-register PDF export's "contains N stale records" footer disclaimer (`utils/securityArchitecturePdf.js`). `GET /stale` (new TM-5 endpoint) lists every stale curated record across every section, tagged with its `section`/`type`, for the Overview "Stale Records" tile drill-through.
3. **API (`routers/security_architecture.py`):** `GET /manifest` returns the corpus version + `sections[]` (the nav source of truth; includes `mitre_attack`, which has no corpus file — it's served entirely from live DB data). `GET /overview` returns raw counts plus a `tiles[]` array — every tile value is a `len()`, exact field match, or a visible ratio over corpus/live rows (no scoring, spec's "no arithmetic invented" rule), each carrying a `section`/`filter` drill target; TM-3 adds `mitre_detection_coverage` and `self_cve_exposure` tiles, TM-4 adds `unreviewed_endpoints`, TM-5 adds `stale_records` and turns `controls` into the "Controls Active" ratio. `GET /mitre` (TM-3) reuses `routers.forge.build_coverage_map`. `GET /threat-scenarios` (TM-3) wraps `threat_model.scenarios.build_threat_scenarios` with a `self_stack=true` toggle. `GET /graph/architecture` (TM-4) returns `graphs/architecture.json` verbatim — no read-time filtering, so "graph nodes match generator output exactly" holds by construction. `GET /graph/attack-surface` (TM-4) is `security_architecture/graphs.py::build_attack_surface` — a read-time join of the generated `api_inventory` against curated `controls.yaml`'s `related_apis` glob patterns (exact path, `<prefix>/*`, or `*`); every endpoint row carries its own `linked_control_count`/`linked_control_ids`, counts only, no composite score. `GET /context/{node_id}` (TM-4) is the context-rail read for a selected graph node — component nodes get their endpoints + glob-matched controls + referenced tables; table nodes get the reverse (`referenced_by`); job nodes get their own record + graph edges. `GET /section/{id}` (TM-2, extended TM-3/TM-5) is a generic read of any manifest section's rows with `type`/`status`/`severity`/`origin`/`stale` filters, every row now carrying `stale`; TM-5's `reviews` section additionally merges live `audit_log` security events (`merge.py::security_audit_log_events`, reusing `redact.mask_audit_log_target`) alongside curated `reviews.yaml`. `GET /stale` and `GET /search` are new TM-5 endpoints — the latter (`merge.py::search_corpus` + `search_mitre_techniques`) is a bounded scan over the already mtime-cached corpus plus one MITRE query, not an index subsystem (CLAUDE.md danger zone 6: this qualifies as light, not heavy, request-path work).
4. **UI (`frontend/src/pages/security-architecture/`):** `/security-architecture` route, header tab **ARCH**. Three-panel shell: left nav from `GET /manifest`'s `sections[]`; `overview` → `OverviewSection` (TM-5: adds an "Export PDF" button); `mitre_attack` → `MitreSection`; `threat_scenarios` → `ThreatScenariosSection` (TM-5: per-scenario "Export PDF" button on every row); `system_architecture` → `ArchitectureGraphSection` (TM-4: SVG pan/zoom graph — a single `<g transform="translate(...) scale(...)">` driven by pointer-drag pan and a native non-passive `wheel` listener for zoom, wheel min 0.15× / fit min 0.08× / max 4×; canvas locked to ~70vh with overflow hidden so the page does not grow with node count; cluster filter chips, node-label search with amber highlight, hover/select shows connected edges only and dims non-neighbors; labels truncated inside node rects; clicking or Enter-selecting a node sets `?node=` and populates the context rail); `trust_boundaries` → `TrustBoundariesSection` (TM-4: vertical flow cards); `attack_surface` → `AttackSurfaceSection` (TM-4: endpoint list with linked-control count); `risks` → `RiskRegisterSection` (TM-5: `AdminDataGrid` wrapper, origin filter tabs, STALE badge from the server's `stale` flag, CSV export (`utils/exportCsv.js`) + PDF export (`utils/securityArchitecturePdf.js::downloadRiskRegisterPdf`)); `security_decisions` → `DecisionsSection` (TM-5: expandable ADR-style cards — decision/alternatives/tradeoffs/consequences); `abuse_cases` → `AbuseCasesSection` (TM-5: in-page search over title/summary/category, attack-flow/impact/current-protection/remaining-risk fields); `reviews` → `ReviewHistorySection` (TM-5: chronological timeline merging curated review passes with live audit-log events); `stale` (virtual, not a manifest nav item) → `StaleRecordsSection` (TM-5: Overview tile drill-through only); every other section still renders `GenericSection`. **Global search (TM-5):** `GlobalSearch.jsx` in the topbar, debounced `GET /search`, results grouped by entity type, arrow-key navigable, Enter opens the matching section. **Context rail (TM-4, first phase to populate it):** selecting a graph node round-trips `?node=<id>` through the URL like every other selection in this module, and renders `ContextRail.jsx` (`GET /context/{node_id}`) in the persistent right rail — endpoints, controls, tables/referenced-by, and source refs, without reflowing the graph panel. All state — `?section=&type=&status=&severity=&origin=&node=` — round-trips through the URL.
5. **PDF export (TM-5, spec §5.16):** `utils/securityArchitecturePdf.js` follows the existing jsPDF pattern exactly (`utils/huntPackPdf.js`/`pdfReport.js` — lazy `import('jspdf')`, shared `exportCommon.js` branding constants, local page-layout helpers; no new dependency). Three exports: Overview posture snapshot (every tile verbatim, no client-side arithmetic), Risk Register (the exact rows currently in view), and a selected Threat Scenario. Every export's footer carries the corpus version, generated timestamp, and — when any included row's `stale` flag is `true` — an explicit "Contains N stale records" disclaimer, so a PDF is never more confident than the screen it came from.
6. **MITRE matrix scope narrowing (TM-3, documented deviation):** spec §5.6 names an `AttackNavigatorMatrix` with 5 coverage layers (Detection/Correlation/YARA/Threat feed/AI). Only Detection has a live data source in this codebase. TM-3 ships a dense grouped-by-tactic list with the one real layer rather than fabricate the other four.
6. **Framework workspaces (TM-6) — the user's own threat surface, not BRIEFR's.** `security_architecture/frameworks/` adds four analyst-facing workspaces — `cwe`, `owasp`, `capec`, `stride` — served entirely from live DB data via `GET /frameworks/{id}` (no corpus file, like `mitre_attack`). This deliberately reframes spec §4.5: instead of "BRIEFR watches BRIEFR" (self-stack), the frameworks describe whatever the operator is defending. A **Scope** selector (`all` | `stack` | `watchlist` | `kev`, + `severity`) resolves to a bounded live query over the ingested `cves` corpus (`frameworks/scope.py`) — `stack` reuses `routers.cves._stack_match_clause` against the caller's saved stack (soft-resolved from the `briefr_at` cookie) or an explicit `?stack=` override, reporting `unavailable`+`reason` rather than a silent whole-corpus fallback when neither exists. All four workspaces are projections of one live aggregation — the CWE weakness classes in `cves.cwe_ids` across that scope (`frameworks/aggregate.py`): CWE is direct; OWASP Top 10 2021, CAPEC (MITRE CWE→CAPEC), and STRIDE (documented heuristic) are reference-mapping projections of the same CWEs (`frameworks/reference.py`, standard published mappings kept as versioned code, not curated corpus). Counting is distinct-CVE per category (never CWE-occurrence sums that double-count an advisory); CWEs with no mapping surface in an explicit `unmapped` bucket so the parts reconcile with the whole; every row ships `example_cves` (KEV/EPSS-prioritised) as its drill-through, and the response reports `sample_size` vs `total_in_scope` so a capped aggregation is visibly capped (CLAUDE.md danger zone 6 — bounded, request-path-safe). **UI:** hosted inside Admin → Security posture (`SecurityPosturePage.jsx`, PM-4a), a FRAMEWORKS subtab group after the operator posture sections, each rendered by the shared `FrameworkSection.jsx` with the Scope bar; example CVEs open the CVE drawer in a new tab. The self-referential posture material (self-stack exposure, control active-flags, and future ASVS/NIST CSF control-backed verification) stays operator/self-monitoring scope, distinct from these analyst threat frameworks.
7. **Program complete at TM-5; TM-6 framework workspaces (CWE/OWASP/CAPEC/STRIDE) shipped:** risk register, decision records, review history, abuse cases, global search, and PDF export (spec `threat-modeling-security-architecture.md` §8 TM-5) close the committed program (TM-0→TM-5, 5 PRs, 11 sections). TM-6 ships the four live-data-backed framework workspaces above; NIST CSF / ASVS (operator control-backed self-assessment) and a scheduled self-monitoring/remediation job remain follow-up work. TM-4 also documented one spec staleness in `manifest.yaml`'s notes: spec §2.2's navigation catalog uses kebab-case section ids (`system-architecture`, `trust-boundaries`, `attack-surface`); code has used snake_case since TM-1 and kept that convention rather than rewriting the established ids.

### G. ML assist — embeddings + LLM product extraction (V1.3, env-gated)

Both features follow the ML placement rules (`docs/planning/ROADMAP.md`): env-gated, CPU-only, scheduler-side only, deterministic fallback, tool fully functional with ML disabled. **Both are off by default.**

**Similar CVEs via embeddings (`EMBEDDINGS_ENABLED=1`):**

1. **Scheduler writes:** `embeddings_backfill` (every `EMBEDDINGS_SYNC_INTERVAL_HOURS`, default 6h) embeds CVE descriptions with a local ONNX model (`ml/embeddings.py`, fastembed, `EMBEDDINGS_MODEL=BAAI/bge-small-en-v1.5`) and stores L2-normalized float32 vectors as BLOBs in `cve_embeddings`. Capped at `EMBEDDINGS_MAX_PER_RUN` per cycle; inference runs in a worker thread so the event loop stays responsive. The `fastembed` package is an optional install — if missing, the job logs one warning and skips. The model downloads into `EMBEDDINGS_CACHE_DIR` — production runs under systemd `ProtectSystem=strict`, so the unit sets `/var/lib/briefr/models` (in `ReadWritePaths`, plus `HF_HOME` for the hf-xet chunk cache); the default home-dir HuggingFace cache would fail with EROFS.
2. **pgvector foundation (E1):** Alembic `032` requires a pgvector-capable Postgres image, installs `CREATE EXTENSION vector`, creates multi-entity `embeddings` (`vector(384)` + HNSW for the active CVE model), and copies existing `cve_embeddings` BLOBs into it (`content_hash` placeholder `migrated:…`). Legacy `cve_embeddings` stays for one release. **E2** will write new vectors to `embeddings`; **E3** will switch related/search to ANN.
3. **Request path reads only:** `GET /api/cves/{id}/related` does **no model inference** — it scans stored vectors (still BLOB/NumPy until E3). Similarity is exact brute-force cosine with NumPy (vectors normalized at write time, so cosine = dot product).
4. **Deterministic fallback:** embeddings disabled, target CVE not embedded yet, or zero hits → the endpoint serves the pre-V1.3 shared-product heuristic. `meta.method` reports which path responded; embedding hits carry an additive `similarity` field.

**LLM product extraction (`LLM_PRODUCT_EXTRACTION_ENABLED=1` + `GROQ_API_KEY`):**

1. `llm_product_extraction` (every `LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS`, default 6h) selects CVEs with **no CPE data and empty `affected_products`** (NVD-unanalyzed), up to `LLM_PRODUCT_EXTRACTION_MAX_PER_RUN` per run.
2. Groq calls go through `resilient_client` (source `groq`, `retries=0` — quota is never burned by retry loops; circuit-open aborts the run). Extracted `{vendor, product, version_range}` entries are normalized to the existing `vendor:product` format.
3. **Write guard + provenance:** products are written only while the field is still empty, and the row is marked `affected_products_source='llm'`. A later NVD sync with official CPE data supersedes the LLM products and clears the marker; an NVD sync that still carries no CPE data does **not** wipe them (upsert CASE rules in `database.py`).
4. **Negative caching:** every completed extraction (including ones that found no products) is recorded in `feed_cache` (`llm_products:<id>`, 7-day window) so the same CVE never costs quota twice. Errors (timeouts, 5xx, rate limits) are **not** cached — the CVE is retried on the next run; repeated provider failures trip the Groq circuit breaker, which aborts the run.

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

- **Audit:** `audit_log` table (actor, action, target, timestamp) written by manual `POST /api/refresh*` calls, backup/restore, and all admin actions (`routers/admin.py`). Actor is `system` for backups/restores; empty for request-driven actions until app login lands. Admin pane exposes it at `GET /api/admin/audit-log` with prefix filter (V1.4 shipped).
- **Auth direction:** BRIEFR ships built-in app login (shipped). Admin and **ingest** `POST /api/refresh*` routes require an `admin` role session. **`POST /api/auth/refresh`** is available to any signed-in user and rejects sessions past `sessions.expires_at` or with token reuse (revokes all user sessions). The legacy shared admin-key header was removed in Sprint A0.

### Rate limiting + structured logging (V1.2 §5.5)

- **Rate limiting:** in-memory token buckets (`rate_limit.py`) on the abuse-prone routes — `POST /api/ioc/lookup` (burns external API quota per cache miss), all `POST /api/refresh*` (kick off heavy ingest), and `GET /api/wallboard` (kiosk poll). Keyed per client IP; capacity = the per-minute rate, continuous refill. Over the limit → `429` with `Retry-After` (whole seconds). Defaults: `RATE_LIMIT_IOC_PER_MINUTE=30`, `RATE_LIMIT_REFRESH_PER_MINUTE=10`, `RATE_LIMIT_WALLBOARD_PER_MINUTE=60`; `RATE_LIMIT_ENABLED=0` disables. The deploy deliberately pins uvicorn to one worker (`deploy/briefr-backend.service`) because the buckets are in-memory and per-worker; more workers would multiply every limit. The refresh bucket is consumed **before** the admin-key check, so unauthenticated bursts cannot bypass it.
- **Wallboard (V1.4 Theme 4):** `GET /api/wallboard` (`wallboard/service.py`) aggregates six read-only tiles (KEV-on-stack count, 24h brief highlights, top risk CVEs via canonical `calculate_risk_score`, ingest health subset, Forge gap summary, incident headline ticker) into one `feed_cache` payload (~45s TTL). Optional `WALLBOARD_TOKEN` read-only gate (`X-BRIEFR-Wallboard-Token` header only — Sprint A7 dropped `?token=`, which leaked into access logs). Frontend `/wallboard` is chromeless — 3×2 grid, 90s poll, rotating tile focus, scrolling ticker. No admin routes, secrets, or write actions exposed.
- **Rate-limit client identity (anti-spoofing):** forwarded headers are honoured only when the socket peer is a loopback proxy (nginx/cloudflared proxy_pass from 127.0.0.1 — `deploy/nginx-briefr*.conf`); direct connections are keyed by socket address, so a spoofed header cannot mint fresh buckets. Behind the tunnel the order is `CF-Connecting-IP` (overwritten at the Cloudflare edge), then the **rightmost non-loopback** `X-Forwarded-For` hop (nginx appends `$remote_addr`; leftmost hops are client-controlled), then `X-Real-IP`. Bucket storage is bounded: idle buckets are pruned, and a flood of distinct keys past a hard cap evicts least-recently-seen buckets (bounded memory beats a remotely triggerable OOM). Residual risk: a LAN host talking to nginx directly can still forge headers — acceptable for the Access-gated private beta; revisit with built-in app login.
- **Structured logging:** `structured_logging.py` emits one JSON object per line on stderr (journald-friendly): `ts`, `level`, `logger`, `message`, `request_id`, plus any `extra={...}` fields. A `request_context` middleware (outermost) assigns each request an ID (honours a well-formed incoming `X-Request-ID`, else generates one), returns it in the `X-Request-ID` response header, and logs a `briefr.access` line per request (`method`, `path`, `status`, `duration_ms`, `client`). uvicorn's startup/error loggers are rerouted through the same JSON handler; uvicorn's own access log is disabled in JSON mode (the `briefr.access` line replaces it — it carries the request ID). Unhandled exceptions are logged by the middleware itself (with `request_id`, `exc_info` and the request metadata) before the contextvar resets, then re-raised. `LOG_FORMAT=plain` restores the previous human-readable format.
- **Production posture self-check (Sprint A6):** `settings.production_posture_warnings()` reports every unsafe flag in the current config — `RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, `WALLBOARD_TOKEN` unset. `main.py` startup logs one warning per entry when `BRIEFR_ENV=production`; `GET /api/admin/security` returns the same list (`posture_warnings`) plus `environment`, and the admin Security panel renders each as an amber callout.
- **Admin log viewer (V1.4 Theme 3):** the same `structured_logging` module attaches a fixed-size in-process ring buffer (`_RingBufferHandler`, capacity 500) to the root logger. Every `INFO+` record is mirrored into the buffer with a derived `category` field (`Application`, `Scheduler`, `Backup`, `Webhooks`, `Security`) and secret-like `extra` keys redacted. `GET /api/admin/logs` (admin-gated, refresh rate-limited) tails the buffer with `level`, `logger`, `request_id`, and `category` filters — no shelling out to journald. The admin pane **Application logs** page surfaces the tail with level/category/logger/request_id filters, auto-refresh, and NDJSON export.

### Backup archive encryption (`age`, V1.2)

- **What:** backup archives (SQLite + `.env` with all API keys + manifest) are encrypted to the age format (X25519, via `pyrage` — interoperable with the `age` CLI) and named `briefr-*.tar.gz.age`. The identity file is `BACKUP_AGE_KEY_FILE` (production default `/var/lib/briefr/keys/backup-age.key`, generated by `deploy/briefr-backup.sh` / `python -m backup keygen` on first run, mode 0600).
- **Key placement:** `backup/manager.py` **refuses to encrypt when the key sits inside `BACKUP_DIR`** — the point is that a stolen archive copy is useless without a file that never travels with it. The key stays readable by the `briefr` service user so restore (`briefr-restore.sh`) and **startup auto-restore** (`ensure_db_or_restore`) decrypt transparently; pre-encryption `.tar.gz` archives keep restoring as before.
- **Scope honesty:** this protects **off-site / at-rest archive copies only** (rclone/S3, stolen disks, leaked archive directories). A compromised host or service user can read the key — see `docs/archive/THREAT_MODEL.md` § Scope of backup encryption.
- **Opt-out:** `BACKUP_AGE_KEY_FILE=""` forces plaintext archives; dev machines without the default key file are unchanged.

### Push notifications (V1.3 Theme 8 → V1.4 engine)

- **Engine:** `webhooks/engine.py` dispatches events (`kev_alert`, `backup_failure`, `health`, `watchlist_alert`, `kev_backlog`, `ioc_watchlist_hit`) to one or more **destinations** loaded from env vars and the `webhook_destinations` table. Env seeds are upserted on startup (`sync_env_destinations_to_db`); per-destination `enabled` and `event_types` can be overridden in SQLite via admin API.
- **Built-in destinations:** Discord (`DISCORD_WEBHOOK_URL`), Telegram (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`), optional generic HTTPS POST (`WEBHOOK_GENERIC_URL`). Each channel can be independently enabled/disabled (`*_WEBHOOK_ENABLED`) and subscribed to event types (`*_WEBHOOK_EVENTS`).
- **Transport:** outbound webhook HTTP uses `webhooks/ssrf.py` — **https only**, DNS resolve + block private/reserved ranges (RFC1918, RFC 6598 CGNAT `100.64.0.0/10`, 127.0.0.0/8, ::1, 169.254.0.0/16, 0.0.0.0, unique-local IPv6), connect to resolved IP with original `Host` header (DNS-rebinding safe), **no redirect following**, 10s timeout, no internal API keys on outbound headers. Failures recorded via `resilient_client` health (`webhook.{destination_id}`).
- **Dedupe:** `webhook_alert_log` stores one row per `(event_type, target)`; `webhook_delivery_log` records every delivery attempt (destination, status, error).
- **KEV-on-stack:** after each `kev_metadata_sync`, newly flagged KEV CVEs matching `BRIEFR_STACK_TERMS` dispatch `kev_alert` (deduped per CVE).
- **IOC watchlist hits:** after each `ioc_retro_match`, local OTX/ThreatFox mirror matches dispatch `ioc_watchlist_hit` (deduped per user/value/source).
- **Backup dead-man:** `backup_deadman_check` dispatches `backup_failure` when the newest archive is older than `2 × BACKUP_INTERVAL_HOURS`. Clears dedupe when a fresh backup appears.
- **Admin:** `GET /api/admin/webhooks/destinations`, `PATCH /api/admin/webhooks/destinations/{id}`, `GET /api/admin/webhooks/delivery-log`, `GET /api/admin/webhooks/log` (dedupe log).

### SQLite over PostgreSQL

- **Why:** Single-user beta, zero ops overhead, `aiosqlite` async support, `feed_cache` + `ioc_cache` adequate at current scale.
- **Mitigations (v1.1):** `PRAGMA journal_mode=WAL`, `busy_timeout=30000`, and `connect(timeout=30)` in `database.get_db()`. Combined Incidents feed loads RSS + ATLAS on a **single connection** (`case_study_feed.py`) to avoid `database is locked` under concurrent scheduler writes.
- **Trade-off:** No horizontal scaling or multi-writer safety — acceptable for v1.1 single-server deploys.

### APScheduler over Celery/Redis

- **Why:** No message broker; embedded in FastAPI process; sufficient for ~12 recurring jobs + 1 one-shot startup backfill (`scheduler.py:start_scheduler`).
- **Trade-off:** Jobs lost on process restart (mitigated by `maybe_run_on_startup` bootstrap when CVE count &lt; 10); no distributed workers.

### Background-job ownership registry (idempotency SSOT — audit F2.2 / IDEM-C)

Two background-job systems coexist. **Every job is owned by exactly one system**, in a
**disjoint namespace** (APScheduler ids never carry the `jobs:` prefix), so a job can never
be registered in both — asserted by `tests/test_job_ownership_registry.py`. At-least-once
delivery means each durable task must be idempotent; the table records the guarantee.

| System | Owner / entrypoint | Jobs | Idempotency mechanism |
|--------|--------------------|------|-----------------------|
| **APScheduler** (in-process) | `scheduler.py:start_scheduler`; gated by `BRIEFR_SCHEDULER_ENABLED` (single owner across replicas) | ~12 recurring syncs + startup backfill (ids in `scheduler_locks.py`, e.g. `nvd_incremental_sync`, `epss_score_sync`) | `max_instances=1` + `coalesce=True` per job; per-job `asyncio.Lock` (`scheduler_locks._LOCKS`); manual `/api/refresh*` shares the same locks |
| **Procrastinate** (durable queue) | `jobs/app.py` + `jobs/worker.py:start_inprocess_worker`; gated by `PROCRASTINATE_ENABLED`, Postgres-only | `jobs:health_ping`, `jobs:stack_backfill` (`jobs/tasks.py`) | `stack_backfill`: per-run `queueing_lock` on defer (IDEM-B) + atomic `claim_run_running` run gate (IDEM-A) — safe under duplicate defer, retry, or overlap with the in-process fallback |

Because `claim_run_running` (IDEM-A) makes stack-backfill execution exactly-once regardless of
how many kicks reach it, an overlap of the durable job and the in-process fallback across a
`PROCRASTINATE_ENABLED` flag flip cannot double-run a run — it is contained at execution, and
duplicate *enqueues* are rejected by the `queueing_lock` (IDEM-B). New durable tasks must add a
row here with their idempotency key before merge.

### Plain JSX + CSS over component library

- **Why:** Full control over dark terminal aesthetic; smaller bundle (`package.json` — React + Vite only).
- **Trade-off:** More custom CSS; no pre-built accessibility primitives.

### Backend-canonical risk scoring

- **Why:** One reproducible score for drawer, brief, exports, and future alerts; no Python/JS drift.
- **Trade-off:** `POST /api/cves/{id}/risk` on drawer open (and on profile change); cards show momentum arrows only until drawer warms cache.

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
| Idempotency | PARTIAL | Upserts + scheduler locks; fix `cve_change_history` duplicate inserts. Graceful shutdown (PR-R1): lifespan waits — bounded by `SHUTDOWN_DRAIN_TIMEOUT_SECONDS` (10s default) — for lock-holding jobs (`scheduler.wait_for_running_jobs`) and registered fire-and-forget tasks (`task_registry.drain_background_tasks`) before closing pools |
| Caching Strategy | PARTIAL | `feed_cache`/`ioc_cache` exist; add React Query + stats cache |
| API Consistency | PARTIAL | v1.2 response envelope (`data` + `meta`) |
| Config Management | PARTIAL | `settings.py`; centralize weights and TTLs |
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
| Groq | `ai/summary.py`, `ml/product_extraction.py` | Executive summary; LLM product extraction | `GROQ_API_KEY` | Console quota | Model: `llama-3.1-8b-instant`; summary falls back to Anthropic/template |
| Anthropic | `ai/summary.py` | Executive summary | `ANTHROPIC_API_KEY` | Console quota | Falls back to template |
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

## 7. Known Limitations — v1.1 Beta

- **Single-user SQLite** — no concurrent write safety under heavy parallel writes.
- ~~No app-level authentication yet~~ — **superseded:** built-in app login shipped; admin/refresh routes require a session with the `admin` role (Sprint A0 removed the interim header gate).
- **`POST /api/investigation/summary`** — legacy route; delegates to `generate_investigation_summary` → `generate_executive_summary`. Prefer `POST /api/ai/summary` for new clients.
- **No circuit breakers** on external APIs (timeouts only).
- **`DetailDrawer.jsx` — ~1,500 lines** — maintenance risk; v1.2 split planned.

### CI — frontend smoke (V1.2)

GitHub Actions job **`playwright-smoke`** in `.github/workflows/backend-tests.yml` runs `tests/test_playwright_smoke.py` with `PLAYWRIGHT_SMOKE=1`: seeds SQLite via `scripts/seed_screenshot_data.py`, builds the incident-feed snapshot, serves the production Vite bundle (`vite preview` with `/api` proxy), and asserts five Chromium interactions — BRIEF CVE cards render, quick-filter click scroll-anchors to the feed (regression for feed UX), CVE drawer open/close restores focus, IOC tab accepts input, Incidents tab renders cards. The default PR pytest job skips these tests (no browser required).

---

## 8. Beta V1.2 roadmap

Near-future engineering and product intent lives in **[`Beta V1.2.md`](archive/beta/Beta%20V1.2.md)** — themes include router split, `services/` layer, `resilient_client.py`, shared risk config, frontend hooks, auth, and E2E CI. Update that document when V1.2 phases ship.

---

## Related documentation

- [`docs/ONBOARDING.md`](ONBOARDING.md) — contributor entry point, local dev, tests, troubleshooting
- [`Beta V1.2.md`](archive/beta/Beta%20V1.2.md) — roadmap and planned work
- [`API_REFERENCE.md`](API_REFERENCE.md) — endpoint catalog
- [`docs/archive/snapshots/TECHNICAL_INVENTORY.md`](archive/snapshots/TECHNICAL_INVENTORY.md) — schema, scheduler, stack
- [`docs/archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md) — startup and request journeys
- [`docs/archive/snapshots/FOLDER_STRUCTURE_GUIDE.md`](archive/snapshots/FOLDER_STRUCTURE_GUIDE.md) — file-by-file map
- [`docs/diagrams/`](diagrams/) — Mermaid diagrams (render in GitHub, VS Code, Notion). Master: [`system-graph.mermaid`](diagrams/system-graph.mermaid). Flows: CVE feed/detail, IOC lookup, NVD sync, PDF export, error handling (`flow_error_handling.mermaid`), startup, schema ERD.
