# BRIEFR / Jupiter — Product Roadmap Index

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-10  
**Status:** Planning — authoritative index for versioned releases

---

## Purpose

This document indexes all version planning docs for **BRIEFR** (the analyst intelligence pane) and the broader **Jupiter** project (self-hosted security operations on your infrastructure). It consolidates product and engineering decisions from the v1.1 beta through future platform releases.

**Start here** if you are an contributor, reviewer, or an AI agent tasked with implementing the next release.

---

## Product positioning (honest category)

BRIEFR is **not** a SIEM, XDR, or enterprise threat-intelligence platform. It is:

> A **self-hosted analyst intelligence pane** — vulnerability and threat context (KEV, EPSS, MITRE, IOC) ranked for **your stack**, connected to **detection engineering** and **investigation**, without enterprise TI pricing or log-scale infrastructure.

See [`JUPITER_VISION.md`](JUPITER_VISION.md) for the full north-star architecture.

---

## Release map (summary)

| Release | Codename | Focus | Ship when |
|---------|----------|-------|-----------|
| **v1.1** | Baseline | CVE intel, IOC, Detect tab, Incidents, backups | ✅ Complete |
| **Beta V1.2** | Foundation | Refactor, auth, resilience, logging, FE hygiene | In progress |
| **Beta V1.3** | Analyst beast | Morning brief, charts, Forge MVP, explainable risk | After V1.2 |
| **Beta V1.4** | Operator beast | Admin pane, webhooks, logs viewer, wallboard | After V1.3 |
| **Beta V1.5** | Detection depth | Threat model UI, rule proof bench, KEV backlog | After V1.4 |
| **Beta V2.0** | Platform | Docker official, optional Postgres, optional multi-user | When scale demands |

Each release ships as **small, independent phases** with tests. Do not merge releases into one mega-PR.

---

## Version documents

| Document | Contents |
|----------|----------|
| [`../Beta V1.2.md`](../Beta%20V1.2.md) | Foundation: structure, repos, auth, resilience — **not a feature explosion** |
| [`../Beta V1.3.md`](../Beta%20V1.3.md) | Analyst pane: action queue, Chart.js, Forge MVP, performance |
| [`../Beta V1.4.md`](../Beta%20V1.4.md) | Operator pane: admin, backups UI, webhooks, wallboard |
| [`../Beta V1.5.md`](../Beta%20V1.5.md) | Threat modeling, detection proof, intel-driven backlog |
| [`../Beta V2.0.md`](../Beta%20V2.0.md) | Containerization, Postgres option, team-ready auth |
| [`JUPITER_VISION.md`](JUPITER_VISION.md) | Jupiter ecosystem, ClickStack relationship, ML split |
| [`THREAT_MODEL.md`](THREAT_MODEL.md) | Application threat model (BRIEFR itself) |
| [`OPERATIONS.md`](OPERATIONS.md) | Backup, logs, container seams, deploy compatibility |
| [`AGENT_IMPLEMENTATION_GUIDE.md`](AGENT_IMPLEMENTATION_GUIDE.md) | Notes for AI agents / implementers |

---

## Architecture reference (current)

| Document | Role |
|----------|------|
| [`SYSTEM_DESIGN.md`](../SYSTEM_DESIGN.md) | Current architecture |
| [`API_REFERENCE.md`](../API_REFERENCE.md) | Endpoint catalog |
| [`TECHNICAL_INVENTORY.md`](../TECHNICAL_INVENTORY.md) | Schema, scheduler, features |
| [`ONBOARDING.md`](ONBOARDING.md) | Contributor entry |
| [`../APPLICATION_EXECUTION_MAP.md`](../APPLICATION_EXECUTION_MAP.md) | Request journeys |

Update `SYSTEM_DESIGN.md` in the same PR when a release phase changes runtime behavior.

---

## Explicit non-goals (all releases until revisited)

| Non-goal | Reason |
|----------|--------|
| Commercial SIEM replacement | BRIEFR is an intel / detection-content / investigation pane |
| Log firehose ingestion in core app | Optional Jupiter sidecar (ClickStack) — see JUPITER_VISION |
| Multi-tenant SaaS in V1.x | Single operator now; schema seams for future users |
| Forking HyperDX / rebuilding Kibana | Use stock ClickStack for telemetry UI if needed |
| Generic LLM chat SOC | Commodity; use LLM sparingly for summaries and detection cards |

---

## Compatibility promise

Releases must remain **additive** for existing systemd + nginx + cloudflared deploys unless documented:

- Stable default paths: `DB_PATH`, `BACKUP_DIR`, `/opt/briefr`
- Forward-only DB migrations
- Public **read** APIs remain unauthenticated until an env flag tightens policy
- Admin / write / destructive actions require auth
- CLI backup/restore scripts remain supported as break-glass

See [`OPERATIONS.md`](OPERATIONS.md).

---

## For AI agents / implementers

1. Read **V1.2** first — do not skip foundation work.
2. Pick **one phase** from the target release doc.
3. Follow [`ONBOARDING.md`](ONBOARDING.md) and existing code conventions.
4. Do not expand scope into a later release without updating these docs in the same PR.
5. Jupiter telemetry (ClickStack) is **optional** and documented in `JUPITER_VISION.md` — not required for BRIEFR core releases.

---

## Related live deployment

Production reference: self-hosted Debian, `briefr-backend` + nginx + `cloudflared-briefr`, backups under `/var/lib/briefr/backups`. Operational hardening notes are captured in `OPERATIONS.md`.
