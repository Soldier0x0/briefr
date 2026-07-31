# Troubleshooting

Find your **symptom** → try the **fix**. No need to read other docs first.

**Not installed yet?** Follow [`SELF_HOST.md`](SELF_HOST.md) (pick §1 SQLite, §2 Postgres+pgvector, or §3 production), then use the [verification checklist](SELF_HOST.md#after-install-verification-checklist).

| Symptom | Fix |
|---------|-----|
| **Empty or slow CVE feed** | First boot ingests in background — wait or run `python scripts/seed_screenshot_data.py`. Check `curl localhost:8000/api/health` |
| **NVD sync slow / 503 / circuit open** | NVD pacing is upstream behavior, not usually a bad key. Wait for cooldown; avoid repeated manual refresh. Keep `NVD_API_KEY` set |
| **VulnCheck / KEV job: `Database command timeout`** | Shared SQL timeout (60s), not that job’s HTTP budget. Confirm NVD is not holding locks across CIRCL/Sploitus (fixed by commit/close before enrich). Do **not** raise `DATABASE_POOL_COMMAND_TIMEOUT_SECONDS` as the first fix — see [POSTGRES.md](POSTGRES.md) |
| **CIRCL DNS / circuit open during NVD** | Upstream CIRCL reachability; circuit breaker is correct. Ingest CVEs still commit; extended enrich is best-effort after watermark |
| **Hybrid search returns no semantic hits** | Keyword CVE results can still work. Enable `EMBEDDINGS_ENABLED=1`, install `fastembed`, use Postgres + pgvector, then run embeddings backfill / Catch-up |
| **Embeddings / pgvector missing** | Use `pgvector/pgvector:pg16`, run migrations, keep `EMBEDDINGS_PGVECTOR=1`. Without pgvector BRIEFR falls back to heuristic related-CVE matching |
| **429 Too Many Requests** | Normal rate limit — wait for `Retry-After`. Don't hammer IOC/refresh endpoints |
| **Security page: RATE LIMIT OFF** | Set `RATE_LIMIT_ENABLED=1` in `.env`, restart backend |
| **Can't connect to database** | Check Postgres running + `DATABASE_URL`. Dev: [`SELF_HOST.md` §2](SELF_HOST.md#2-local-development-with-postgresql--pgvector) — `docker compose -f deploy/docker-compose.postgres.yml up -d` |
| **Install verify fails** (`backend` not `postgresql`) | Set `DATABASE_URL` + `BRIEFR_REQUIRE_POSTGRES=1`, restart backend — see [SELF_HOST verify checklist](SELF_HOST.md#after-install-verification-checklist) |
| **Backup / restore failed** | Need age key for encrypted archives. `briefr-restore.sh --list` · see [SELF_HOST.md](SELF_HOST.md#updates--backups) |
| **OTX / correlation empty** | Set `OTX_API_KEY`, wait for nightly job |
| **Durable jobs panel empty/off** | Set `PROCRASTINATE_ENABLED=1`, restart backend, then check Admin → Scheduler → Durable outbound jobs. If stuck, use Ping queue and inspect the request ID in the backend logs (`X-Request-ID` / structured `request_id`) to trace the job. |
| **Catch-up active but backlog not moving** | Catch-up only kicks eligible jobs and never raises provider limits. Check Admin → Scheduler for LOCKED jobs, source cooldowns, and outbound queue rows |
| **Stack backfill deferred / partial** | FEED backfill respects rate limits and runtime caps. Use Resume from the banner; lower stack terms if the request is too broad |
| **IOC providers empty** | Add keys in `.env` — see `backend/.env.example` |
| **BRIEF / widgets: `Not authenticated` while header still shows user** | Access cookie expired and a bare `/auth/refresh` raced API 401 retries (reuse detection revoked sessions). Fixed in #731: shared `refreshAccessToken()` + AuthContext uses `fetchMe()` only. Retry / re-login recovers; multi-tab concurrent refresh can still hit reuse detection by design |
| **Can't log in** | Complete first-run setup once ([SELF_HOST](SELF_HOST.md)). Fix `ALLOWED_ORIGINS` for CORS |
| **Cloud / bare VM: `ConnectionRefusedError` on `:5432`** | No Docker/Postgres on the box; `.env` may still have a Postgres placeholder DSN. Run with `DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0` for SQLite (see `AGENTS.md`) |
| **`/api` 404 in dev** | Start backend on `:8000` before frontend |
| **Model download / HF warnings** | Optional: `HF_TOKEN`, `EMBEDDINGS_CACHE_DIR=/var/lib/briefr/models`; embeddings are optional |
| **Wallboard asks for token** | Set `WALLBOARD_TOKEN`, restart backend, open `/wallboard`, enter the token once to create the read-only session cookie |
| **Backend won't start: `Failed to set up mount namespacing: /var/lib/briefr/intel-publish`** | PR #788 added this path to systemd `ReadWritePaths`; the directory must exist before restart. Run `sudo mkdir -p /var/lib/briefr/intel-publish && sudo chown briefr:briefr /var/lib/briefr/intel-publish`, then `sudo systemctl restart briefr-backend`. Fixed in deploy scripts from the next release — re-run `briefr-update.sh` after pulling |
| **Production UI blank or stale** | Production serves `frontend/dist` via nginx — not Vite. Re-run `npm run build` in `frontend/` (or `briefr-update.sh` / `briefr-deploy.sh`) after frontend changes |
| **Installed Postgres but still on `npm run dev`** | `npm run dev` is local development only (`:5173`). Production uses [SELF_HOST §3](SELF_HOST.md#3-production-debian--systemd--nginx): `briefr-install.sh`, nginx on `:80`, `BRIEFR_ENV=production` |
| **API keys / `.env` changes ignored** | Process env vars win over `backend/.env`, but a running backend does not reload them — **restart** `uvicorn` or `briefr-backend` after changes |
| **First-visit tutorial blocks clicks** | Dismiss the overlay or complete the walkthrough; preference is stored in browser `localStorage` (`briefr_tutorial_seen`) |
| **`database is locked` (SQLite dev)** | SQLite allows one writer — stop parallel pytest/dev servers or switch to Postgres ([SELF_HOST §2](SELF_HOST.md#2-local-development-with-postgresql--pgvector)) |
| **SigmaHQ / Detect tab empty** | First sync is manual: Admin → Feed health → SigmaHQ → **Sync** (weekly job does not populate on day one) |
| **Swagger `/api/docs` missing in production** | Expected when `BRIEFR_ENV=production` — use [`API_REFERENCE.md`](API_REFERENCE.md) or enable only in dev |

---

## Still stuck?

- [`SELF_HOST.md`](SELF_HOST.md) — install paths and verification checklist
- [PRODUCT_STATUS.md](PRODUCT_STATUS.md) — what's supposed to work today
- [HOW_IT_WORKS.md](HOW_IT_WORKS.md) — architecture if you need context
- [Official docs](https://docs.projectjupiter.in) — user guide, FAQ, integrations
- [GitHub Discussions → Q&A](https://github.com/Soldier0x0/briefr/discussions/new?category=q-a) — community help (preferred over issues for questions)
- [GitHub issues](https://github.com/Soldier0x0/briefr/issues/new/choose) — reproducible bugs only
