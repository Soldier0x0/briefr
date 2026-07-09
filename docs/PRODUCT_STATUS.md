# BRIEFR product status

**Last updated:** 2026-07-09  
**Purpose:** Single page for “what’s true in production today.” When README or beta docs disagree, this wins.

---

## Release snapshot

| Area | Status |
|------|--------|
| **Release** | **v1.5.0** — V1.5 product phases 1–3 + 5 shipped (#373–#376); Phase 4 STIX excluded |
| **Performance (Track I)** | **Complete** (#378–#382): feed scroll isolation (`FeedVisibleRange`), CVE detail enrichments parallel off pool, bulk CVE upsert (`executemany`), `/api/cves` KEV JOIN + 45s count cache + Postgres `pg_trgm` indexes (Alembic `012`). |
| **Security tail** | CGNAT SSRF block (`100.64.0.0/10`) + refresh rejects past `sessions.expires_at` (#381). JWT role revalidation and LLM summary auth remain open. |
| **Database** | **PostgreSQL required** (`DATABASE_URL`, `BRIEFR_REQUIRE_POSTGRES=1`). SQLite removed from production path. **Intel snapshot:** `scripts/export_intel_snapshot.py` exports allowlisted tables per `docs/DATA_SNAPSHOT.md` with versioned manifest (`format_version: 1`); `scripts/verify_intel_snapshot.py` and `scripts/import_intel_snapshot.py` validate/import bundles; upgrade steps in `docs/OPERATIONS.md`. Postgres CI runs export→restore smoke (`test_intel_snapshot_export.py`). **Backup round-trip:** Postgres CI runs `test_backup_roundtrip_postgres.py` (`run_backup` → wipe → `restore_backup`, row-count assert on `cves` / `kev_deadlines`). |
| **Auth** | Built-in app login + sessions (first-run `/api/auth/setup`); admin/refresh routes require the **admin role** (Sprint A0). Legacy `BRIEFR_ADMIN_API_KEY` removed. Wallboard token is **header-only** (`X-BRIEFR-Wallboard-Token`; `?token=` removed, Sprint A7). Optional Cloudflare Zero Trust at **edge** (operator policy, not in app code). |
| **Rate limits** | Token buckets on IOC, refresh, admin, auth; set `RATE_LIMIT_ENABLED=1` in production. |
| **API queue** | Outbound API serialization (#221) for NVD/OTX/etc.; admin/health expose per-source task-level queue status (#341). |
| **UI (Track E)** | Track E complete (E-PR1–10): Intel/GreyNoise drawer; BRIEF states audit; header/timezone; tooltips; stat deltas; IOC auto-detect; **⌘K command palette**. |
| **CVE Overview (analyst workflow)** | Overview headline is **Operational Priority (P1–P4)** + **Threat Score (0–100)** + **Environment Relevance tier** (ADR-002). Threat is asset-independent with KEV floor; UNKNOWN environment is provisional (no phantom 17.5 pts). v1.1b blend retained in API as `legacy_risk_v11b` only. Tab order: OP hero → environment relevance → threat signals → remediation → exploitation. Investigation Score route removed. |
| **Data utilization (C2)** | Drawer **CAPEC** chips (CIRCL), **CISA SSVC** section (Vulnrichment), **KEV ransomware** badge on feed cards + drawer; OTX targeted countries; OSV drawer table; EPSS percentile. |
| **Detection (D1)** | Generated Sigma rules use **CWE class templates** when no ATT&CK technique is mapped (`briefr_basis`: `attack_technique` \| `cwe` \| `generic`). |
| **Detection (D2)** | **`DetectionContext`** scaffold: `feed_cache` keys `detection_ctx:{cve_id}` hold `{cwe_ids, product, class, artifacts, model, provider, generated_at}`; read on detection/forge paths; written by scheduler job (`DETECTION_CONTEXT_SYNC_ENABLED=0` default). Generated rules add `briefr_class` when context is present. |
| **Detection (D4)** | Deterministic **Nuclei YAML parser** enriches `detection_ctx` artifacts on `exploit_sync` (Nuclei-touched CVEs); generated Sigma rules merge artifact keywords/paths (`briefr_artifacts`, `briefr_note`). `DETECTION_CONTEXT_NUCLEI_ENABLED=1` default. LLM extract (K4) remains optional overlay. |
| **Detection (D3)** | **Unified class router** (`class_router.py`): `_resolve_detection_class(cve)` drives Sigma `briefr_class`, SIEM query selection, and `log_patterns` so all three agree on class when no ATT&CK technique is mapped. |
| **Detection (D5)** | Detect tab frames outputs as **class-aware hunt starters**; generated Sigma shown as supplement even when community rules exist; `briefr_basis` / experimental status tooltips. |
| **LLM router (K1–K3)** | Scheduler-side multi-provider router: Groq (`openai/gpt-oss-20b` / `120b` for PDF) → Gemini Flash-Lite → Cerebras → OpenRouter `:free`; product extraction + PDF executive summary wired through router; Anthropic removed from chain; `feed_cache` provenance `{provider, model}`. |
| **LLM detection context (K4)** | Scheduler job `detection_context_llm` extracts `{paths, params, keywords, method}` artifacts from CVE/exploit text into `detection_ctx:{cve_id}` via LLM router (`DETECTION_CONTEXT_LLM_ENABLED=0` default). Vision (Cerebras `gemma-4-31b`) deferred until image inputs exist. |
| **Cache retention (C3)** | Daily `cache_retention_cleanup` job sweeps stale `ioc_cache` / `feed_cache` rows and ages out `epss_history`, `cve_change_history`, and OTX mirror tables; read-path TTLs unchanged. Admin `change_history_old` purge fixed (`detected_at`). |
| **Admin** | Security, backups, job status, config (V1.4 operator features largely shipped). **First-hour onboarding:** Admin → System health shows a live checklist (CVE ingest, stack, backups, feeds, production posture) until dismissed or complete. **Support pack:** Admin → System health “Export support pack” and `GET /api/admin/diagnostics/support-pack` export redacted health + ring-buffer logs (no secrets); `deploy/briefr-doctor.sh` runs health/import checks and optional pack download. **Operator settings:** writable admin config keys persist to `app_settings` in DB (survives `.env` refresh on deploy); process env wins, then DB, then `.env`. Admin Save still mirrors to `.env` for compatibility. **Config editor:** per-field Save on Admin → API keys & config — immediate save for API keys/toggles; rows tagged `restart` use Save & restart (Wave 1). **Notifications:** shared toast tray pauses auto-dismiss on hover/focus; errors/warnings persist until dismissed; success/info auto-dismiss in 8s; max 4 visible; copy-ref shows “Copied” feedback; backend restart shows a top banner (health poll) instead of a transient restart toast (Wave 1 PR 2 / H1a). **User stack:** Feed stack input persists via `GET/PUT /api/me/stack` (Wave 2 PR 3–4); legacy `briefr_stack` localStorage migrates on login. KEV-on-stack webhooks and wallboard use `BRIEFR_STACK_TERMS` when set, otherwise the newest saved user stack. **Display prefs:** Admin → Display settings and header timezone persist via `GET/PATCH /api/me/preferences` (Wave 2 PR 5); legacy `briefr_*` display/timezone localStorage migrates on login. **My Stack inventory:** session-only by default; optional “Remember on server” toggle (Wave 2 PR 6) stores asset profile JSON on `user_preferences` and restores on sign-in. Production posture self-check (Sprint A6): startup logs one warning per unsafe flag (`RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, tokenless wallboard) when `BRIEFR_ENV=production`; the Security panel shows the same warnings. |
| **Snooze** | Removed from UI (#137). **Watchlist monitor alerts** ship via `watchlist_alert` webhooks when pinned CVEs enter KEV or show EPSS/PoC changes (scheduler job `watchlist_monitor_alerts`). |
| **Theme** | Dark only. |
| **Docker compose** | Postgres compose exists; full V2.0 platform compose not shipped. |

---

## Auth layers (two independent)

![Auth layers — pending](assets/placeholder-diagram.svg)

> **Asset:** [`assets/auth-layers.png`](assets/auth-layers.png) — see [IMAGE_BRIEFS §8](IMAGE_BRIEFS.md#8-auth-layers)

| Layer | What | Notes |
|-------|------|-------|
| **Edge (optional)** | Cloudflare Tunnel + Zero Trust email OTP | Protects public hostname; not embedded in FastAPI |
| **Application** | Username/password + server sessions; admin routes check the `admin` role | Portable self-host; CF JWT middleware **dropped** (#93); legacy admin key **removed** (Sprint A0 — it failed open when unset) |

---

## Deployment reference

![Production architecture — pending](assets/placeholder-diagram.svg)

> **Asset:** [`assets/production-architecture.png`](assets/production-architecture.png) — see [IMAGE_BRIEFS §1](IMAGE_BRIEFS.md#1-production-architecture)

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
| Postgres, auth, rate limits, API queue | Full `docker-compose.yml` (V2.0) |
| Correlation v2 core (campaigns, typed IOC edges, hub suppression, dismiss, priority, lifecycle, feed badge, drawer chip) + **Phase 4–5** cluster list + admin correlation status (#364) | Correlation phase-4 tail (Forge/PDF/webhook enrichments, watchlist sort in feed) — see sprint Phase B |
| Admin ops, webhooks, wallboard | STIX export (excluded from current loop) |
| **Forge threat scenarios (V1.5 Phase 1)** | STIX export (excluded from current loop) |
| **Rule proof bench (V1.5 Phase 2)** — `POST /api/proof/run`; Forge hunt pack panel paste-and-run against saved Sigma | Wave 4 / open-core (parked) |
| **KEV detection backlog (V1.5 Phase 3)** — `GET /api/detection-backlog`; KEV sync + weekly reconcile; Forge **Backlog** tab; optional `kev_backlog` webhook | Correlation phase-4 tail (Phase B) |
| **IOC watchlist depth (V1.5 Phase 5)** — `ioc_watchlist` + ThreatFox mirror + retro-match job; IOC tab watchlist UI; optional `ioc_watchlist_hit` webhook; VulnCheck exploited tier (`is_vulncheck_exploited`) | Extended watchlist alert signals (campaign join, severity) |
| **V1.5 ship housekeeping** — version 1.5.0, PDF/xlsx regen scripts verified, security audit (no critical/high) | STIX export (excluded) |
| **Track I performance** — I4 scroll, I6 detail pool, I7 list query, I10 bulk upsert (#378–#382) | Wave 4 / open-core (parked) |
| Embeddings optional (fastembed) | Extended watchlist alert signals (campaign join, severity) |
| Chart.js admin dashboard partial | Logrotate deploy artifacts (V1.4 theme) |

Details: [`ROADMAP.md`](ROADMAP.md). Historical beta specs → `docs/archive/` (phase 2).

---

## Documentation rollout

| Phase | Status |
|-------|--------|
| Doc structure + image briefs | In progress |
| Living API / architecture docs | Current — `API_REFERENCE.md`, `SYSTEM_DESIGN.md`, `TECHNICAL_INVENTORY.md`, `docs/PRODUCT_STATUS.md` synced through Track I (#383) |
| Graphify knowledge graph | Current — `graphify-out/graph.json` + `GRAPH_REPORT.md` (5923 nodes; HTML viz omitted when >5000 nodes) |
| Archive beta root `.md` files | Pending |
| MkDocs site | Pending |
| Stale README / API_REFERENCE auth claims | Pending |

Plan: [`DOCUMENTATION_PLAN.md`](DOCUMENTATION_PLAN.md).
