# BRIEFR Beta V1.4 — Operator Beast

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.1  
**Last updated:** 2026-06-19  
**Status:** Theme 1 (Admin pane) **shipped** in PR cursor/admin-overhaul-17e8. Themes 2–4 remain planned.

**Prerequisite:** [`Beta V1.3.md`](Beta%20V1.3.md)  
**Index:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Purpose

V1.4 makes BRIEFR **operator-grade** for self-hosted solo use: full **admin pane**, **push notifications**, **application logs**, and a **read-only wallboard** — without SSH for daily tasks.

Single user today (admin = analyst); routes and audit model ready for future roles.

---

## Theme 1 — Admin pane (`/admin`) — ✅ SHIPPED (PR cursor/admin-overhaul-17e8, 2026-06-19)

Separate surface from analyst UI. **All destructive actions admin-gated.**

**Shipped scope:** System health (stat cards, active locks, recent errors, quick diagnostics), Backups (list, run, upload, verify), Storage (disk partition usage, table counts, purge controls, DB export), Watchlist & cache, API keys & config (queue-edit model, apply-all + restart), Scheduler (manual triggers, global pause/resume, run-now per job), Webhooks (alert log, test send), Security (rate limit status, key rotation), Feed health (card grid, circuit reset), Ingest log (level colors, logger filter, export), Audit log (prefix filter chips). All scheduler jobs report ACTIVE/PAUSED/LOCKED/DISABLED status with last 5 run history and error messages. Disk usage NaN bug fixed.

**Admin gating:** built-in app login with an `admin` role gates `/admin/*` (decision 2026-06-11 — replaces the earlier Cloudflare Access plan); if login has not shipped yet when the admin pane lands, gate interim with `BRIEFR_ADMIN_API_KEY`.

### Sections

| Section | Features |
|---------|----------|
| **System health** | Service status, CVE count, disk, ingest freshness, last backup |
| **Backup & restore** | Manual backup, list archives, integrity badge, restore wizard, retention view |
| **Ingest & scheduler** | Job list, last/next run, manual refresh triggers, pause flags |
| **Configuration** | Safe settings editor (origins, TTLs, retention); secrets masked |
| **Integrations** | API keys (masked rotate), outbound webhook catalog |
| **Users & access** | Stub for V2.0; today single admin session |
| **Audit log** | Backup, restore, config change, auth failure |
| **Documentation** | Links + “export support pack” (health + logs, no secrets) |

**CLI preserved:** `deploy/briefr-backup.sh`, `briefr-restore.sh` call same backend logic as UI.

---

## Theme 2 — Webhooks & notifications

**Note:** the first channel + KEV-on-stack rule + backup dead-man ping ship early in [`Beta V1.3.md`](Beta%20V1.3.md) Theme 8. V1.4 builds the full engine around them.

| Item | Goal |
|------|------|
| **Channels** | Telegram, Discord, Slack, generic HTTP POST, optional SMTP |
| **Rules** | KEV-on-stack, EPSS threshold, digest, ingest failure, backup failure |
| **Delivery log** | Last N attempts, errors, retries |
| **Dedupe & quiet hours** | Prevent alert fatigue |
| **Test send** | Per channel |
| **Security** | SSRF protection on generic URLs; encrypted token storage; admin-only config |

Analyst benefits from pushes; **configuration lives in admin**.

---

## Theme 3 — Application logs (admin)

| Item | Goal |
|------|------|
| **Structured JSON logging** | Build on V1.2 Theme 3 |
| **Log categories** | Application, Scheduler, Backup, Webhooks, Security |
| **Admin log viewer** | Tail last N lines; severity filter; redact secrets |
| **Container-ready** | stdout JSON + optional `/var/lib/briefr/logs/` volume |
| **No shell** | Read-only API; rate limited |

**Not in scope:** full nginx/host log management in UI — document in [`OPERATIONS.md`](docs/OPERATIONS.md).

---

## Theme 4 — Wallboard (`/wallboard`)

Read-only **intel posture** display for kiosk / TV — **not** a SOC log wall.

| Tile | Data |
|------|------|
| KEV on stack | count |
| New/changed 24h | brief API |
| Top risk CVEs | risk score |
| Ingest health | `/api/health` |
| Coverage gaps | Forge summary |
| Headline ticker | Incidents snapshot |

| Item | Goal |
|------|------|
| **Route** | Chromeless full-screen; 60–120s poll |
| **API** | `GET /api/wallboard` aggregated cached payload |
| **Auth** | Optional `WALLBOARD_TOKEN` read-only scope |
| **Security** | No secrets, no write actions; rate limit |

---

## Theme 5 — Chart.js ops dashboard

Admin home: ingest duration trends, backup size, API errors, webhook success rate.

---

## Theme 6 — Log rotation & deploy artifacts

| Item | Goal |
|------|------|
| **`deploy/logrotate-briefr.conf`** | App log file if used |
| **Document journald** | vacuum policy for systemd |
| **Backup log rotation** | `/var/lib/briefr/backups/logs/` retention |

---

## Explicit non-goals for V1.4

| Non-goal | Reason |
|----------|--------|
| Full Linux server admin (UFW, cloudflared) | OS runbook |
| Docker official compose | V2.0 |
| Environment threat model UI | V1.5 |
| Rule proof on live logs | V1.5 |
| Multi-user RBAC UI | V2.0 (audit fields ready) |

---

## Implementation order

```
Phase 1  Admin shell + auth gate + health dashboard
Phase 2  Backup/restore UI wired to backup/manager.py
Phase 3  Scheduler controls + manual refresh
Phase 4  Webhook engine + Telegram/Discord + delivery log
Phase 5  Application logs viewer
Phase 6  Wallboard route + aggregated API
Phase 7  deploy/logrotate + OPERATIONS.md updates
```

---

## Success criteria

| Criterion | Measure |
|-----------|---------|
| Backup | Manual + list + restore from UI without SSH |
| Webhook | Test KEV-on-stack alert to Telegram |
| Logs | Admin sees last 200 JSON log lines with redaction |
| Wallboard | Loads 6 tiles in <2s; readable at 3m distance |
| Security | All admin routes require auth; audit entries on restore |
| Break-glass | CLI restore still works |

---

## Related documents

| Document | Role |
|----------|------|
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Backup, container, compatibility |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Admin attack surface |
| [`Beta V1.5.md`](Beta%20V1.5.md) | Next — threat model + proof bench |
