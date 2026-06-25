# Production deployment

How BRIEFR runs on a Debian-style server: systemd, nginx, optional Cloudflare Tunnel.

---

![Production architecture — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/production-architecture.png`](../assets/production-architecture.png)  
> **Miro prompt:** [IMAGE_BRIEFS §1](../IMAGE_BRIEFS.md#1-production-architecture)

## Topology summary

| Tier | Components |
|------|------------|
| Client | Browser → React SPA |
| Edge (optional) | Cloudflare Tunnel, Zero Trust OTP |
| Proxy | nginx :80 → static `dist` + `/api` proxy |
| App | `briefr-backend.service` → uvicorn :8000 |
| Data | PostgreSQL 16, backups under `/var/lib/briefr` |

## Initial setup

```bash
bash deploy/setup.sh
```

Edit `backend/.env`: `DATABASE_URL`, `ALLOWED_ORIGINS`, API keys, `RATE_LIMIT_ENABLED=1`.

## Update

```bash
bash deploy/briefr-update.sh
```

See [updates-and-backups.md](updates-and-backups.md).

## Production checklist

| Item | Action |
|------|--------|
| `BRIEFR_ENV=production` | Disables Swagger |
| `RATE_LIMIT_ENABLED=1` | Required for IOC/refresh/auth throttling |
| `ALLOWED_ORIGINS` | Your public URL (not `:5173`) |
| Backups | `briefr-pg-backup.timer` enabled |
| Age key | Off-site copy of `/var/lib/briefr/keys/backup-age.key` |

## Legacy reference

Full ops contract: [`OPERATIONS.md`](../OPERATIONS.md).

## Troubleshooting

| Symptom | Page |
|---------|------|
| 429 / rate limits | [../troubleshoot/rate-limits-and-429.md](../troubleshoot/rate-limits-and-429.md) |
| DB / restore | [../troubleshoot/postgres-and-backups.md](../troubleshoot/postgres-and-backups.md) |
| Auth / CORS | [../troubleshoot/auth-and-security.md](../troubleshoot/auth-and-security.md) |
