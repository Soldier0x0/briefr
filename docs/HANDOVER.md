# BRIEFR — Agent Handover (V1.2 in progress → V1.5)

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-18
**Status:** Temporary working document — delete or archive when V1.5 ships.
**Audience:** the next AI agent (or human) continuing the Beta V1.2–V1.5 programme.

---

## 1. What this document is

The previous agent session planned and partially executed the approved roadmap
(V1.2 → V1.5, **V2.0 parked**). This document is the complete state transfer:
what shipped, what is open, exactly what to build next, and the **mandatory
workflow** every future PR must follow — including post-merge testing
checklists the operator runs on production.

Read in this order before writing any code:

1. This document
2. [`ROADMAP.md`](ROADMAP.md) § Approved execution scope (authoritative scope + amendments)
3. The target release doc (`../Beta V1.x.md`)
4. [`AGENT_IMPLEMENTATION_GUIDE.md`](AGENT_IMPLEMENTATION_GUIDE.md) and [`ONBOARDING.md`](ONBOARDING.md)

---

## 2. Deployment context (do not violate)

- **Private instance**: Cloudflare Access policy gates everything; 3 beta testers; not open source.
- Production: Debian, systemd (`briefr-backend`), nginx :80, cloudflared, SQLite at `/opt/briefr/backend/briefr.db`, backups in `/var/lib/briefr/backups`.
- Operator deploys with: `cd /opt/briefr && bash deploy/briefr-update.sh` (script pulls main itself).
- **Single complete tool now; modular SIEM later.** Intel stays in SQLite. No NiFi/Postgres/ClickHouse for intel ingest. ML is env-gated, CPU-only, scheduler-side, with deterministic fallback. See `JUPITER_VISION.md` § Strategy statement.

---

## 3. Shipped so far (PR ledger)

