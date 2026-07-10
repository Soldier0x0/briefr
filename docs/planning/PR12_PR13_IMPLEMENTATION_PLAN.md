# PR12 & PR13 — Implementation plan (planning only)

**Status:** Plan of record — amended per maintainer review (PR #409 comment, 2026-07-10) —
**no implementation in this document**  
**Date:** 2026-07-10  
**Source:** UX audit (`docs/planning/BRIEFR_VISUAL_OPERATIONAL_UX_AUDIT.md`) Issues 18 & 22  
**Deferred from:** Approved 11-PR UX correction pass (PR1–PR11 + PR8 merged 2026-07-10)

This file is the single planning artifact for Cloud Code / maintainer validation before any
implementation PRs are opened.

---

## Executive summary

| PR | Name | User value | Risk | Scope | DB migration |
|----|------|------------|------|-------|--------------|
| **PR12** (3 PRs: 12a/12b/12c) | Multi-webhook endpoints | Daily ops — multiple alert channels | HIGH | LARGE | Yes — Alembic **013** |
| **PR13** | ~~Read-only DB explorer~~ → **Storage sample-rows MVP** | Occasional debugging without `psql` | LOW (MVP) | SMALL (MVP) | No |

**Recommended order:** PR12 series first (existing webhook engine + table); PR13 MVP second.

**Do not parallelize** with shared-surface work (DetailDrawer, etc.). Admin-only but large blast
radius.

### Sequencing vs sprint queue (maintainer review §3, corrected 2026-07-10)

Verified against `main` at head: **D4 and Post-B are complete** (`db/dialect.py` deleted in
Post-B Phase 3 — `db/` is Postgres-native now), the wave-model queue in
`docs/SPRINT_2026-07.md` is closed through Wave 3 with Wave 4 parked, and the UX audit pass
PR1–PR11 is merged. Nothing blocks this work; **PR12a–c is the next implementation queue**,
in this order: PR-A cleanup (#411) → PR12a → 12b → 12c → AI-1/AI-2 (#410 plan) → PR13-MVP.

New CRUD queries are written **Postgres-native** per the post-Post-B `db/` convention — the
SQLite-dialect + `db/dialect.py` rule in `CLAUDE.md` is stale (flagged for its own doc fix).
Migration numbering is serialized with the AI ops plan (#410): the repo has migrations
001–012, so PR12 takes **013**, AI ops takes **014**.

---

## Current state (code-confirmed)

### Webhooks (PR12 baseline)

- `webhook_destinations` table exists (Alembic `004_sqlite_schema_parity.py`).
- Fixed env-seeded IDs: `discord`, `telegram`, `generic` (`backend/webhooks/destinations.py`).
- Dispatch engine + dedupe + `webhook_delivery_log` ship (`backend/webhooks/engine.py`).
- SSRF protections ship (`backend/webhooks/ssrf.py`): HTTPS only, block private/reserved IPs,
  DNS pin, no redirects, forbidden outbound headers.
- Admin API today:
  - `GET /api/admin/webhooks/destinations` — list (no secrets)
  - `PATCH /api/admin/webhooks/destinations/{id}` — enable, event_types, label only
  - `POST /api/admin/config/webhook-test` — test send
- **Gap:** no `POST`/`DELETE` for new destinations; secrets still primarily in `.env`; UI
  (`WebhooksPage.jsx`) reads config env keys, not destinations API as primary UX.
- `webhooks_enabled()` and `configured_channels()` are **synchronous** and read **env only**
  (`load_env_destinations()`). DB-backed destinations require an explicit refactor before
  DB-only endpoints work (see **Gemini review §1** below).

### DB visibility (PR13 baseline)

- `GET /api/admin/storage` returns **row counts** per table (`_STORAGE_TABLES` in
  `routers/admin.py`) — no row browser.
- `docs/DATA_SNAPSHOT.md` already classifies **INTEL vs OPERATOR** tables — use as allowlist
  seed.
- Auth: `require_admin` sufficient for MVP (audit Q13). No super-admin tier today.

---

# PR12 — Multi-webhook endpoints

## Goal

Let admins **create, name, enable, test, and delete multiple webhook destinations per provider
type**, with honest delivery logging and **no regression** to SSRF protections or legacy env-based
setups.

## Phased delivery — three PRs (maintainer review §4)

### PR 12a — Async refactor (no behavior change)

- `async def webhooks_enabled()` / `configured_channels()` → `await load_destinations()`
  (Option 1 from the async refactor note below, confirmed).
- Call-site sweep: `webhooks/engine.py`, `webhooks/alerts.py`, `webhooks/sender.py`, tests.
- Zero behavior change, independently reviewable. Lands first.

### PR 12b — Migration + CRUD API + per-destination dedupe

- Alembic migration **013** (see DB migration section)
- `POST /api/admin/webhooks/destinations` — create destination
- `DELETE /api/admin/webhooks/destinations/{id}` — delete (typed confirm via destructive-actions
  pattern or inline confirm word)
- Extend `PATCH` to update **config** (URL / token / chat_id) for **DB-only** destinations
- Multiple rows per `kind`: `discord`, `telegram`, `generic`
- Generated IDs: `{kind}-{short-uuid}` or validated operator slug `^[a-z0-9-]{3,64}$`
- Legacy env destinations (`discord` / `telegram` / `generic`) keep working unchanged
- **Per-destination dedupe** — record sent-state per `(destination_id, event_type, dedupe_key)`.
  Verified current behavior (`engine.py`: `was_webhook_alert_sent` guard ~L159, `record_webhook_alert`
  ~L219): the dedupe check runs once per event **before** the destination loop, and the key is
  recorded when **any** destination succeeds. Consequences under multi-destination: a destination that fails while another
  succeeds is permanently skipped for that key (no retry), and a destination added after an
  event fired never receives that keyed event. Multi-destination delivery **is** the feature —
  this ships in 12b, not a follow-up.
- Audit every create / update / delete / test
- Admin **test send** may target a **disabled** destination (verify credentials before enable) —
  `send_test_message` today returns `destination disabled` when `enabled=false` (see Gemini §2)
- Masking on GET (no secrets returned after save)
- Tests: CRUD, SSRF rejection on write, multi-delivery, per-destination dedupe, env+DB merge,
  no secret leakage in API, test-while-disabled for admin only

### PR 12c — WebhooksPage rewrite

- Rebuild **WebhooksPage** around `GET /webhooks/destinations` (not raw ApiKeys config keys)
- Legacy notice on ApiKeysPage webhook fields
- `env` vs `db` source badge per destination

**Out of scope (all of PR12)**

- Removing or deprecating `.env` webhook vars — env destinations stay **forever** as bootstrap
  (decision, see Open questions). The previous "Phase B env deprecation" is dropped: churn with
  no operator value.
- Encrypting `config_json` at rest
- New provider kinds beyond existing `generic` HTTPS JSON
- Per-destination retry policy changes

### Possible follow-up (only if operators ask)

- Destination health from `webhook_delivery_log` (last success / last error)

## DB migration (what it means for PR12)

The **table already exists**. A new **Alembic forward-only** revision (**`013_…py`** — the repo
has migrations 001–012; 014 is reserved for the AI ops plan in #410) is still likely because:

| Change | Reason |
|--------|--------|
| Generated IDs (not only `discord`/`telegram`/`generic`) | Multiple rows per kind |
| Optional new columns | `description`, `sort_order`, `created_by_user_id`, `deleted_at` |
| Constraints | `CHECK (kind IN (...))`, optional unique `(kind, label)` |
| Data backfill | Preserve existing rows + `webhook_delivery_log.destination_id` consistency |
| Per-destination dedupe | New sent-state keyed by `(destination_id, event_type, dedupe_key)` — new table or column on the existing dedupe store |

**Minimal path:** no new columns — only allow multiple rows + generated IDs; migration may still
add indexes/constraints + backfill script.

**Rules:** never edit applied migrations; new query paths follow the Postgres-native `db/`
convention (Post-B), with test fixtures per Post-B part 1 (#303).

## Architecture decisions (resolve before coding)

| # | Decision | Recommendation |
|---|----------|----------------|
| 1 | Source of truth | DB for user-created; env for legacy bootstrap — **permanently** (env deprecation dropped) |
| 2 | ID format | `{kind}-{short-uuid}` or validated slug; reserve `discord`/`telegram`/`generic` for env |
| 3 | Secrets in API | Never return full URL/token after save — mask like `GET /api/admin/config` |
| 4 | Config UI location | **Webhooks page** primary; ApiKeysPage legacy notice only (12c) |
| 5 | Delete env-backed row | Disable only — env re-syncs on boot |
| 6 | Max destinations | **20 per kind** (decided) |

## Security threats & mitigations (PR12)

| Threat | Impact | Mitigation |
|--------|--------|------------|
| SSRF via malicious URL | Critical | Reuse `webhooks/ssrf.py` on **create and update** of URL fields |
| Secret exfiltration via GET | High | Mask `config_json`; never return full webhook URL or Telegram token |
| Secrets in `audit_log` | High | Audit `destination_id` + action only; no URL/token in detail |
| Compromised admin session spam | Medium | `require_admin` + rate limit POST/test; destination cap |
| Telegram token in URL path / errors | Medium | Truncate/redact token in delivery errors and logs |
| SQL drift vs tests | Medium | Write Postgres-native SQL per post-Post-B `db/` convention (`db/dialect.py` is deleted; the CLAUDE.md dialect rule is stale) |

## What can go wrong

| Risk | Severity |
|------|----------|
| Breaking single Discord `.env` setup on upgrade | Critical |
| `webhooks_enabled()` ignores DB-only destinations | High |
| Duplicate config on ApiKeysPage + WebhooksPage | Medium |
| Orphan `destination_id` in delivery log after delete | Medium |
| Dedupe is global per `(event_type, dedupe_key)` — a failed or later-added destination is **permanently skipped** for a recorded key | High — **fixed in 12b** (per-destination dedupe) |

## What will go wrong (expected operator issues)

1. “Second Discord doesn’t fire” — merge/precedence or `webhooks_enabled()` bug.
2. HTTP URLs rejected — need clear “HTTPS only” error.
3. `localhost` webhooks blocked — explain internal URL block by design.
4. Env vs DB `source` confusion — UI must show `env` vs `db` badge.
5. Generic receivers expect custom JSON — document `webhook_json_payload` shape.

## Acceptance criteria (12a–12c combined)

- [ ] Create 2+ Discord destinations; both receive test when subscribed to same event
- [ ] **Per-destination dedupe:** with a recorded dedupe key, a destination that failed the
      first dispatch (or was added later) still receives the event on the next dispatch
- [ ] Legacy `.env` single Discord works with zero migration steps
- [ ] SSRF tests pass for create/update paths
- [ ] GET destinations never returns full secrets
- [ ] Admin test send works on a **disabled** destination (connectivity check before enable)
- [ ] WebhooksPage is primary management surface
- [ ] `./scripts/verify-local.sh` green; `--full` when Postgres available
- [ ] `PRODUCT_STATUS.md`, `API_REFERENCE.md`, `OPERATIONS.md` updated in implementation PR

## Async refactor note (PR12 — Gemini §1, validated)

`webhooks_enabled()` / `configured_channels()` cannot simply call `load_destinations()` without
becoming `async`. Call sites today include:

| Location | Pattern |
|----------|---------|
| `webhooks/engine.py` | `dispatch_event` — async, sync `webhooks_enabled()` guard |
| `webhooks/alerts.py` | multiple async alert processors, sync guard |
| `webhooks/sender.py` | sync `discord_configured()` / `telegram_configured()` wrappers |
| Tests | `test_webhooks_engine.py`, `test_webhooks_sender.py` |

**Implementation options:**

1. **Async helpers (decided):** `async def webhooks_enabled()` → `await load_destinations()`;
   update all call sites to `await`. Straightforward; touches alerts + engine + tests.
   This is **PR 12a** in its entirety.
2. ~~Sync cache~~ — rejected: stale-read risk if cache invalidation is missed.

## Suggested implementation order (PR12)

1. **PR 12a** — async refactor + call-site sweep (no behavior change)
2. **PR 12b** — Alembic 013 + backfill test; POST / DELETE / extended PATCH + SSRF on write;
   per-destination dedupe; masking on GET + audit hardening
3. **PR 12c** — WebhooksPage rewrite; legacy notice on ApiKeysPage webhook fields
4. Integration tests + docs land inside each PR, not as a trailing step

## Files likely touched (PR12)

- `backend/webhooks/destinations.py`, `engine.py`, `ssrf.py`
- `backend/db/webhooks.py`, `backend/routers/admin.py`
- `backend/alembic/versions/013_*.py`
- `frontend/src/pages/admin/WebhooksPage.jsx`, possibly `ApiKeysPage.jsx` (notice only)
- `backend/tests/test_webhooks_*.py`, new CRUD tests
- `API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

---

# PR13 — DB visibility

## Decision (maintainer review): ship the sample-rows MVP, defer the full explorer

The full read-only explorer below is **HIGH risk / LARGE scope** for "occasional debugging
without `psql`", with a security model where one missing deny-list entry exposes credentials.
The MVP that solves the actual debugging need:

**PR13-MVP — Storage sample rows**

- Extend the existing `GET /api/admin/storage` surface with a sample-rows endpoint for
  **Tier 1 intel tables only** (hardcoded allowlist from `docs/DATA_SNAPSHOT.md`).
- Server-defined ordering, `LIMIT 50`, **no filters, no pagination params, no operator tables
  queryable at all** — Tier 2/3 tables simply do not exist to this endpoint (404).
- Rendered as a sub-view of the existing Storage page — no new admin nav item.
- This deletes the entire Tier 2/3 masking problem: nothing sensitive is ever queryable.

**Build the full explorer below only if operators concretely ask for filtered browsing
afterward.** Everything from here to the PR13 open questions is retained as the deferred
design of record, with decisions pre-answered (see Open questions).

---

## Deferred design — full read-only DB explorer (reference only)

### Goal

Give admins a **safe, read-only browser** for allowlisted PostgreSQL tables — paginated rows,
masked columns, **no arbitrary SQL** — for debugging without `psql`.

### Phase A — Table catalog + row browser

**In scope**

- `GET /api/admin/db-explorer/tables` — allowlisted tables, row counts, column metadata
- `GET /api/admin/db-explorer/tables/{table}/rows` — paginated read:
  - `limit` max 100; offset or keyset cursor
  - Optional **single-column equality filter** on allowlisted columns only (e.g. `cve_id`, `key`)
  - **No** client `ORDER BY`, no joins, no free-text SQL
- Admin UI: table picker → headers → paginated rows
- Column mask list focused on **allowed Tier 1/2 tables** (Tier 3 tables are denied — masking
  `password_hash` / `refresh_token_hash` there is moot). Priority masks:
  - `sync_state.value` (if Option B key allowlist — may hold operator settings)
  - `webhook_delivery_log.error` (may echo webhook URLs/tokens from upstream)
  - `audit_log` detail fields that could contain config snippets
  - Large JSON/TEXT blobs (truncate ~2 KB, `truncated: true`)
- **Hard deny tables:** `users`, `sessions`, `webhook_destinations`, `app_settings`,
  `alembic_version` (and others per registry)
- Audit: `db.explorer.browse.{table}` with filter summary — **no row body**

**Out of scope (Phase A)**

- Full-text search, SQL console, joins
- CSV export of operator tables
- Write/update/delete from explorer
- Super-admin role

### Phase B — Follow-up

- CSV export for INTEL-only tables (reuse `DATA_SNAPSHOT.md` allowlist)
- Postgres `information_schema` fast path; SQLite stubs for tests
- Optional “must provide filter” for wide tables (`cves`)

## Allowlist tiers (seed from `docs/DATA_SNAPSHOT.md`)

**Tier 1 — Browse allowed (INTEL / ops-safe)**  
`cves`, `kev_deadlines`, `epss_history`, `mitre_techniques`, `mitre_groups`, `cve_change_history`,
correlation tables, etc.

**Tier 2 — Browse with heavy masking**  
`audit_log`, `webhook_delivery_log`

**Tier 3 — Never expose (404, not 403)**  
`users`, `sessions`, `user_preferences`, `webhook_destinations`, `app_settings`, `ioc_cache`,
`hunt_packs`, `alembic_version`

**`sync_state` — special case**  
High risk (may contain operator keys). **Decided: Option A — deny entirely** (key-prefix
allowlists are a standing audit burden for marginal debugging value).

Default rule: **deny** — table not in registry → 404.

## Architecture decisions (resolve before coding)

| # | Decision | Recommendation |
|---|----------|----------------|
| 1 | Query construction | Static registry; parameterized `WHERE col = ?` only |
| 2 | Ordering | Server-defined per table (PK or `created_at DESC`) |
| 3 | Pagination | Hard cap 100 rows; limit max offset or keyset to prevent DoS |
| 4 | Large columns | Truncate TEXT/JSON (~2 KB) with `truncated: true` |
| 5 | Auth | `require_admin` only |
| 6 | Rate limit | Stricter than default admin GET (e.g. 30/min) |
| 7 | UI placement | TBD: new Admin nav item vs Storage sub-tab |

## Security threats & mitigations (PR13)

| Threat | Impact | Mitigation |
|--------|--------|------------|
| SQL injection | Critical | No arbitrary SQL; whitelist table/column names in Python module only |
| Reading `password_hash` | Critical | Deny `users` table entirely |
| Webhook secrets | Critical | Deny `webhook_destinations`, `app_settings` |
| IOC investigation leaks | High | Deny `ioc_cache` in MVP |
| DoS via wide scans | Medium | Row cap, query timeout, rate limit, optional required filter |
| Schema enumeration | Medium | Unknown table → generic 404 |

## What can go wrong

| Risk | Severity |
|------|----------|
| One missing deny-list entry exposes credentials | Critical |
| `sync_state` leaks secrets via key names | High |
| SQLite tests pass, Postgres prod breaks | Medium |
| Operators expect write access from explorer | Medium (UX copy) |
| Full `cves` row scan slows instance | Medium |

## What will go wrong (expected)

1. “Why can’t I see users?” — intentional; document on Security page.
2. CVE search returns nothing — filter column typo or wrong table.
3. Requests for `ioc_cache` browse — deny with explanation.
4. Confusion vs Storage page (counts only) — cross-link in UI.

## Acceptance criteria (Phase A)

- [ ] Forbidden tables return **404**
- [ ] Fuzz/param tests: no injectable SQL via table/column/filter params
- [ ] Masked columns never return raw secrets
- [ ] Browse audited without row content in audit detail
- [ ] Pagination cap enforced server-side
- [ ] UI: loading / empty / error + `X-Request-ID` on errors
- [ ] `PRODUCT_STATUS.md`, `API_REFERENCE.md` updated in implementation PR
- [ ] Security checklist reviewed before merge

## Suggested implementation order (PR13)

1. Static registry module (tables, columns, filters, masks, deny list)
2. pytest: injection attempts, deny list, mask assertions
3. GET tables + GET rows endpoints
4. Admin UI page
5. Rate limit + audit
6. Docs + first-visit warning banner

## Files likely touched (PR13)

- New `backend/db/explorer_registry.py` (or `admin/db_explorer.py`)
- `backend/routers/admin.py`
- `frontend/src/pages/admin/` (new `DatabaseExplorerPage.jsx` or Storage extension)
- `backend/tests/test_db_explorer.py`
- `API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

---

## Open questions — **decided** (maintainer review, PR #409 comment, 2026-07-10)

### PR12

1. Keep env `discord`/`telegram`/`generic` forever or deprecate? → **Keep forever** as
   bootstrap; env deprecation dropped entirely (churn with no operator value).
2. Max destinations per `kind`? → **20**.
3. Is duplicate delivery to all subscribed destinations on same event desired? → **Yes,
   intended behavior.**
4. Should dedupe become per-destination? → **Yes, in PR 12b** (not deferred — see the verified
   failure mode in the 12b scope).

### PR13

1. `sync_state`: deny entirely (Option A) or key allowlist (Option B)? → **Option A, deny.**
2. Require a filter for `cves` browse? → **Yes** (deferred design only; the MVP has no
   filters and caps at 50 rows).
3. New admin nav item vs tab under Storage? → **Storage sub-view**, no new nav item.
4. Include `audit_log` in Tier 2 or deny? → **Deferred with the full explorer** — the MVP
   exposes Tier 1 intel tables only.

---

## Gemini review reconciliation (PR #409, 2026-07-10)

| # | Comment | Verdict | Action |
|---|---------|---------|--------|
| 1 | `webhooks_enabled()` must become async (or use cache) for DB destinations | **Valid** | Added async refactor note + call-site table; default Option 1 |
| 2 | Allow admin test of **disabled** destinations before enable | **Valid** | Added to Phase A scope; `send_test_message` guard is real (engine.py L258–264) |
| 3 | Masking should target allowed-table columns, not denied-table columns | **Valid** | Rewrote Phase A mask list; Tier 3 deny list unchanged |

No Gemini inline comments rejected. CodeRabbit skipped (draft PR).

---

## Maintainer review reconciliation (PR #409 comment, 2026-07-10)

| # | Point | Action |
|---|-------|--------|
| 1 | Migration numbering — the review comment claimed 006/007 based on a **stale checkout**; the repo actually has migrations 001–012, so this plan's original 013 was correct | **013** confirmed for PR12; **014** reserved for AI ops plan (#410) |
| 2 | Per-destination dedupe belongs in scope, not Phase B — verified `engine.py` (`was_webhook_alert_sent` ~L159, `record_webhook_alert` ~L219): key recorded when **any** destination succeeds, so failed/later-added destinations are permanently skipped | Moved into **PR 12b** scope + acceptance criteria; risk raised to High |
| 3 | Sequencing — the review comment said "queue after D4/Post-B", also from the stale checkout; D4 and Post-B are in fact **complete** and the wave queue is drained | Corrected sequencing section: PR12a–c is the next implementation queue after PR-A (#411) |
| 4 | Split Phase A into three PRs; answer open questions with defaults | Restructured as 12a/12b/12c; all open questions decided |
| 5 | PR13 oversized for its value — cut to lazy MVP | PR13-MVP = Storage sample rows, Tier 1 only; full explorer deferred |
| 6 | `db/dialect.py` references (this plan + CLAUDE.md) are stale — deleted in Post-B Phase 3 | SQL risk row updated to Postgres-native convention; CLAUDE.md fix flagged as its own task |

---

## Validation checklist (for Cloud Code / review on this plan)

- [ ] Phase boundaries are clear; no scope creep into V2 platform
- [ ] PR12 migration needs match actual `webhook_destinations` schema
- [ ] PR13 allowlist aligns with `DATA_SNAPSHOT.md` OPERATOR exclusions
- [ ] Security mitigations are testable (named pytest files)
- [ ] PR12 async refactor approach chosen (Option 1 vs 2)
- [ ] PR12 test-while-disabled scoped to admin test endpoint only
- [ ] Acceptance criteria are measurable
- [ ] Open questions answered or explicitly deferred with default
- [ ] No contradiction with `CLAUDE.md` danger zones (SQL dialect, migrations forward-only)
- [ ] No contradiction with `docs/PRODUCT_STATUS.md` runtime truth

---

## References

- `docs/planning/BRIEFR_VISUAL_OPERATIONAL_UX_AUDIT.md` — Issues 18, 22; PR12/PR13 sections
- `docs/DATA_SNAPSHOT.md` — INTEL vs OPERATOR table taxonomy
- `backend/webhooks/ssrf.py` — outbound webhook security baseline
- `docs/HANDOVER.md` — UX audit queue complete; PR12/PR13 deferred

---

*Planning document only. Implementation PRs: `cursor/ux-audit-pr12-*` and `cursor/ux-audit-pr13-*`
(branches TBD after this plan is approved).*
