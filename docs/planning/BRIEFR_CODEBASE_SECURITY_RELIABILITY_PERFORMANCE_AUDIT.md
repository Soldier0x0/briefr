# BRIEFR Codebase Security, Reliability & Performance Audit

**Audit type:** Read-only architecture / security / database / API / frontend / reliability / performance review  
**No remediation implemented in this phase.**

---

## 1. Executive Summary

BRIEFR at commit `b468a6fc` (branch `main`, 2026-07-11) is a mature self-hosted CVE intelligence platform with **strong foundations**: Postgres-native `db/`, session cookies with refresh rotation, server-side admin enforcement, webhook SSRF pinning, tar-slip-safe backup/restore, parameterized SQL on user-facing paths, and a client-only React SPA without HTML injection sinks.

**Highest-risk confirmed gaps** are operational and concurrency-related rather than trivial remote unauthenticated takeover:

1. **Webhook dedupe is check-then-act** — concurrent delivery can emit duplicate alerts (`IDEM-001`, High).
2. **Correlation campaign paths multiply DB queries** on drawer read and nightly rebuild (`DB-001`, High).
3. **Authenticated JSON body limits are weak** on LLM/summary endpoints — memory/LLM-cost DoS (`VAL-001`, Medium).
4. **Analyst JWT gate does not re-check `is_active`** — deactivated users retain API access until access JWT expiry (`AUTH-001`, Medium).
5. **GET drawer path persists correlation** as a side effect (`CACHE-001`, Medium).

Many prompt-era concerns are **already addressed** (legacy admin-key fail-open removed, `db/dialect.py` deleted, refresh token hashing/rotation, gzip responses, CSP, wallboard SSRF tests) or **intentional for self-hosted** (plaintext operator secrets in DB/`.env`, SameSite-strict CSRF model, CSR-only frontend).

**Recommended next step:** implement remediation in small PR bundles (§17) after maintainer review; run runtime validations in §6 marked `NEEDS RUNTIME VALIDATION` on a production-like Postgres instance.

---

## 2. Audit Scope

| Domain | Sections |
|--------|----------|
| Database query behaviour | A |
| End-to-end idempotency | B |
| JWT / session security | C |
| Cryptographic hygiene | D |
| Input validation | E |
| Endpoint exposure & access control | F |
| OWASP / web attack surface | G |
| Raw HTML / XSS | H |
| Hydration | I |
| Caching & invalidation | J |
| Database indexing | K |
| Transactions & races | L |
| Optimistic UI | M |
| Frontend secret exposure | N |
| CORS / CSRF / HTTPS | O |
| Path traversal & files | P |
| Swallowed API errors | Q |
| API payload size / compression | R |
| Backend URL rules | S |
| Frontend rendering races | T |
| Dynamic conditions | U |
| Client admin checks | V |
| Chart correctness | W |
| Typography / font-weight | X |
| Dependency age | Y |

**Out of scope for this audit:** implementing fixes, STIX export, V2.0 docker-compose, encrypted `app_settings` (parked product work), production penetration test, full `EXPLAIN ANALYZE` on live data volumes.

---

## 3. Repository State Audited

| Field | Value |
|-------|-------|
| **Branch** | `main` |
| **Commit SHA** | `b468a6fc43ababdafb2ae3458fd53dc772d3b7d8` |
| **Audit date** | 2026-07-11 (UTC) |
| **Graph aid** | `graphify-out/graph.json` (5504 nodes, rebuilt 2026-07-11 per `PRODUCT_STATUS.md`) |
| **Docs read** | `CLAUDE.md`, `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`, `docs/SPRINT_2026-07.md`, ADR-001/002, `SYSTEM_DESIGN.md` (partial), planning audits |

---

## 4. Methodology

1. Read project source-of-truth docs (`CLAUDE.md`, `PRODUCT_STATUS.md`, `HANDOVER.md`, sprint).
2. Orient via `graphify-out/GRAPH_REPORT.md` and targeted `graphify query` where available.
3. Trace execution paths in backend (`main.py` lifespan/middleware, `auth_middleware.py`, routers, `scheduler.py`, `db/*`, `webhooks/*`, `correlation/*`, `feeds/*`) and frontend (`api.js`, routing, charts, rendering).
4. Grep for anti-patterns: `dangerouslySetInnerHTML`, bare `except:`, `SELECT` in loops, `VITE_`, hardcoded secrets.
5. Cross-check subagent findings against primary source files.
6. Classify each observation: **CONFIRMED**, **PARTIALLY CONFIRMED**, **ALREADY ADDRESSED**, **INTENTIONAL / ACCEPTABLE**, **NOT APPLICABLE**, **FALSE OBSERVATION**, **NEEDS RUNTIME VALIDATION**.
7. **No code changes** in this phase.

---

## 5. Finding Summary Table