| PR | Branch | Content | Status |
|----|--------|---------|--------|
| #84 | roadmap-plan-amendments | Roadmap codification + review fixes (JWT-validated CF Access spec, embeddings fallback, watchlist index, backup-key scope) | ✅ Merged |
| #85 | kev-enrichment-fields | KEV `knownRansomwareCampaignUse`/`cwes`/`vendorProject`/`vulnerabilityName` ingest + API + RANSOMWARE badges | ✅ Merged |
| #86 | incident-feed-snapshot | Incidents & News served from scheduler-built snapshot (7s → ~20ms), parallel RSS, `feeds.incidents` health, `meta.{refreshed_at,stale,warming}` | ✅ Merged + verified in prod |
| #87 | resilient-http-client | Resilient client (retries, circuit breakers, `feeds.sources` health) | ⚠️ Merged **into the wrong branch** — see §4 |
| #88 | ci-audits-version | `/api/version` + deploy stamping + `pip-audit`/`npm audit` CI jobs | ✅ Merged |
| #89 | restore-resilient-client | Clean cherry-pick of #87's content onto `main` | ✅ Merged |
| #90 | ui-ux-fixes | UI/UX correctness pass: feed scroll/filter fixes, stale-while-revalidate, overlay layering/focus traps, self-hosted fonts, reduced-motion, request timeouts, sidebar cache | ✅ Merged |
| #92 | enrichment-resilience | CIRCL migrated to vulnerability.circl.lu (+`CIRCL_API_KEY`, negative caching), OSV alias-follow fix (was silently broken with HTTP 400), resilient client adoption completed for ALL outbound modules (VT/AbuseIPDB/GreyNoise at `retries=0` — never burn quota) | ✅ Merged |
| #91 | v12-status-handover | Doc sync + this handover | ✅ Merged |
| #93 | cf-access-identity-audit-log | §5.1 reworked after operator decision (2026-06-11): **CF Access middleware and fail-closed admin key removed** — auth will be a **built-in app login** before public release. PR now ships only the `audit_log` table + writes (refreshes, backups, restores) | ✅ Merged |
| #94 | settings-and-refresh-router | §5.2 phase 1: `settings.py` (BaseSettings), `dependencies.py` (`require_admin_key`, `audit`), `routers/refresh.py` | ✅ Merged |
| #95 | router-split-ioc-atlas-health | §5.2 phase 2: `routers/health.py`, `routers/atlas.py`, `routers/ioc.py` moved out of `main.py` verbatim; OpenAPI route list byte-identical (snapshot test `tests/test_router_split.py`). +1 review fix: cached IOC hit now commits on-demand GreyNoise/OTX feed_cache writes (were rolled back on close — pre-existing in main.py) | ✅ Merged |
| #96 | router-split-cves-meta-final | §5.2 phase 3 (final): `routers/cves.py` (changes/stats/list/export/detail/momentum/detection/correlation/KEV + CVE filter SQL) + `routers/meta.py` (version/time/usage/AI summaries) moved out of `main.py` verbatim; full OpenAPI JSON diffed byte-identical against pre-split main; `main.py` now app wiring only (~130 lines — V1.2 exit criterion met). +4 review fixes: stack-relevance sort no longer crashes on NULL `affected_products` (pre-existing in main.py); momentum/detection/correlation now validate the `CVE-` prefix like their siblings; `/api/stats` is one conditional-aggregation scan instead of five COUNT(*) scans (same response); `_row_to_cve_dict` normalizes NULL/'' list columns to `[]` per the API_REFERENCE contract | ✅ Merged |
| #97 | risk-weights-api | §5.3: `GET /api/config/risk` in `routers/config.py` reads weights from `scoring/risk.py`; `riskScore.js` fetches at startup and caches, hardcoded constants as fallback. Weights sum to 1.0 invariant tested. | ✅ Merged |
| #100 | add-pytest-to-requirements | `pytest` in `requirements.txt` so deploy venv has it | ✅ Merged |
| #101 | playwright-ci-smoke | §5.7: Chromium-only Playwright smoke in `backend-tests.yml` (third job) against `scripts/seed_screenshot_data.py` — BRIEF cards, filter→feed anchor, drawer focus restore, IOC input, Incidents cards (`tests/test_playwright_smoke.py`, skipped unless `PLAYWRIGHT_SMOKE=1`) | ✅ Merged |
| #102 | epss-backfill | §5.4: one-shot EPSS history backfill via FIRST API `scope=time-series`; `epss_backfill_done` sync_state marker; batched (100/req) + throttled (2 s/batch ≈ 30 req/min); `INSERT OR IGNORE` idempotency; new DB helpers `get_sync_state_value`, `set_sync_state_value`, `insert_epss_history_rows`; wired into `maybe_run_on_startup` as background task. | ✅ Merged |
| #103 | backup-age-encryption | §5.6: age-encrypted backups (`pyrage`), key at `/var/lib/briefr/keys/backup-age.key` | ✅ Merged |
| #104 | rate-limit-structured-logging | §5.5: in-memory token bucket (`rate_limit.py`) on `POST /api/ioc/lookup` (30/min) + all `POST /api/refresh*` (10/min shared, consumed before admin-key check), per client IP, 429 + `Retry-After`; JSON structured logging (`structured_logging.py`) with `request_id` contextvar, `X-Request-ID` response header, `briefr.access` per-request line, uvicorn loggers unified; env: `RATE_LIMIT_ENABLED/IOC_PER_MINUTE/REFRESH_PER_MINUTE`, `LOG_FORMAT`. +3 review fixes: forwarded headers trusted only from loopback proxy peers (`CF-Connecting-IP` → rightmost non-loopback XFF hop → `X-Real-IP`; direct connections keyed by socket — spoofed XFF can no longer mint buckets); hard cap with LRU eviction on bucket storage (key-flood OOM); unhandled exceptions logged with `request_id` before contextvar reset | ✅ Merged |
| #106 | change-intel-kev-countdown | V1.3 tranche 2: What changed panel (`GET /api/changes`, field + 24h/48h/7d filters, row → drawer); KEV **Due in N days** chip on cards (`kev_due_date` additive on list/export/detail); sidebar deadlines `sort=urgent` | ✅ Merged |
| #107 | vulnrichment-cvelistv5-feeds | Vulnrichment snapshot + cvelistV5 incremental sync | ✅ Merged |
| #108 | forge-mvp-coverage-hunt-packs | V1.3 Forge MVP: `hunt_packs` table (idempotent migration), `routers/forge.py` (`GET /api/forge/coverage` coverage map with yours/community/gap statuses, `GET /api/hunt-packs/{technique_id}`, `POST /api/hunt-packs/generate` CVE→pack upsert), FORGE tab (coverage map grouped by tactic + hunt pack panel with Sigma/SIEM copy + generate). All local/deterministic — no outbound HTTP, no new env vars. Community-rule GitHub search stays on `/api/cves/{id}/detection` | ✅ Merged |
| #109 | exploit-sources-batch2 | PoC-in-GitHub, ExploitDB, Metasploit, Nuclei exploit sources | ✅ Merged |
| #110 | embeddings-llm-product-extraction | V1.3 Theme 7 (partial): CVE description embeddings (`cve_embeddings` BLOBs, NumPy brute-force cosine default, `sqlite-vec` importable-only accelerator, `fastembed` optional install) powering semantic `GET /api/cves/{id}/related` (additive: `meta.method` + per-item `similarity`; product heuristic stays the fallback) + LLM product extraction for NVD-unanalyzed CVEs (Groq via `resilient_client` `retries=0`, writes only empty `affected_products`, provenance `affected_products_source='llm'`, official CPE supersedes, completed extractions negative-cached 7 days, errors retried next run). Both scheduler jobs env-gated, off by default (`EMBEDDINGS_ENABLED=0`, `LLM_PRODUCT_EXTRACTION_ENABLED=0`) | ✅ Merged |
| #111 | epss-change-noise-fix | Follow-up: EPSS change history uses 0.1% display precision (stops `0.0% → 0.0%` noise); frontend hides legacy identical rows | ✅ Merged |
| #112 | filter-rejected-cves | Skip NVD `vulnStatus: Rejected` + cvelistV5 `state: REJECTED` on ingest; `purge_legacy_rejected_cves` + `delete_cves_by_ids` each scheduler sync | ✅ Merged |
| #113 | embeddings-cache-dir-erofs-fix | Follow-up to #110: embeddings model download failed in prod with EROFS — `EMBEDDINGS_CACHE_DIR` env (unit sets `/var/lib/briefr/models` + `HF_HOME`) | ✅ Merged |
| #114 | setup-dev-environment | AGENTS.md cloud-agent bootstrap + seed script path clarity | ✅ Merged |
| #115 | webhook-alerts-c999 | V1.3 Theme 8: Telegram + Discord webhook sender (`webhooks/sender.py`, resilient_client retries=2); KEV-on-stack after KEV sync (`BRIEFR_STACK_TERMS`, `webhook_alert_log` dedupe); backup dead-man scheduler check (2× `BACKUP_INTERVAL_HOURS`) | ✅ Merged |
| #121–#131 | dependabot + deploy fixes | Backend: FastAPI 0.137.2, uvicorn 0.49.0, numpy 2.4.6, PyYAML 6.0.3, pytest 9.1.0. Frontend: React 19.2.7, Vite 8, lockfile sync. Deploy: `briefr-update.sh` cleanup, git-drift fix, FastAPI 0.137 router-split test fix | ✅ Merged |
| #132 | groq-llama-8b-instant | Pin Groq model to `llama-3.1-8b-instant`; playwright-smoke incident-feed flake fix | ✅ Merged |
| #117 | morning-brief-explainable-risk | V1.3 Phase 2: `GET /api/brief` (`backend/brief/service.py`, read-path only) — EPSS movers, new KEV, KEV due soon, stack activity + ranked `action_queue`; BRIEF tab landing (`MorningBrief.jsx`), full feed demoted to FEED tab; drawer explainable risk math (`score × weight × 100`, momentum signals, weights from `/api/config/risk`) | 🔲 Open — **merge first** |
| #116 | chartjs-brief-dashboard | V1.3 Theme 2: Chart.js analyst brief dashboard (lazy-loaded, bundled — no CDN) | 🔲 Open |
| #119 | brief-heatmap-layout | Side-by-side BRIEF heatmap + What changed panel layout | 🔲 Open |
| #118 | watchlist-pin-snooze | V1.3 Theme 1: CVE watchlist pin/snooze (`watchlist` table, `GET/POST/DELETE /api/watchlist`) | 🔲 Open |
| #134 | brief-charts-ux-polish | V1.3 Theme 2 follow-up: urgency hierarchy, heatmap labels, Chart.js restyle, EPSS table, KEV bucket clicks | ✅ Merged |
| #135 | morning-brief-unified-queue | V1.3 Theme 1 follow-up: BRIEF-only Hero/StatsRow/heatmap; FEED compact FilterBar stack; unified action_queue list + filters; histogram → due-window | 🔲 Open |

