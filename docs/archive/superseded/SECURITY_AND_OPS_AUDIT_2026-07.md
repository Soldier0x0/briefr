# Security & ops hygiene audit (2026-07-10)

**Status:** findings documented — **no fixes applied yet.**  
**Trigger:** Operator audit log showed partial API keys in `config.set.*` targets; backup
cluster after backend restarts.

**Scope:** full-repo pass for (1) secret exposure / weak redaction, (2) interval and
restart semantics, (3) duplicate scheduled work. Read-only code review + grep.

---

## Executive summary

| Severity | Count | Theme |
|----------|------:|-------|
| **High** | 9 | Secrets in audit log, API responses, DB, backups, public health |
| **Medium** | 12 | Partial masking, delivery errors, restart duplicate sync, logging gaps |
| **Low** | 8 | Path disclosure, username audits, intentional bootstrap jobs |

**Immediate operator actions (no code):**

1. **Rotate** any API key ever saved via Admin → API keys (audit log may hold up to 100
   chars per `config.set.*` row; retention ~365 days).
2. Treat backup archives and `GET /storage/export` as **credential-bearing** (full `.env`
   + `app_settings` + `webhook_destinations`).
3. Expect **extra backups** after every `briefr-backend` restart until S-2 is fixed.

---

## A — Secret exposure & redaction

### A-1 · Audit log stores raw config values (HIGH)

| | |
|---|---|
| **Where** | `backend/routers/admin.py` — `set_config()` |
| **Code** | `await audit(request, f"config.set.{key}", value[:100])` |
| **Issue** | First 100 characters of **every** writable key written to `audit_log.target`,
including all `type: "secret"` fields (`GROQ_API_KEY`, `DATABASE_URL`, etc.). |
| **UI** | `AuditLogPage.jsx` renders `target`; CSS ellipsis only — full value in API JSON. |
| **Contrast** | `config.apply` logs key **names** only (safe). `database.migrate.start` redacts DSN. |
| **Fix** | Central `redact_audit_target(action, key, value)` — for `config.set.*` + secret/url
fields use first4…last4 (match webhook `_mask_secret`) or `[REDACTED]`. |

### A-2 · POST `/api/admin/config` returns full secrets (HIGH)

| | |
|---|---|
| **Where** | `backend/routers/admin.py` — `set_config()` return body |
| **Code** | `masked_value` uses `_mask_key()` only for Discord/Telegram/generic webhook URLs;
**all API keys and `DATABASE_URL` return full plaintext** in field named `masked_value`. |
| **Contrast** | `GET /config` masks API keys (last 6) — tested in `test_admin_config.py`. |
| **Fix** | Use `config_schema.get_field(key).type` — mask all `secret` and `url` types on POST
response; never return full value after save. |

### A-3 · `app_settings` persists secrets in plaintext (HIGH)

| | |
|---|---|
| **Where** | `backend/operator_settings.py` — `persist_operator_setting()` |
| **Issue** | Every admin save writes full value to `app_settings.value`. |
| **Contrast** | `seed_app_settings_from_dotenv()` **skips** `type == "secret"` on one-time import. |
| **Exposure** | Postgres `pg_dump` backups, `GET /storage/export` (full DB vacuum-into). |
| **Fix options** | (a) Do not persist secrets to DB — `.env` only; (b) encrypt at rest; (c) at
minimum exclude secrets from DB export docs + never log. Document chosen model in
`PRODUCT_STATUS.md`. |

### A-4 · Webhook destinations: masked in API, plaintext in DB (HIGH)

| | |
|---|---|
| **Where** | `webhooks/destinations.py`, `db/webhooks.py` |
| **Issue** | `config_json` stores full Discord webhook URLs / Telegram tokens. |
| **Mitigation** | `destination_to_api_dict()` masks on read (`first4…last4`, URL prefix). |
| **Exposure** | Full DB backup/export (A-3). |

### A-5 · Webhook delivery log errors (HIGH admin / MEDIUM if leaked)

| | |
|---|---|
| **Where** | `webhooks/engine.py` → `webhook_delivery_log.error`; `GET /webhooks/delivery-log` |
| **Issue** | `str(exc)[:300]` may include URL fragments or upstream responses. |
| **Fix** | Sanitize errors before store/return; generic message + `request_id` for operators. |

### A-6 · Public `/api/health` exposes feed errors + queue context (HIGH)

| | |
|---|---|
| **Where** | `backend/routers/health.py` — unauthenticated |
| **Issue** | Returns `get_feed_health()` (`last_error` up to 300 chars) and
`get_api_queue_status()` with `context_id` from `api_queue_operations.sanitize_context()`. |
| **Gap** | URL sanitizer strips **query** only; Discord/Telegram webhook **tokens are in the
path** — can appear on public health for webhook outbound ops. |
| **Fix** | Redact URL paths in queue status; consider moving detailed errors to admin-only
health; keep `/api/health/live` minimal (already is). |

