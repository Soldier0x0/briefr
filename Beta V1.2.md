# BRIEFR Beta V1.2 — Roadmap

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.1  
**Last updated:** 2026-06-10  
**Status:** Planning document for work after v1.1 beta stabilization

---

## Purpose

This document captures what BRIEFR has **completed in v1.1 beta**, what ships in the **recent stabilization pass**, and what is **planned for Beta V1.2** and beyond. It is the single place for near-future product and engineering intent.

For current architecture and data flows, see [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md). New contributors should start with [`docs/ONBOARDING.md`](docs/ONBOARDING.md).

**Roadmap index:** [`docs/ROADMAP.md`](docs/ROADMAP.md) — V1.3+ (analyst beast, admin, platform) are **out of scope** for V1.2 except items listed in [Allowed V1.2 additions](#allowed-v12-additions-from-planning-2026-06-10) below.

---

## v1.1 beta — completed baseline

| Area | Status |
|------|--------|
| CVE ingest (NVD, KEV, EPSS, MITRE, ATLAS) | Complete |
| CVE feed, detail enrichment, IOC lookup | Complete |
| Correlation, detection, investigation panel | Complete |
| Client risk score v1.1b + momentum | Complete |
| PDF export + AI executive summary | Complete |
| Incidents & News (RSS + ATLAS) | Complete |
| Integrity-checked backups + auto-restore | Complete |
| ATLAS per-CVE drawer wiring | Complete |
| Legacy investigation summary endpoint | Complete |

---

## Recent stabilization (pre–V1.2)

These gaps were closed immediately before V1.2 planning:

| Task | Delivery |
|------|----------|
| **AI/ML alerts stat chip** | `GET /api/stats?frameworks=` returns `ai_ml_alerts`; clicking the chip filters the CVE feed via `frameworks` + `ai_context_only` |
| **Incidents tab performance** | `GET /api/case-studies/feed` loads RSS + ATLAS server-side (single DB connection); client session cache (5 min) |
| **Documentation sync** | README, API_REFERENCE, SYSTEM_DESIGN, TECHNICAL_INVENTORY, xlsx generator aligned with codebase |
| **Dead code removal** | Removed `AIThreats.jsx`, `utils/riskScore.js` (v1.1a), unused `Phase2Block` |

---

## Beta V1.2 — engineering themes

V1.2 is a **maintainability and production-hardening** release, not a feature explosion. Four themes:

### Theme 1 — Configuration and structure

| Item | Goal |
|------|------|
| `settings.py` | Single typed config (Pydantic `BaseSettings`) for env vars, TTLs, weights |
| Router split | `routers/cves.py`, `ioc.py`, `atlas.py`, `health.py`, `refresh.py` |
| `dependencies.py` | FastAPI `Depends()` for DB sessions and settings |
| `services/` layer | `cve_service`, `enrichment_service`, `ioc_service` between routers and DB |

**Why:** `main.py` (~1,400 lines) and `database.py` (~1,680 lines) are hard to test and review in isolation.

### Theme 2 — Data layer

| Item | Goal |
|------|------|
| `repositories/` | Extract table access from `database.py` (cves, feeds, correlation, atlas) |
| Idempotent change history | Deduplicate `cve_change_history` inserts on repeated syncs |
| Shared risk config | One source of truth for v1.1b weights (API config or YAML) |

**Why:** Risk weights today exist in both Python and JavaScript; drift is possible.

### Theme 3 — Resilience and observability

| Item | Goal |
|------|------|
| `resilient_client.py` | ✅ Shipped — shared pooled httpx client: timeouts, retries, per-source circuit breakers, `/api/health` `feeds.sources`. Initial adoption: NVD, KEV, EPSS, MITRE, ATLAS, OSV, RSS. Follow-up: `enrichment/ioc.py`, `feeds/extended.py`, `feeds/otx.py` |
| Structured logging | JSON logs with request IDs across the request lifecycle |
| API response envelope | Consistent `{ data, meta }` shape on list endpoints |
| Production Swagger lockdown | Env flag to disable `/api/docs` in production |

**Why:** ~15 external APIs with per-file error handling; outages should fail fast and recover gracefully.

### Theme 4 — Frontend architecture

| Item | Goal |
|------|------|
| Hooks extraction | `useCVEFeed`, `useCveDrawerData`, `useIOCLookup`, `useCaseStudyFeed` |
| `DetailDrawer` split | Overview, Intel, Related, Detect as separate components |
| React Query (or similar) | Cache stats, feed pages, drawer sub-fetches with stale-while-revalidate |
| Composite risk badge on cards | Optional — show v1.1b score on `CVECard` without extra API calls |

**Why:** `DetailDrawer.jsx` (~1,500 lines) and `IOCLookup.jsx` (~1,170 lines) are maintenance risks.

---

## Beta V1.2 — product / security backlog

| Item | Priority | Notes |
|------|----------|-------|
| **API authentication** | High | API keys or OAuth for multi-user / exposed deployments |
| **Rate limiting** | Medium | Protect `/api/ioc/lookup` and refresh endpoints |
| **Operator “changes” UI** | Low | Surface `GET /api/changes` in the analyst UI |
| **Investigation pivots from Incidents** | Low | CVE links in ATLAS cards → open drawer / investigation thread |
| **IOC lookup history persistence** | Low | Optional `localStorage` history (privacy-reviewed) |
| **Frontend E2E in CI** | Medium | Playwright smoke for BRIEF / IOC / Incidents tabs |
| **Monitoring hooks** | Medium | Health + backup failure alerts (webhook or email) |

---

## Explicit non-goals for V1.2

| Non-goal | Reason |
|----------|--------|
| PostgreSQL migration | SQLite adequate for single-node beta; revisit in [`Beta V2.0.md`](Beta%20V2.0.md) |
| Multi-tenant SaaS | Requires auth, row-level security, horizontal scaling |
| Commercial SIEM replacement | BRIEFR remains an analyst workbench, not a full SOC platform |
| Real-time WebSocket feed | Incremental polling + scheduler sufficient today |
| Chart.js dashboards | [`Beta V1.3.md`](Beta%20V1.3.md) |
| Admin pane / webhooks UI / wallboard | [`Beta V1.4.md`](Beta%20V1.4.md) |
| Forge / threat model UI | [`Beta V1.3.md`](Beta%20V1.3.md) / [`Beta V1.5.md`](Beta%20V1.5.md) |
| Official Docker compose | [`Beta V2.0.md`](Beta%20V2.0.md) |

---

## Allowed V1.2 additions (from planning 2026-06-10)

These user-visible or ops items are **approved exceptions** to “no feature explosion” because they improve resilience without expanding product category:

| Item | Rationale |
|------|-----------|
| **Incident feed snapshot + scheduler job** | Fixes >7s Incidents tab; serve precomputed RSS+ATLAS |
| **Parallel RSS fetch inside job** | `asyncio.gather` — not on request path |
| **Health: incidents `last_refresh`, `stale`** | Monitoring hooks backlog |
| **Structured log fields for scheduler/feeds** | Prep for V1.4 admin logs viewer |
| **`DATABASE_URL` / path settings only** | Container-ready config; SQLite default unchanged |
| **`docs/THREAT_MODEL.md`, `docs/OPERATIONS.md`** | Documentation only |

Do **not** add Forge, admin UI, webhooks configuration, or wallboard under V1.2.

---

## Suggested implementation order

```
Phase 1  settings.py + dependencies.py + router split
Phase 2  services/ layer + resilient_client
Phase 3  repositories/ extraction (incremental, table by table)
Phase 4  Frontend hooks + DetailDrawer split
Phase 5  Auth + rate limits + API envelope
Phase 6  React Query + E2E CI
```

Each phase should ship independently with tests; no big-bang rewrite.

---

## Success criteria for Beta V1.2

| Criterion | Measure |
|-----------|---------|
| `main.py` under 300 lines | Routers + services own business logic |
| No duplicated risk weights | Single config served to frontend |
| External API outage | Circuit breaker skips source within 60s; UI shows partial results |
| Production deploy | Auth required for write/refresh endpoints; docs disabled |
| CI | Backend + frontend smoke green on every PR |

---

## Related documents

| Document | Role |
|----------|------|
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Master release index |
| [`docs/JUPITER_VISION.md`](docs/JUPITER_VISION.md) | Jupiter / BRIEFR north star |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Backup, logs, deploy compatibility |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Application security model |
| [`Beta V1.3.md`](Beta%20V1.3.md) | Next — analyst beast |
| [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) | Current architecture (update when V1.2 phases land) |
| [`API_REFERENCE.md`](API_REFERENCE.md) | Endpoint catalog |
| [`TECHNICAL_INVENTORY.md`](TECHNICAL_INVENTORY.md) | Schema, scheduler, feature matrix |
| [`APPLICATION_EXECUTION_MAP.md`](APPLICATION_EXECUTION_MAP.md) | Request journeys |
| [`FOLDER_STRUCTURE_GUIDE.md`](FOLDER_STRUCTURE_GUIDE.md) | File map |

When a V1.2 phase completes, update the relevant doc in the same PR — do not let `Beta V1.2.md` and `SYSTEM_DESIGN.md` diverge for long.
