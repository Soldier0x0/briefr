# Troubleshooting

Find your **symptom** → try the **fix**. No need to read other docs first.

| Symptom | Fix |
|---------|-----|
| **Empty or slow CVE feed** | First boot ingests in background — wait or run `python scripts/seed_screenshot_data.py`. NVD 503? Wait and retry (circuit breaker). Check `curl localhost:8000/api/health` |
| **429 Too Many Requests** | Normal rate limit — wait for `Retry-After`. Don't hammer IOC/refresh endpoints |
| **Security page: RATE LIMIT OFF** | Set `RATE_LIMIT_ENABLED=1` in `.env`, restart backend |
| **Can't connect to database** | Check Postgres running + `DATABASE_URL`. Dev: `docker compose -f deploy/docker-compose.postgres.yml up -d` |
| **Backup / restore failed** | Need age key for encrypted archives. `briefr-restore.sh --list` · see [SELF_HOST.md](SELF_HOST.md#updates--backups) |
| **OTX / correlation empty** | Set `OTX_API_KEY`, wait for nightly job |
| **IOC providers empty** | Add keys in `.env` — see `backend/.env.example` |
| **Can't log in** | Complete first-run setup once. Fix `ALLOWED_ORIGINS` for CORS |
| **`/api` 404 in dev** | Start backend on `:8000` before frontend |
| **Embeddings / HF warnings** | Optional: `HF_TOKEN`, `EMBEDDINGS_CACHE_DIR=/var/lib/briefr/models` |

---

## Still stuck?

- [PRODUCT_STATUS.md](PRODUCT_STATUS.md) — what's supposed to work today
- [HOW_IT_WORKS.md](HOW_IT_WORKS.md) — architecture if you need context
- GitHub issues on the repo