### A-7 · Backup archives include full `.env` (HIGH — by design, risky)

| | |
|---|---|
| **Where** | `backend/backup/manager.py` — `_create_*_archive_bundle()` |
| **Issue** | Copies `backend/.env` into tarball when present (all keys). |
| **Mitigation** | Optional age encryption; key file must live outside `BACKUP_DIR`. |
| **Doc** | Ensure `SELF_HOST.md` / `OPERATIONS.md` state backups are secret-bearing. |

### A-8 · Full DB export (HIGH admin)

| | |
|---|---|
| **Where** | `GET /api/admin/storage/export` |
| **Issue** | SQLite `VACUUM INTO` / Postgres equivalent of **entire** DB — includes
`app_settings`, `webhook_destinations`, `audit_log` (with A-1 material), `users.password_hash`,
`sessions.refresh_token_hash`. |
| **Mitigation** | Admin auth required; not a public leak. |

### A-9 · GET config partial key suffix (MEDIUM)

| | |
|---|---|
| **Where** | `_mask_key()` — `…{value[-6:]}` |
| **Issue** | Reveals last 6 chars of every API key on config page. Weaker than webhook
`first4…last4`. |
| **Fix** | Align all masks to `first4…last4` (user preference from audit discussion). |

### A-10 · Structured logging redacts `extra` only (MEDIUM)

| | |
|---|---|
| **Where** | `backend/structured_logging.py` |
| **Issue** | `message` and `exc_info` not scanned; webhook `logger.error(..., result["error"])`
can put delivery errors in message → journal, admin `/logs`, support pack. |
| **Fix** | Never interpolate upstream errors into log message strings; use `extra` + redaction
or static messages per `CLAUDE.md`. |

### A-11 · Intel snapshot export (LOW — OK)

| | |
|---|---|
| **Where** | `scripts/export_intel_snapshot.py` |
| **Status** | `INTEL_TABLES` excludes `app_settings`, `audit_log`, `webhook_*`, `users`,
`sessions`. `FORBIDDEN_TABLES` guard. **No issue** for standard intel export. |

### A-12 · Auth/session APIs (LOW — OK)

| | |
|---|---|
| **Where** | `routers/auth.py` |
| **Status** | Passwords never returned; `refresh_token_hash` stripped from session list;
generic login failure message (tested). |

### A-13 · AI operations (LOW — OK)

| | |
|---|---|
| **Where** | `db/ai_operations.py` |
| **Status** | Metadata only — no prompts/completions. |

### A-14 · JWT / admin API key (LOW — OK)

| | |
|---|---|
| **Status** | Not writable via admin config API; auto-generated JWT if missing. |

---

## B — Backup & interval / restart semantics

### B-1 · `scheduled_backup` fires ~2 min after every backend restart (HIGH — confirmed bug)

| | |
|---|---|
| **Where** | `backend/scheduler.py` — `start_scheduler()` |
| **Code** | `next_run_time=datetime.now(sched_tz) + timedelta(minutes=2)` on `scheduled_backup` |
| **Issue** | Ignores `BACKUP_INTERVAL_HOURS` and last archive mtime. Every
`systemctl restart briefr-backend` → new backup ~2 min later. |
| **User impact** | Matches audit log clusters (12:19, 12:22, 13:07…) alongside normal 6h
entries (00:51, 06:51, 18:52). |

### B-2 · Duplicate backup schedulers in production (HIGH — architecture)

| | |
|---|---|
| **Paths** | (1) APScheduler `scheduled_backup` in uvicorn process; (2) systemd
`deploy/briefr-pg-backup.timer` (`OnBootSec=15min`, `OnUnitActiveSec=6h`). |
| **Issue** | Two independent triggers; **no cross-process file lock** on `run_backup()`. |
| **Docs** | `OPERATIONS.md` describes timer; in-process job undocumented as second owner. |
| **Fix** | Pick single owner (recommend: **systemd timer only** in production — disable
in-process `scheduled_backup` when `BRIEFR_USE_SYSTEMD_BACKUP=1` or detect timer active);
or add `last_backup_age` guard inside `run_backup()` for all callers. |

### B-3 · No minimum interval inside `run_backup()` (HIGH)

| | |
|---|---|
| **Where** | `backend/backup/manager.py` — `run_backup()` |
| **Issue** | Only checks `BACKUP_ENABLED`; never skips if last archive younger than interval. |
| **Fix** | At start: `list_backups()[0].mtime` vs `BACKUP_INTERVAL_HOURS` — skip with
`status: skipped, reason: interval` unless `reason` is `manual-admin` / `pre-update` /
`pre-restore`. |

### B-4 · Deploy pre-update backup + post-restart backup (MEDIUM)

| | |
|---|---|
| **Where** | `deploy/lib.sh` — `run_pre_update_backup()` then restart → scheduler +2m |
| **Issue** | Every `briefr-update.sh` can produce two backups within minutes. |

