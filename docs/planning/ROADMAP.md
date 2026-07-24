# BRIEFR / Jupiter — Product Roadmap Index

Copyright © 2026 Sai Harsha Vardhan. Licensed under the Apache License, Version 2.0 (`SPDX-License-Identifier: Apache-2.0`); see the repository `LICENSE` and `NOTICE` files.

**Last updated:** 2026-06-10 (light touch 2026-07-12 — see compatibility-promise fix below)  
**Status:** Planning — historical release-ladder framing. Execution has since moved to
direct PR-numbered programs tracked in [`planning/BACKLOG.md`](BACKLOG.md) and
[`planning/specs/`](specs/); **for what's actually true in production, read
[`PRODUCT_STATUS.md`](../PRODUCT_STATUS.md) first.**

---

## Purpose

This document indexes all version planning docs for **BRIEFR** (the analyst intelligence pane) and the broader **Jupiter** project (self-hosted security operations on your infrastructure). It consolidates product and engineering decisions from the v1.1 beta through future platform releases.

**Start here** if you are a contributor, reviewer, or an AI agent tasked with implementing the next release.

---

## Product positioning (honest category)

BRIEFR is **not** a SIEM, XDR, or enterprise threat-intelligence platform. It is:

> A **self-hosted analyst intelligence pane** — vulnerability and threat context (KEV, EPSS, MITRE, IOC) ranked for **your stack**, connected to **detection engineering** and **investigation**, without enterprise TI pricing or log-scale infrastructure.

See [`archive/JUPITER_VISION.md`](../archive/JUPITER_VISION.md) for the full north-star architecture.

---

## Release map (summary)

| Release | Codename | Focus | Ship when |
|---------|----------|-------|-----------|
| **v1.1** | Baseline | CVE intel, IOC, Detect tab, Incidents, backups | ✅ Complete |
| **Beta V1.2** | Foundation | Refactor, auth, resilience, logging, FE hygiene | In progress |
| **Beta V1.3** | Analyst beast | Morning brief, charts, Forge MVP, explainable risk | After V1.2 |
| **Beta V1.4** | Operator beast | Admin pane, webhooks, logs viewer, wallboard | After V1.3 |
| **Beta V1.5** | Detection depth | Threat model UI, rule proof bench, KEV backlog | After V1.4 |
| **Beta V2.0** | Platform | Docker official, optional Postgres, optional multi-user | **Parked** — revisit when scale demands |

Each release ships as **small, independent phases** with tests. Do not merge releases into one mega-PR.

---

## Approved execution scope (2026-06-10)

Decision: implement **V1.2 → V1.5**; **V2.0 stays parked** while the deployment is private.

**Live execution state, PR ledger, and the mandatory per-PR workflow for implementing agents: [`HANDOVER.md`](../HANDOVER.md).**

**Deployment reality:** private instance behind a **Cloudflare Access policy** (closed beta, 3 testers). Edge authentication exists today; this informs priorities below.

Cross-release amendments approved in planning (details in each release doc):

| Amendment | Lands in | Rationale |
|-----------|----------|-----------|
| `audit_log` table (actor, action, target, timestamp) | **V1.2** | Populated by backups, restores, manual refreshes; admin pane reads it in V1.4 |
| ~~Cloudflare Access identity trust (validated JWT)~~ — **dropped 2026-06-11**: BRIEFR targets public self-hosting, so identity comes from a **built-in app login** (lands with/before public release; replaces edge-auth identity everywhere it was referenced — V1.3 watchlist keying, V1.4 admin gating). `audit_log.actor` stays empty until then | — | Self-hosted users won't run Cloudflare Access; app-owned auth is portable |
| One webhook channel (KEV-on-stack) + backup dead-man ping | **V1.3** (pulled from V1.4) | Highest daily value; webhook engine doubles as future module interface |
| KEV extra fields (`knownRansomwareCampaignUse`, `cwes`, `vendorProject`, `vulnerabilityName`) | **V1.2** | Already downloaded every 15 min; currently discarded |
| EPSS 30-day history backfill via FIRST API (`scope=time-series`) | **V1.2** | Warm-start sparklines/momentum; idempotent one-shot job |
| New intel sources (Vulnrichment, cvelistV5, PoC-in-GitHub, ExploitDB, Metasploit metadata, Nuclei index) | **V1.3** | Fresh-CVE stack matching + exploit-availability scoring |
| ThreatFox IOC feed + persistent IOC watchlist retro-match; VulnCheck KEV tier | **V1.5** | Aggregator depth; zero extra API quota for retro-match |
| STIX 2.1 export raised in priority | **V1.5** | Interop seam for the future modular SIEM |
| Embeddings (similar CVEs, news clustering, semantic search) + LLM product extraction for unanalyzed CVEs | **V1.3** | Env-gated, CPU-only, scheduler-side; deterministic fallback mandatory |
| Lean admin pane first (health, backups, scheduler, feed health, audit log) | **V1.4** | Defer config editor, integrations UI, users stub, restore wizard |
| STRIDE-lite worksheet and HyperDX provisioner | **Deferred** | Speculative until the modular-SIEM future is real |
| Repository layer | **Pay-as-you-go** | Extract per table only when needed; full layer waits for V2.0 Postgres |

