# BRIEFR Beta V2.0 — Platform

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.0  
**Last updated:** 2026-06-10  
**Status:** Planning — **when scale or packaging demands it**

**Prerequisite:** Beta V1.5 recommended; Beta V1.2 repository layer **required**  
**Index:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Purpose

V2.0 is **platform packaging and scale** — not a new product category. Trigger when: Docker deploy is desired, concurrent users appear, or SQLite limits bite.

---

## Theme 1 — Official containerization

| Item | Goal |
|------|------|
| **`deploy/docker-compose.yml`** | `briefr-api`, optional `briefr-web` (nginx + dist) |
| **Volumes** | `briefr-data` (DB), `briefr-backups`, optional logs |
| **Env parity** | Same variables as systemd (`DATABASE_URL`, `BACKUP_DIR`, etc.) |
| **Non-root user** | `USER briefr`; read-only root where possible |
| **Healthcheck** | Docker `HEALTHCHECK` → `/api/health` |
| **Publish** | `127.0.0.1:8000` default — cloudflared/nginx on host |

**Migration path:** parallel run on `:8001`, cutover nginx upstream, disable systemd unit.

See [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## Theme 2 — Optional PostgreSQL

| Item | Goal |
|------|------|
| **`DATABASE_URL`** | `sqlite:///` default; `postgresql://` supported |
| **Repositories only** | No SQL in routers/services |
| **Alembic migrations** | Versioned from SQLite baseline |
| **Migration tool** | Documented pgloader path + rollback to SQLite backup |

**Non-goal:** require Postgres for single-node homelab.

---

## Theme 3 — Multi-user readiness (optional)

| Item | Goal |
|------|------|
| **Local users table** | 2–5 users realistic |
| **Roles** | `analyst`, `admin` |
| ~~Cloudflare Access~~ | Dropped (2026-06-11) — built-in app login is the auth mechanism |
| **Row ownership** | Nullable `user_id` on watchlists, notes |

**Non-goal:** multi-tenant SaaS billing.

---

## Theme 4 — Jupiter sidecar documentation

In-repo docs only (or separate repo later):

- ClickStack compose for telemetry
- `jupiter-detection` worker sketch
- Forge → ClickHouse SQL export contract

Not required to ship V2.0 BRIEFR core.

---

## Theme 5 — uvicorn workers

| Mode | Workers |
|------|---------|
| SQLite | **1 worker** (mandatory) |
| PostgreSQL | 2+ workers + connection pool |

---

## Explicit non-goals for V2.0

| Non-goal | Reason |
|----------|--------|
| Managed cloud SaaS | Out of scope |
| SIEM in core | Jupiter sidecar |
| HyperDX fork | Stock ClickStack |

---

## Success criteria

| Criterion | Measure |
|-----------|---------|
| Docker | `docker compose up` with health green; data on volumes |
| systemd parity | Same `.env` keys documented |
| Postgres | Integration test suite passes on PG; SQLite still default CI |
| Rollback | Document restore from pre-migration SQLite archive |

---

## Related documents

| Document | Role |
|----------|------|
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Volume mapping, secrets |
| [`Beta V1.2.md`](Beta%20V1.2.md) | Repository prerequisite |
