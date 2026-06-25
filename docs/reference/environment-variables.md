# Environment variables

Key variables for self-hosting. **Full list:** `backend/.env.example`.

| Variable | Purpose | Default / notes |
|----------|---------|-----------------|
| `DATABASE_URL` | PostgreSQL DSN | **Required** |
| `BRIEFR_REQUIRE_POSTGRES` | Refuse without Postgres | `1` |
| `BRIEFR_ENV` | `production` disables Swagger | `development` |
| `ALLOWED_ORIGINS` | CORS | Your public URL |
| `RATE_LIMIT_ENABLED` | Inbound throttling | `1` in prod |
| `NVD_API_KEY` | NVD rate limits | Recommended |
| `OTX_API_KEY` | OTX + correlation | Optional |
| `VIRUSTOTAL_API_KEY` | IOC | Optional |
| `ABUSEIPDB_API_KEY` | IOC | Optional |
| `BACKUP_DIR` | Archives | `/var/lib/briefr/backups` |
| `BACKUP_AGE_KEY_FILE` | Encryption key path | Outside backup dir |
| `EMBEDDINGS_ENABLED` | Semantic related CVEs | `0` |
| `EMBEDDINGS_CACHE_DIR` | Model cache | `/var/lib/briefr/models` in prod |

**Precedence:** process environment overrides `backend/.env` (no `override` in `load_dotenv`). Restart backend after changing secrets.

## By topic

| Topic | Doc |
|-------|-----|
| Deploy | [../deploy/production.md](../deploy/production.md) |
| Rate limits | [../concepts/rate-limits-and-queues.md](../concepts/rate-limits-and-queues.md) |
| API keys | [../troubleshoot/api-keys-and-quotas.md](../troubleshoot/api-keys-and-quotas.md) |
