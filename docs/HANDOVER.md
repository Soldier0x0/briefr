# BRIEFR — Agent Handover (V1.2 in progress → V1.5)

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-11
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
| #89 | restore-resilient-client | Clean cherry-pick of #87's content onto `main` | 🔲 Open — **merge first** |
| #90 | ui-ux-fixes | UI/UX correctness pass: feed scroll/filter fixes, stale-while-revalidate, overlay layering/focus traps, self-hosted fonts, reduced-motion, request timeouts, sidebar cache | 🔲 Open |
| #92 | enrichment-resilience | CIRCL migrated to vulnerability.circl.lu (+`CIRCL_API_KEY`, negative caching), OSV alias-follow fix (was silently broken with HTTP 400), resilient client adoption completed for ALL outbound modules (VT/AbuseIPDB/GreyNoise at `retries=0` — never burn quota) | ✅ Merged |
| #91 | v12-status-handover | Doc sync + this handover | ✅ Merged |
| #93 | cf-access-identity-audit-log | §5.1 reworked after operator decision (2026-06-11): **CF Access middleware and fail-closed admin key removed** — auth will be a **built-in app login** before public release. PR now ships only the `audit_log` table + writes (refreshes, backups, restores) | 🔲 Open |
| #94 | settings-and-refresh-router | §5.2 phase 1: `settings.py` (BaseSettings), `dependencies.py` (`require_admin_key`, `audit`), `routers/refresh.py` | ✅ Merged |
| #95 | router-split-ioc-atlas-health | §5.2 phase 2: `routers/health.py`, `routers/atlas.py`, `routers/ioc.py` moved out of `main.py` verbatim; OpenAPI route list byte-identical (snapshot test `tests/test_router_split.py`). +1 review fix: cached IOC hit now commits on-demand GreyNoise/OTX feed_cache writes (were rolled back on close — pre-existing in main.py) | ✅ Merged |
| #96 | router-split-cves-meta-final | §5.2 phase 3 (final): `routers/cves.py` (changes/stats/list/export/detail/momentum/detection/correlation/KEV + CVE filter SQL) + `routers/meta.py` (version/time/usage/AI summaries) moved out of `main.py` verbatim; full OpenAPI JSON diffed byte-identical against pre-split main; `main.py` now app wiring only (~130 lines — V1.2 exit criterion met). +4 review fixes: stack-relevance sort no longer crashes on NULL `affected_products` (pre-existing in main.py); momentum/detection/correlation now validate the `CVE-` prefix like their siblings; `/api/stats` is one conditional-aggregation scan instead of five COUNT(*) scans (same response); `_row_to_cve_dict` normalizes NULL/'' list columns to `[]` per the API_REFERENCE contract | 🔲 Open |
| TBD | risk-weights-api | §5.3: `GET /api/config/risk` in `routers/config.py` reads weights from `scoring/risk.py`; `riskScore.js` fetches at startup and caches, hardcoded constants as fallback. Weights sum to 1.0 invariant tested. Removes drift risk (README § Known limitations). | 🔲 Open |

Each merged PR's description contains its own **post-merge verification
checklist** — that is the house style; keep it (see §7).

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

## 5. Remaining V1.2 work (do these before V1.3)

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

### 5.4 EPSS 30-day history backfill
- One-shot resumable job (marker in `sync_state`, e.g. `epss_backfill_done`)
  using the FIRST API `scope=time-series`, batched CVE IDs, throttled well
  below 1,000 req/min, off the request path, via `resilient_client`.
  Only CVEs already in the DB. Full history `.gz` archives are **out of
  scope** (depth-greed — see ROADMAP amendments).
- Post-merge tests: `epss_history` row count grows; sparklines show >1 point
  for older CVEs; job idempotent on restart (marker respected).

### 5.5 Rate limiting + structured logging
- Rate limit `/api/ioc/lookup` and `/api/refresh*` (slowapi or simple
  in-memory token bucket — single worker makes this easy).
- JSON structured logging with request IDs (prep for V1.4 log viewer).
- Post-merge tests: burst the IOC endpoint → 429 with Retry-After; journal
  shows JSON lines with request_id.

### 5.6 Backup encryption (`age`)
- Encrypt archives in `backend/backup/manager.py` + `deploy/briefr-backup.sh`;
  key outside `BACKUP_DIR`, readable by the `briefr` user (auto-restore must
  keep working). Scope honesty: protects off-site/at-rest copies only — see
  `THREAT_MODEL.md` § Scope of backup encryption.
- Post-merge tests: new archive is age-encrypted; `briefr-restore.sh` round-trips;
  startup auto-restore from an encrypted archive works on a copy of prod DB.

### 5.7 Playwright smoke in CI
- Chromium-only, against seeded data (`scripts/seed_screenshot_data.py`):
  BRIEF renders cards; filter click anchors to feed (regression for #90);
  drawer opens/closes with focus restore; IOC tab accepts input; Incidents
  renders cards. Wire into `.github/workflows/backend-tests.yml` as a third job.

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

1. Morning brief as landing view? (§6)
2. Webhook channel preference: Telegram or Discord first?
3. ~~CF Access secrets for 5.1~~ — moot: CF identity dropped (2026-06-11);
   auth = built-in app login before public release.
4. When V1.2 exit criteria are met: bump version, regenerate
   `SYSTEM_DESIGN.pdf` + `TECHNICAL_INVENTORY.xlsx` (commands in
   `ONBOARDING.md` §8), and update this document or retire it.