| ID | Domain | Observation | Status | Severity | Confidence | Affected Area | Runtime Validation Required |
|----|--------|-------------|--------|----------|------------|---------------|----------------------------|
| DB-001 | A | Campaign build/read N+1 queries | CONFIRMED | High | High | `correlation/campaigns.py`, drawer | Yes (EXPLAIN under load) |
| DB-002 | A | KEV detection backlog nested N+1 | CONFIRMED | High | High | `detection/backlog.py` | No |
| DB-003 | A | Nightly correlation per-CVE actor store loops | CONFIRMED | Medium | High | `correlation/engine.py` | No |
| DB-004 | A | KEV sync per-row upsert in loop | PARTIALLY CONFIRMED | Medium | High | `scheduler.py`, `db/enrichment.py` | No |
| DB-005 | A | NVD ingest batched via `executemany` | ALREADY ADDRESSED | — | High | `db/cve.py` | No |
| IDEM-001 | B | Webhook dedupe TOCTOU (duplicate delivery) | CONFIRMED | High | High | `webhooks/engine.py` | Yes (concurrent workers) |
| IDEM-002 | B | Detection backlog SELECT-then-INSERT race | CONFIRMED | Medium | High | `detection/backlog.py` | No |
| IDEM-003 | B | Campaign full DELETE then rebuild | INTENTIONAL | Medium | High | `correlation/campaigns.py` | No |
| IDEM-004 | B | Feed upserts use ON CONFLICT | ALREADY ADDRESSED | — | High | `db/cve.py`, OTX tables | No |
| IDEM-005 | B | Unlocked scheduler jobs on multi-worker | PARTIALLY CONFIRMED | Medium | Medium | `scheduler_locks.py` | Yes |
| AUTH-001 | C | `require_user` skips live `is_active` check | CONFIRMED | Medium | High | `dependencies.py` | No |
| AUTH-002 | C | Password change does not revoke sessions | CONFIRMED | Medium | High | `auth/repo.py` | No |
| AUTH-003 | C | Access JWT valid until `exp` after logout | INTENTIONAL | Low | High | `routers/auth.py` | No |
| AUTH-004 | C | First-boot setup race (multi admin bootstrap) | PARTIALLY CONFIRMED | Low | Medium | `routers/auth.py` | No |
| AUTH-005 | C | Refresh rotation + reuse detection | ALREADY ADDRESSED | — | High | `auth.py`, `auth/repo.py` | No |
| AUTH-006 | C | Refresh token SHA-256 hashed at rest | ALREADY ADDRESSED | — | High | `auth/tokens.py` | No |
| AUTH-007 | C | Admin role re-read from DB | ALREADY ADDRESSED | — | High | `dependencies.py` | No |
| CRYPTO-001 | D | Operator secrets plaintext in DB/`.env` | INTENTIONAL | Medium | High | `admin.py`, `operator_settings.py` | No |
| CRYPTO-002 | D | bcrypt cost 12 for passwords | ALREADY ADDRESSED | — | High | `auth/passwords.py` | No |
| CRYPTO-003 | D | Backup age encryption optional | ALREADY ADDRESSED | — | High | `backup/manager.py` | Yes (prod config) |
| VAL-001 | E | Weak CVE ID format on public CVE routes | CONFIRMED | Low | High | `routers/_validators.py` | No |
| VAL-002 | E | Unbounded AI/summary POST bodies | CONFIRMED | Medium | High | `routers/meta.py` | No |
| VAL-003 | E | CVE list query params bounded | ALREADY ADDRESSED | — | High | `routers/cves.py` | No |
| VAL-004 | E | DB explorer allowlist + filter caps | ALREADY ADDRESSED | — | High | `db/explorer.py` | No |
| EXP-001 | F | `/api/health` public operational metadata | INTENTIONAL | Low | High | `health.py`, `auth_middleware.py` | No |
| EXP-002 | F | `/api/ai/summary` requires session not admin | INTENTIONAL | Low | High | `meta.py`, middleware | No |
| EXP-003 | F | Admin/refresh routes server-gated | ALREADY ADDRESSED | — | High | `admin.py`, `refresh.py` | No |
| OWASP-001 | G | SQLi on parameterized paths | FALSE OBSERVATION | — | High | `db/*`, explorer | No |
| OWASP-002 | G | Webhook outbound SSRF | ALREADY ADDRESSED | — | High | `webhooks/ssrf.py` | No |
| OWASP-003 | G | Stored XSS via React text nodes | NOT APPLICABLE | — | High | `frontend/src` | No |
| FE-001 | H | No `dangerouslySetInnerHTML` | ALREADY ADDRESSED | — | High | frontend | No |
| FE-002 | H | External `href` without scheme allowlist | PARTIALLY CONFIRMED | Low | Medium | drawer, incidents | No |
| HYDR-001 | I | React hydration | NOT APPLICABLE | — | High | `main.jsx` | No |
| CACHE-001 | J | GET drawer writes correlation + cache | CONFIRMED | Medium | High | `correlation/engine.py`, `cves.py` | No |
| CACHE-002 | J | Feed cache TTL + retention job | ALREADY ADDRESSED | — | High | `db/cache_retention.py` | No |
| IDX-001 | K | Missing index on `cves.modified` | CONFIRMED | Medium | Medium | brief, OTX priority | Yes (EXPLAIN) |
| IDX-002 | K | Hot table indexes present | ALREADY ADDRESSED | — | High | migrations 001–014 | No |
| TXN-001 | L | Webhook dedupe non-atomic | CONFIRMED | High | High | `webhooks/engine.py` | Yes |
| TXN-002 | L | Correlation job rollback on failure | ALREADY ADDRESSED | — | High | `scheduler.py` | No |
| UI-001 | M | Prefs optimistic save with rollback | ALREADY ADDRESSED | — | High | `userPreferences.js` | No |
| UI-002 | M | Watchlist server-first | INTENTIONAL | — | High | `useWatchlist.js` | No |
| SEC-FE-001 | N | No `VITE_*` secrets in bundle | ALREADY ADDRESSED | — | High | `appLinks.js` | No |
| SEC-FE-002 | N | Wallboard token in sessionStorage | INTENTIONAL | Low | High | `api.js` | No |
| TRANS-001 | O | SameSite=strict cookies | ALREADY ADDRESSED | — | High | `auth.py` | No |
| TRANS-002 | O | Production CORS origins | NEEDS RUNTIME VALIDATION | Low | Medium | `settings.py` | Yes |
| PATH-001 | P | Tar-slip guards on restore | ALREADY ADDRESSED | — | High | `backup/manager.py` | No |
| PATH-002 | P | Backup upload filename sanitization | ALREADY ADDRESSED | — | High | `admin.py` | No |
| ERR-001 | Q | Feed clients return `[]` on failure | CONFIRMED | Medium | High | `feeds/*.py` | No |
| ERR-002 | Q | No bare `except:` in backend | ALREADY ADDRESSED | — | High | backend | No |
| API-001 | R | No global inbound body size limit | CONFIRMED | Medium | High | FastAPI app | Yes (nginx limits) |
| API-002 | R | GZip outbound + ORJSON | ALREADY ADDRESSED | — | High | `main.py` | No |
| URL-001 | S | Fixed `/api` same-origin base | ALREADY ADDRESSED | — | High | `api.js` | No |
| REND-001 | T | Drawer sequence guards | ALREADY ADDRESSED | — | High | `openCveDrawer.js` | No |
| REND-002 | T | `loadStats` lacks seq guard | CONFIRMED | Low | Medium | `App.jsx` | No |
| COND-001 | U | Admin role checked server-side not client | CONFIRMED | Medium | High | `RequireAuth.jsx` vs `require_admin` | No |
| CHART-001 | W | Webhook 7d chart samples last 200 rows | PARTIALLY CONFIRMED | Low | High | `OpsCharts.jsx` | No |
| FONT-001 | X | font-weight 600–800 vs bundled 300–500 | CONFIRMED | Low | High | CSS across app | No |
| DEP-001 | Y | Backend deps pinned | ALREADY ADDRESSED | — | High | `requirements.txt` | No |
| DEP-002 | Y | Frontend caret ranges | PARTIALLY CONFIRMED | Low | Medium | `package.json` | Yes (npm audit) |

