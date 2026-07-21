# BRIEFR — Image briefs for documentation

Copy the **Miro / AI prompt** for each asset. Export as **PNG @2×** (or SVG). Save to `docs/assets/` using the **exact filename**.

**Brand tokens:** background `#0a0a08`, surface `#111110`, text `#e8e6df`, accent `#c8b88a`, success `#4a9e6a`, link `#6eb5ff`. Dark mode only. Clean SaaS spacing — not cluttered Mermaid.

---

## Deploy & operations

### 1. production-architecture

| Field | Value |
|-------|--------|
| **File** | `docs/assets/production-architecture.png` |
| **Used in** | [`SELF_HOST.md`](SELF_HOST.md), [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** Top-to-bottom self-hosted topology in **5 numbered zones**: (01) Analyst browser → (02) Optional Cloudflare Tunnel + nginx → (03) Application host `/opt/briefr` with FastAPI/Uvicorn, APScheduler, Admin → (04) Data plane PostgreSQL 16 + encrypted backups + optional model cache → (05) External intel APIs as a chip row (NVD, KEV, EPSS, OTX, VT, AbuseIPDB, etc.). Downward flow arrows between zones.

**Miro prompt:**

> Dark-mode professional system architecture diagram for a self-hosted security product "BRIEFR". Five horizontal zones stacked vertically with subtle tinted backgrounds and gold accent headers. Zone 01 CLIENT: web browser, React SPA. Zone 02 EDGE optional: Cloudflare Tunnel, nginx :80 proxy to :8000. Zone 03 APPLICATION: FastAPI, APScheduler (~26 registered jobs + optional catch-up/embeddings/detection-context jobs), admin console. Zone 04 DATA: PostgreSQL 16 + pgvector, pg_dump backups to /var/lib/briefr/backups. Zone 05 EXTERNAL: outbound API chips. Clean spacing, numbered labels, no clip art clutter. Colors: near-black #0a0a08, gold accent #c8b88a, green for database.

---

### 2. deploy-update-flow

| Field | Value |
|-------|--------|
| **File** | `docs/assets/deploy-update-flow.png` |
| **Used in** | [`SELF_HOST.md`](SELF_HOST.md) |

**Shows:** `briefr-update.sh` sequence: git pull → pre-update backup → frontend build → restart backend + nginx → optional pytest.

**Miro prompt:**

> Horizontal flowchart, dark theme: Deploy update pipeline for BRIEFR on Debian. Steps: git pull /opt/briefr → briefr-backup.sh pre-update → npm build frontend/dist → systemctl restart briefr-backend → reload nginx → health check /api/health. Gold arrows, monospace path labels, minimal boxes.

---

### 3. backup-restore-flow

| Field | Value |
|-------|--------|
| **File** | `docs/assets/backup-restore-flow.png` |
| **Used in** | [`SELF_HOST.md`](SELF_HOST.md), [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |

**Shows:** Timer (6h) + pre-update + manual → age-encrypted archive → restore path stops backend → pg_restore → restart.

**Miro prompt:**

> Dark SaaS diagram: PostgreSQL backup and restore for BRIEFR. Left: triggers (systemd timer 6h, pre-update script, manual). Center: pg_dump custom format inside age-encrypted tar at /var/lib/briefr/backups. Right: restore script stops backend, replaces DB and .env, startup auto-restore on failure. Use green for DB, gold for backup archive.

---

### 4. postgres-topology

| Field | Value |
|-------|--------|
| **File** | `docs/assets/postgres-topology.png` |
| **Used in** | [`SELF_HOST.md`](SELF_HOST.md) |

**Shows:** App (asyncpg pool) → PostgreSQL 16 (Docker or host) → volume; not SQLite.

**Miro prompt:**

> Simple dark infrastructure diagram: BRIEFR FastAPI with asyncpg connection pool connects to PostgreSQL 16 on 127.0.0.1:5432. Show Docker container optional label /opt/infra/postgres. DATABASE_URL required. No SQLite. Clean two-tier drawing.

---

## Concepts & pipelines

### 5. correlation-pipeline

| Field | Value |
|-------|--------|
| **File** | `docs/assets/correlation-pipeline.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md), [`USE.md`](USE.md) |

**Shows:** Horizontal pipeline: OTX nightly → PostgreSQL tables → `correlation/engine.py` → `GET /api/cves/{id}/correlation` → Detail drawer Intel tab. Below: four lanes (Campaigns, Infrastructure, Actor/sector, Temporal).

**Miro prompt:**

> Dark professional data pipeline diagram for "BRIEFR Correlation Engine v2". Left to right: OTX nightly job → PostgreSQL otx_pulse_iocs and campaign tables → correlation engine (no live external API) → REST API → CVE detail drawer Intel tab. Below, four equal cards explaining lanes: Campaigns, Infrastructure, Actor/sector, Temporal. Purple accent for correlation, gold arrows, explainable-not-ML callout.

---

### 6. ingest-pipeline

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ingest-pipeline.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** APScheduler jobs feeding PostgreSQL: NVD, KEV, EPSS, cvelistV5, Vulnrichment, OTX, MITRE, exploit sources, embeddings (optional).

**Miro prompt:**

> Dark scheduler diagram: APScheduler hub with spokes to external feeds (NVD, CISA KEV, EPSS, cvelistV5, Vulnrichment, OTX, MITRE ATT&CK+ATLAS, exploit sources). All write to central PostgreSQL cves and related tables. Show intervals (1h NVD, 15m KEV, etc.) as small labels. Gold accent, not overcrowded.

---

### 7. nvd-sync-detail

| Field | Value |
|-------|--------|
| **File** | `docs/assets/nvd-sync-detail.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** Watermark → fetch → upsert → change_history → extended enrich; failure does not advance watermark.

**Miro prompt:**

> Sequence-style flowchart dark theme: NVD incremental sync. APScheduler triggers lock → read watermark from sync_state → fetch NVD API → upsert_cves capped by MAX_CVES_PER_FETCH → change_history → optional Sploitus/CIRCL enrich → commit watermark. Side note: 503 retries, circuit breaker, API queue. Compact horizontal layout.

---

### 8. auth-layers

| Field | Value |
|-------|--------|
| **File** | `docs/assets/auth-layers.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** Two layers: (A) optional Cloudflare Zero Trust at edge, (B) built-in app login sessions; clarify CF JWT removed from app code (#93).

**Miro prompt:**

> Layered security diagram dark mode: Internet user → optional Cloudflare Access email OTP (edge only, operator policy) → nginx → BRIEFR app with built-in username/password sessions and /api/auth/setup first-run. Label "two independent layers". Dashed box for optional edge. Gold and blue accents.

---

### 9. rate-limits-and-queue

| Field | Value |
|-------|--------|
| **File** | `docs/assets/rate-limits-and-queue.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** Client IP → token buckets (IOC, refresh, admin read, login) + separate API queue for outbound NVD/OTX/etc.

**Miro prompt:**

> Dark diagram: incoming HTTP requests hit rate_limit.py token buckets per endpoint family (IOC 30/min, refresh 10/min, admin read generous, login/refresh strict). Below, outbound calls go through API queue (#221) to protect NVD OTX Groq quotas. Show 429 Retry-After. Table-style legend.

---

### 10. data-model-overview

| Field | Value |
|-------|--------|
| **File** | `docs/assets/data-model-overview.png` |
| **Used in** | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** Entity **groups** only (not full ER): cves hub, kev/epss, mitre/atlas, otx/correlation, cache, auth/admin — ~8 boxes.

**Miro prompt:**

> High-level dark ER overview, NOT full column list. Central "cves" hub connected to groups: KEV/EPSS, MITRE maps, OTX pulses+IOCs, correlation tables, feed_cache/ioc_cache, users/sessions/audit_log. PostgreSQL label. Clean rounded rectangles, readable at doc width.

---

## User-facing (screenshots or annotated UI)

### 11. ui-brief-tab

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ui-brief-tab.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** Annotated screenshot of BRIEF tab: morning brief, what changed, heatmap callouts.

**Miro prompt:**

> Use real BRIEFR screenshot at 1440×900 dark UI OR recreate simplified wireframe: BRIEF tab with morning brief queue, stats row, 90-day heatmap, what-changed panel. Add 3–5 callout arrows with short labels. Match terminal dark aesthetic.

---

### 12. ui-feed-tab

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ui-feed-tab.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** FEED with filter bar, CVE cards, KEV sidebar.

**Miro prompt:**

> Annotated screenshot or wireframe: FEED tab with stack filter bar, CVE cards, pagination, KEV deadlines sidebar. Dark BRIEFR style, minimal callouts.

---

### 13. ui-detail-drawer

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ui-detail-drawer.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** CVE detail drawer tabs: Intel, Related, Detect, correlation section.

**Miro prompt:**

> Annotated UI: CVE detail drawer open on Intel tab showing correlation findings, EPSS sparkline, OTX context. Call out pivot to IOC and investigation thread.

---

### 14. ui-ioc-lookup

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ui-ioc-lookup.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** IOC lookup form + multi-source results + quota display.

**Miro prompt:**

> Annotated screenshot: IOC LOOKUP tab with IP/hash/domain input, VirusTotal AbuseIPDB GreyNoise result cards, API quota meters. Dark theme.

---

### 15. ui-admin-security

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ui-admin-security.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** Admin Security page with rate limit status, auth settings.

**Miro prompt:**

> Annotated admin Security page screenshot: rate limits enabled, auth session info, admin API key optional. Dark BRIEFR admin UI.

---

## Flows

### 16. ioc-lookup-flow

| Field | Value |
|-------|--------|
| **File** | `docs/assets/ioc-lookup-flow.png` |
| **Used in** | [`USE.md`](USE.md), [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |

**Shows:** User → POST /api/ioc/lookup → cache check → parallel VT/AIPDB/GN/OTX → store ioc_cache.

**Miro prompt:**

> Dark sequence flowchart: IOC lookup request checks PostgreSQL ioc_cache TTL → on miss parallel external APIs (VirusTotal, AbuseIPDB, GreyNoise, OTX, abuse.ch) → aggregate JSON response → cache 6h. Rate limit bucket on entry.

---

### 17. investigation-pivot-flow

| Field | Value |
|-------|--------|
| **File** | `docs/assets/investigation-pivot-flow.png` |
| **Used in** | [`USE.md`](USE.md) |

**Shows:** CVE → IOC → related CVE cross-tab pivots; session-only thread.

**Miro prompt:**

> User journey diagram: Analyst opens CVE in FEED → pivots IOC in lookup → returns to related CVE in drawer. Session-only investigation thread in browser memory. Three nodes with gold pivot arrows, dark theme.

---

## Checklist

| # | Filename | Priority | Done |
|---|----------|----------|------|
| 1 | production-architecture.svg | **P0** | [x] |
| 5 | correlation-pipeline.svg | **P0** | [x] |
| 6 | ingest-pipeline.png | **P0** | [ ] |
| 8 | auth-layers.svg | **P0** | [x] |
| 9 | rate-limits-and-queue.png | **P1** | [ ] |
| 3 | backup-restore-flow.png | **P1** | [ ] |
| 11–15 | ui-*.png | **P1** (screenshots OK) | [ ] |
| 2,4,7,10,16,17 | others | **P2** | [ ] |

When an asset is added, update the doc `![...]()` path and mark **Done** `[x]` here.
