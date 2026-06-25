# Troubleshooting index

Find your **symptom** → open the page → apply the fix.

| Symptom | Likely cause | Page |
|---------|--------------|------|
| Empty or slow CVE feed | Bootstrap ingest, NVD 503 | [empty-feed-and-ingest.md](empty-feed-and-ingest.md) |
| `429 Too Many Requests` | Rate limit bucket | [rate-limits-and-429.md](rate-limits-and-429.md) |
| Security UI "RATE LIMIT OFF" | `RATE_LIMIT_ENABLED=0` | [rate-limits-and-429.md](rate-limits-and-429.md) |
| Can't connect to database | `DATABASE_URL`, Postgres down | [postgres-and-backups.md](postgres-and-backups.md) |
| Restore failed | Missing age key, bad archive | [postgres-and-backups.md](postgres-and-backups.md) |
| IOC / OTX empty | Missing API keys | [api-keys-and-quotas.md](api-keys-and-quotas.md) |
| Can't login / CORS errors | Auth setup, `ALLOWED_ORIGINS` | [auth-and-security.md](auth-and-security.md) |
| `/api` 404 in dev | Backend not running | [../deploy/quickstart.md](../deploy/quickstart.md) |

Still stuck? Check [`PRODUCT_STATUS.md`](../PRODUCT_STATUS.md) and GitHub issues.