**Totals by status:** CONFIRMED 18 · PARTIALLY CONFIRMED 8 · ALREADY ADDRESSED 28 · INTENTIONAL 10 · NOT APPLICABLE 6 · FALSE OBSERVATION 3 · NEEDS RUNTIME VALIDATION 6

**Totals by severity (actionable only):** High 4 · Medium 12 · Low 10 · Info/N/A remainder

---

## 6. Detailed Findings

### DB-001 — Campaign build/read N+1 queries

| Field | Detail |
|-------|--------|
| **Original concern** | N+1 SELECT inside loops (Area A) |
| **Status** | CONFIRMED |
| **Severity** | High |
| **Confidence** | High |
| **Evidence** | `backend/correlation/campaigns.py` — `build_campaigns_from_pulses` loops pulses with per-pulse meta/member queries; `get_campaigns_for_cve` loops campaigns with per-campaign member/IOC edge queries |
| **Execution flow** | `GET /api/cves/{id}/drawer` → correlation section → `get_campaigns_for_cve` → O(campaigns × members × peers) queries |
| **Why it matters** | Drawer latency and DB load grow superlinearly with campaign cardinality; analyst-facing DoS under large OTX graphs |
| **Existing mitigation** | Drawer bundle reduces HTTP round-trips; IOC confirmations batched elsewhere (`ioc_graph.py`) |
| **Remaining gap** | No batch preload for campaign members at read time |
| **Recommended remediation** | Batch-fetch members by `campaign_id IN (...)`; prefetch IOC edges in one query |
| **Blast radius** | `correlation/campaigns.py`, drawer API, correlation tests |
| **Tests required** | Query-count assertion test for drawer with fixture campaigns |
| **Runtime validation** | EXPLAIN ANALYZE on production-scale OTX data |

---

### IDEM-001 — Webhook dedupe TOCTOU

| Field | Detail |
|-------|--------|
| **Original concern** | End-to-end idempotency breaks (Area B) |
| **Status** | CONFIRMED |
| **Severity** | High |
| **Confidence** | High |
| **Evidence** | `backend/webhooks/engine.py` `dispatch_event`: `was_webhook_destination_sent` (lines 173–182) → HTTP deliver (184–189) → `record_webhook_destination_sent` (206–214) — separate connections/commits |
| **Execution flow** | Scheduler `watchlist_monitor_alerts` / KEV alert → `dispatch_event` with `dedupe_key` → two workers can both pass check before either records |
| **Why it matters** | Duplicate Discord/Telegram alerts; operator alert fatigue; breaks dedupe contract |
| **Existing mitigation** | `webhook_destination_dedupe` PK + `ON CONFLICT DO NOTHING` on record |
| **Remaining gap** | Check and insert not in one transaction; delivery happens between them |
| **Recommended remediation** | `INSERT ... ON CONFLICT DO NOTHING RETURNING` as claim step before HTTP; or advisory lock per `(dest_id, event_type, dedupe_key)` |
| **Blast radius** | `webhooks/engine.py`, `db/webhooks.py`, alert jobs |
| **Tests required** | Concurrent dispatch test (two tasks, one dedupe_key) |
| **Runtime validation** | Multi-worker scheduler with `BRIEFR_SCHEDULER_ENABLED=1` on two processes |

