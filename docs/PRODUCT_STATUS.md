# BRIEFR product status

**Last updated:** 2026-06-24  
**Purpose:** Single page for “what’s true in production today.” When README or beta docs disagree, this wins.

---

## Release snapshot

| Area | Status |
|------|--------|
| **Database** | **PostgreSQL required** (`DATABASE_URL`, `BRIEFR_REQUIRE_POSTGRES=1`). SQLite removed from production path. |
| **Auth** | Built-in app login + sessions (first-run `/api/auth/setup`). Optional Cloudflare Zero Trust at **edge** (operator policy, not in app code). |
| **Rate limits** | Token buckets on IOC, refresh, admin, auth; set `RATE_LIMIT_ENABLED=1` in production. |
| **API queue** | Outbound API serialization (#221) for NVD/OTX/etc. |
| **Correlation** | Engine v2 — DB-backed campaigns, nightly OTX, drawer Intel tab. |
| **Admin** | Security, backups, job status, config (V1.4 operator features largely shipped). |
| **Snooze** | Removed from UI (#137); future **Monitor** alerts not built. |
| **Theme** | Dark only. |
| **Docker compose** | Postgres compose exists; full V2.0 platform compose not shipped. |

---

## Auth layers (two independent)

![Auth layers — pending](assets/placeholder-diagram.svg)

> **Asset:** [`assets/auth-layers.png`](assets/auth-layers.png) — see [IMAGE_BRIEFS §8](IMAGE_BRIEFS.md#8-auth-layers)

| Layer | What | Notes |
|-------|------|-------|
| **Edge (optional)** | Cloudflare Tunnel + Zero Trust email OTP | Protects public hostname; not embedded in FastAPI |
| **Application** | Username/password + server sessions | Portable self-host; CF JWT middleware **dropped** (#93) |
| **Interim admin** | `BRIEFR_ADMIN_API_KEY` on refresh routes | Optional until edge removed |

---

## Deployment reference

![Production architecture — pending](assets/placeholder-diagram.svg)

> **Asset:** [`assets/production-architecture.png`](assets/production-architecture.png) — see [IMAGE_BRIEFS §1](IMAGE_BRIEFS.md#1-production-architecture)

| Item | Value |
|------|--------|
| Code | `/opt/briefr` |
| DB | PostgreSQL 16 (often Docker at `/opt/infra/postgres`) |
| Backups | `/var/lib/briefr/backups` (age-encrypted) |
| Backend | `briefr-backend.service` → uvicorn :8000 |
| Frontend | `frontend/dist` via nginx |

---

## Shipped vs planned (high level)

| Shipped | Planned / open |
|---------|----------------|
| Postgres, auth, rate limits, API queue | Full `docker-compose.yml` (V2.0) |
| Correlation v2 core, OTX continuous ingest | Correlation v2 phases 3–5 (see `CORRELATION_V2_PLAN.md`) |
| Admin ops, webhooks, wallboard | V1.5 threat-model UI depth, STIX |
| Embeddings optional (fastembed) | Monitor/watchlist **alerts** (product idea) |
| Chart.js admin dashboard partial | Logrotate deploy artifacts (V1.4 theme) |

Details: [`ROADMAP.md`](ROADMAP.md). Historical beta specs → `docs/archive/` (phase 2).

---

## Documentation rollout

| Phase | Status |
|-------|--------|
| Doc structure + image briefs | In progress |
| Archive beta root `.md` files | Pending |
| MkDocs site | Pending |
| Stale README / API_REFERENCE auth claims | Pending |

Plan: [`DOCUMENTATION_PLAN.md`](DOCUMENTATION_PLAN.md).
