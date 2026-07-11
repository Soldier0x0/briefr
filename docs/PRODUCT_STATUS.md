# BRIEFR product status

**Last updated:** 2026-07-11  
**Purpose:** Single page for “what’s true in production today.” When README or beta docs disagree, this wins.

---

## Release snapshot

| Area | Status |
|------|--------|
| **Release** | **v1.5.0** — V1.5 product phases 1–3 + 5 shipped (#373–#376); Phase 4 STIX excluded |
| **License** | **AGPL-3.0-or-later** (`LICENSE`, `CONTRIBUTING.md`). Active source trees carry SPDX headers; public GitHub flip still gated on beta feedback (Track F). |
| **Performance (Track I)** | **Phase 1–2 complete** (#378–#382): feed scroll isolation, parallel enrichments, bulk upsert, `/api/cves` KEV JOIN + count cache + `pg_trgm`. **Phase 3a–b shipped** (#436–#437): ORJSON default responses, keyset feed pagination (`pagination=keyset`), drawer bundle (`GET /api/cves/{id}/drawer`), shared rate-limit store (`BRIEFR_RATE_LIMIT_STORE=db`). **Phase 3 tail shipped** (#443–#444): I15 feed windowing (`content-visibility: auto`), I16 server-side stack relevance sort, `BRIEFR_SCHEDULER_ENABLED` for API-only workers. |
| **Security tail** | CGNAT SSRF block (`100.64.0.0/10`) + refresh rejects past `sessions.expires_at` (#381). **JWT role revalidation** shipped (#392). LLM summary auth remains open. |
| **Database** | **PostgreSQL required** (`DATABASE_URL`, `BRIEFR_REQUIRE_POSTGRES=1`). SQLite removed from production path. **Intel snapshot:** `scripts/export_intel_snapshot.py` exports allowlisted tables per `docs/DATA_SNAPSHOT.md` with versioned manifest (`format_version: 1`); `scripts/verify_intel_snapshot.py` and `scripts/import_intel_snapshot.py` validate/import bundles; upgrade steps in `docs/OPERATIONS.md`. Postgres CI runs export→restore smoke (`test_intel_snapshot_export.py`). **Backup round-trip:** Postgres CI runs `test_backup_roundtrip_postgres.py` (`run_backup` → wipe → `restore_backup`, row-count assert on `cves` / `kev_deadlines`). |
| **Auth** | Built-in app login + sessions (first-run `/api/auth/setup`); **analyst `/api/*` routes require a valid session** (`briefr_at` cookie; #441 — matches React `RequireAuth`). Admin/refresh routes require the **admin role** (Sprint A0). Legacy `BRIEFR_ADMIN_API_KEY` removed. Wallboard token is **header-only** (`X-BRIEFR-Wallboard-Token`; `?token=` removed, Sprint A7). Optional Cloudflare Zero Trust at **edge** (operator policy, not in app code). |
| **Rate limits** | Token buckets on IOC, refresh, admin, auth; set `RATE_LIMIT_ENABLED=1` in production. **Multi-worker:** optional shared store via `BRIEFR_RATE_LIMIT_STORE=db` persists buckets in `sync_state` (#437); set `BRIEFR_SCHEDULER_ENABLED=0` on API-only workers (#444). Scheduler runs on one owner only — see `OPERATIONS.md`. |
| **API queue** | Outbound API serialization (#221) for NVD/OTX/etc.; `/api/health` exposes per-source task-level queue status (#341). Feed sync paths pass `operation` + safe `context_id` so rows show analyst copy (not generic “Outbound API request”). Header/admin indicator groups by provider, caps panel height with scroll, and summary counts distinguish **waiting** vs **queued**. |
| **DB integrity** | SQLite uses `PRAGMA integrity_check` / `foreign_key_check`. PostgreSQL uses real `pg_catalog` probes (invalid indexes, unvalidated constraints, FK orphan scan) — no silent always-ok stub. Admin Overview “Check DB integrity” reports `method` + `backend`. |
| **UI (Track E)** | Track E complete (E-PR1–10): Intel/GreyNoise drawer; BRIEF states audit; header/timezone; tooltips; stat deltas; IOC auto-detect; **⌘K command palette**. |
| **CVE Overview (analyst workflow)** | Overview headline is **Operational Priority (P1–P4)** + **Threat Score (0–100)** + **Environment Relevance tier** (ADR-002). Threat is asset-independent with KEV floor; UNKNOWN environment is provisional (no phantom 17.5 pts). v1.1b blend retained in API as `legacy_risk_v11b` only. Tab order: OP hero → environment relevance → threat signals → remediation → exploitation. Investigation Score route removed. |
| **Data utilization (C2)** | Drawer **CAPEC** chips (CIRCL), **CISA SSVC** section (Vulnrichment), **KEV ransomware** badge on feed cards + drawer; OTX targeted countries; OSV drawer table; EPSS percentile. |
| **Detection (D1)** | Generated Sigma rules use **CWE class templates** when no ATT&CK technique is mapped (`briefr_basis`: `attack_technique` \| `cwe` \| `generic`). |
| **Detection (D2)** | **`DetectionContext`** scaffold: `feed_cache` keys `detection_ctx:{cve_id}` hold `{cwe_ids, product, class, artifacts, model, provider, generated_at}`; read on detection/forge paths; written by scheduler job (`DETECTION_CONTEXT_SYNC_ENABLED=0` default). Generated rules add `briefr_class` when context is present. |
| **Detection (D4)** | Deterministic **Nuclei YAML parser** enriches `detection_ctx` artifacts on `exploit_sync` (Nuclei-touched CVEs); generated Sigma rules merge artifact keywords/paths (`briefr_artifacts`, `briefr_note`). `DETECTION_CONTEXT_NUCLEI_ENABLED=1` default. LLM extract (K4) remains optional overlay. |
| **Detection (D3)** | **Unified class router** (`class_router.py`): `_resolve_detection_class(cve)` drives Sigma `briefr_class`, SIEM query selection, and `log_patterns` so all three agree on class when no ATT&CK technique is mapped. |
| **Detection (D5)** | Detect tab frames outputs as **class-aware hunt starters**; generated Sigma shown as supplement even when community rules exist; `briefr_basis` / experimental status tooltips. |
| **LLM router (K1–K3)** | Scheduler-side multi-provider router: Groq (`openai/gpt-oss-20b` / `120b` for PDF) → Gemini Flash-Lite → Cerebras → OpenRouter `:free`; product extraction + PDF executive summary wired through router; Anthropic removed from chain; `feed_cache` provenance `{provider, model}`. **Outbound payload guard:** `ai/llm_payload.py` skips provider HTTP when user/assistant messages or task source text (CVE description, exploit text, investigation items) are empty — no quota burn on blank requests; enforced in router + OpenAI/Gemini clients. **AI operations (AI-1, #416):** each `chat_completion_task` attempt records a redacted row in `ai_operations` (no prompt text); model failover chains centralized in `ai/model_catalog.py`; disable recording with `AI_OPERATIONS_RECORD=0`; admin `GET /api/admin/ai/operations/models` exposes the catalog. **Token usage (#420):** when a provider reports usage (OpenAI-compatible `usage`, Gemini `usageMetadata`), `input_tokens`/`output_tokens`/`total_tokens` are stored; Usage and Activity tabs show rollups and per-row counts; `estimated_cost_usd` stays NULL (no price SSOT). **AI-3 quota (#432):** advisory quota snapshots from provider rate-limit response headers (`ai/quota.py`); surfaced on AI Operations provider rows and `quota_warnings` in overview. **K5 pacing (#433):** shared `ai/llm_pacing.py` headroom (~85% default) below RPM/TPM ceilings for all LLM providers; PDF user-prompt trim. **AI Operations admin page (AI-2, #417; #419):** Operator → **AI operations** — read-only Overview / Providers / Models / Usage / Activity tabs backed by `/api/admin/ai/operations/*`; Activity tab filters by task class and provider. |
| **LLM detection context (K4)** | Scheduler job `detection_context_llm` extracts `{paths, params, keywords, method}` artifacts from CVE/exploit text into `detection_ctx:{cve_id}` via LLM router (`DETECTION_CONTEXT_LLM_ENABLED=0` default). Vision (Cerebras `gemma-4-31b`) deferred until image inputs exist. |
| **Cache retention (C3)** | Daily `cache_retention_cleanup` job sweeps stale `ioc_cache` / `feed_cache` rows and ages out `epss_history`, `cve_change_history`, and OTX mirror tables; read-path TTLs unchanged. Admin `change_history_old` purge fixed (`detected_at`). Operator append-only tables now age out in the same job (**#418**): `ai_operations` (30d) and `webhook_delivery_log` (30d) as high-frequency logs, `audit_log` (365d) as a compliance-conservative window; `api_usage` is excluded (a bounded `(service, date_utc)` aggregate). |
| **Admin** | Security, backups, job status, config (V1.4 operator features largely shipped). **Operator admin bundle (#428–#429):** `AdminDataGrid` on Feed health + Storage; collapsible config sections + sticky apply bar (O-1/O-2); compact purge cards; Storage adds per-table sizes, host disk I/O, growth estimate; Download DB removed from UI (legacy `GET /storage/export` remains for SQLite dev); audit/config secret masking (`redact.py`). **API key health (#435):** scheduler `api_key_health_check` job + `GET /api/admin/api-keys/health` and manual `POST .../run`. **Notification center (#439):** admin StatusBar panel from `GET /api/admin/notifications` (recent audit events, scheduler job errors, unhealthy API keys). **Read-only DB explorer (PR13):** Admin → **Storage** includes a table browser backed by `GET /api/admin/db-explorer/tables` and `GET /api/admin/db-explorer/tables/{table}/rows` — dropdown-driven allowlisted tables only (deny-by-default; `users`, `sessions`, `webhook_destinations`, `ioc_cache`, `sync_state`, etc. return 404); optional single-column equality filters; `cves` requires a `cve_id` filter; Tier-2 masking on `audit_log` and `webhook_delivery_log`; paginated (max 100 rows); browse audited without row bodies; 30/min rate limit. **Webhook destinations API (PR12b):** `POST/DELETE /api/admin/webhooks/destinations` for database-backed multi-destination CRUD (20/kind cap); masked `config` on GET; PATCH `config` for db sources only; event dedupe is per `(destination_id, event_type, dedupe_key)`; admin webhook test works on disabled destinations. **Webhooks admin page (PR12c):** primary destination management UI — list/create/delete db destinations, env/db source badges, event subscription editor, per-destination test; API keys page webhooks section is legacy bootstrap only. **Config apply lifecycle:** `GET /api/admin/config/schema` exposes `apply_strategy` per key (`immediate`, `scheduler_reschedule`, `restart`); Admin → API keys & config shows human `display_label`, unit suffixes on intervals, and badges for reschedule vs restart; scheduler interval saves reschedule APScheduler triggers without a full restart; `ALLOWED_ORIGINS` is honestly marked restart-required (CORS middleware binds at startup). **Structured logging:** every scheduled job runs inside `job_log_context` — ring-buffer entries carry `job_id` + `run_id`; failures include `error_type` + `exc_info`; Admin → Application logs filters by job/run; Scheduler job table links “View in application log” to the last run. **Ops charts:** System health ingest durations use horizontal bars with explicit `s`/`min`/`h` units; backup sizes render as a sparkline with `fmtBytes` Y-axis; empty chart wells collapse compactly. **Analyst charts:** KEV due-date histogram replaced with `GET /api/stats/top-vendors` horizontal vendor bar chart; unified `daysUntilDue` UTC math in `kevDeadline.js`. **Admin density:** compact `admin-empty` rows; destructive `DangerZone` panels moved below operational tables with subdued styling; Security page documents optional `WALLBOARD_TOKEN` gate. **Responsive analyst surfaces:** IOC lookup uses fixed single-line input; feed filter bar and detail drawer tighten at ≤960px. **First-hour onboarding:** Admin → System health shows a live checklist (CVE ingest, stack, backups, feeds, production posture) until dismissed or complete. **Support pack:** Admin → System health “Export support pack” and `GET /api/admin/diagnostics/support-pack` export redacted health + ring-buffer logs (no secrets); `deploy/briefr-doctor.sh` runs health/import checks and optional pack download. **Operator settings:** writable admin config keys persist to `app_settings` in DB (survives `.env` refresh on deploy); process env wins, then DB, then `.env`. Admin Save still mirrors to `.env` for compatibility. **Config editor:** per-field Save on Admin → API keys & config — immediate save for API keys/toggles; rows tagged `restart` use Save & restart (Wave 1). **Notifications:** shared toast tray pauses auto-dismiss on hover/focus; errors/warnings persist until dismissed; success/info auto-dismiss in 8s; max 4 visible; copy-ref shows “Copied” feedback; backend restart shows a top banner (health poll) instead of a transient restart toast (Wave 1 PR 2 / H1a). **User stack:** Feed stack input persists via `GET/PUT /api/me/stack` (Wave 2 PR 3–4); legacy `briefr_stack` localStorage migrates on login. KEV-on-stack webhooks and wallboard use `BRIEFR_STACK_TERMS` when set, otherwise the newest saved user stack. **Display prefs:** Admin → Display settings and header timezone persist via `GET/PATCH /api/me/preferences` (Wave 2 PR 5); legacy `briefr_*` display/timezone localStorage migrates on login. **My Stack inventory:** session-only by default; optional “Remember on server” toggle (Wave 2 PR 6) stores asset profile JSON on `user_preferences` and restores on sign-in. Production posture self-check (Sprint A6): startup logs one warning per unsafe flag (`RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, tokenless wallboard) when `BRIEFR_ENV=production`; the Security panel shows the same warnings. |
| **Embeddings** | Nightly `embeddings_backfill` scheduler job when `EMBEDDINGS_ENABLED=1`. **Auto-on-ingest (#438):** when `EMBEDDINGS_AUTO_ON_INGEST=1`, NVD incremental sync embeds newly updated CVE IDs in-process (bounded batch). Powers semantic related-CVE lookup when vectors exist. |
| **Wallboard** | **v2 shipped (#430):** session-cookie token storage, responsive tile grid, auto-rotation, stack-aware KEV tile, mono terminal styling. Token via `X-BRIEFR-Wallboard-Token` or admin config `WALLBOARD_TOKEN`. |
| **Snooze** | Removed from UI (#137). **Watchlist monitor alerts** ship via `watchlist_alert` webhooks when pinned CVEs enter KEV or show EPSS/PoC changes (scheduler job `watchlist_monitor_alerts`). |
| **Theme** | Dark only. |
| **Docker compose** | Postgres compose exists; full V2.0 platform compose not shipped. |

---

## Auth layers (two independent)

![Auth layers](assets/auth-layers.svg)

> **Asset:** [`assets/auth-layers.svg`](assets/auth-layers.svg) — see [IMAGE_BRIEFS §8](IMAGE_BRIEFS.md#8-auth-layers)

| Layer | What | Notes |
|-------|------|-------|
| **Edge (optional)** | Cloudflare Tunnel + Zero Trust email OTP | Protects public hostname; not embedded in FastAPI |
| **Application** | Username/password + server sessions; admin routes check the `admin` role | Portable self-host; CF JWT middleware **dropped** (#93); legacy admin key **removed** (Sprint A0 — it failed open when unset) |

---

## Deployment reference

![Production architecture](assets/production-architecture.svg)

> **Asset:** [`assets/production-architecture.svg`](assets/production-architecture.svg) — see [IMAGE_BRIEFS §1](IMAGE_BRIEFS.md#1-production-architecture)

| Item | Value |
|------|--------|
| Code | `/opt/briefr` |
| DB | PostgreSQL 16 (often Docker at `/opt/infra/postgres`) |
| Backups | `/var/lib/briefr/backups` (age-encrypted) |
| Backend | `briefr-backend.service` → uvicorn :8000 |
| Frontend | `frontend/dist` via nginx |

---

## Shipped vs planned (high level)

| Shipped | Planned / open |
|---------|----------------|
| Postgres, auth, rate limits, API queue, shared rate-limit store (#437) | Full `docker-compose.yml` (V2.0) |
| Correlation v2 core + phase-4–5 tail (#364, #389, #434 `cve_id` filter) | STIX export (excluded from current loop) |
| Admin ops, webhooks (#413–#415), wallboard v2 (#430), AI ops (#416–#420), 12-PR operator bundle (#428–#439), 4-PR tail (#441–#444) | **G0** LEARNING_PATH / ONBOARDING refresh |
| **Forge** threat scenarios, proof bench, KEV backlog, IOC watchlist (V1.5 #373–#376) | LLM summary auth |
| Track I performance Phases 1–3 (#378–#382, #436–#437, #443–#444) | `IMAGE_BRIEFS` tail; MkDocs |
| Track L Wave 4: monitor alerts, onboarding, doctor, operator settings (#366–#372) | Encrypted `app_settings` / secrets SSOT |
| K5 LLM pacing (#433), AI-3 quota snapshots (#432), embeddings auto-on-ingest (#438) | RSS↔CVE linking |
| Chart.js admin ops dashboard, logrotate deploy artifacts, F2 AGPL (#423) | |
| Architecture diagrams (phase A); session auth middleware (#441); M-5 backup owner + N-4 kiosk docs (#442) | |

Details: [`ROADMAP.md`](ROADMAP.md). Historical beta specs → `docs/archive/` (phase 2).

---

## Documentation rollout

| Phase | Status |
|-------|--------|
| Doc structure + image briefs | Phase A diagrams shipped (`production-architecture`, `auth-layers`, `correlation-pipeline` SVGs) |
| Living API / architecture docs | Current — synced through **#444** (4-PR tail bundle) |
| Graphify knowledge graph | **Current** — `graphify-out/graph.json` + `GRAPH_REPORT.md` rebuilt **2026-07-11**, synced through **#444** (`5504` nodes, `11760` edges, `327` communities). A git `post-commit`/`post-checkout` hook now auto-rebuilds the graph from changed code files after every commit/checkout; doc/image changes still need a manual `/graphify --update` (semantic extraction, not AST) since the hook only re-parses code |
| Archive beta root `.md` files | Pending (do not edit `docs/archive/beta/*`) |
| MkDocs site | Pending |
| Stale README / API_REFERENCE auth claims | **Done** — session-cookie auth + refresh route errors updated |

Plan: [`DOCUMENTATION_PLAN.md`](DOCUMENTATION_PLAN.md).