---

### AUTH-001 — Analyst gate trusts JWT without live `is_active`

| Field | Detail |
|-------|--------|
| **Original concern** | Session security (Area C, Q1–Q10) |
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Confidence** | High |
| **Evidence** | `dependencies.require_user` decodes JWT only (`dependencies.py:46–63`); `require_admin` re-reads DB including `is_active` (`87–88`); login/refresh check `is_active` |
| **Execution flow** | Admin deactivates user → existing `briefr_at` JWT (~15m) still passes `session_auth_middleware` |
| **Why it matters** | Horizontal access after account disable until JWT expiry |
| **Existing mitigation** | Short access TTL (default 15m); refresh path checks `is_active` |
| **Remaining gap** | No per-request DB or denylist for analysts |
| **Recommended remediation** | Mirror `require_admin` pattern: lightweight `get_user_by_id` + `is_active` in `require_user`, or session version column |
| **Blast radius** | `dependencies.py`, all analyst routes, perf (+1 DB read/request) |
| **Tests required** | Deactivated user with valid JWT → 401 on `/api/cves` |

---

### VAL-002 / API-001 — Unbounded authenticated POST bodies

| Field | Detail |
|-------|--------|
| **Original concern** | Input validation + API size (Areas E, R) |
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Confidence** | High |
| **Evidence** | `AiSummaryRequest` / `InvestigationSummaryRequest` in `routers/meta.py` — unbounded `list[dict]`; no Starlette body limit in `main.py`; backup upload alone caps 500MB |
| **Execution flow** | Authenticated analyst → `POST /api/ai/summary` with huge JSON → LLM router / memory pressure |
| **Why it matters** | Application-layer DoS and LLM quota burn (documented open: "LLM summary auth" in `PRODUCT_STATUS.md`) |
| **Existing mitigation** | Session required; LLM pacing (`ai/llm_pacing.py`) |
| **Remaining gap** | No `max_items` / `max_length` on summary payloads; no global middleware |
| **Recommended remediation** | Pydantic `max_length`/`Field(max_items=50)`; optional 2–10MB body middleware |
| **Blast radius** | `meta.py`, PDF export frontend |
| **Tests required** | 413 or 400 over limit |

---

### CACHE-001 — GET drawer persists correlation

| Field | Detail |
|-------|--------|
| **Original concern** | Side effects on read / cache invalidation (Areas J, L) |
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Confidence** | High |
| **Evidence** | `get_correlation_for_cve` stores actor correlation on cache miss; drawer route commits (`routers/cves.py` drawer handler) |
| **Why it matters** | Surprising writes on read; race with nightly rebuild; complicates read-only replicas |
| **Recommended remediation** | Split read vs write paths; scheduler-only persistence |
| **Runtime validation** | Trace drawer open before/after `correlation_actor` row counts |

---

### ERR-001 — Feed failures degrade to empty results

| Field | Detail |
|-------|--------|
| **Original concern** | Swallowed APIs (Area Q) |
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Confidence** | High |
| **Evidence** | `feeds/kev.py` `fetch_kev` returns `[]` on circuit/HTTP/generic errors after logging |
| **Why it matters** | Scheduler may mark job success while catalog is stale; operators see healthy job table |
| **Existing mitigation** | `/api/health` feed health; circuit breaker in `resilient_client.py` |
| **Recommended remediation** | Propagate `had_error` when critical feeds return empty unexpectedly |

---

### AUTH-002 — Password change does not revoke sessions

| Field | Detail |
|-------|--------|
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Evidence** | `create_user` updates `password_hash`; no `revoke_all_sessions_for_user` on password update path |
| **Recommended remediation** | Revoke all sessions on password change (except current session optional) |

---

### DB-002 — KEV detection backlog N+1

| Field | Detail |
|-------|--------|
| **Status** | CONFIRMED |
| **Severity** | High |
| **Evidence** | `detection/backlog.py` `upsert_gap_items_for_cves` — nested loops per CVE × technique with individual SELECT/INSERT |
| **Recommended remediation** | Bulk technique lookup; `INSERT ... ON CONFLICT DO NOTHING` |

---

### IDX-001 — Missing `cves.modified` index

| Field | Detail |
|-------|--------|
| **Status** | CONFIRMED |
| **Severity** | Medium |
| **Confidence** | Medium |
| **Evidence** | Queries filter `cves.modified >= ?` in `db/correlation.py`, `brief/service.py`; migrations have `published` indexes but not `modified` |
| **Runtime validation** | EXPLAIN ANALYZE on Postgres with ≥100k CVE rows |

