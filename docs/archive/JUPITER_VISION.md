# Jupiter Project — Vision & Architecture

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-10  
**Status:** Planning document

---

## What is Jupiter?

**Jupiter** is the umbrella for a self-hosted security analyst environment:

```text
┌─────────────────────────────────────────────────────────────────┐
│ JUPITER                                                          │
├─────────────────────────────┬───────────────────────────────────┤
│ BRIEFR (core product)       │ Optional sidecars (later)         │
│ Intel + detection content   │ ClickStack — logs & hunt UI       │
│ + investigation + ops UI    │ jupiter-detection — rule/ML worker│
└─────────────────────────────┴───────────────────────────────────┘
         │                                    │
         └──────── shared ATT&CK / CVE / IOC IDs ────────┘
```

- **BRIEFR** = threat intelligence pane (this repo).
- **Sidecars** = telemetry and execution — optional, not required to ship BRIEFR releases.

---

## Strategy statement (2026-06-10)

> BRIEFR is a **single, complete, self-hosted threat intel aggregator today** — private, behind a Cloudflare Access policy, in closed beta (3 testers). It is deliberately built with clean seams (API envelope, webhook/event engine, STIX export, repository boundary) so it can later become the **intel module of a self-hosted SIEM** for analysts, enthusiasts, and researchers — without committing to that future now.

Consequences:

- **Intel storage stays SQLite inside BRIEFR.** No NiFi / external Postgres / ClickHouse for intel ingest — volumes do not justify it, and it would break the single-tool deploy + backup contract. ClickHouse is the **telemetry sidecar** store only.
- **The module seams are the webhook engine, STIX 2.1 export, the `{data, meta}` API envelope, and the repository boundary** — these are what a future SIEM shell consumes.
- **ML rules:** env-gated, CPU-only, scheduler-side, deterministic fallback; intel ML (embeddings, extraction) in BRIEFR; log ML in the future `jupiter-detection` worker; EPSS is consumed, never re-derived; the explainable risk score is never replaced by a black box.

---

## BRIEFR — three pillars (beast identity)

| Pillar | Question | Examples |
|--------|----------|----------|
| **Intel beast** | What changed? Why care? | Morning brief, KEV/EPSS, explainable risk, change delta |
| **Detection beast** | What do I deploy? | Forge: coverage map, CVE→pack, SIEM/SQL snippets |
| **Investigation beast** | What happened? Proof? | IOC, investigation thread, PDF export |

**Moat:** Closed loop — intel → prioritize → detect content → investigate → report. No single free tool covers this for self-hosted solo/small teams.

---

## What BRIEFR is not

| Not this | Why |
|----------|-----|
| SIEM / log platform | No billions of events in SQLite core |
| Enterprise TI (RF, ThreatConnect) | No global actor database mandate |
| VM scanner (Tenable) | No agentless asset discovery |
| HyperDX fork | Use stock ClickStack if needed |

Tagline direction:

> **From overnight CVEs to deployable detections — one self-hosted analyst command center.**

---

## Optional telemetry layer (ClickStack)

When homelab or small-team **log hunting** is needed:

```text
Internet / LAN → cloudflared / nginx → BRIEFR (intel UI)
nginx/auth logs → OTel Collector → ClickHouse → HyperDX (hunt UI)
BRIEFR Forge exports SQL/alerts → HyperDX API (optional)
```

**Do not fork HyperDX** for MITRE — integrate via API and deep links.

**NiFi** is optional enrichment upstream of ClickHouse; default path is OTel.

---

## ML and heuristics — where code lives

| Layer | Owns |
|-------|------|
| **BRIEFR** | Intel ML (optional): CVE text, summaries; priority scoring function (KEV+EPSS+stack) |
| **jupiter-detection** (future worker) | Log features, baselines, classical ML, rule execution on ClickHouse |
| **ClickStack** | Display alerts and hunts — not MITRE/CVE brain |

Rule: **train on logs in the worker; reason on intel in BRIEFR.**

---

## Deployment topology (reference)

**Current (production):**

```text
Cloudflare → cloudflared-briefr → nginx :80 → uvicorn :8000
LAN → nginx :80
systemd: briefr-backend, briefr-backup.timer
State: /opt/briefr (code), briefr.db, /var/lib/briefr/backups
```

**Target (V2.0, optional):**

```text
Same edge; BRIEFR in container with volumes for DB + backups
Optional Postgres via DATABASE_URL
```

See [`OPERATIONS.md`](OPERATIONS.md).

---

## UI surfaces (planned)

| Surface | Route | User |
|---------|-------|------|
| Analyst pane | `/` | Daily CVE, IOC, Incidents, Investigate |
| Admin pane | `/admin` | Backup, ingest, config, logs, webhooks |
| Wallboard | `/wallboard` | Read-only kiosk display |
| Forge / Detect | drawer + dedicated views | Detection engineering |

Single operator today; routes and audit fields designed for future roles.

---

## Interview / portfolio narrative

> BRIEFR is a self-hosted analyst intelligence pane with stack-aware prioritization, detection pack generation (Forge), investigation export, and operator admin — optionally paired with ClickStack for telemetry. Intel and log execution are separate layers with shared ATT&CK and CVE identifiers.

---

## Related docs

- [`ROADMAP.md`](ROADMAP.md) — release index
- [`beta/Beta V1.3.md`](beta/Beta%20V1.3.md) — Forge and analyst features
- [`beta/Beta V1.4.md`](beta/Beta%20V1.4.md) — admin and webhooks
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — app security model
