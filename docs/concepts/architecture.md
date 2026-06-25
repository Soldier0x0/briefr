# System architecture

High-level view of BRIEFR: self-hosted CVE intelligence with PostgreSQL as the source of truth.

---

![Production architecture — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/production-architecture.png`](../assets/production-architecture.png)  
> **Miro prompt:** [IMAGE_BRIEFS §1](../IMAGE_BRIEFS.md#1-production-architecture)

![Data model overview — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/data-model-overview.png`](../assets/data-model-overview.png)  
> **Miro prompt:** [IMAGE_BRIEFS §10](../IMAGE_BRIEFS.md#10-data-model-overview)

## At a glance

| Question | Answer |
|----------|--------|
| What it is | FastAPI backend + React SPA + PostgreSQL |
| Data flow | Schedulers ingest → DB; UI reads precomputed rows |
| External calls | On-demand for CVE detail / IOC; not on every list scroll |

## Subsystems

| Subsystem | Doc |
|-----------|-----|
| Ingest & schedulers | [ingest-pipeline.md](ingest-pipeline.md) |
| Correlation | [correlation.md](correlation.md) |
| Auth | [auth-and-sessions.md](auth-and-sessions.md) |
| Rate limits & API queue | [rate-limits-and-queues.md](rate-limits-and-queues.md) |

## Decision log

| Date | Decision | Why |
|------|----------|-----|
| 2026 | PostgreSQL required | SQLite lock/contention under load |
| 2026-06 | Built-in auth vs CF JWT in app | Portable self-host (#93) |
| 2026 | API queue (#221) | Protect NVD/OTX quotas |

## Code map

| Area | Path |
|------|------|
| App entry | `backend/main.py` |
| Routers | `backend/routers/` |
| Scheduler | `backend/scheduler.py` |
| DB | `backend/database.py` |
| Frontend | `frontend/src/` |

## Legacy deep dives

- [`SYSTEM_DESIGN.md`](../../SYSTEM_DESIGN.md)
- [`docs/diagrams/`](../diagrams/) — old Mermaid (dev reference only)