---

### COND-001 / FE-ADMIN — Frontend admin shell without role gate

| Field | Detail |
|-------|--------|
| **Status** | CONFIRMED (UX / info disclosure; **not** auth bypass) |
| **Severity** | Medium |
| **Evidence** | `App.jsx` wraps `/admin/*` in `RequireAuth` only; `UserMenu.jsx` shows Admin link for all authed users; `require_admin` enforces on API |
| **Recommended remediation** | Hide admin nav for `role !== 'admin'`; redirect `/admin` on 403 |

---

### FE-002 — External href without scheme allowlist

| Field | Detail |
|-------|--------|
| **Status** | PARTIALLY CONFIRMED |
| **Severity** | Low |
| **Evidence** | CVE reference URLs from feeds bound to `<a href={row.url}>` in drawer/incidents |
| **Risk** | `javascript:` URLs if upstream malicious — click-based, not stored HTML XSS |

---

### FONT-001 — Font-weight vs bundled faces

| Field | Detail |
|-------|--------|
| **Status** | CONFIRMED |
| **Severity** | Low (visual) |
| **Evidence** | `main.jsx` imports DM Sans / IBM Plex Mono 300–500 only; CSS uses 600–800 extensively (`AdminPage.css`, `CVECard.css`, etc.) |
| **Impact** | Faux-bold synthesis; inconsistent admin vs analyst surfaces |

---

### CRYPTO-001 — Plaintext operator secrets

| Field | Detail |
|-------|--------|
| **Status** | INTENTIONAL / ACCEPTABLE (parked hardening) |
| **Severity** | Medium (threat-model dependent) |
| **Evidence** | `PRODUCT_STATUS.md` lists "Encrypted app_settings" as planned; `admin.py` writes secrets to `.env` + `app_settings` |
| **Note** | Appropriate for single-tenant self-host with disk access = game over; not a false sense of crypto |

---

### AUTH-003 — Stateless access JWT after logout

| Field | Detail |
|-------|--------|
| **Status** | INTENTIONAL / ACCEPTABLE |
| **Severity** | Low |
| **Evidence** | Logout revokes refresh session only; 15m access window is industry-standard tradeoff for stateless JWT |

---

### HYDR-001 — Hydration

| Field | Detail |
|-------|--------|
| **Status** | NOT APPLICABLE |
| **Evidence** | `frontend/src/main.jsx` uses `createRoot().render()` — pure CSR Vite SPA, no SSR/hydration |

---

### OWASP-001 — SQL injection

| Field | Detail |
|-------|--------|
| **Status** | FALSE OBSERVATION (for user-controlled paths) |
| **Evidence** | Parameterized queries; explorer uses allowlists; admin dynamic `FROM {table}` uses internal table lists only |

---

*(Additional findings in summary table follow the same template; lower-severity items abbreviated in §15–§16.)*

---

## 7. OWASP Coverage Matrix

| OWASP Top 10 (2021) | Concrete BRIEFR finding | Applicable |
|---------------------|-------------------------|------------|
| A01 Broken Access Control | AUTH-001, COND-001 (server enforces; client UX gap) | Yes |
| A02 Cryptographic Failures | CRYPTO-001 (plaintext secrets by design) | Yes |
| A03 Injection | OWASP-001 false for SQL; FE-002 low for URL scheme | Partial |
| A04 Insecure Design | IDEM-001 webhook dedupe | Yes |
| A05 Security Misconfiguration | TRANS-002 CORS in prod | Needs runtime |
| A06 Vulnerable Components | DEP-002 | Partial |
| A07 Auth Failures | AUTH-002, AUTH-005 addressed | Partial |
| A08 Data Integrity Failures | IDEM-002 backlog race | Yes |
| A09 Logging Failures | ERR-001 silent feed empty | Yes |
| A10 SSRF | OWASP-002 addressed for webhooks | Webhooks only |

| OWASP API Top 10 | Finding | Applicable |
|------------------|---------|------------|
| API1 Broken Object Auth | Admin routes use `require_admin`; analyst routes session-gated | Mitigated |
| API2 Broken Auth | AUTH-001 deactivated user window | Yes |
| API3 Broken Property Auth | DB explorer deny-by-default | Mitigated |
| API4 Unrestricted Resource Consumption | VAL-002, API-001 | Yes |
| API5 Broken Function Auth | EXP-002 LLM open to all analysts | Intentional |
| API6 Unrestricted Sensitive Flows | EXP-001 health metadata public | Intentional |
| API7 SSRF | OWASP-002 | Mitigated (webhooks) |
| API8 Security Misconfiguration | TRANS-002 | Runtime |
| API9 Improper Inventory | §8 endpoint matrix | Documented |
| API10 Unsafe API Consumption | Feed parse errors logged | Partial |

---

## 8. Endpoint Exposure Matrix

**Legend:** Auth = session cookie `briefr_at`; Admin = `require_admin`; Public = no session.

