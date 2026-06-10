# Notes for AI implementers (Claude / Cursor agents)

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-10

---

## Start here

1. Read [`ROADMAP.md`](ROADMAP.md) — release you are implementing.  
2. Read the matching `Beta V1.x.md` at repo root.  
3. Read [`ONBOARDING.md`](ONBOARDING.md) for codebase layout and tests.  
4. Do **not** skip [`Beta V1.2.md`](../Beta%20V1.2.md) foundation if V1.2 is incomplete.

---

## Product truth (do not misbuild)

- BRIEFR = **self-hosted analyst intelligence pane** (CVE, KEV, MITRE, IOC, detection *content*, investigation).  
- **Not** a SIEM, log platform, or enterprise TI replacement.  
- Optional Jupiter sidecars (ClickStack, detection worker) are **documented in [`JUPITER_VISION.md`](JUPITER_VISION.md)** — not required in core repo releases.

---

## Release discipline

| Release | Build | Do not build yet |
|---------|-------|------------------|
| **V1.2** | Refactor, auth, resilient feeds, incident snapshot | Admin UI, Forge, webhooks, wallboard |
| **V1.3** | Morning brief, Chart.js, Forge MVP | Full admin pane |
| **V1.4** | Admin, webhooks, logs viewer, wallboard | Postgres, Docker official |
| **V1.5** | Threat model UI, rule proof | ML on logs in core app |
| **V2.0** | Docker compose, optional Postgres | Multi-tenant SaaS |

One phase per PR where possible. Update `SYSTEM_DESIGN.md` when behavior changes.

---

## Known performance issue

**Incidents & News** tab: sequential RSS fetch on cold API path causes 7s+ loads.  
**Fix (V1.2 allowed or V1.3):** scheduler precomputes combined feed; API reads snapshot; parallel RSS in job only.

See [`Beta V1.3.md`](../Beta%20V1.3.md) Theme 4 and [`OPERATIONS.md`](OPERATIONS.md).

---

## Security defaults

- See [`THREAT_MODEL.md`](THREAT_MODEL.md).  
- Admin/destructive routes require auth.  
- Webhook SSRF protection when implementing V1.4.  
- Secrets never in logs or API GET responses.

---

## Deploy compatibility

Existing production: systemd + nginx + cloudflared, SQLite, `/var/lib/briefr/backups`.  
Releases must stay **additive** — see [`OPERATIONS.md`](OPERATIONS.md).

---

## Credit-efficient implementation order (suggested)

If budget-limited (e.g. small API credit allowance):

1. V1.2 Phase 1–2 (settings, routers, services)  
2. Incident feed snapshot  
3. V1.3 morning brief + Forge coverage map  
4. V1.4 admin backup UI + one webhook channel  

Avoid: fork HyperDX, full SIEM UI, monolithic “beast in one PR”.

---

## Key existing modules to extend (not replace)

| Area | Path |
|------|------|
| Detection / Forge | `backend/detection/` |
| Backups | `backend/backup/manager.py`, `deploy/briefr-backup.sh` |
| Incidents feed | `backend/feeds/case_study_feed.py`, `incident_news.py` |
| Risk score | `backend/scoring/risk.py`, `frontend/src/scoring/riskScore.js` |
| Deploy | `deploy/` |

---

## Questions?

If scope is ambiguous, prefer the **smaller release doc** and [`ROADMAP.md`](ROADMAP.md) non-goals over inventing features.