**Storage decision:** intel data stays in **PostgreSQL** inside BRIEFR (production: Postgres 16 in Docker at `/opt/infra/postgres`). ClickHouse remains the **telemetry sidecar** store only (see [`archive/JUPITER_VISION.md`](../archive/JUPITER_VISION.md)).

**ML placement rules:** all ML is env-gated, CPU-only, runs in scheduler jobs (never the request path), and the tool stays fully functional with ML disabled. No log ML in core; no black-box replacement of the explainable risk score; EPSS is consumed, never re-derived.

---

## Version documents

| Document | Contents |
|----------|----------|
| [`archive/beta/Beta V1.2.md`](../archive/beta/Beta%20V1.2.md) | Foundation: structure, repos, auth, resilience — **not a feature explosion** |
| [`archive/beta/Beta V1.3.md`](../archive/beta/Beta%20V1.3.md) | Analyst pane: action queue, Chart.js, Forge MVP, performance |
| [`archive/beta/Beta V1.4.md`](../archive/beta/Beta%20V1.4.md) | Operator pane: admin, backups UI, webhooks, wallboard |
| [`archive/beta/Beta V1.5.md`](../archive/beta/Beta%20V1.5.md) | Threat modeling, detection proof, intel-driven backlog |
| [`archive/beta/Beta V2.0.md`](../archive/beta/Beta%20V2.0.md) | Containerization, Postgres option, team-ready auth |
| [`archive/JUPITER_VISION.md`](../archive/JUPITER_VISION.md) | Jupiter ecosystem, ClickStack relationship, ML split |
| [`archive/THREAT_MODEL.md`](../archive/THREAT_MODEL.md) | Application threat model (BRIEFR itself) |
| [`OPERATIONS.md`](../OPERATIONS.md) | Backup, logs, container seams, deploy compatibility |
| [`archive/AGENT_IMPLEMENTATION_GUIDE.md`](../archive/AGENT_IMPLEMENTATION_GUIDE.md) | Notes for AI agents / implementers |

---

## Architecture reference (current)

| Document | Role |
|----------|------|
| [`archive/superseded/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md`](../archive/superseded/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md) | **Durable architecture-review reasoning** (correlation, scoring, freshness, scheduler, production verdicts + execution graph) |
| [`planning/BACKLOG.md`](BACKLOG.md) | Open / parked work queue |
| [`planning/specs/`](specs/) | Active program PR specs |
| [`SYSTEM_DESIGN.md`](../SYSTEM_DESIGN.md) | Current architecture |
| [`API_REFERENCE.md`](../API_REFERENCE.md) | Endpoint catalog |
| [`archive/snapshots/TECHNICAL_INVENTORY.md`](../archive/snapshots/TECHNICAL_INVENTORY.md) | Schema, scheduler, features |
| [`ONBOARDING.md`](../ONBOARDING.md) | Contributor entry |
| [`archive/snapshots/APPLICATION_EXECUTION_MAP.md`](../archive/snapshots/APPLICATION_EXECUTION_MAP.md) | Request journeys |

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

- Stable default paths: `DATABASE_URL`, `BACKUP_DIR`, `/opt/briefr`
- Forward-only DB migrations
- All analyst `/api/*` routes require a valid session (built-in app login shipped #441 —
  this superseded the original "public read APIs stay unauthenticated" plan below).
  Admin / write / destructive actions additionally require the admin role.
- CLI backup/restore scripts remain supported as break-glass

See [`OPERATIONS.md`](../OPERATIONS.md).

---

## For AI agents / implementers

1. Read **V1.2** first — do not skip foundation work.
2. Pick **one phase** from the target release doc.
3. Follow [`ONBOARDING.md`](../ONBOARDING.md) and existing code conventions.
4. Do not expand scope into a later release without updating these docs in the same PR.
5. Jupiter telemetry (ClickStack) is **optional** and documented in `archive/JUPITER_VISION.md` — not required for BRIEFR core releases.

---

## Related live deployment

Production reference: self-hosted Debian, `briefr-backend` + nginx + `cloudflared-briefr`, backups under `/var/lib/briefr/backups`. Operational hardening notes are captured in `OPERATIONS.md`.