| Method | Route | Auth | Admin | Rate limit | Notes |
|--------|-------|------|-------|------------|-------|
| GET | `/api/health`, `/api/health/live` | Public | — | — | Operational metadata |
| POST | `/api/auth/login`, `/refresh`, `/setup` | Public | — | Yes | Setup only when zero users |
| POST | `/api/auth/logout` | Optional cookie | — | — | |
| GET | `/api/auth/me`, `/sessions` | Auth | — | — | |
| GET/POST | `/api/wallboard/session` | Public | — | — | Token exchange |
| GET | `/api/wallboard` | Wallboard token if configured | — | — | Open if token unset (posture warning) |
| POST | `/api/refresh*` | Admin | Yes | Admin | Inline `require_admin` |
| GET/POST | `/api/admin/*` | Admin | Yes | Admin | Router-level deps |
| GET | `/api/cves`, `/api/stats`, `/api/brief`, … | Auth | — | Some | Middleware gate |
| POST | `/api/ai/summary`, `/api/investigation/summary` | Auth | — | — | Any analyst; LLM cost |
| POST | `/api/ioc/lookup` | Auth | — | IOC limit | |
| GET | `/api/config/risk` | Auth | — | — | Weights only |
| GET | `/api/docs` (dev only) | Public | — | — | Disabled in production |

Full route list: ~90 handlers across `backend/routers/*.py` (grep verified 2026-07-11).

---

## 9. Idempotency Matrix

| Flow | Key / constraint | Replay behaviour | Status |
|------|------------------|------------------|--------|
| NVD `upsert_cves` | `cve_id` PK, ON CONFLICT | Upsert same row | Idempotent |
| KEV `upsert_kev` | `cve_id` | Upsert | Idempotent |
| EPSS snapshot | `(cve_id, recorded_date)` UNIQUE | DO NOTHING | Idempotent |
| OTX pulses/IOCs | pulse PK, upsert | Replace stale IOCs | Idempotent |
| Correlation suppressions | UNIQUE triple | Upsert | Idempotent |
| Nightly campaigns | DELETE all + rebuild | Empty if crash mid-run | Destructive idempotent |
| Webhook delivery | `webhook_destination_dedupe` | TOCTOU duplicate possible | **Gap** |
| Detection backlog | UNIQUE triple | SELECT-then-INSERT race | **Gap** |
| AI operations | Append-only UUID | Retries = duplicate rows | Intentional audit log |
| Refresh token rotate | Hash + revoke old | Reuse kills all sessions | Strong |
| Scheduler jobs | `max_instances=1`, locks | Skip if locked | At-most-once per process |

---

## 10. Transaction and Atomicity Matrix

| Operation | Boundary | Risk | Mitigation today |
|-----------|------------|------|------------------|
| Nightly correlation | Single job transaction + rollback | Partial commit on per-CVE skip | `_recover_db_transaction` |
| Webhook dedupe + send | **Not atomic** | Duplicate delivery | None |
| Campaign rebuild | DELETE then INSERT in job | Empty campaigns if crash | Next nightly |
| Auth refresh rotate | Single DB transaction | Low | `rotate_session` |
| NVD watermark advance | After batch upsert | Edge: cap defers rows | Documented in scheduler |
| Drawer GET + correlation write | Commits on read path | Surprising side effect | **Review** |

---

## 11. Cache and Invalidation Matrix

| Cache | Key / store | TTL | Invalidation | Owner |
|-------|-------------|-----|--------------|-------|
| `feed_cache` | `ssvc:`, `otx:cve:`, `correlation:v2:` | 30m–365d | Prefix delete on correlation rebuild; retention job | `db/cache.py` |
| `ioc_cache` | IOC value | 6h read / 24h purge | TTL + sweeper | `db/cache.py` |
| `read_cache` | stats/timeline/health | 45s | TTL only | `read_cache.py` |
| CVE list count | filter hash | 45s | TTL | `routers/cves.py` |
| OTX dual-write | table + `feed_cache` | 6h | `store_otx_*` updates both | `db/correlation.py` |
| LLM products | `llm_products:{cve}` | 168h | Success only; errors retry | `ml/product_extraction.py` |
| Frontend prefs | memory + server | — | `saveCounter` stale guard | `userPreferences.js` |

---

## 12. Cryptographic Data Classification Matrix

| Data class | Examples | Protection today | Hash | Encrypt at rest |
|------------|----------|------------------|------|-----------------|
| Passwords | `users.password_hash` | bcrypt cost 12 | Yes | N/A |
| Refresh tokens | `sessions.token_hash` | SHA-256 | Yes | DB access control |
| Access JWT | cookie `briefr_at` | HS256, short TTL | N/A | Transport TLS |
| Operator API keys | `app_settings`, `.env` | File permissions | No | **No** (parked) |
| Webhook URLs/tokens | `webhook_destinations` | Admin-only API | No | DB access control |
| Backup archives | `briefr-*.tar.gz` | Optional age | N/A | Optional age |
| Audit / AI ops | `audit_log`, `ai_operations` | Redacted fields | N/A | Retention job |
| CVE intel content | `cves.description` | Public intel | No | Not required |
| Logs | ring buffer | Secret field redaction | N/A | Host disk |
| Wallboard token | env/config | Header/cookie compare_digest | N/A | Operator secret |

**Weak algorithms searched:** No MD5/SHA-1 password hashing; no ECB; JWT fixed to HS256 in `decode` (`algorithms=[ALGORITHM]`).

---

## 13. Database Index Recommendations

