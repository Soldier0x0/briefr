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
│ APScheduler (scheduler.py) — 11 recurring jobs (+1 opt-in) + 1 one-shot     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. NVD incremental      → cves, sync_state, cve_change_history, feed_cache  │
│ 2. KEV metadata         → kev_deadlines, cves.is_kev, summaries             │
│ 3. EPSS scores          → cves.epss_score, epss_history                     │
│ 4. MITRE+ATLAS weekly   → mitre_*, atlas_*, cve_*_map, has_ai_context       │
│ 5. OTX nightly          → otx_cve_pulses, otx_pulse_iocs, feed_cache        │
│ 6. Incident RSS (4h)    → feed_cache (incident_rss:*)                       │
│ 7. Correlation nightly  → correlation_*, feed_cache, otx_pulse_iocs         │
│ 8. Vulnrichment (6h)    → cves (additive CVSS/CWE/CPE)                      │
│ 9. cvelistV5 delta (30m)→ cves, sync_state.cvelistv5_head_sha               │
│ 10. Embeddings backfill → cve_embeddings (no-op unless EMBEDDINGS_ENABLED)  │
│ 11. LLM product extract → cves.affected_products(+_source), feed_cache      │
│ 12. Exploit sources (opt-in) → cve_exploits, cves.has_poc                   │
│ 13. EPSS history backfill (one-shot) → epss_history, sync_state marker      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SQLite (briefr.db) — 24 tables — see TECHNICAL_INVENTORY.md                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI (main.py + routers/) — /api/* — ~30 endpoints                       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React + Vite (frontend/src)                                                 │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│ BRIEF tab        │ FEED tab         │ IOC LOOKUP tab   │ INCIDENTS tab    │ DetailDrawer       │
│ MorningBrief.jsx │ CVEFeed.jsx      │ IOCLookup.jsx    │ CaseStudies.jsx  │ (global overlay)   │
│ → GET /brief     │ → GET /cves      │ → POST /ioc      │ → combined feed  │ → 6+ sub-routes    │
│ BriefCharts.jsx  │ CVECard.jsx      │                  │                  │ explainable risk   │
│ WhatChangedPanel │ TimelineHeatmap  │                  │                  │ breakdown (math)   │
│ TimelineHeatmap  │ Sidebar.jsx      │                  │                  │                    │
│ (side-by-side    │                  │                  │                  │                    │
│  with What       │                  │                  │                  │                    │
│  changed ≥901px) │                  │                  │                  │                    │
│ StatsRow.jsx     │                  │                  │                  │                    │
│ Hero stack bar   │                  │                  │                  │                    │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

Mermaid source: [`docs/diagrams/architecture.mermaid`](docs/diagrams/architecture.mermaid)

### DB tables → primary API readers

| Table(s) | Primary endpoints | Frontend consumers |
|---|---|---|
| `cves` | `GET /api/cves`, `GET /api/cves/{id}`, `GET /api/stats`, `GET /api/brief` | CVEFeed, CVECard, DetailDrawer, StatsRow, TimelineHeatmap, MorningBrief |
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
| `audit_log` | Written by `POST /api/refresh*` and backup/restore (admin UI reads in V1.4) | — (not exposed yet) |
| `hunt_packs` (+ `mitre_techniques`, `cve_technique_map`) | `GET /api/forge/coverage`, `GET /api/hunt-packs/{technique_id}`, `POST /api/hunt-packs/generate` | Forge tab (coverage map + hunt pack panel) |
| `watchlist` | `GET/POST/DELETE /api/watchlist`; join on `GET /api/cves` for sort/filter | CVECard + DetailDrawer pin/snooze; WATCHLIST feed filter |
| `scoring/risk.py` constants | `GET /api/config/risk` — v1.1b weights, no DB | `riskScore.js` fetchAndCacheRiskWeights (startup) |

---

### Risk score weight single-sourcing (v1.1b)

`GET /api/config/risk` reads the six component weights directly from
`backend/scoring/risk.py` and returns them as JSON. `frontend/src/scoring/riskScore.js`
fetches this once at startup (fire-and-forget) and caches the result in a
module-level variable. If the request fails, the hardcoded fallback constants
(identical to the backend values) are used unchanged. The drawer risk breakdown
shows per-component math (`score × weight × 100 = points`) using these weights
plus `GET /api/cves/{id}/momentum` signals for the momentum component.

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
2. **Server enrichment (serial awaits in handler):** `cve_exploits` rows (scheduler-fed sources first), on-demand Sploitus fallback, GreyNoise scans, OTX pulses, OSV packages, CIRCL merge (`routers/cves.py:get_cve`).
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

### F2. Analyst Brief charts (Chart.js, V1.3)

1. **UI:** `BriefCharts.jsx` on the BRIEF tab (below the SVG activity heatmap). The component is `React.lazy`-loaded; `chart.js` is dynamically imported into a separate Vite chunk (`chart-*.js`) so the main bundle stays lean and CSP `script-src 'self'` is satisfied without a CDN.
2. **Charts (3):**
   - **Severity / volume timeline** — `GET /api/stats/timeline?days=30` → line chart (total + critical counts per UTC day).
   - **KEV due-date histogram** — `GET /api/kev/deadlines?sort=urgent` → bar chart bucketed Overdue / 0–7d / 8–14d / 15–30d / 31d+.
   - **Top EPSS movers** — `GET /api/changes?field=epss_score&since_hours=168&limit=50` → horizontal bar chart of the top 10 positive EPSS deltas (same display-precision filter as What changed).
3. **Refresh:** parallel fetch on mount + 5-minute poll (`POLL_MS`); cancellation guards on unmount/filter change per house convention.
4. **Motion:** `prefers-reduced-motion: reduce` disables Chart.js animation (`duration: 0`); global CSS from PR #90 still zeroes transitions site-wide.
5. **Layout:** three-column grid at ≥1100px; stacks to one column on narrower viewports (1080p-safe).

### F. Forge — detection coverage + hunt packs (V1.3 MVP)

1. **UI:** `Forge.jsx` (FORGE tab) loads `GET /api/forge/coverage` on mount; the
   optional "MY STACK ONLY" toggle re-fetches with the saved stack from
   localStorage (`briefr_stack` — same terms as the BRIEF stack filter).
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
   `GET /api/cves/{cve_id}/detection` (drawer Detect tab). Rule proof on live
   logs and HyperDX provisioning are out of scope until V1.5/V1.4.

### F. Watchlist — pin / snooze (V1.3)

Single-user instance: `watchlist` rows are not keyed by identity until built-in app login ships.

1. **Persistence:** `watchlist` table (`cve_id` PRIMARY KEY, `state` `pin`|`snooze`, `snooze_until`, `created_at`). Idempotent forward migration in `database.py:init_db`.
2. **API:** `GET/POST/DELETE /api/watchlist` (`routers/watchlist.py`). POST validates the CVE exists; snooze default is 7 days (`snooze_days` 1–365).
3. **Feed behaviour (`GET /api/cves`):** `LEFT JOIN` active watchlist rows. Pinned CVEs sort first. Active snoozes (`datetime(snooze_until) > datetime('now')`) are excluded from the default feed. `watchlist_only=true` returns only watchlist rows (pins + active snoozes) so analysts can review snoozed items.
4. **UI:** `useWatchlist` hook loads state on mount; Pin / Snooze 7d on `CVECard` and `DetailDrawer`; **WATCHLIST** quick-filter chip. Mutations bump a version counter so `CVEFeed` refetches without a full page reload. No `localStorage`.

### G. ML assist — embeddings + LLM product extraction (V1.3, env-gated)

Both features follow the ML placement rules (`docs/ROADMAP.md`): env-gated, CPU-only, scheduler-side only, deterministic fallback, tool fully functional with ML disabled. **Both are off by default.**

**Similar CVEs via embeddings (`EMBEDDINGS_ENABLED=1`):**

1. **Scheduler writes:** `embeddings_backfill` (every `EMBEDDINGS_SYNC_INTERVAL_HOURS`, default 6h) embeds CVE descriptions with a local ONNX model (`ml/embeddings.py`, fastembed, `EMBEDDINGS_MODEL=BAAI/bge-small-en-v1.5`) and stores L2-normalized float32 vectors as BLOBs in `cve_embeddings`. Capped at `EMBEDDINGS_MAX_PER_RUN` per cycle; inference runs in a worker thread so the event loop stays responsive. The `fastembed` package is an optional install — if missing, the job logs one warning and skips. The model downloads into `EMBEDDINGS_CACHE_DIR` — production runs under systemd `ProtectSystem=strict`, so the unit sets `/var/lib/briefr/models` (in `ReadWritePaths`, plus `HF_HOME` for the hf-xet chunk cache); the default home-dir HuggingFace cache would fail with EROFS.
2. **Request path reads only:** `GET /api/cves/{id}/related` does **no model inference** — it scans stored vectors. Default path is exact brute-force cosine with NumPy (vectors normalized at write time, so cosine = dot product); `sqlite-vec` is used as an accelerator only when importable and the Python build supports loadable extensions (never a hard dependency; identical rankings).
3. **Deterministic fallback:** embeddings disabled, target CVE not embedded yet, or zero hits → the endpoint serves the pre-V1.3 shared-product heuristic. `meta.method` reports which path responded; embedding hits carry an additive `similarity` field.

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

- **Audit:** `audit_log` table (actor, action, target, timestamp) written by manual `POST /api/refresh*` calls and by backup runs/restores (`backup/manager.py`, actor = `system`, sync + best-effort so a locked DB never fails a backup or admin action). Admin pane reads it in V1.4.
- **Auth direction:** BRIEFR ships as a self-hosted platform with a **built-in app login** before public release (not enterprise SSO / edge-auth based). Until then the beta runs on a trusted private network; `BRIEFR_ADMIN_API_KEY` optionally gates refresh routes. `audit_log.actor` stays empty for request-driven actions until login lands (`request.state.user_email` is the wiring hook). A Cloudflare-Access JWT middleware was prototyped and dropped — see `docs/ROADMAP.md` amendments.

### Rate limiting + structured logging (V1.2 §5.5)

- **Rate limiting:** in-memory token buckets (`rate_limit.py`) on the abuse-prone routes — `POST /api/ioc/lookup` (burns external API quota per cache miss) and all `POST /api/refresh*` (kick off heavy ingest). Keyed per client IP; capacity = the per-minute rate, continuous refill. Over the limit → `429` with `Retry-After` (whole seconds). Defaults: `RATE_LIMIT_IOC_PER_MINUTE=30`, `RATE_LIMIT_REFRESH_PER_MINUTE=10`; `RATE_LIMIT_ENABLED=0` disables. SQLite pins the deploy to one uvicorn worker, so process-local buckets need no shared store. The refresh bucket is consumed **before** the admin-key check, so unauthenticated bursts cannot bypass it.
- **Rate-limit client identity (anti-spoofing):** forwarded headers are honoured only when the socket peer is a loopback proxy (nginx/cloudflared proxy_pass from 127.0.0.1 — `deploy/nginx-briefr*.conf`); direct connections are keyed by socket address, so a spoofed header cannot mint fresh buckets. Behind the tunnel the order is `CF-Connecting-IP` (overwritten at the Cloudflare edge), then the **rightmost non-loopback** `X-Forwarded-For` hop (nginx appends `$remote_addr`; leftmost hops are client-controlled), then `X-Real-IP`. Bucket storage is bounded: idle buckets are pruned, and a flood of distinct keys past a hard cap evicts least-recently-seen buckets (bounded memory beats a remotely triggerable OOM). Residual risk: a LAN host talking to nginx directly can still forge headers — acceptable for the Access-gated private beta; revisit with built-in app login.
- **Structured logging:** `structured_logging.py` emits one JSON object per line on stderr (journald-friendly): `ts`, `level`, `logger`, `message`, `request_id`, plus any `extra={...}` fields. A `request_context` middleware (outermost) assigns each request an ID (honours a well-formed incoming `X-Request-ID`, else generates one), returns it in the `X-Request-ID` response header, and logs a `briefr.access` line per request (`method`, `path`, `status`, `duration_ms`, `client`). uvicorn's startup/error loggers are rerouted through the same JSON handler; uvicorn's own access log is disabled in JSON mode (the `briefr.access` line replaces it — it carries the request ID). Unhandled exceptions are logged by the middleware itself (with `request_id`, `exc_info` and the request metadata) before the contextvar resets, then re-raised. `LOG_FORMAT=plain` restores the previous human-readable format. This is the prep work for the V1.4 log viewer.

### Backup archive encryption (`age`, V1.2)

- **What:** backup archives (SQLite + `.env` with all API keys + manifest) are encrypted to the age format (X25519, via `pyrage` — interoperable with the `age` CLI) and named `briefr-*.tar.gz.age`. The identity file is `BACKUP_AGE_KEY_FILE` (production default `/var/lib/briefr/keys/backup-age.key`, generated by `deploy/briefr-backup.sh` / `python -m backup keygen` on first run, mode 0600).
- **Key placement:** `backup/manager.py` **refuses to encrypt when the key sits inside `BACKUP_DIR`** — the point is that a stolen archive copy is useless without a file that never travels with it. The key stays readable by the `briefr` service user so restore (`briefr-restore.sh`) and **startup auto-restore** (`ensure_db_or_restore`) decrypt transparently; pre-encryption `.tar.gz` archives keep restoring as before.
- **Scope honesty:** this protects **off-site / at-rest archive copies only** (rclone/S3, stolen disks, leaked archive directories). A compromised host or service user can read the key — see `docs/THREAT_MODEL.md` § Scope of backup encryption.
- **Opt-out:** `BACKUP_AGE_KEY_FILE=""` forces plaintext archives; dev machines without the default key file are unchanged.

### Push notifications (V1.3 Theme 8)

- **Channels:** `webhooks/sender.py` delivers plain-text alerts to **Discord** (`DISCORD_WEBHOOK_URL`) and/or **Telegram** (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`). Channels are independent — configure one or both. Disabled when no channel env vars are set.
- **Transport:** all outbound delivery uses `resilient_client` (`retries=2`); health keys `webhook.discord` / `webhook.telegram` appear in `feeds.sources` after the first attempt.
- **KEV-on-stack:** after each `kev_metadata_sync`, newly flagged KEV CVEs (`mark_cves_as_kev` return value) are matched against `BRIEFR_STACK_TERMS` (comma-separated server-side stack — same matching rules as `GET /api/cves?stack=`). One alert per CVE, deduped in `webhook_alert_log`.
- **Backup dead-man:** `backup_deadman_check` scheduler job (every `max(1, BACKUP_INTERVAL_HOURS // 2)`) warns when the newest archive in `BACKUP_DIR` is older than `2 × BACKUP_INTERVAL_HOURS` (default 12h). Skipped when `BACKUP_ENABLED=0` or no webhook channel is configured. Clears its dedupe marker when a fresh backup appears.
- **V1.4:** full webhook engine (rules UI, delivery log viewer, SSRF protection) — see `Beta V1.4.md`.

### SQLite over PostgreSQL

- **Why:** Single-user beta, zero ops overhead, `aiosqlite` async support, `feed_cache` + `ioc_cache` adequate at current scale.
- **Mitigations (v1.1):** `PRAGMA journal_mode=WAL`, `busy_timeout=30000`, and `connect(timeout=30)` in `database.get_db()`. Combined Incidents feed loads RSS + ATLAS on a **single connection** (`case_study_feed.py`) to avoid `database is locked` under concurrent scheduler writes.
- **Trade-off:** No horizontal scaling or multi-writer safety — acceptable for v1.1 single-server deploys.

### APScheduler over Celery/Redis

- **Why:** No message broker; embedded in FastAPI process; sufficient for ~12 recurring jobs + 1 one-shot startup backfill (`scheduler.py:start_scheduler`).
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
| Observability | PARTIAL | ✅ Shipped — JSON structured logs with `request_id` (`structured_logging.py`), `X-Request-ID` on every response, token-bucket rate limiting on `/api/ioc/lookup` + `/api/refresh*` |

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
| Groq | `ai/summary.py`, `ml/product_extraction.py` | Executive summary; LLM product extraction | `GROQ_API_KEY` | Console quota | Model: `llama-3.1-8b-instant`; summary falls back to Anthropic/template |
| Anthropic | `ai/summary.py` | Executive summary | `ANTHROPIC_API_KEY` | Console quota | Falls back to template |
| GitHub | `detection/rule_sources.py` | Sigma/Elastic rule search | `GITHUB_TOKEN` (optional) | 60/hr anon | `[]` rules |
| RSS (6 sources) | `feeds/incident_news.py` | News cards (editorial titles filtered) | — | Per-feed | Per-source error in `errors[]` |
| CISA Vulnrichment | `feeds/vulnrichment.py` | CISA ADP CVSS / CWE / CPE gap-fill | `GITHUB_TOKEN` (optional) | 60/hr anon GitHub API | Log error; skip run |
| cvelistV5 | `feeds/cvelistv5.py` | CVE JSON 5.x + ADP (pre-NVD) | `GITHUB_TOKEN` (optional) | 60/hr anon GitHub API | Log error; watermark retained |

### Scheduler intel enrichment (V1.3)

Two repo-based feeds run **only on the scheduler** (never on the request path):

1. **Vulnrichment** (`vulnrichment_snapshot_sync`) — lists `cisagov/vulnrichment` tree each run (snapshot, no watermark), fetches JSON for CVE rows still missing NVD analysis fields (`cvss_score`, `severity`, `cwe_ids`), and merges additively. Official NVD ingest later supersedes CISA ADP values because NVD upserts overwrite `cvss_score` / `severity` / `cwe_ids`.
2. **cvelistV5** (`cvelistv5_incremental_sync`) — compares `sync_state.cvelistv5_head_sha` against `main` via GitHub compare API, fetches only changed `cves/**/CVE-*.json` paths, parses CNA-first CVE 5.x records, and merges additively (or inserts new CVE rows). First boot seeds the watermark from commits in the last `CVELISTV5_INITIAL_SINCE_DAYS` (default 7).

Health for both appears under `GET /api/health` → `feeds.sources.vulnrichment` and `feeds.sources.cvelistv5`.

**Rejected CVEs:** NVD `vulnStatus: Rejected` and cvelistV5 `cveMetadata.state: REJECTED` records are **not upserted**. Each NVD sync also runs `purge_legacy_rejected_cves` (rows whose description starts with `Rejected reason:`) and deletes any reject IDs seen in the current feed batch. cvelistV5 deltas delete matching rows when a file flips to `REJECTED`.

RSS sources defined in `feeds/incident_sources.py`: The Hacker News, Bleeping Computer, Krebs, Dark Reading, Schneier, CISA Advisories. Non-security editorial items (e.g. Dark Reading cartoon contests) are excluded via `EXCLUDED_NEWS_TITLE_PATTERNS` in `incident_news.py`.

---

## 7. Known Limitations — v1.1 Beta

- **Single-user SQLite** — no concurrent write safety under heavy parallel writes.
- **No app-level authentication yet** — built-in app login ships before the public self-hosted release; the beta instance runs on a trusted private network with an optional `X-BRIEFR-Admin-Key` gate on `POST /api/refresh*`.
- **`POST /api/investigation/summary`** — legacy route; delegates to `generate_investigation_summary` → `generate_executive_summary`. Prefer `POST /api/ai/summary` for new clients.
- **Risk weights duplicated** in `backend/scoring/risk.py` and `frontend/src/scoring/riskScore.js` — shared config planned for Beta V1.2.
- **No circuit breakers** on external APIs (timeouts only).
- **`DetailDrawer.jsx` — ~1,500 lines** — maintenance risk; v1.2 split planned.

### CI — frontend smoke (V1.2)

GitHub Actions job **`playwright-smoke`** in `.github/workflows/backend-tests.yml` runs `tests/test_playwright_smoke.py` with `PLAYWRIGHT_SMOKE=1`: seeds SQLite via `scripts/seed_screenshot_data.py`, builds the incident-feed snapshot, serves the production Vite bundle (`vite preview` with `/api` proxy), and asserts five Chromium interactions — BRIEF CVE cards render, quick-filter click scroll-anchors to the feed (regression for feed UX), CVE drawer open/close restores focus, IOC tab accepts input, Incidents tab renders cards. The default PR pytest job skips these tests (no browser required).

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
