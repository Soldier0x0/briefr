# PR12 & PR13 — Implementation plan (planning only)

**Status:** Draft for review — **no implementation in this document**  
**Date:** 2026-07-10  
**Source:** UX audit (`docs/planning/BRIEFR_VISUAL_OPERATIONAL_UX_AUDIT.md`) Issues 18 & 22  
**Deferred from:** Approved 11-PR UX correction pass (PR1–PR11 + PR8 merged 2026-07-10)

This file is the single planning artifact for Cloud Code / maintainer validation before any
implementation PRs are opened.

---

## Executive summary

| PR | Name | User value | Risk | Scope | DB migration |
|----|------|------------|------|-------|--------------|
| **PR12** | Multi-webhook endpoints | Daily ops — multiple alert channels | HIGH | LARGE | Likely (Alembic) |
| **PR13** | Read-only DB explorer | Occasional debugging without `psql` | HIGH | LARGE | No (registry-only MVP) |

**Recommended order:** PR12 Phase A first (existing webhook engine + table); PR13 Phase A second
(security-sensitive, no rush).

**Do not parallelize** with shared-surface work (DetailDrawer, etc.). Admin-only but large blast
radius.

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
- `webhooks_enabled()` currently derives from **env** destinations only — must be fixed before
  DB-only endpoints work.

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

## Phased delivery

### Phase A — Multi-destination CRUD (MVP) — **implement first**

**In scope**

- `POST /api/admin/webhooks/destinations` — create destination
- `DELETE /api/admin/webhooks/destinations/{id}` — delete (typed confirm via destructive-actions
  pattern or inline confirm word)
- Extend `PATCH` to update **config** (URL / token / chat_id) for **DB-only** destinations
- Multiple rows per `kind`: `discord`, `telegram`, `generic`
- Generated IDs: `{kind}-{short-uuid}` or validated operator slug `^[a-z0-9-]{3,64}$`
- Legacy env destinations (`discord` / `telegram` / `generic`) keep working unchanged
- Audit every create / update / delete / test
- Rebuild **WebhooksPage** around `GET /webhooks/destinations` (not raw ApiKeys config keys)
- Tests: CRUD, SSRF rejection on write, multi-delivery, env+DB merge, no secret leakage in API

**Out of scope (Phase A)**

- Removing `.env` webhook vars entirely
- Encrypting `config_json` at rest
- New provider kinds beyond existing `generic` HTTPS JSON
- Per-destination retry policy changes
- Per-destination dedupe (see risks below)

### Phase B — Env deprecation & polish (follow-up PR)

- Deprecate `DISCORD_WEBHOOK_URL` / `TELEGRAM_*` / `WEBHOOK_GENERIC_*` on ApiKeysPage
  (migrate-on-first-save or read-only legacy panel)
- Optional encryption for secrets in `config_json`
- Destination health from `webhook_delivery_log` (last success / last error)
- Document dedupe semantics when multiple destinations subscribe to same event

## DB migration (what it means for PR12)

The **table already exists**. A new **Alembic forward-only** revision (`013_…py`) is still
likely because:

| Change | Reason |
|--------|--------|
| Generated IDs (not only `discord`/`telegram`/`generic`) | Multiple rows per kind |
| Optional new columns | `description`, `sort_order`, `created_by_user_id`, `deleted_at` |
| Constraints | `CHECK (kind IN (...))`, optional unique `(kind, label)` |
| Data backfill | Preserve existing rows + `webhook_delivery_log.destination_id` consistency |

**Minimal path:** no new columns — only allow multiple rows + generated IDs; migration may still
add indexes/constraints + backfill script.

**Rules:** never edit applied migrations; SQLite parity if shared query paths touch new columns.

## Architecture decisions (resolve before coding)

| # | Decision | Recommendation |
|---|----------|----------------|
| 1 | Source of truth | DB for user-created; env for legacy bootstrap until Phase B |
| 2 | ID format | `{kind}-{short-uuid}` or validated slug; reserve `discord`/`telegram`/`generic` for env |
| 3 | Secrets in API | Never return full URL/token after save — mask like `GET /api/admin/config` |
| 4 | Config UI location | **Webhooks page** primary; ApiKeysPage legacy notice only (Phase A) |
| 5 | Delete env-backed row | Disable only — env re-syncs on boot |
| 6 | Max destinations | Cap per kind (e.g. 20) — TBD by maintainer |

## Security threats & mitigations (PR12)