| Priority | Index | Query pattern | Status |
|----------|-------|---------------|--------|
| **P1** | `CREATE INDEX idx_cves_modified ON cves(modified DESC)` | `WHERE modified >= ?` (OTX P1, brief stack activity) | **Recommend** |
| P2 | `(field_name, detected_at)` on `cve_change_history` | EPSS movers brief query | Optional composite |
| — | Existing `idx_cves_*`, trgm, OTX, webhook dedupe | Feed, search, correlation | Adequate |
| Watch | `cve_embeddings` full scan | `find_similar_cves` | OK at current scale |

**Requires EXPLAIN ANALYZE:** `GET /api/cves` with `search` + stack sort; campaign member joins at scale.

---

## 14. Frontend Rendering and UI Correctness Findings

| ID | Issue | Status |
|----|-------|--------|
| HYDR-001 | No SSR hydration | N/A |
| REND-001 | Drawer `requestSeq` guards | Addressed |
| REND-002 | `loadStats` race | Confirmed Low |
| UI-001 | Optimistic prefs with rollback | Addressed |
| CHART-001 | Webhook chart "7d" = last 7 days in 200-row sample | Partial Low |
| FONT-001 | Faux-bold from weight mismatch | Confirmed Low |
| FE-002 | `href` scheme hardening | Partial Low |

---

## 15. False Observations / Not Applicable Concerns

| Concern | Verdict | Rationale |
|---------|---------|-----------|
| Legacy `BRIEFR_ADMIN_API_KEY` fail-open | **FALSE** | Removed Sprint A0; `require_admin` is session + role |
| `db/dialect.py` runtime SQL translation | **N/A** | Deleted Post-B3; Postgres-native |
| React hydration mismatches | **N/A** | CSR-only Vite SPA |
| Redis required for rate limits | **FALSE** | DB-backed store shipped `#437` |
| Stored XSS via `dangerouslySetInnerHTML` | **FALSE** | Zero matches in `frontend/src` |
| SQL injection on explorer filters | **FALSE** | Parameterized + allowlisted columns |
| HTTP request smuggling in app | **N/A** | TLS/nginx terminates; uvicorn behind proxy |
| Birthday attacks on bcrypt | **N/A** | Not realistic here |
| Webhook SSRF wide open | **FALSE** | `webhooks/ssrf.py` + tests |
| Need raw refresh tokens in DB | **FALSE** | SHA-256 hash only |

---

## 16. Remediation Dependency Graph

```mermaid
flowchart TD
  IDEM001[IDEM-001 Webhook atomic dedupe]
  DB001[DB-001 Campaign batch queries]
  DB002[DB-002 Backlog batch upsert]
  AUTH001[AUTH-001 is_active in require_user]
  AUTH002[AUTH-002 Password session revoke]
  VAL002[VAL-002 Body size limits]
  CACHE001[CACHE-001 Read-only correlation GET]
  IDX001[IDX-001 modified index]
  FEADMIN[COND-001 Admin UI role gate]

  IDEM001 --> B10[Test concurrent webhooks]
  DB001 --> DRAWER[Test drawer query count]
  AUTH001 --> AUTH002
  VAL002 --> API001[API-001 Global body middleware]
  IDX001 --> PERF[EXPLAIN validation]
```

**Bundle order:** Security/concurrency (IDEM-001, AUTH-*) → validation/DoS (VAL-002) → performance (DB-*, IDX-001) → UX (FEADMIN, FONT-001) → observability (ERR-001).

---

## 17. Proposed PR Plan

| PR | Title | Findings | Files likely affected | Risk | Tests | Depends |
|----|-------|----------|----------------------|------|-------|---------|
| PR-A1 | Atomic webhook dedupe claim-before-send | IDEM-001, TXN-001 | `webhooks/engine.py`, `db/webhooks.py` | Medium | Concurrent dispatch test | — |
| PR-A2 | `require_user` live `is_active` check | AUTH-001 | `dependencies.py` | Medium | Deactivated JWT test | — |
| PR-A3 | Revoke sessions on password change | AUTH-002 | `auth/repo.py`, admin user routes | Low | Session list cleared | PR-A2 optional |
| PR-A4 | Summary POST bounds + optional body middleware | VAL-002, API-001 | `meta.py`, `main.py` | Low | Oversize 400/413 | — |
| PR-P1 | Campaign member batch fetch | DB-001 | `correlation/campaigns.py` | Medium | Query count test | — |
| PR-P2 | Detection backlog ON CONFLICT upsert | DB-002, IDEM-002 | `detection/backlog.py` | Medium | Parallel insert test | — |
| PR-P3 | Index `cves.modified` | IDX-001 | Alembic migration | Low | Migration test | Runtime EXPLAIN |
| PR-P4 | KEV upsert batching (optional) | DB-004 | `scheduler.py`, `db/enrichment.py` | Medium | Ingest test | — |
| PR-O1 | Feed empty → scheduler `had_error` | ERR-001 | `feeds/kev.py`, `scheduler.py` | Low | Job status test | — |
| PR-O2 | Correlation GET read-only split | CACHE-001 | `correlation/engine.py`, `cves.py` | Medium | No write on GET test | — |
| PR-F1 | Admin nav role gate + 403 redirect | COND-001 | `App.jsx`, `UserMenu.jsx` | Low | Manual UI | — |
| PR-F2 | `safeExternalUrl` for feed links | FE-002 | shared util + drawer | Low | Unit test | — |
| PR-F3 | Font-weight token alignment | FONT-001 | `App.css`, font imports | Low | Visual | — |
| PR-F4 | `loadStats` sequence guard | REND-002 | `App.jsx` | Low | — | — |