### B-5 · Separate locks: scheduler vs admin manual backup (MEDIUM)

| | |
|---|---|
| **Where** | `get_lock("scheduled_backup")` vs `_backup_running` in admin |
| **Issue** | Manual and scheduled backups can overlap (parallel `pg_dump`). |

### B-6 · `BACKUP_INTERVAL_HOURS` reschedule resets interval from “now” (MEDIUM)

| | |
|---|---|
| **Where** | `scheduler.reschedule_jobs_for_keys()` — `job.reschedule(trigger)` only |
| **Issue** | Changing interval in admin does not anchor to last backup time. |

---

## C — Restart duplicate work (non-backup)

### C-1 · NVD / KEV / EPSS run immediately on scheduler start (MEDIUM)

| | |
|---|---|
| **Where** | `scheduler.py` — `nvd_incremental_sync`, `kev_metadata_sync`, `epss_score_sync` |
| **Issue** | No `next_run_time` delay — APScheduler fires at process start. |
| **`scheduler.last_run.*`** | Written after jobs but **never read** for scheduling. |
| **Mitigation** | Watermarks reduce duplicate work; still API burst on restart. |
| **Fix** | `next_run_time = max(now, last_run + interval)` using `scheduler.last_run` or
`sync_state` watermarks. |

### C-2 · Startup deferred jobs overlap scheduler (MEDIUM)

| | |
|---|---|
| **Where** | `main.py` — `maybe_run_on_startup()` after `start_scheduler()` |
| **Issue** | Race with immediate interval jobs; locks usually prevent double execution but
scheduling is wasteful and ordering is nondeterministic. |

### C-3 · Exploit sources: startup + scheduler +30m (MEDIUM)

| | |
|---|---|
| **Where** | `maybe_run_on_startup()` + `exploit_sources_sync` with `next_run_time=+30m` |
| **Issue** | Duplicate within 30 minutes of every restart when enabled. |

### C-4 · Boot warmup jobs (LOW — intentional)

| | |
|---|---|
| **Jobs** | incident_feed +20s, llm_product_extraction +150s, vulnrichment +45s, etc. |
| **Verdict** | Intentional post-downtime freshness; document in operator guide. Only a
“bug” if operators expect strict interval-from-last-success everywhere. |

---

## D — Recommended fix track (sprint **Track M**)

Implement as small PRs; order by risk.

| ID | Item | Primary files | Acceptance |
|----|------|---------------|------------|
| **M-1** | Audit redaction for `config.set.*` secrets/urls | `admin.py`, `dependencies.py` or shared `redact.py`, `test_audit_log.py` | No secret substring in audit `target` for API keys |
| **M-2** | POST `/config` `masked_value` uses schema type | `admin.py`, `test_admin_config.py` | POST never returns full secret |
| **M-3** | Unified mask helper (`first4…last4`) | `admin.py`, align with `destinations._mask_secret` | GET/POST/audit consistent |
| **M-4** | Backup interval guard in `run_backup()` | `backup/manager.py`, tests | Restart within interval → `skipped` |
| **M-5** | Single backup owner / disable in-process when timer active | `scheduler.py`, `deploy/`, `OPERATIONS.md` | No double pg_dump in prod |
| **M-6** | Webhook URL path redaction in `sanitize_context` | `api_queue_operations.py`, `test_api_queue.py` | Public health queue safe |
| **M-7** | Delivery-log error sanitization | `webhooks/engine.py`, admin endpoint | No raw URL in `error` column |
| **M-8** | `app_settings` secret policy (decision + impl) | `operator_settings.py`, docs | Document: env-only vs encrypted DB |
| **M-9** | Ingest `next_run_time` from `scheduler.last_run` | `scheduler.py`, tests | Restart does not immediate-fire NVD/KEV/EPSS |
| **M-10** | Global backup mutex (fcntl) | `backup/manager.py` | Overlapping triggers serialize |

**Out of scope for M track:** encrypting backup `.env` (already age); rotating existing audit
rows (operator purge or wait for retention).

---

## E — Controls already working

- `GET /api/admin/config` masks API keys (tested).
- Webhook destination CRUD masks config in API responses.
- `validate_value()` rejects masked placeholders (`…`, `***`) on write.
- Support pack redacts DB URL; log `extra` secrets redacted.
- Intel snapshot excludes operator/auth/webhook tables.
- Outbound webhooks strip internal API headers (`webhooks/ssrf.py`).
- `config.apply` audit logs key names only.
- Production disables OpenAPI/docs URLs (`main.py`).

---

## F — Cross-reference

- LLM prompt/pacing hygiene: **Track K5** (`docs/SPRINT_2026-07.md`, Spec K §2).
- Danger zone logging rules: `CLAUDE.md` § Secrets in logs.
- Backup operations truth: `docs/OPERATIONS.md`, `docs/POSTGRES.md`.