Each merged PR's description contains its own **post-merge verification
checklist** — that is the house style; keep it (see §7).

### Open PR merge order (2026-06-18)

Rebased onto current `main` (includes merged #132 playwright-smoke fix + Groq model pin). **Merge one at a time**.

| Order | PR | Branch | Notes |
|-------|-----|--------|-------|
| 1 | #117 | `cursor/morning-brief-explainable-risk-df48` | Foundation: `GET /api/brief`, BRIEF landing tab |
| 2 | #116 | `cursor/chartjs-brief-dashboard-9662` | Rebased on #117; Chart.js in BriefView |
| 3 | #119 | `cursor/brief-heatmap-layout-adcb` | Rebased on #116; heatmap + What changed side-by-side |
| 4 | #118 | `cursor/watchlist-pin-snooze-8656` | Rebased on #119; pin/snooze API + feed controls |

Gemini Code Assist review fixes are already incorporated on #116–#118 (date SQL, chart guards, watchlist key normalization).

---

## 4. ⚠️ Process lesson: the stacked-PR mishap

#87 was stacked on #86's branch. #86 merged to `main`, but #87's base was
**not retargeted** — so #87 "merged" into an already-merged side branch and
its code never reached `main`. #89 fixes this by cherry-pick.

**Rules going forward:**

1. Prefer independent branches off `main`. Stack only when files genuinely overlap.
2. If stacked: after the base PR merges, **verify on the GitHub UI that the
   stacked PR now targets `main`** (it auto-retargets only when the base
   branch gets deleted) before telling the operator to merge.
3. After any merge: `git fetch origin main && git log origin/main --oneline -3`
   and confirm the expected commits are actually there.

---

## 5. V1.2 work — ✅ complete (2026-06-18)

All V1.2 exit criteria met on `main` (PRs #89–#104, #101, #103). Section retained for reference.

Ordered; each is one PR unless noted. File pointers are current as of this doc.

### 5.1 ~~Cloudflare Access identity middleware~~ + `audit_log` table — ✅ done (PR #93 open)
- **Scope amended by operator decision (2026-06-11):** BRIEFR targets public
  self-hosting, so identity will come from a **built-in app login** (lands
  with/before public release), NOT Cloudflare Access. The CF JWT middleware
  and the production fail-closed admin key were implemented, then removed
  from the PR. Do not rebuild them.
- What ships in #93: `audit_log` table (actor, action, target, timestamp) +
  writes from backup runs, restores, manual `/api/refresh*` calls. Actor is
  `system` for backups/restores and empty for request-driven actions until
  app login lands (`request.state.user_email` is the wiring hook in
  `dependencies.py:audit` — moved out of `main.py` by the §5.2 split).
- Post-merge tests: `PRAGMA table_info(audit_log)` shows columns; manual
  refresh and a backup run each add a row; pytest green.

### 5.2 `settings.py` + router split — ✅ done (PR #96 open)
- Pydantic `BaseSettings` for env config; `routers/` (cves, ioc, atlas,
  health, refresh, meta) + `dependencies.py`. **Pure mechanical moves, no
  behavior change.** Done in 3 PRs, one router group each.
- **Phase 1 shipped (#94):** `settings.py` (import-time vars: `BRIEFR_ENV`,
  `BRIEFR_ADMIN_API_KEY`, `ALLOWED_ORIGINS`), `dependencies.py`
  (`require_admin_key`, `audit`), `routers/refresh.py` (all
  `POST /api/refresh*`). Per-request `os.environ.get` reads stay as-is and
  migrated with their router groups.
- **Phase 2 shipped (#95):** `routers/health.py` (`GET /api/health` +
  `format_time_in_tz`), `routers/atlas.py` (`/api/atlas/*`,
  `/api/case-studies/*`), `routers/ioc.py` (`POST /api/ioc/lookup`,
  `GET /api/otx/pulses/{id}/iocs`). Routers are included mid-module in
  `main.py` to keep OpenAPI route order identical;
  `tests/test_router_split.py` snapshots the route list.
- **Phase 3 shipped (#96):** `routers/cves.py` (4 sub-routers because CVE
  routes were interleaved with ATLAS/IOC groups: changes, list/stats/export,
  detail, momentum/detection/correlation/KEV) + `routers/meta.py`
  (2 sub-routers: version/time, usage/AI summaries). `main.py` is app wiring
  only (~130 lines). `/api/cves/{cve_id}` still registers after literal
  siblings (`/api/cves/export` etc.) — regression-tested. Full OpenAPI JSON
  verified byte-identical against pre-split `main`.
- Post-merge tests: full pytest suite; `diff` of `/api/openapi.json` route
  list before/after (must be identical); smoke `deploy/smoke-intel.sh`.

### 5.3 Single-source risk weights — ✅ done (PR TBD open)
- `GET /api/config/risk` in `routers/config.py` reads the six v1.1b weights
  directly from `scoring/risk.py` constants and returns `{version, weights}`.
- `frontend/src/scoring/riskScore.js` imports `fetchRiskWeights` from `api.js`,
  calls `fetchAndCacheRiskWeights()` at startup (fire-and-forget via `main.jsx`),
  and uses the module-level `_weights` cache in `calculateRiskScore`. Falls
  back to bundled constants on any network/parse error.
- Weights-sum-to-1.0 validated client-side (tolerance 1e-6) and tested by
  `tests/test_config_risk_endpoint.py`. Removes drift risk documented in
  README § Known limitations.
- Post-merge tests: drawer risk breakdown unchanged for a known CVE;
  `curl http://127.0.0.1:8000/api/config/risk` returns weights summing to 1.0.

### 5.4 EPSS 30-day history backfill — ✅ done (PR #102 open)
- One-shot resumable job (marker `epss_backfill_done` in `sync_state`).
  `feeds/epss.py:fetch_epss_time_series_batch` calls the FIRST API with
  `scope=time-series` for 100 CVEs at a time, throttled at 2 s/batch
  (≈30 req/min, well below 1,000/min limit). Only CVEs already in the DB;
  `INSERT OR IGNORE` prevents duplicates on restart. Wired into
  `scheduler.py:maybe_run_on_startup` as `asyncio.create_task`.
- Post-merge tests: `epss_history` row count grows; sparklines show >1 point
  for older CVEs; job idempotent on restart (marker respected).
- New DB helpers: `get_sync_state_value`, `set_sync_state_value`,
  `insert_epss_history_rows` (all in `database.py`).

### 5.5 Rate limiting + structured logging — ✅ done (PR #104 open)
- Shipped: simple in-memory token bucket (`rate_limit.py`, no slowapi dep)
  keyed per client IP — forwarded headers honoured only from loopback proxy
  peers (`CF-Connecting-IP` → rightmost non-loopback `X-Forwarded-For` hop →
  `X-Real-IP`), direct connections keyed by socket address, bucket storage
  hard-capped with LRU eviction;
  `POST /api/ioc/lookup` at `RATE_LIMIT_IOC_PER_MINUTE` (30) and all
  `POST /api/refresh*` sharing `RATE_LIMIT_REFRESH_PER_MINUTE` (10), consumed
  **before** the admin-key check; over limit → 429 + `Retry-After` (seconds);
  `RATE_LIMIT_ENABLED=0` disables. JSON structured logging
  (`structured_logging.py`): one JSON line per record with `request_id`
  (contextvar set by the outermost `request_context` middleware in `main.py`),
  `X-Request-ID` echoed/generated on every response, `briefr.access`
  per-request line (method/path/status/duration_ms/client) replaces uvicorn's
  access log in JSON mode; `LOG_FORMAT=plain` opt-out for local dev.
- Post-merge tests: burst the IOC endpoint → 429 with Retry-After; journal
  shows JSON lines with request_id.

### 5.6 Backup encryption (`age`) — ✅ done (PR open)
- Shipped: archives age-encrypted in `backend/backup/manager.py` (X25519 via
  `pyrage`, interoperable with the `age` CLI) + `deploy/briefr-backup.sh`
  generates the key on first run at `/var/lib/briefr/keys/backup-age.key`
  (`BACKUP_AGE_KEY_FILE`); manager **refuses** a key inside `BACKUP_DIR`;
  key readable by the `briefr` user so restore and startup auto-restore keep
  working for both `.tar.gz` and `.tar.gz.age`. Scope honesty: protects
  off-site/at-rest copies only — see `THREAT_MODEL.md` § Scope of backup
  encryption.
- Post-merge tests: new archive is age-encrypted; `briefr-restore.sh` round-trips;
  startup auto-restore from an encrypted archive works on a copy of prod DB.

### 5.7 Playwright smoke in CI — ✅ done (PR #101 open)
- Chromium-only, against seeded data (`scripts/seed_screenshot_data.py`):
  BRIEF renders cards; filter click anchors to feed (regression for #90);
  drawer opens/closes with focus restore; IOC tab accepts input; Incidents
  renders cards. Wired into `.github/workflows/backend-tests.yml` as the
  `playwright-smoke` job; pytest module `tests/test_playwright_smoke.py`
  (skipped in the default `pytest tests/ -q` run unless `PLAYWRIGHT_SMOKE=1`).
- Post-merge tests: GitHub Actions `playwright-smoke` job green; locally
  `cd frontend && npm ci && npm run build && cd ../backend &&
  PLAYWRIGHT_SMOKE=1 pytest tests/test_playwright_smoke.py -q`.

**V1.2 exit criteria** (from `Beta V1.2.md`, amended 2026-06-11): `main.py`
under ~300 lines; no duplicated risk weights; circuit breaker behavior
verified; CI green including smoke. (Auth criterion moved out: built-in app
login ships before public release, not in V1.2.)

---

## 6. After V1.2: tranche plan (already approved — do not re-litigate)

**Tranche 2 (V1.3):** "what changed" UI + KEV due-date countdown (data
already in DB — cheapest analyst value, do these first) → morning brief API +
explainable risk UI → Chart.js brief dashboard → Forge MVP (coverage map,
hunt-packs API, CVE→pack) → watchlist/pin/snooze (single-user now; keyed by
app-login user once built-in auth ships) → new intel sources (Vulnrichment, cvelistV5, PoC-in-GitHub,
ExploitDB, Metasploit metadata, Nuclei index — all as `resilient_client` feed
modules; snapshot-type sources need no watermark) → embeddings (BLOBs +
NumPy brute-force default; `sqlite-vec` optional) + LLM product extraction for
NVD-unanalyzed CVEs → **first webhook channel** (Telegram or Discord,
env-configured) + KEV-on-stack rule + backup dead-man ping.

**Tranche 3 (V1.4):** webhook engine (SSRF protection mandatory — block
private IP ranges) → lean admin pane (health, backups list/trigger, scheduler
controls, feed health, audit log viewer; gate via dedicated CF Access policy
on `/admin/*`) → log viewer → wallboard last.

**Tranche 4 (V1.5):** threat model UI → rule proof bench (file-based) → KEV
delta backlog → STIX 2.1 export + Sigma pack zip → IOC watchlist (indexed on
IOC value) + ThreatFox + retro-match + VulnCheck KEV tier.

Deferred (do not build): STRIDE-lite worksheet, HyperDX provisioner, V2.0
(Docker/Postgres/multi-user), dynamic malware sandbox (static dissection
bench is a possible V1.5+ item; detonation only ever as an isolated sidecar).

UI/IA decision needed before the morning brief lands: whether the brief
becomes the landing view with the full feed demoted to a second view. Ask the
operator; default recommendation is yes.

---

## 7. Mandatory per-PR workflow

1. **One phase per PR.** Small, independently shippable, no mega-PRs.
2. Branch off fresh `main`: `cursor/<descriptive-name>-<agent-suffix>`.
3. **Tests in the same PR** (pytest for backend; build + Playwright once 5.7
   lands). Run `cd backend && pytest tests/ -q` before every push — baseline
   is currently ~100+ passing, never merge red.
4. **Docs in the same PR**: update `SYSTEM_DESIGN.md` when runtime behavior
   changes; `API_REFERENCE.md` for endpoint changes; `TECHNICAL_INVENTORY.md`
   for schema/scheduler changes; `.env.example` + `README.md` +
   `ONBOARDING.md` for new env vars; mark shipped items in the
   `Beta V1.x.md` doc.
5. **PR description must contain a "Post-merge verification" section** with
   copy-pasteable commands for the operator's production box
   (`http://127.0.0.1:8000`, `journalctl -u briefr-backend`,
   `sqlite3 /opt/briefr/backend/briefr.db`). The operator runs these after
   `bash deploy/briefr-update.sh`. Patterns to imitate: PRs #85, #86, #89, #90.
6. **Compatibility rules** (from `OPERATIONS.md`): additive API responses;
   forward-only idempotent migrations (the `ALTER TABLE` try/except list in
   `database.py:init_db`); env defaults unchanged; CLI backup/restore always
   works; SQLite = 1 uvicorn worker.
7. Code conventions: imports at top of module (no inline imports); follow
   existing patterns (`resilient_client` for outbound HTTP, `feed_cache` for
   caching, cancellation guards in frontend effects, `useModalLayer` for any
   new overlay).

### Post-merge testing methodology by change type

| Change type | Verify |
|---|---|
| New feed/source | `feeds.sources.<name>` in `/api/health` shows `last_success`, `circuit_open: false`; row counts in target table; journal free of errors |
| New endpoint | curl with expected params; additive shape confirmed; `API_REFERENCE.md` matches reality |
| Scheduler job | journal line for first run; `sync_state` marker if watermarked; idempotency on restart |
| Schema migration | `PRAGMA table_info(<table>)` shows columns; old DB upgrades in place (deploy does this implicitly); fresh DB boots |
| Frontend | `npm run build` green; the specific interaction tested in browser (list exact clicks/keys); no console errors; DevTools network tab if requests changed |
| Deploy script | `bash -n` syntax check; one full `briefr-update.sh` run; smoke output (`smoke-intel.sh` passes for CVE-2021-44228) |

Universal 30-second smoke after any deploy:
```bash
bash /opt/briefr/deploy/check-backend.sh
journalctl -u briefr-backend --since "-5 min" -p err   # expect empty
curl -s http://127.0.0.1:8000/api/health | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d['cve_count'], d['feeds']['incidents'])"
curl -s http://127.0.0.1:8000/api/version              # commit must match deployed HEAD
```

---

## 8. Agent environment bootstrap (fresh VM)

```bash
pip3 install --user -r backend/requirements.txt pytest pip-audit
export PATH="$HOME/.local/bin:$PATH"
cd backend && pytest tests/ -q        # must be green before you start
cd ../frontend && npm install && npm run build
```

Known quirks: `python3 -m venv` may be unavailable (use `pip3 --user`);
an empty dev DB triggers a full bootstrap ingest on app start (set
`BACKUP_ENABLED=0`, expect `database is locked` noise from write contention —
the snapshot/feed code degrades gracefully through it); test the API on a
spare port with `DB_PATH=/tmp/test.db`.

---

## 9. Open questions for the operator (ask before assuming)

1. ~~Morning brief as landing view?~~ — **Yes** (operator confirmed 2026-06-12); BRIEF tab is the landing view, FEED tab holds the full paginated list.
2. Webhook channel preference: Telegram or Discord first?
3. ~~CF Access secrets for 5.1~~ — moot: CF identity dropped (2026-06-11);
   auth = built-in app login before public release.
4. When V1.2 exit criteria are met: bump version, regenerate
   `SYSTEM_DESIGN.pdf` + `TECHNICAL_INVENTORY.xlsx` (commands in
   `ONBOARDING.md` §8), and update this document or retire it.
