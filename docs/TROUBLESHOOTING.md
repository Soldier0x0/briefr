# Troubleshooting

Find your **symptom** → try the **fix**. No need to read other docs first.

| Symptom | Fix |
|---------|-----|
| **Empty or slow CVE feed** | First boot ingests in background — wait or run `python scripts/seed_screenshot_data.py`. Check `curl localhost:8000/api/health` |
| **NVD sync slow / 503 / circuit open** | NVD pacing is upstream behavior, not usually a bad key. Wait for cooldown; avoid repeated manual refresh. Keep `NVD_API_KEY` set |
| **Hybrid search returns no semantic hits** | Keyword CVE results can still work. Enable `EMBEDDINGS_ENABLED=1`, install `fastembed`, use Postgres + pgvector, then run embeddings backfill / Catch-up |
| **Embeddings / pgvector missing** | Use `pgvector/pgvector:pg16`, run migrations, keep `EMBEDDINGS_PGVECTOR=1`. Without pgvector BRIEFR falls back to heuristic related-CVE matching |
| **429 Too Many Requests** | Normal rate limit — wait for `Retry-After`. Don't hammer IOC/refresh endpoints |
| **Security page: RATE LIMIT OFF** | Set `RATE_LIMIT_ENABLED=1` in `.env`, restart backend |
| **Can't connect to database** | Check Postgres running + `DATABASE_URL`. Dev: `docker compose -f deploy/docker-compose.postgres.yml up -d` |
| **Backup / restore failed** | Need age key for encrypted archives. `briefr-restore.sh --list` · see [SELF_HOST.md](SELF_HOST.md#updates--backups) |
| **OTX / correlation empty** | Set `OTX_API_KEY`, wait for nightly job |
| **Durable jobs panel empty/off** | Set `PROCRASTINATE_ENABLED=1`, restart backend, then check Admin → Scheduler → Durable outbound jobs. If stuck, use Ping queue and inspect the request ID in the backend logs (`X-Request-ID` / structured `request_id`) to trace the job. |
| **Catch-up active but backlog not moving** | Catch-up only kicks eligible jobs and never raises provider limits. Check Admin → Scheduler for LOCKED jobs, source cooldowns, and outbound queue rows |
| **Stack backfill deferred / partial** | FEED backfill respects rate limits and runtime caps. Use Resume from the banner; lower stack terms if the request is too broad |
| **IOC providers empty** | Add keys in `.env` — see `backend/.env.example` |
| **Can't log in** | Complete first-run setup once. Fix `ALLOWED_ORIGINS` for CORS |
| **`/api` 404 in dev** | Start backend on `:8000` before frontend |
| **Model download / HF warnings** | Optional: `HF_TOKEN`, `EMBEDDINGS_CACHE_DIR=/var/lib/briefr/models`; embeddings are optional |
| **Wallboard asks for token** | Set `WALLBOARD_TOKEN`, restart backend, open `/wallboard`, enter the token once to create the read-only session cookie |

---

## Still stuck?

- [PRODUCT_STATUS.md](PRODUCT_STATUS.md) — what's supposed to work today
- [HOW_IT_WORKS.md](HOW_IT_WORKS.md) — architecture if you need context
- GitHub issues on the repo