| Threat | Impact | Mitigation |
|--------|--------|------------|
| SSRF via malicious URL | Critical | Reuse `webhooks/ssrf.py` on **create and update** of URL fields |
| Secret exfiltration via GET | High | Mask `config_json`; never return full webhook URL or Telegram token |
| Secrets in `audit_log` | High | Audit `destination_id` + action only; no URL/token in detail |
| Compromised admin session spam | Medium | `require_admin` + rate limit POST/test; destination cap |
| Telegram token in URL path / errors | Medium | Truncate/redact token in delivery errors and logs |
| SQL dialect breakage | Medium | Shared SQL via `?` placeholders + `db/dialect.py` (CLAUDE.md danger zone) |

## What can go wrong

| Risk | Severity |
|------|----------|
| Breaking single Discord `.env` setup on upgrade | Critical |
| `webhooks_enabled()` ignores DB-only destinations | High |
| Duplicate config on ApiKeysPage + WebhooksPage | Medium |
| Orphan `destination_id` in delivery log after delete | Medium |
| Dedupe is global per `(event_type, dedupe_key)` — second destination may not fire for same key | Medium — document or fix in Phase B |

## What will go wrong (expected operator issues)

1. “Second Discord doesn’t fire” — merge/precedence or `webhooks_enabled()` bug.
2. HTTP URLs rejected — need clear “HTTPS only” error.
3. `localhost` webhooks blocked — explain internal URL block by design.
4. Env vs DB `source` confusion — UI must show `env` vs `db` badge.
5. Generic receivers expect custom JSON — document `webhook_json_payload` shape.

## Acceptance criteria (Phase A)

- [ ] Create 2+ Discord destinations; both receive test when subscribed to same event
- [ ] Legacy `.env` single Discord works with zero migration steps
- [ ] SSRF tests pass for create/update paths
- [ ] GET destinations never returns full secrets
- [ ] CRUD/test audited without secrets in detail
- [ ] WebhooksPage is primary management surface
- [ ] `./scripts/verify-local.sh` green; `--full` when Postgres available
- [ ] `PRODUCT_STATUS.md`, `API_REFERENCE.md`, `OPERATIONS.md` updated in implementation PR

## Suggested implementation order (PR12)

1. Fix `webhooks_enabled()` + `load_destinations()` for DB-only destinations
2. Alembic migration (if needed) + backfill test
3. POST / DELETE / extended PATCH + SSRF on write
4. Masking on GET + audit hardening
5. WebhooksPage rewrite
6. Legacy notice on ApiKeysPage webhook fields
7. Integration tests + docs

## Files likely touched (PR12)

- `backend/webhooks/destinations.py`, `engine.py`, `ssrf.py`
- `backend/db/webhooks.py`, `backend/routers/admin.py`
- `backend/alembic/versions/013_*.py` (if schema changes)
- `frontend/src/pages/admin/WebhooksPage.jsx`, possibly `ApiKeysPage.jsx` (notice only)
- `backend/tests/test_webhooks_*.py`, new CRUD tests
- `API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

---

# PR13 — Read-only DB explorer

## Goal

Give admins a **safe, read-only browser** for allowlisted PostgreSQL tables — paginated rows,
masked columns, **no arbitrary SQL** — for debugging without `psql`.

## Phased delivery

### Phase A — Table catalog + row browser (MVP)

**In scope**

- `GET /api/admin/db-explorer/tables` — allowlisted tables, row counts, column metadata
- `GET /api/admin/db-explorer/tables/{table}/rows` — paginated read:
  - `limit` max 100; offset or keyset cursor
  - Optional **single-column equality filter** on allowlisted columns only (e.g. `cve_id`, `key`)
  - **No** client `ORDER BY`, no joins, no free-text SQL
- Admin UI: table picker → headers → paginated rows
- Column mask list (truncate or redact): `password_hash`, `refresh_token_hash`, `config_json`,
  `profile_json`, large JSON blobs
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
High risk (may contain operator keys). Options:

- **Option A (safer):** deny entire table in MVP
- **Option B:** allow with key prefix allowlist only (`scheduler.last_run.*`, NVD watermark keys)
- **Decision required before implementation**

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

## Open questions (maintainer / Cloud Code validation)

### PR12

1. Keep env `discord`/`telegram`/`generic` forever or deprecate in Phase B?
2. Max destinations per `kind`?
3. Is duplicate delivery to all subscribed destinations on same event **desired**?
4. Should dedupe become per-destination in Phase B?

### PR13

1. `sync_state`: deny entirely (Option A) or key allowlist (Option B)?
2. Require a filter for `cves` browse in MVP?
3. New admin nav item vs tab under Storage?
4. Include `audit_log` in Tier 2 or deny?

---

## Validation checklist (for Cloud Code / review on this plan)

- [ ] Phase boundaries are clear; no scope creep into V2 platform
- [ ] PR12 migration needs match actual `webhook_destinations` schema
- [ ] PR13 allowlist aligns with `DATA_SNAPSHOT.md` OPERATOR exclusions
- [ ] Security mitigations are testable (named pytest files)
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
