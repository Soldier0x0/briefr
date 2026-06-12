# BRIEFR Beta V1.2 — Roadmap

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.2  
**Last updated:** 2026-06-11  
**Status:** In progress — shipped items marked ✅; live execution state in [`docs/HANDOVER.md`](docs/HANDOVER.md)

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
| `settings.py` | Single typed config (Pydantic `BaseSettings`) for env vars, TTLs, weights — 🔶 Phase 1 shipped (`BRIEFR_ENV`, `BRIEFR_ADMIN_API_KEY`, `ALLOWED_ORIGINS`; remaining vars migrate with their router groups) |
| Router split | `routers/cves.py`, `meta.py`, `ioc.py`, `atlas.py`, `health.py`, `refresh.py` — ✅ Shipped (3 PRs); `main.py` is app wiring only (~130 lines) |
| `dependencies.py` | FastAPI `Depends()` for DB sessions and settings — 🔶 Shipped with admin-key gate + audit writer |
| `services/` layer | `cve_service`, `enrichment_service`, `ioc_service` between routers and DB |

**Why:** `main.py` (~1,400 lines) and `database.py` (~1,680 lines) are hard to test and review in isolation.

### Theme 2 — Data layer

| Item | Goal |
|------|------|
| `repositories/` | Extract table access from `database.py` **pay-as-you-go** — per table, only where a service needs it; full layer waits for V2.0 Postgres |
| Idempotent change history | Deduplicate `cve_change_history` inserts on repeated syncs |
| Shared risk config | ✅ Shipped — `GET /api/config/risk` reads weights from `scoring/risk.py`; `riskScore.js` fetches at startup with bundled-constant fallback |

**Why:** Risk weights today exist in both Python and JavaScript; drift is possible.

### Theme 3 — Resilience and observability

| Item | Goal |
|------|------|
| `resilient_client.py` | ✅ Shipped — shared pooled httpx client: timeouts, retries, per-source circuit breakers, `/api/health` `feeds.sources`. Initial adoption: NVD, KEV, EPSS, MITRE, ATLAS, OSV, RSS. Follow-up: `enrichment/ioc.py`, `feeds/extended.py`, `feeds/otx.py` |
| Structured logging | JSON logs with request IDs across the request lifecycle |
| API response envelope | Consistent `{ data, meta }` shape on list endpoints (`/api/case-studies/feed` already ships `meta`) |
| Production Swagger lockdown | ✅ Shipped — `docs_url=None` when `BRIEFR_ENV=production` (`main.py`) |

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
| ~~Cloudflare Access identity trust~~ | — | **Dropped (2026-06-11)** — BRIEFR ships as a public self-hosted platform, so identity will come from a **built-in app login**, not edge auth. A CF JWT middleware was prototyped and removed; `request.state.user_email` remains the wiring hook for login |
| **`audit_log` table** | High | ✅ Shipped — actor, action, target, timestamp; populated by backups, restores, manual refreshes (admin UI reads it in V1.4; actor empty until app login lands) |
| **API authentication** | Medium | **Built-in app login** before public release (decision 2026-06-11); beta interim: trusted private network + optional `BRIEFR_ADMIN_API_KEY` on refresh routes |
| **Rate limiting** | Medium | Protect `/api/ioc/lookup` and refresh endpoints |
| **Backup encryption** | High | ✅ Shipped — archives age-encrypted (`briefr-*.tar.gz.age`, X25519 via `pyrage`); key `BACKUP_AGE_KEY_FILE` (default `/var/lib/briefr/keys/backup-age.key`, auto-generated by `briefr-backup.sh`) enforced outside `BACKUP_DIR`; restore + startup auto-restore decrypt transparently; protects off-site/at-rest copies only (`docs/THREAT_MODEL.md` § Scope of backup encryption) |
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
| **Incident feed snapshot + scheduler job** | ✅ Shipped (PR #86) — 7s tab → ~20ms snapshot reads |
| **Parallel RSS fetch inside job** | ✅ Shipped (PR #86) — `asyncio.gather`, job-side only |
| **Health: incidents `last_refresh`, `stale`** | ✅ Shipped (PR #86) |
| **Structured log fields for scheduler/feeds** | Prep for V1.4 admin logs viewer |
| **`DATABASE_URL` / path settings only** | Container-ready config; SQLite default unchanged |
| **`docs/THREAT_MODEL.md`, `docs/OPERATIONS.md`** | ✅ Shipped (PR #84) |
| **KEV extra fields** | ✅ Shipped (PR #85) — ransomware flag, CWEs, vendor, name + UI badges |
| **EPSS 30-day history backfill** | ✅ Shipped — one-shot resumable job (`epss_backfill_done` marker); FIRST API `scope=time-series`; 100 CVEs/batch, 2 s throttle (≈30 req/min); `INSERT OR IGNORE` idempotency; wired into `maybe_run_on_startup` |
| **CI dependency audits + `/api/version`** | ✅ Shipped (PR #88) |
| **Playwright smoke in CI (early)** | Safety net before V1.2 Phase 4+ frontend refactors |
| **UI/UX correctness pass** | ✅ Shipped (PR #90) — feed scroll/filter fixes, overlay layering + focus traps, self-hosted fonts, reduced-motion, request timeouts |

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
| `main.py` under 300 lines | ✅ Met — ~130 lines; routers own all endpoints |
| No duplicated risk weights | Single config served to frontend |
| External API outage | Circuit breaker skips source within 60s; UI shows partial results |
| Production deploy | Swagger/OpenAPI disabled; refresh endpoints optionally key-gated (full auth = app login, pre-public release) |
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