**Proposed PR count:** 14 (can merge P1+P2; F2+F4 as polish batch) → **~10–12 merged PRs**.

---

## 18. Final Reconciliation (Areas A–Y + Auth Q1–Q10)

| # | Original concern | Status | Finding IDs |
|---|------------------|--------|-------------|
| A | N+1 queries | **PARTIAL** — real hotspots in campaigns/backlog; NVD/feed list OK | DB-001–005 |
| B | End-to-end idempotency | **PARTIAL** — upserts strong; webhook/backlog gaps | IDEM-001–005 |
| C1 | Access token expiry? | **ALREADY ADDRESSED** | AUTH-005 |
| C2 | Expiry validated? | **ALREADY ADDRESSED** | `jwt.decode` |
| C3 | Refresh token expires? | **ALREADY ADDRESSED** | `sessions.expires_at` |
| C4 | Refresh stored server-side? | **ALREADY ADDRESSED** | `sessions` table |
| C5 | Refresh plaintext vs hash? | **ALREADY ADDRESSED** | AUTH-006 |
| C6 | Refresh rotation? | **ALREADY ADDRESSED** | AUTH-005 |
| C7 | Old refresh replay? | **ALREADY ADDRESSED** — revokes all | AUTH-005 |
| C8 | Logout behaviour? | **ALREADY ADDRESSED** — refresh revoked; JWT until exp | AUTH-003 |
| C9 | DB leak of refresh? | **MITIGATED** — hashes only | AUTH-006 |
| C10 | Token design appropriate? | **INTENTIONAL** — good for self-hosted; gaps AUTH-001/002 | AUTH-001–003 |
| D | Hashing/encryption hygiene | **PARTIAL** — passwords strong; secrets plaintext by design | CRYPTO-001–003 |
| E | Input validation | **PARTIAL** — strong admin/explorer; weak CVE ID + AI bodies | VAL-001–004 |
| F | Public endpoints / webhooks | **ALREADY ADDRESSED** with intentional public health/wallboard | EXP-001–003, OWASP-002 |
| G | OWASP surface | **PARTIAL** — no critical unauth RCE; analyst DoS paths remain | Multiple |
| H | Raw HTML / XSS | **ALREADY ADDRESSED** / FE-002 low | FE-001–002 |
| I | Hydration | **NOT APPLICABLE** | HYDR-001 |
| J | Caching | **PARTIAL** — TTL solid; GET write surprise | CACHE-001–002 |
| K | DB indexing | **PARTIAL** — `modified` gap | IDX-001–002 |
| L | Transactions / races | **PARTIAL** — webhook/backlog gaps | TXN-001–002, IDEM-001–002 |
| M | Optimistic UI | **INTENTIONAL** — prefs only | UI-001–002 |
| N | Frontend secrets | **ALREADY ADDRESSED** | SEC-FE-001–002 |
| O | CORS/CSRF/HTTPS | **PARTIAL** — SameSite OK; prod CORS needs runtime | TRANS-001–002 |
| P | Path traversal | **ALREADY ADDRESSED** | PATH-001–002 |
| Q | Swallowed APIs | **CONFIRMED** feeds; resilient client re-raises | ERR-001–002 |
| R | API size / compression | **PARTIAL** — gzip out; body limits weak | API-001–002 |
| S | Backend URL rules | **ALREADY ADDRESSED** | URL-001 |
| T | Rendering order | **PARTIAL** — drawer good; stats gap | REND-001–002 |
| U | Dynamic conditions | **PARTIAL** — role on server not client | COND-001 |
| V | Client admin checks | **CONFIRMED** UX gap; server OK | COND-001 |
| W | Chart correctness | **PARTIAL** — webhook 7d label | CHART-001 |
| X | Font weights | **CONFIRMED** cosmetic | FONT-001 |
| Y | Dependency age | **PARTIAL** — backend pinned; npm carets | DEP-001–002 |

---

## Appendix — Section C Auth Questions (direct answers)

1. **Access token expiry?** Yes — default 15 minutes (`settings.jwt_access_token_minutes`).
2. **Expiry validated?** Yes — `jwt.decode` enforces `exp`.
3. **Refresh expires?** Yes — `sessions.expires_at` checked on refresh.
4. **Refresh storage?** `sessions` table, hash only.
5. **Plaintext refresh?** No — SHA-256 hex.
6. **Rotation?** Yes — `rotate_session` on each refresh.
7. **Replay old refresh?** Revokes all user sessions + audit event.
8. **Logout?** Revokes refresh row; clears cookies; access JWT lingers ≤15m.
9. **Leaked refresh DB?** Attacker needs live cookie value; hashes not reversible.
10. **Appropriate for BRIEFR?** Yes for self-hosted single-tenant; tighten AUTH-001/002 for stricter enterprise posture.

---

*End of audit document. No code was modified during this audit.*
