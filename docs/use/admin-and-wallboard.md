# Admin and wallboard

Operator console: security, backups, jobs, webhooks, wallboard.

---

![Admin security — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ui-admin-security.png`](../assets/ui-admin-security.png)  
> **Miro prompt:** [IMAGE_BRIEFS §15](../IMAGE_BRIEFS.md#15-ui-admin-security)

## Admin (`/admin`)

| Area | Purpose |
|------|---------|
| Security | Rate limit status, auth overview |
| Backups | Trigger, list archives |
| Jobs | Scheduler / ingest status |
| Config | Env-backed settings |

## Wallboard

Read-only dashboard — optional `WALLBOARD_TOKEN` gate.

## Webhooks

Discord, Telegram, generic HTTPS — scheduler alerts.

## Deploy context

[production.md](../deploy/production.md), [updates-and-backups.md](../deploy/updates-and-backups.md)
