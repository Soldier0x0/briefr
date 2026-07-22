# BRIEFR API Reference

Copyright © 2026 Sai Harsha Vardhan. Licensed under the Business Source License 1.1 (`SPDX-License-Identifier: BUSL-1.1`); see the repository `LICENSE` for the full text.

**Base URL:** `/api` (proxied from Vite dev server at `http://localhost:5173/api` → `http://localhost:8000/api`)  
**Auth:** built-in app login (`briefr_at` / `briefr_rt` cookies). **Analyst routes** (`/api/*` except health, auth, wallboard, and dev OpenAPI) pass through `require_user` and require a valid session — 401 without login (#441). **Ingest** `POST /api/refresh*` and all `/api/admin/*` routes require the `admin` role. See [Authentication](#authentication) below.
**Interactive docs:** `GET /api/docs` (Swagger UI), `GET /api/redoc` (ReDoc), `GET /api/openapi.json` — available outside production only; `BRIEFR_ENV=production` disables all three.

Default error shape (FastAPI): `{"detail": "<message>"}`

**Request IDs:** every response carries an `X-Request-ID` header (echoed from the request when a well-formed `X-Request-ID` is supplied, generated otherwise). The same ID appears as `request_id` in the backend's JSON log lines.

**Rate limiting:** `POST /api/ioc/lookup` and all `POST /api/refresh*` routes are token-bucket rate limited per client IP (defaults: 30/min and 10/min — `RATE_LIMIT_IOC_PER_MINUTE`, `RATE_LIMIT_REFRESH_PER_MINUTE`; `RATE_LIMIT_ENABLED=0` disables). Over the limit → `429` with a `Retry-After` header (whole seconds). Auth routes use separate buckets (`RATE_LIMIT_LOGIN_PER_MINUTE`, `RATE_LIMIT_AUTH_REFRESH_PER_MINUTE`). **Multi-worker:** set `BRIEFR_RATE_LIMIT_STORE=db` to persist token buckets in `sync_state` (shared across uvicorn workers). Run the scheduler on one owner only (`BRIEFR_SCHEDULER_ENABLED=1`, default); set `BRIEFR_SCHEDULER_ENABLED=0` on API-only workers (#444).

---

## Authentication

Built-in app login (Sprint A0). Sessions use HttpOnly cookies:

| Cookie | Path | Purpose |
|--------|------|---------|
| `briefr_at` | `/` | Short-lived JWT access token |
| `briefr_rt` | `/api/auth` | Rotating refresh token (stored hashed in `sessions`) |

**Roles:** `admin` (full admin/ingest routes) and standard users. Admin-only routes return `403` for non-admin sessions.

**Route gate:** middleware calls `require_user` for non-public `/api/*` routes. Public API paths are limited to `/api/auth/*`, `/api/health`, `/api/health/live`, `/api/wallboard/*`, and the dev-only docs/OpenAPI paths above. `/api/admin/*` and `/api/refresh*` skip the middleware gate because their routers call `require_admin`.

### GET /api/auth/setup-required

**Description:** First-run bootstrap probe — `true` when no users exist.

**Auth:** None

**Response:** `{"required": true|false}`

### POST /api/auth/setup

**Description:** Create the first admin account (once only). Permanently disabled after any user row exists — not self-service signup.

**Auth:** None (rate-limited like login)

**Body:** `{"username": "...", "password": "..."}`

**Response:** `{"username": "...", "role": "admin"}` — sets auth cookies.

**Error responses:** `409` when setup already completed; `400` weak username/password.

### POST /api/auth/login

**Body:** `{"username": "...", "password": "...", "remember_me": false}`

**Response:** `{"username": "...", "role": "admin"|"user"}` — sets auth cookies.

**Error responses:** `401` generic invalid credentials (timing-safe dummy verify on unknown users).

### POST /api/auth/logout

**Description:** Revokes the current refresh session and clears cookies.

**Auth:** Optional (revokes when `briefr_rt` present)

**Response:** `{"status": "ok"}`

### POST /api/auth/refresh

**Description:** Rotate refresh token and issue a new access JWT.

**Auth:** Valid `briefr_rt` cookie (any active user — not admin-only)

**Response:** `{"username": "...", "role": "..."}` — new cookies.

**Error responses:** `401` when cookie missing, session revoked, user inactive, **`sessions.expires_at` in the past**, or refresh-token reuse detected (reuse revokes all sessions for the user).

**Client note (#731):** The SPA must share one in-flight refresh (`frontend/src/api.js` `refreshAccessToken`). Concurrent bare `POST /api/auth/refresh` calls after rotation trip reuse detection and revoke every session for the user.

### GET /api/auth/me

**Auth:** Required (`briefr_at`)

**Response:** `{"username": "...", "role": "...", "last_login_at": "..."}`

### GET /api/auth/sessions

**Description:** List active refresh sessions for the signed-in user.

**Auth:** Required

**Response:** `{"user": {...}, "sessions": [{id, created_at, last_used_at, expires_at, user_agent, ip, remember_me, is_current}, ...]}`

### DELETE /api/auth/sessions/{session_id}

**Description:** Revoke one session owned by the signed-in user.

**Auth:** Required

**Response:** `{"status": "revoked"}` — `404` / `403` when not found or not owned.

---

## CVE Feed

### GET /api/cves

**Description:** Paginated CVE feed with filters.

**Auth:** Required (`briefr_at`; enforced by `require_user` middleware).

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (≥ 1) |
| `limit` | int | 20 | Results per page (1–**50**, not 100) |
| `severity` | str | null | `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW` |
| `kev_only` | bool | false | Only CISA KEV entries |
| `poc_only` | bool | false | Only CVEs with `has_poc` |
| `patch_only` | bool | false | Only CVEs with `patch_available` |
| `epss_min` | float | null | Minimum EPSS (0.0–1.0) |
| `search` | str | null | CVE ID exact match or description/summary substring (max 200) |
| `stack` | str | null | Comma-separated product/CVE terms (max 500) |
| `vendors` | str | null | Comma-separated vendor/product terms (max 500) |
| `technique` | str | null | ATT&CK technique ID e.g. `T1190` (max 32) |
| `published_on` | str | null | `YYYY-MM-DD` calendar day filter |
| `summary_only` | bool | false | Only CVEs with enriched plain-English summary |
| `ai_context_only` | bool | false | Only CVEs with `has_ai_context = 1` |
| `frameworks` | str | null | Comma-separated AI/ML tokens; implies `has_ai_context` and matches description/products |
| `watchlist_only` | bool | false | Only CVEs on the active watchlist (pinned + unexpired snoozes) |
| `pagination` | str | null | Set to `keyset` for cursor-based chronological pagination (published DESC, then `cve_id` DESC). Omits `total`/`pages`. |
| `cursor` | str | null | Opaque keyset cursor from a prior response's `next_cursor`. Requires `pagination=keyset`. |

**Response (keyset mode):** Same `data` array shape; adds `pagination: "keyset"` and `next_cursor` (null when no further page). `total`, `page`, and `pages` are null. Invalid cursor → `400`.

**Response:**

```json
{
  "total": 6992,
  "page": 1,
  "limit": 20,
  "pages": 350,
  "data": [
    {
      "cve_id": "CVE-2024-0001",
      "description": "...",
      "cvss_score": 9.8,
      "severity": "CRITICAL",
      "published": "2024-01-01T00:00:00.000",
      "modified": "...",
      "affected_products": ["vendor:product"],
      "mitre_technique": "T1190",
      "summary": "...",
      "is_kev": false,
      "epss_score": 0.42,
      "has_poc": true,
      "patch_available": true,
      "source_urls": ["https://..."],
      "cwe_ids": ["CWE-79"],
      "updated_at": "2024-01-02 12:00:00",
      "kev_due_date": null
    }
  ]
}
```

Each CVE object may include `kev_due_date` (`YYYY-MM-DD` from `kev_deadlines.due_date`, or `null` when not on the KEV catalog). Additive fields — present on list and export responses when applicable:

- `watchlist_state` — `"pin"`, `"snooze"`, or omitted when not on the watchlist
- `watchlist_snooze_until` — UTC `YYYY-MM-DD HH:MM:SS` when `watchlist_state` is `"snooze"`, otherwise omitted
- `member_of_campaign` — `true` when the CVE is a member of a nightly-built OTX pulse campaign cluster; `false` otherwise
- `campaign_lifecycle` — `"active"`, `"emerging"`, `"declining"`, or `"stale"` when `member_of_campaign` is `true`; omitted otherwise (cheapest lifecycle when multiple campaigns apply)

**Default sort:** pinned watchlist CVEs first; then CVEs that share a **gated** campaign cluster with a pinned peer (campaign confidence ≥ MEDIUM, lifecycle ∈ {active, emerging}, not retracted — CORR-PR-13 / D9); then `published` DESC, severity (CRITICAL→LOW), EPSS DESC. When `stack` is set, an additional client-side exposure sort may apply in the feed UI.

**Error responses:**

- `400` — invalid `severity`, `technique`, or `published_on`
- `422` — invalid query param types (FastAPI validation)

**Notes:** Pinned CVEs sort first (`watchlist.state = 'pin'`), then `published DESC`, severity, EPSS. Active snoozes (`state = 'snooze'` with `snooze_until > now`) are excluded from the default feed; `watchlist_only=true` shows the watchlist including snoozed rows. Stack filter re-sorts page by relevance. The `total` field is served from a 45-second in-process cache keyed by the active filter set (same filters → same total within TTL). On PostgreSQL, text search uses `pg_trgm` GIN indexes (Alembic migration `012_cve_trgm_search`).

---

### GET /api/cves/export

**Description:** Up to 500 CVE rows for CSV/XLSX export (same filters as list).

**Query params:** Same as `GET /api/cves` except no `page`; adds `max_rows` (default 500, max 500).

**Response:** `{"total": N, "data": [ CVE objects ]}`

---

### POST /api/cves/match

**Description:** CPE-based asset exposure match scores (asset inventory sent only here).

**Body:**

```json
{
  "assets": [
    { "product": "nginx", "version": "1.24", "vendor": "" }
  ]
}
```

**Response:** `{"matches": {"CVE-2024-0001": 0.85, ...}}`

**Error responses:** `422` — body validation (max 500 assets)

---

### GET /api/brief

**Description:** Server-computed morning brief — ranked analyst action queue from existing DB state (read-path only; no ingest).

| Param | Type | Default | Description |
|---|---|---|---|
| `stack` | str | null | Comma-separated stack terms (same matching as `/api/cves` `stack`) |
| `since_hours` | int | 24 | Lookback window for movers / new KEV / stack activity (1–168) |
| `limit` | int | 10 | Max items per section (1–50) |
| `kev_due_days` | int | 14 | KEV remediation horizon for the due-soon section (1–90) |

**Response:**

```json
{
  "meta": {
    "generated_at": "2026-06-12T21:00:00Z",
    "stack_profile_id": "stack:a1b2c3d4e5f6",
    "stack_terms": ["log4j"],
    "since_hours": 24,
    "kev_due_days": 14
  },
  "sections": {
    "epss_movers": { "title": "EPSS movers", "count": 2, "items": [...] },
    "new_kev": { "title": "New KEV entries", "count": 1, "items": [...] },
    "kev_due_soon": { "title": "KEV due within 14 days", "count": 3, "items": [...] },
    "stack_matches": { "title": "Stack activity", "count": 5, "items": [...] },
    "active_campaigns": { "title": "Active campaigns on your stack", "count": 1, "items": [...] }
  },
  "action_queue": [ { "cve_id": "...", "reasons": ["kev_due_soon", "stack_match"], ... } ]
}
```

Each item includes core card fields (`cve_id`, `severity`, `cvss_score`, `epss_score`, `is_kev`, `has_poc`, `summary`, `published`, `kev_due_date`, `reasons`) plus section-specific extras (`epss_delta`, `kev_date_added`, etc.). `active_campaigns` items are cluster-level (`campaign_id`, `label`, `adversary`, `confidence`, `member_count`, `lifecycle`) rather than CVE-keyed, so they're excluded from `action_queue`.

**Frontend:** BRIEF tab landing view (`MorningBrief.jsx`) — default tab on load; renders a **single unified list** from `action_queue` (reason filter chips + optional KEV due-window from histogram click; `CveDescriptionClamp` per row). Full paginated CVE list lives on the FEED tab (`FilterBar` stack field + `CVEFeed`; no Hero/StatsRow/heatmap on FEED).

---

## Watchlist (pin / snooze)

Single-user for now — no `user_id` column. Built-in app login will add per-user keying (ROADMAP amendment 2026-06-11).

### GET /api/watchlist

**Description:** List active watchlist entries (pins and snoozes whose `snooze_until` has not passed).

**Response:** `{"data": [{"cve_id": "CVE-...", "state": "pin"|"snooze", "snooze_until": null|"YYYY-MM-DD HH:MM:SS", "created_at": "..."}], "count": N}`

---

### POST /api/watchlist

**Description:** Pin or snooze a CVE. Upserts by `cve_id` (one row per CVE).

**Body:**

```json
{ "cve_id": "CVE-2024-0001", "state": "pin" }
```

```json
{ "cve_id": "CVE-2024-0001", "state": "snooze", "snooze_days": 7 }
```

`snooze_days` is optional when `state` is `"snooze"` (default **7**, range 1–365).

**Response:** `{"data": { watchlist row }}`

**Error responses:**

- `400` — invalid CVE ID format or `state`
- `404` — CVE not in `cves` table

---

### DELETE /api/watchlist/{cve_id}

**Description:** Remove a CVE from the watchlist (unpin).

**Response:** `{"ok": true, "cve_id": "CVE-..."}`

**Error responses:** `400` — invalid CVE ID; `404` — no watchlist row

---

### DELETE /api/watchlist/snoozes

**Description:** Remove all snoozed CVE rows from the watchlist (restores them to the default feed). Called once on app load after snooze was removed from the UI.

**Response:** `{"ok": true, "deleted": N}`

---

**Frontend:** Pin control on `CVECard` and `DetailDrawer`; **WATCHLIST** quick-filter chip on the feed (`watchlist_only=true`). Snooze controls were removed from the UI — legacy snooze rows are cleared via `DELETE /api/watchlist/snoozes` on startup. State is server-backed (`watchlist` table), not `localStorage`.

**Feed layout:** Stack filter bar (prominent) → CVE keyword search → quick filter chips (ALL, WATCHLIST, KEV, …) → common vendor chips (scrolls with the list, not sticky).

**Analyst charts:** `TimeWindowPicker` dropdown on the BRIEF tab — presets (6h–90d) plus custom datetime range for KEV due dates and EPSS movers.

**Morning brief:** `action_queue` items include `description` and `summary`; rows use severity color coding on reason chips and metrics.

---

## User stack (per-user preferences)

Server-backed stack terms and optional asset profile JSON, keyed by `user_id`. Replaces the analyst `briefr_stack` localStorage split (Wave 2 PR 4 wires the frontend). Requires a valid session (`briefr_at` cookie) — 401 without login.

### GET /api/me/stack

**Description:** Read the authenticated user's stack terms and optional asset profile.

**Response:**

```json
{
  "stack_terms": "nginx,log4j",
  "profile": {
    "version": 1,
    "operatingSystems": [],
    "applications": [],
    "environment": {
      "internetFacing": "Some",
      "industry": "Technology",
      "criticality": "Medium"
    },
    "aiSystems": []
  },
  "updated_at": "2026-07-07 12:00:00"
}
```

When no row exists yet, `stack_terms` is `""`, `profile` is `null`, and `updated_at` is `null`.

### PUT /api/me/stack

**Description:** Upsert the authenticated user's stack terms and optional asset profile.

**Body:**

```json
{
  "stack_terms": "nginx, log4j",
  "profile": { "...": "same shape as GET response profile, or null to clear" }
}
```

**Response:** Same shape as GET (with non-null `updated_at`).

**Validation:** `stack_terms` is normalized (trimmed, empty segments dropped, rejoined with commas). `profile` must be a JSON object when present; unknown keys are dropped and lists are sanitized to the asset-wizard shape. Omit `profile` to leave the saved inventory unchanged; send `null` to clear. Oversized payloads → `422`.

**Notes:** `BRIEFR_STACK_TERMS` in admin config overrides the saved user stack for KEV-on-stack webhooks and the wallboard tile. When unset, the backend uses the most recently updated non-empty `user_preferences.stack_terms` row.

### GET /api/stack/catalog/suggest

**Description:** Autocomplete products from the NVD CPE–seeded `software_catalog` (Q3). Auth required.

**Params:** `q` (string; results only when length ≥ 3 — shorter queries return `{items: []}` with no table scan), `limit` (1–50, default 20), `category` (optional: `app` \| `library` \| `os` \| `web_server` \| `firewall` \| `database` \| `other`).

**Response:** `{ok, query, items: [{vendor, product, display_name, category, versions}]}`. Versions are suggestions; free-typed versions remain allowed in the UI. Catalog is populated by scheduler job `cpe_catalog_sync` when `CPE_CATALOG_SYNC_ENABLED=1`.

### GET /api/stack/coverage
Auth required. Returns corpus hit counts for saved My Stack products, `needs_backfill` when any product is shallow (&lt;3 matching CVEs) and `STACK_BACKFILL_ENABLED=1`, plus preflight `eta` (low/high seconds).

### POST /api/stack/backfill/agree
Auth required. Enqueues Tier A backfill (NVD keyword pages → upsert → EPSS + KEV). `403` when `STACK_BACKFILL_ENABLED=0`. Response: `{ok, run_id, eta, message}`. Deep enrichment (OTX/exploits/correlation) is **not** part of Agree.

### GET /api/stack/backfill/{run_id}
Auth required (owner only). `{ok, run, checkpoints}` with status `pending|running|deferred|on_hold|partial|completed|failed|not_found` per product.

### POST /api/stack/backfill/{run_id}/resume
Auth required. Re-kicks a deferred/on_hold/partial run.

### GET /api/me/preferences

**Description:** Read the authenticated user's display preferences and timezone.

**Response:**

```json
{
  "font_scale": "medium",
  "density": "comfortable",
  "show_technical_ids": false,
  "poll_interval_seconds": 30,
  "utc_time": false,
  "reduce_motion": false,
  "notification_sound": true,
  "typography_px": {
    "title": 20,
    "heading": 15,
    "subheading": 14,
    "id": 18,
    "body": 14,
    "meta": 13,
    "micro": 12
  },
  "timezone": "UTC",
  "remember_profile_on_server": false,
  "updated_at": "2026-07-08 12:00:00"
}
```

When no row exists yet, fields use defaults and `updated_at` is `null`.

### PATCH /api/me/preferences

**Description:** Partially update display preferences and/or timezone. At least one field is required.

**Body:** Any subset of the GET fields (snake_case). Omitted fields are unchanged.

**Response:** Same shape as GET (with non-null `updated_at`).

**Validation:** `font_scale` ∈ `xsmall|small|medium|large|xlarge`; `density` ∈ `compact|comfortable|spacious`; `poll_interval_seconds` ∈ `15|30|60|120`; booleans for `show_technical_ids`, `utc_time`, `reduce_motion`, `notification_sound`, `remember_profile_on_server`; `typography_px` object with integer px per role (`title`, `heading`, `subheading`, `id`, `body`, `meta`, `micro`) in range 9–20; `timezone` must be a valid IANA zone. Invalid values → `422`.

**Response also includes:** `instance_typography_default` — operator-configured default profile from `app_settings` (null when unset). Users without a saved `typography_px` inherit this on read.

### GET /api/me/notifications

**Description:** Server-backed in-app notification inbox for the signed-in user.

| Param | Type | Default | Description |
|---|---|---|---|
| `scope` | str | `analyst` | `analyst` (watchlist/CVE/IOC alerts) or `operator` (job errors, unhealthy API keys; admin role only) |
| `limit` | int | 30 | 1–100 |

**Response:** `{notifications: [{id, scope, category, severity, title, body, entity_type, entity_id, created_at, read_at}], unread_count}` — `unread_count` counts undismissed `critical`/`high` rows with `read_at` null.

### GET /api/me/notifications/unread-count

**Description:** Lightweight badge count for one scope. Standard users requesting `operator` scope receive `{unread_count: 0}` rather than operator events.

**Params:** `scope` = `analyst` (default) or `operator`.

**Response:** `{unread_count}`

### POST /api/me/notifications/seen

**Body:** `{scope}` — marks all undismissed rows in scope as read (clears badge). **Response:** `{marked_seen, unread_count}`.

### POST /api/me/notifications/{id}/dismiss

Dismiss one notification (removed from list). **Response:** `{ok: true}` or `404`.

### POST /api/me/notifications/dismiss-all

**Body:** `{scope}` — dismiss all active rows in scope. **Response:** `{dismissed}`.

**Notes:** `PUT /api/me/stack` updates `profile` only when the `profile` field is present in the body; omitting it preserves the saved inventory. Send `"profile": null` to clear.

---

### GET /api/changes

**Description:** Recent tracked field changes (`cvss_score`, `epss_score`, `is_kev`, `has_poc`).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | 1–500 |
| `field` | str | null | Filter to one tracked field |
| `since_hours` | int | 24 | 1–168 |

**Response:** `{"data": [...], "count": N}` — each change row: `id`, `cve_id`, `field_name`, `old_value`, `new_value`, `detected_at`, `severity` (joined from `cves`; null when the CVE row is missing).

**EPSS noise:** `update_epss_scores` only writes history when the score would display differently at **0.1%** precision (matching the What changed panel). Sub-threshold float jitter (e.g. `0.0001` → `0.0002`, both shown as `0.0%`) is ignored.

**Postgres:** `detected_at` is `TIMESTAMPTZ` (migration `026`); SQLite dev fallback keeps `TEXT`.

**Frontend:** BRIEF tab **What changed** panel (`WhatChangedPanel.jsx`) — field + time-window filter chips; row click opens the CVE drawer; rows with identical formatted old/new values are hidden (legacy noise). `BriefCharts.jsx` uses `field=epss_score&since_hours=168` for the **Top EPSS movers** compact table (top 10 positive deltas, 7-day sparklines per row via `GET /api/cves/{id}/epss-history`, row click opens the drawer). On viewports **≥901px** wide, the panel sits beside the 90-day activity heatmap in a flex row (`brief-intel-row` in `App.jsx`); below 900px they stack full-width (heatmap above). Alternating row shading uses `--surface-sunken`.

**Error responses:** `400` — invalid `field`

---

## CVE Detail & Enrichment

### GET /api/cves/{cve_id}

**Description:** Full CVE detail with live enrichment (scheduler-fed exploits, Sploitus fallback, OTX, OSV, CIRCL). Core DB reads complete before outbound I/O; enrichments run in parallel with short-lived pool connections (GreyNoise excluded — on-demand only).

**Response:** Bare CVE object (no `data` wrapper), including:

- Core fields from `cves` table
- `watchlist_state`, `watchlist_snooze_until` when the CVE is on the active watchlist (same semantics as list feed)
- `kev_date_added`, `kev_due_date`, `kev_vendor_project`, `kev_vulnerability_name`, `kev_ransomware_use` (boolean), `kev_cwes[]`, `techniques[]`, `public_exploits[]`, `exploit_provenance` (object — see below), `greynoise_configured` (boolean), `greynoise_scans[]` (always `[]` on detail — use on-demand endpoint), `otx_pulses[]`, `otx_configured`, `osv_packages[]`

**Error responses:**

- `400` — invalid CVE ID format
- `404` — CVE not found

**Notes:** Includes `has_ai_context`, `atlas_techniques[]`, and `atlas_case_studies[]` when MITRE ATLAS data is present in the DB. Enrichment failures return `200` with empty arrays.

**Provenance (additive — added in V1.3):** `affected_products_source` is `""` for official CPE-derived (or unset) product lists and `"llm"` when `affected_products` was filled by the env-gated LLM product extraction job for an NVD-unanalyzed CVE. Official CPE data supersedes LLM output on the next NVD sync and clears the marker. The field also appears on items returned by `GET /api/cves` and `GET /api/cves/export`.

---

### GET /api/cves/{cve_id}/drawer

**Description:** Aggregate on-open drawer payloads in one round trip — sentences, EPSS history, related CVEs, related Incidents/News mentions, correlation, and momentum. Used by `DetailDrawer` on open (#436).

**Auth:** Required (session cookie).

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `sector` | str | `""` | User industry sector for correlation actor matching |

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "sentences": { },
  "epss_history": { },
  "related": { },
  "related_news": [
    {
      "title": "CISA Adds CVE-2024-0001 to KEV",
      "source": "CISA Advisories",
      "url": "https://www.cisa.gov/…",
      "publishedAt": "2026-07-01T00:00:00+00:00",
      "kind": "news"
    }
  ],
  "correlation": { },
  "momentum": { }
}
```

Sub-objects match the shapes returned by `GET /api/cves/{cve_id}/sentences`, `/epss-history`, `/related`, `/correlation`, and `/momentum` respectively. Correlation includes `provenance` derived server-side. `related_news` is built from the Incidents feed snapshot (RSS + ATLAS cards that mention this CVE ID); empty list when none.

**Error responses:** `400` invalid CVE ID; `404` CVE not found.

---

### GET /api/cves/{cve_id}/sentences

**Description:** Human-readable intelligence sentences (risk, EPSS, exploits, patch, KEV).

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "risk": "...",
  "exploit_likelihood": "...",
  "public_exploits": "...",
  "patch": "...",
  "kev": "..."
}
```

---

### GET /api/cves/{cve_id}/epss-history

**Description:** EPSS score history for sparkline (30 days).

**Response:** Raw array: `[{"date": "2024-01-01", "score": 0.12}, ...]`

---

### GET /api/cves/{cve_id}/related

**Description:** Related CVEs. Default: shared-product heuristic (last 30 days). When `EMBEDDINGS_ENABLED=1` and the target has a stored vector, returns semantically similar CVEs: prefers **pgvector ANN** (or SQLite BLOB cosine) on the multi-entity `embeddings` table, then legacy `cve_embeddings` NumPy scan. Vectors are written by `embeddings_backfill` / auto-on-ingest (E2 dual-write).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 5 | 1–20 |

**Response:** `{"data": [ related CVE summaries ], "meta": {"method": "product_heuristic" | "embeddings"}}`

**Notes (additive — added in V1.3; E3 upgraded retrieval):**

- `meta.method` reports which path produced the results. Embeddings disabled/absent, target CVE not yet embedded, or zero semantic hits → automatic fallback to `product_heuristic` (the pre-V1.3 response shape, plus `meta`).
- When `meta.method` is `"embeddings"`, each item additionally carries `similarity` (cosine, 0–1, higher = closer). Heuristic items have no `similarity` field.
- Related never runs model inference on the request path — only stored vectors.

---

### GET /api/search/semantic

**Description (E3/E6/E7/E8):** One-box CVE (+ technique + campaign) search — hybrid (default), keyword, or semantic. Keyword uses CVE-id exact / description+summary substring match, plus ATT&CK technique and correlation-campaign label/adversary/malware/tags. Semantic/hybrid may use stored vectors (ANN) when `EMBEDDINGS_ENABLED=1`; free-text semantic embeds the query once (design §7.1). Cold index / disabled embeddings → keyword fallback. Honest `meta.method` reports the path used. Optional filters (`stack` / `severity` / `kev_only`) keep hybrid usable with My Stack / severity chips.

| Param | Type | Default | Description |
|---|---|---|---|
| `q` | str | `""` | Query text (max 500) |
| `mode` | str | `hybrid` | `hybrid` \| `keyword` \| `semantic` |
| `limit` | int | 20 | 1–50 |
| `stack` | str | `null` | Comma-separated stack terms (same matching as `/api/cves`) — narrows **CVE** hits |
| `severity` | str | `null` | Exact severity match on CVE hits (e.g. `CRITICAL`) |
| `kev_only` | bool | `false` | Only KEV CVE hits |

**Query-shape (hybrid):** CVE-id → keyword-first; 1–2 tokens → keyword-heavy RRF; longer natural language → vector-heavier RRF.

**Response:**

```json
{
  "data": [
    {
      "entity_type": "cve",
      "entity_id": "CVE-2024-0001",
      "cve_id": "CVE-2024-0001",
      "score": 0.012345,
      "match_reasons": ["keyword", "vector"],
      "description": "...",
      "severity": "CRITICAL"
    },
    {
      "entity_type": "technique",
      "entity_id": "T1566.001",
      "technique_id": "T1566.001",
      "name": "Spearphishing Attachment",
      "tactic": "initial-access",
      "match_reasons": ["keyword"],
      "score": 0.01
    },
    {
      "entity_type": "campaign",
      "entity_id": "camp_ab12cd34ef56",
      "campaign_id": "camp_ab12cd34ef56",
      "label": "APT29 cloud spearphish",
      "adversary": "APT29",
      "lifecycle": "active",
      "member_count": 3,
      "confidence": "high",
      "match_reasons": ["keyword"],
      "score": 0.01
    }
  ],
  "meta": {
    "method": "hybrid",
    "mode_requested": "hybrid",
    "query_shape": "long",
    "includes_techniques": true,
    "includes_campaigns": true,
    "stack_terms": ["nginx"],
    "severity": null,
    "kev_only": false
  }
}
```

`meta.method` values: `hybrid` \| `keyword` \| `keyword_first` \| `semantic` \| `keyword_fallback`.
Technique hits (E6) appear when keyword/vector matches ATT&CK catalog rows.
Campaign hits (E8) appear for non-retracted `correlation_campaigns` (keyword + ANN).
`stack` / `severity` / `kev_only` filter **CVE** hits only (techniques/campaigns remain typed hits).

**Auth:** Analyst session **or** search service token (`Authorization: Bearer briefr_search_…` — E5).

---

### Search service tokens (E5)

Admin-managed tokens for agent/script retrieval. Plaintext shown **once** at create; bcrypt hash at rest.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/search-tokens` | List tokens (prefix, scopes, last_used; never plaintext) |
| `POST` | `/api/admin/search-tokens` | Create — body `{ "name": "…" }`; response includes `token` once |
| `DELETE` | `/api/admin/search-tokens/{id}` | Soft-revoke |

**Bearer allowlist:** `GET /api/search/semantic`, `GET /api/cves/{cve_id}`, `GET /api/cves/{cve_id}/related`, `GET /api/cves/{cve_id}/drawer`. All other routes → 403 for search tokens.

**Rate limit:** `RATE_LIMIT_SEARCH_TOKEN_PER_MINUTE` (default 30), dedicated bucket.

**Transport:** `Authorization: Bearer briefr_search_<secret>`

---

### GET /api/cves/{cve_id}/momentum

**Description:** Momentum score 0–1 and signal breakdown.

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "momentum_score": 0.45,
  "momentum_signals": [
    { "type": "epss_rising", "description": "...", "contribution": 0.35 }
  ]
}
```

---

### GET /api/otx/pulses/{pulse_id}/iocs

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 10 | 1–50 |

**Response:** `{"data": {"iocs": [], "ips": [], "indicators": []}}`

**Error responses:** `503` — `OTX_API_KEY` not configured

---

## IOC Lookup

### POST /api/ioc/lookup

**Description:** Multi-source IOC enrichment with 6-hour server cache.

**Body:**

```json
{
  "value": "1.2.3.4",
  "type": "ip",
  "greynoise": false
}
```

`type` must be `ip`, `hash`, or `domain`. `value` max 512 chars.

**Response:** Result object with `cached` boolean, VT/AbuseIPDB fields, optional `greynoise`, `malwarebazaar`, `urlhaus`, `otx`, template `*_sentence` fields, `sources_missing[]`.

**Error responses:**

- `400` — missing/invalid value or type
- `422` — body validation
- `429` — rate limit exceeded (`RATE_LIMIT_IOC_PER_MINUTE`, default 30/min per client IP); `Retry-After` header gives seconds until the next allowed request

### GET /api/ioc/watchlist

**Description:** List the signed-in user's saved IOC watchlist entries.

**Auth:** Required (`require_user` session).

**Response:** `{ "items": [{ "id", "user_id", "ioc_type", "ioc_value", "label", "created_at" }] }`

### POST /api/ioc/watchlist

**Description:** Add or update a watchlist entry (upsert on `(user_id, ioc_type, ioc_value)`).

**Auth:** Required.

**Body:**

```json
{
  "value": "evil.example",
  "type": "domain",
  "label": "Phishing C2"
}
```

`type` must be `ip`, `hash`, or `domain`. `value` max 512 chars; `label` optional (max 200).

**Response:** `{ "item": { ... } }`

**Error responses:** `400` — invalid type/value

### DELETE /api/ioc/watchlist/{entry_id}

**Description:** Remove one watchlist row owned by the signed-in user.

**Auth:** Required.

**Response:** `{ "deleted": true, "id": <entry_id> }` — `404` when not found.

**UI:** IOC tab → watchlist panel (save from lookup result; list/remove when signed in).

**Scheduler (local mirrors + retro-match):**

| Job id | Default schedule | Env gates | Writes |
|---|---|---|---|
| `threatfox_sync` | Every 24h (`THREATFOX_SYNC_INTERVAL_HOURS`) | `ABUSECH_AUTH_KEY` | `threatfox_iocs` |
| `vulncheck_kev_sync` | Every 24h (`VULNCHECK_KEV_SYNC_INTERVAL_HOURS`) | `VULNCHECK_API_KEY` | `cves.is_vulncheck_exploited` |
| `ioc_retro_match` | Daily cron (`IOC_RETRO_MATCH_HOUR`/`MINUTE`, default 04:00) | — | dispatches `ioc_watchlist_hit` webhooks |

Retro-match joins `ioc_watchlist` against local `otx_pulse_iocs` and `threatfox_iocs` (no live IOC lookup). Optional webhook event: `ioc_watchlist_hit` (dedupe key `{user_id}:{ioc_value}:{source}`). Message body includes OTX **campaign** context when the pulse maps to `correlation_campaigns` (label, lifecycle, linked CVE count, confidence) and ThreatFox **severity** fields (`confidence_level`, malware, threat type, first seen) when present.

---

## ATLAS & Case Studies

### GET /api/atlas/techniques

**Response:** `{"data": [ tactic groups ], "source": "MITRE ATLAS"}`

---

### GET /api/atlas/casestudies

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | 1–100 |

**Response:** `{"data": [ studies with technique_details ], "source": "MITRE ATLAS"}`

---

### GET /api/case-studies/news

**Description:** Server-side RSS aggregation for Incidents tab.

**Response:** `{"data": [ news cards ], "errors": [ per-source errors ]}`

---

### GET /api/case-studies/feed

**Description:** Combined Incidents tab feed — served from a **precomputed snapshot** rebuilt by the scheduler every `INCIDENT_FEED_REFRESH_MINUTES` (default 30). The request path is a pure read; a cold cache miss returns immediately with `meta.warming=true` and triggers a background build.

| Param | Type | Default | Description |
|---|---|---|---|
| `atlas_limit` | int | 80 | 1–100 ATLAS studies to include |

**Response:** `{"data": [ merged news + atlas cards ], "errors": [ per-source errors ], "meta": {...}}` — cards sorted by `publishedAt` descending. `meta` carries `refreshed_at` (snapshot build time), `stale` (older than 2× refresh interval), `warming` (snapshot being built), and `refresh_interval_minutes`.

---

## Risk & Correlation

### POST /api/cves/{cve_id}/risk

**Description:** Canonical ADR-002 scoring for one CVE — Threat Score, Environment
tier, Operational Priority band, legacy v1.1b under `legacy_risk_v11b`, plus
momentum. Optional body `profile` / `assets` personalise Environment.

**OP escalations (W3):** EPSS from `cves.epss_score` and rising-EPSS momentum
signals (`momentum_signals[].type == "epss_rising"`) may bump OP one band per
ADR-002 addendum (HIGH/MED + EPSS ≥ 0.5 + env ≥ POSSIBLE; or rising EPSS
P3→P2). Threat formula unchanged; low EPSS never lowers KEV/CRIT P1.
Correlation-based OP escalation is **not** computed on this path (E1-2) — the
drawer may apply campaign escalation client-side when correlation data arrives.

**Exposure flags (W5):** optional `profile` fields `internet_facing` (bool),
`criticality` (`MISSION_CRITICAL`|`IMPORTANT`|`SUPPORTING`), plus optional
`privileged_service` / `ot_safety` (bool). These modify **OP and/or SSVC
only** — never Threat. Absent → pre-W5 behaviour. OP (`operational-priority-1.2`):
KEV/CRIT + `internet_facing` + env ≠ `NO_MATCH` prefers P1 when band would be P2.

**SSVC annotation (W4):** response includes parallel `ssvc` object from
`scoring/ssvc.py` (`version` `ssvc-annotation-1.0`). Outcomes are exactly
`Act` | `Attend` | `Track*` | `Track`. Computed after Threat / Environment / OP;
does **not** change Threat math or replace the OP P-band. W5 profile
`internet_facing` / `criticality` (and optional privileged/OT flags) are
passed into SSVC factors / mission prevalence when present.

**Response shape (ADR-002 + W4 + W5):**

```json
{
  "cve_id": "CVE-2024-0001",
  "threat": { "version": "threat-1.0", "score": 84.0, "band": "CRIT", "components": {} },
  "environment": { "version": "environment-1.0", "tier": "CONFIRMED", "evidence_label": "…" },
  "operational_priority": { "version": "operational-priority-1.2", "band": "P1", "rationale": "…" },
  "ssvc": {
    "version": "ssvc-annotation-1.0",
    "outcome": "Act",
    "factors": {
      "exploitation": "active",
      "technical_impact": "total",
      "mission_prevalence": "high",
      "environment_tier": "CONFIRMED",
      "threat_band": "CRIT",
      "internet_facing": true,
      "criticality": "MISSION_CRITICAL",
      "privileged_service": null,
      "ot_safety": null
    },
    "path": "active+high→Act"
  },
  "legacy_risk_v11b": {},
  "momentum": {},
  "hasProfile": true,
  "momentumScore": 0.0
}
```

**P↔SSVC documentation crosswalk (OP remains primary):** P1↔Act, P2↔Attend,
P3↔Track*, P4↔Track.
### GET /api/cves/{cve_id}/greynoise-scans

On-demand GreyNoise Community lookups for IPv4 addresses found in the CVE
description and reference URLs. **Not** called by `GET /api/cves/{cve_id}` —
preserves the 50 lookups/week free-tier quota. Intel tab loads this when the
analyst clicks **Load GreyNoise scanning**.

**Response:**

```json
{
  "configured": true,
  "scans": [
    {
      "ip": "1.2.3.4",
      "classification": "benign",
      "name": "...",
      "sentence": "...",
      "link": "https://viz.greynoise.io/ip/1.2.3.4"
    }
  ]
}
```

When `GREYNOISE_API_KEY` is unset: `{"configured": false, "scans": []}`.

### GET /api/cves/{cve_id}/correlation

| Param | Type | Default | Description |
|---|---|---|---|
| `sector` | str | `""` | User industry for actor sector matching |

**Response:** Campaign / infrastructure / actor correlation graph for the CVE.
Correlation-based OP escalation is applied separately (E1-2 / temporary FE merge
after `/risk`) — this route does not recompute Threat.

```json
{
  "cve_id": "CVE-2024-0001",
  "campaigns": [
    {
      "campaign_id": "camp_abc123",
      "label": "Ransomware wave",
      "members": ["CVE-2024-0001", "CVE-2024-0002"],
      "confidence": "medium",
      "confidence_factors": [{"factor": "same_pulse", "reason": "Co-tagged in the same OTX pulse"}],
      "evidence": [{"type": "same_pulse", "pulse_id": "...", "pulse_name": "..."}],
      "boosters": {"kev": ["CVE-2024-0002"], "exploit": []},
      "summary": "Linked to 1 other CVE(s) via OTX pulse ...",
      "attribution_conflict": false
    }
  ],
  "infrastructure": [
    {
      "cve_id_b": "CVE-2024-0002",
      "shared_ip_count": 1,
      "shared_domain_count": 0,
      "shared_hash_count": 1,
      "shared_url_count": 0,
      "confidence": "high",
      "confidence_factors": [{"factor": "ioc_type", "value": "HASH", "reason": "Hash-type indicator"}],
      "evidence": [{"type": "shared_indicator", "ioc_type": "HASH", "value": "..."}],
      "summary": "Shares 1 hash with CVE-2024-0002 via OTX pulses."
    }
  ],
  "actor": [
    {
      "actor_name": "APT99",
      "actor_sectors": ["finance"],
      "user_sector_match": false,
      "confidence": "medium",
      "source": "mitre_attack",
      "technique_overlap": 0.67
    }
  ],
  "temporal": [],
  "boosters": {"kev": ["CVE-2024-0002"], "exploit": []},
  "priority": {
    "score": 31.0,
    "components": [{"signal": "campaign", "points": 31.0, "sentence": "Linked to a medium-confidence campaign (Ransomware wave). Includes a KEV-listed member."}]
  },
  "otx_status": "ok",
  "meta": {"engine_version": "2.0", "cache_hit": false},
  "computed_at": "2024-01-01T00:00:00+00:00"
}
```

Per-campaign `boosters` reflect KEV/exploit signals among that campaign's members (excluding the anchor CVE); the top-level `boosters` is the union across all campaigns. As of CORR-PR-4, boosters no longer move campaign *confidence* (they don't make the pulse-link itself more certain) — they contribute to this same response's `priority.components[].signal == "campaign"` score instead. Campaign confidence is `medium` at the same-pulse co-tag baseline, `high` when strong (hash/domain) shared indicators back it, independent of member count. `actor` matches require MITRE ATT&CK technique overlap ≥ `CORRELATION_MITRE_MIN_OVERLAP` (default 0.25); `technique_overlap` is `matched / total CVE techniques`, and confidence is `medium` at ≥0.5 else `low`.

**`confidence_factors`** (CORR-PR-5, additive): on both `campaigns[]` and `infrastructure[]` items, an ordered list of `{factor, value?, reason}` objects tracing every step that moved the confidence level — e.g. `ioc_type` (base level), `confirmation` (GreyNoise/MalwareBazaar/URLhaus), `degree` (shared-IOC hub penalty, CORR-PR-3), `noise_ip`, `same_pulse`, `shared_indicators`, `attribution_conflict`. `why_not_higher` is kept for compatibility and equals the last factor's `reason` when present. The drawer's connection panel renders each factor's `reason` as a bulleted "why this level" list.

Cached 6 hours in `feed_cache` (`correlation:v2:{cve}:{sector}`). When `CORRELATION_PRECOMPUTE_ENABLED=1`, the handler prefers a scheduler-written row in `correlation_cve_snapshot` (cheap indexed read); actor sector matching still runs live when `sector` is set. Nightly job backfills snapshots for tier-prioritized CVEs (`CORRELATION_PRECOMPUTE_MAX_PER_RUN`, default 500). Hub IOCs above `CORRELATION_HUB_CVE_PULSE_CAP` are excluded from shared-IOC joins. On engine error, returns empty arrays + `"error"` string.

### POST /api/cves/{cve_id}/correlation/suppress

Dismiss a campaign or infrastructure finding for this CVE.

**Body:**

```json
{
  "scope": "campaign_id",
  "key": {"campaign_id": "camp_abc123"},
  "reason": "optional analyst note"
}
```

Scopes: `campaign_id`, `cve_pair`, `pulse_id`, `infrastructure`.

### DELETE /api/cves/{cve_id}/correlation/suppress

Query params: `scope` plus `campaign_id`, `cve_id_b`, or `pulse_id` depending on scope.

### GET /api/cves/{cve_id}/correlation/feedback

List persisted analyst feedback for correlation findings on this CVE.

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "feedback": [
    {
      "id": 1,
      "cve_id": "CVE-2024-0001",
      "scope": "campaign_id",
      "scope_key": "camp_abc123",
      "verdict": "confirm",
      "reason": "validated in case",
      "created_by": "analyst@example.com",
      "created_at": "2026-07-14 12:00:00"
    }
  ]
}
```

Verdicts: `confirm`, `reject`, `resolve_conflict`. Scopes match suppress:
`campaign_id`, `cve_pair`, `pulse_id`, `infrastructure`.

### POST /api/cves/{cve_id}/correlation/feedback

Record analyst confirm/reject/resolve feedback. Upserts on
`(cve_id, scope, scope_key, verdict)`; writes an `audit_log` entry
(`correlation.feedback.<verdict>`).

**Body:**

```json
{
  "scope": "campaign_id",
  "key": {"campaign_id": "camp_abc123"},
  "verdict": "confirm",
  "reason": "optional analyst note",
  "created_by": "analyst@example.com"
}
```

### DELETE /api/cves/{cve_id}/correlation/feedback

Query params: `scope`, `verdict`, plus `campaign_id`, `cve_id_b`, or `pulse_id`
depending on scope. Writes `correlation.feedback.delete` to `audit_log`.

### GET /api/correlation/clusters

| Param | Type | Default | Description |
|---|---|---|---|
| `stack` | str | `null` | Comma-separated stack terms (same matching as `/api/cves`) |
| `cve_id` | str | `null` | Return only campaigns that include this CVE (max 32 chars) |
| `limit` | int | `20` | Max clusters (1–100) |
| `include_stale` | bool | `false` | Include `lifecycle=stale` campaigns |

**Response:**

```json
{
  "meta": {
    "stack_terms": ["log4j"],
    "limit": 20,
    "include_stale": false,
    "count": 1
  },
  "clusters": [
    {
      "campaign_id": "camp_abc123",
      "primary_pulse_id": "pulse-1",
      "label": "Ransomware wave",
      "adversary": "APT-TEST",
      "confidence": "medium",
      "lifecycle": "active",
      "member_count": 3,
      "stack_member_count": 2,
      "watchlisted_member_count": 1,
      "members": ["CVE-2024-0001", "CVE-2024-0002", "CVE-2024-0003"],
      "members_on_stack": ["CVE-2024-0001", "CVE-2024-0002"],
      "watchlisted_members": ["CVE-2024-0002"]
    }
  ]
}
```

`members` is the full campaign CVE list (ordered). `members_on_stack` /
`watchlisted_members` are subsets for ranking and UI priority when opening a
representative CVE in the drawer.

Clusters rank by stack overlap, then watchlisted members, then size and lifecycle.

---

## Detection

### GET /api/cves/{cve_id}/detection

| Param | Type | Default | Description |
|---|---|---|---|
| `product` | str | `""` | Product name for generated Sigma title |

**Auth:** Required (session cookie).

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "technique_ids": ["T1190"],
  "sigma_rules": [],
  "elastic_rules": [],
  "has_community_rules": false,
  "generated_sigma": "...",
  "generated_sigma_meta": {
    "briefr_basis": "cwe",
    "status": "experimental",
    "compose_basis": "template_fallback"
  },
  "detection_context": null,
  "siem_queries": { },
  "yara_rules": [],
  "evidence": {
    "cve_id": "CVE-2024-0001",
    "technique_ids": ["T1190"],
    "detection_class": "path_traversal",
    "community": {
      "sigma_rules": [],
      "elastic_rules": [],
      "has_community_rules": false
    },
    "artifacts": [],
    "observables": { "nuclei_urls": [], "yara_rules": [] },
    "detection_context": null,
    "evidence_summary": {
      "community_count": 0,
      "artifact_count": 0,
      "nuclei_count": 0,
      "primary_source": "none"
    }
  },
  "provenance": { }
}
```

Sigma/Elastic rules cached 24h. `generated_sigma` is always returned as a labeled supplement (D5). Additive `evidence` (DC-1) is the shared evidence pack. DC-2 emits Sigma/SIEM/YARA from that pack via `emit_composed_detection` — artifact paths/keywords are injected into Sigma and SIEM queries; `generated_sigma_meta.compose_basis` is `community|nuclei_artifacts|yara|template_fallback`. No LLM.

---

## Forge (V1.3 MVP)

All Forge endpoints are local and deterministic — content comes from the bundled
template library (`backend/detection/`), no outbound HTTP, no API quota.

### GET /api/forge/coverage

**Description:** MITRE coverage map — techniques linked to CVEs in the database,
each with exposure counts and a rule status.

| Param | Type | Default | Description |
|---|---|---|---|
| `stack` | str | — | Comma-separated stack terms (same matching as `/api/cves` `stack`); filters CVE exposure to the analyst's stack |

**Response:**

```json
{
  "techniques": [
    {
      "technique_id": "T1190",
      "name": "Exploit Public-Facing Application",
      "tactic": "Initial Access",
      "url": "https://attack.mitre.org/techniques/T1190/",
      "cve_count": 12,
      "kev_count": 3,
      "max_epss": 0.97,
      "pack_count": 1,
      "status": "yours",
      "case_study_count": 2
    }
  ],
  "meta": {
    "generated_at": "2026-06-12T12:00:00Z",
    "stack_terms": ["log4j"],
    "counts": { "yours": 1, "community": 4, "gap": 7 },
    "technique_total": 12
  }
}
```

Status semantics: `yours` = at least one saved hunt pack for the technique;
`community` = the bundled template library covers the technique (sub-techniques
inherit the parent's coverage); `gap` = neither. Techniques with saved packs stay
on the map even when the stack filter matches none of their CVEs. Sorted by
tactic, gaps first within each tactic.

`case_study_count` (Forge Redesign FR-3): number of distinct MITRE ATLAS case
studies linked to this technique's CVEs. ATLAS and ATT&CK are separate
technique taxonomies, so the join is through the shared CVE, not a technique
ID match.

### GET /api/hunt-packs/{technique_id}

**Description:** Hunt pack content for one ATT&CK technique.

**Validation:** `technique_id` must match `T####` or `T####.###` → else 400.
404 when the technique is unknown (no `mitre_techniques` row, no packs, no CVE links).

**Response:**

```json
{
  "technique": { "technique_id": "T1190", "name": "...", "description": "...",
                 "tactic": "...", "url": "...", "platforms": [], "detection": "..." },
  "status": "community",
  "packs": [ { "id": 1, "technique_id": "T1190", "cve_id": "CVE-2021-44228",
               "title": "...", "priority": "critical", "sigma_yaml": "...",
               "siem_queries": {}, "log_patterns": [], "notes": "",
               "created_at": "...", "updated_at": "...",
               "cwe_ids": ["CWE-502"], "cvss_score": 10.0, "epss_score": 0.97 } ],
  "siem_queries": { "elastic_kql": {"query": "...", "notes": "..."}, "splunk_spl": {},
                    "sentinel_kql": {}, "qradar_aql": {} },
  "log_patterns": ["..."],
  "case_studies": [ { "study_id": "AML.CS0001", "name": "...", "summary": "...",
                      "target": "AI system", "incident_date": "2021-12-15" } ],
  "linked_cve_total": 1,
  "linked_cves": [ { "cve_id": "CVE-2021-44228", "severity": "CRITICAL",
                     "cvss_score": 10.0, "epss_score": 0.97, "is_kev": true,
                     "published": "...",
                     "description": "Apache Log4j2 JNDI features allow remote code execution." } ]
}
```

`linked_cves` is capped at 20, ordered KEV first, then EPSS, then recency.
`linked_cve_total` is the uncapped map count (may exceed the preview list).
Each `linked_cves[].description` is truncated to ~180 characters for inventory rows.
`packs[].cwe_ids`/`cvss_score`/`epss_score` and `case_studies` are Forge
Redesign FR-3 additions — read from the same `cve_technique_map` join already
used for `linked_cves`, no extra query. `case_studies` capped at 5, matched
through the pack's/technique's linked CVEs (see `case_study_count` note above).

### POST /api/hunt-packs/generate

**Description:** Generate a detection pack for a CVE and persist the CVE→pack
link in `hunt_packs`. Idempotent — regenerating the same (technique, CVE) pair
updates the row in place.

**Body:**

```json
{ "cve_id": "CVE-2021-44228", "technique_id": "T1190" }
```

`technique_id` is optional — defaults to the CVE's primary technique, then the
first `cve_technique_map` entry; 400 when the CVE has no technique link and none
is supplied. 400 on malformed CVE ID, 404 when the CVE is not in the database.

**Response:**

```json
{
  "pack": { "...": "same shape as packs[] above" },
  "created": true,
  "compose_basis": "nuclei_artifacts",
  "evidence_summary": {
    "community_count": 0,
    "artifact_count": 1,
    "nuclei_count": 0,
    "primary_source": "nuclei_artifacts"
  }
}
```

Content is emitted via the detection composer (`include_community=False` — no
GitHub Sigma/Elastic search on this path). Artifact evidence injects into Sigma
and SIEM; `compose_basis` is `nuclei_artifacts|yara|template_fallback` (community
basis appears on Detect, not Forge generate).

Pack priority is derived from the CVE: KEV → `critical`; CVSS ≥ 9.0 or
EPSS ≥ 0.5 → `high`; CVSS ≥ 7.0 or EPSS ≥ 0.1 → `medium`; else `low`.

### GET /api/hunt-packs

**Description:** List saved hunt packs (Forge Redesign FR-1 — Library view).
Analyst-facing; distinct from the pre-existing `GET/DELETE /api/admin/hunt-packs*`
operator utility (no filters, no audit log, no 404 on missing delete) — that one
is untouched by this endpoint.

| Param | Type | Default | Description |
|---|---|---|---|
| `technique_id` | str | — | Exact match; validated `T####`/`T####.###` → 400 |
| `cve_id` | str | — | Exact match, case-insensitive |
| `priority` | str | — | One of `low`/`medium`/`high`/`critical` → else 400 |
| `q` | str | — | Case-insensitive substring match on `title` |
| `limit` | int | 50 | 1–200 |
| `offset` | int | 0 | — |

**Response:** `{ "packs": [ ...same shape as generate's pack... ], "total": N }`,
ordered by `updated_at DESC`.

### DELETE /api/hunt-packs/{pack_id}

**Description:** Delete one saved hunt pack. 404 when `pack_id` doesn't exist.
Writes an `audit_log` entry (`action: "hunt_pack_deleted"`, `target:
"{technique_id}/{cve_id}"`).

**Response:** `{ "ok": true }`

### GET /api/threat-model/scenarios

**Description:** V1.5 environment threat scenarios — stack-scoped ATT&CK technique
cards with plain-language scenario text, CVE evidence, coverage status (same
semantics as Forge), and suggested mitigation actions (patch KEV, generate hunt pack,
close detection gap).

| Param | Type | Default | Description |
|---|---|---|---|
| `stack` | str | — | Comma-separated stack terms (asset profile products / feed stack); required for non-empty results |

**Response:**

```json
{
  "scenarios": [
    {
      "technique_id": "T1190",
      "name": "Exploit Public-Facing Application",
      "tactic": "initial-access",
      "url": "https://attack.mitre.org/techniques/T1190/",
      "coverage_status": "gap",
      "community_template": true,
      "cve_count": 3,
      "kev_count": 1,
      "scenario": "An adversary may use …",
      "evidence_cves": [{ "cve_id": "CVE-…", "is_kev": true, "epss_score": 0.5 }],
      "mitigations": [{ "type": "patch", "label": "…", "cve_id": "CVE-…", "technique_id": "T1190" }]
    }
  ],
  "meta": {
    "generated_at": "2026-07-09T09:00:00Z",
    "stack_terms": ["nginx"],
    "profile_required": false,
    "technique_total": 12,
    "gap_count": 4
  }
}
```

UI: Forge tab → **Threat scenarios** view (requires loaded asset profile).

### POST /api/proof/run

**Description:** V1.5 file-based rule proof bench — run a Sigma rule (or explicit
patterns) against pasted log lines. No live SIEM or ClickHouse required.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `lines` | string[] | yes | Log lines (1–5000); empty lines ignored in counts |
| `sigma_yaml` | string | one of | Sigma rule YAML; keywords/selection strings extracted for matching |
| `patterns` | string[] | one of | Explicit substring patterns (case-insensitive) |
| `max_samples` | int | no | Max sample hits returned (default 10, max 50) |

**Response:**

```json
{
  "total_lines": 3,
  "hit_count": 1,
  "miss_count": 2,
  "hit_rate": 0.3333,
  "patterns": ["../", "/etc/passwd"],
  "false_positive_hints": ["Vulnerability scanners"],
  "sample_hits": [
    {
      "line_number": 2,
      "line": "GET /../../etc/passwd HTTP/1.1",
      "matched_patterns": ["../"]
    }
  ]
}
```

400 when neither `sigma_yaml` nor `patterns` is provided, or when no match
patterns can be extracted. UI: Forge → hunt pack panel → **Rule proof bench**
(after a pack is saved).

### GET /api/detection-backlog

**Description:** V1.5 KEV-driven detection backlog — open items where a stack-matched
KEV CVE maps to an ATT&CK technique with **gap** coverage (no saved hunt pack and
no bundled community template).

| Param | Type | Default | Description |
|---|---|---|---|
| `status` | str | `open` | `open`, `dismissed`, or `all` |
| `stack` | str | — | Comma-separated stack terms; defaults to operator effective stack |

**Response:** `{ "items": [...], "meta": { "count", "stack_terms", "generated_at" } }`

Each item includes `cve_id`, `technique_id`, `technique_name`, `priority`,
`status`, `kev_due_date`, and CVE severity scores.

UI: Forge tab → **Backlog** view (requires asset profile / stack).

### POST /api/detection-backlog/{item_id}/dismiss

Soft-dismiss a backlog row. Dismissed items are not recreated on later KEV sync.

**Response:** `{ "item": { ... } }` — 404 when the id does not exist.

Backlog rows are created by the KEV metadata sync job when CVEs newly enter KEV
and match the operator stack, and by the weekly `kev_backlog_reconcile` job.
Optional webhook event: `kev_backlog`.

---

## Security Architecture (TM-0→TM-5 committed program; TM-6 analyst framework workspaces)

Mounted at `/api/security-architecture/*`, session auth required (analyst+). Backed by
the Security Architecture Corpus (SAC) — versioned YAML under
`backend/security_architecture/corpus/` — loaded and validated by
`security_architecture/corpus_loader.py`. Every corpus record carries `origin:
generated | curated | live`: generated records (components, API endpoint inventory,
scheduler jobs, DB tables, `self_stack.yaml` dependency terms, and TM-4's
`graphs/architecture.json`) are emitted by `scripts/generate_security_corpus.py` from
live code introspection and drift-tested in CI
(`backend/tests/test_security_architecture_corpus.py`) — renaming a router, scheduler
job, table, or dependency breaks the build until the script is re-run.
Curated records: controls got their first real security-review pass in TM-3;
trust boundaries in TM-4; TM-5 seeded `security_decisions.yaml` (2 records mapped from
the real ADRs in `docs/decisions/`), `abuse_cases.yaml` (6 entries, each citing real
protection code as evidence), and `reviews.yaml` (the program's own TM-3/TM-4/TM-5
review passes). `risks.yaml` stays intentionally empty — no real risk-register judgment
pass has happened yet; its only non-empty content is `live` rows. `live` rows
(self-stack risk register entries, and `reviews` section's audit-log security events)
are computed at read time, never stored — see `security_architecture/merge.py`.

**Staleness decay (TM-5, spec §4.1):** every curated row carries a `stale: boolean`
field (`security_architecture/merge.py::annotate_stale`) — `true` once
`review_date` is more than 90 days in the past. The Overview "Controls Active" tile is
a ratio (`active / total`, spec §5.1) that excludes stale controls from **both**
numerator and denominator — the module's one live percentage a curated record feeds.
The same `stale` flag drives the frontend STALE badge and the PDF export disclaimer, so
all three never disagree.

Frontend: `/security-architecture` route, header tab **ARCH**, three-panel shell
(`frontend/src/pages/security-architecture/`) mirroring Forge/Admin — manifest-driven
left nav, Overview center workspace with drill-through evidence tiles. TM-3 adds
dedicated MITRE ATT&CK and Threat Scenarios section components. TM-4 adds the
interactive pan/zoom System Architecture graph, Trust Boundaries flow cards, Attack
Surface endpoint list, and the first working context rail (populated on graph node
selection). TM-5 adds dedicated Risk Register (`RiskRegisterSection.jsx`, AdminDataGrid,
CSV + PDF export), Decision Records (`DecisionsSection.jsx`), Abuse Cases
(`AbuseCasesSection.jsx`, in-page search), Review History (`ReviewHistorySection.jsx`,
curated + live audit-log timeline), Stale Records (`StaleRecordsSection.jsx`,
cross-section drill-through), and global search (`GlobalSearch.jsx`, topbar) — this
closes the committed program (TM-0→TM-5, 5 PRs, 11 sections) per
`docs/planning/specs/threat-modeling-security-architecture.md` §8.

**TM-6 framework workspaces (analyst threat-intelligence lens).** Four framework sections
— `cwe`, `owasp`, `capec`, `stride` — ship as live views over the **user's own** ingested
CVE corpus rather than the spec §4.5 self-stack. Each is a projection of one live
aggregation: the CWE weakness classes present in `cves.cwe_ids` across a selected
**Scope** (`all` | `stack` | `watchlist` | `kev`). CWE is direct; OWASP Top 10 2021,
CAPEC (MITRE CWE→CAPEC), and STRIDE (documented heuristic) are reference-mapping
projections of those same CWEs (`security_architecture/frameworks/reference.py`). CWEs
with no mapping are reported in an explicit `unmapped` bucket so the parts reconcile with
the whole, and every count drills through to its `example_cves`. No new matching/scoring
code — `stack` scope reuses `routers.cves._stack_match_clause`. The self-referential
posture material (self-stack exposure, control active-flags, ASVS/NIST CSF verification)
stays operator/self-monitoring scope, not the analyst frameworks.

### GET /api/security-architecture/manifest

**Response:** `{ "version": 1, "schema_version": 1, "last_reviewed": "...", "sections": [...] }`

`sections[]` includes `mitre_attack` — it has no corpus file of its own; it's served
entirely from live `mitre_techniques`/`cve_technique_map` DB data.

### GET /api/security-architecture/overview

**Response:**

```json
{
  "generated": {"components": 20, "api_endpoints": 151, "scheduler_jobs": 26, "db_tables": 42},
  "curated": {"trust_boundaries": 2, "controls": 10, "abuse_cases": 6, "threat_scenarios": 0,
              "security_decisions": 2, "risks": 0, "reviews": 3},
  "self_exposure": {"count": 0, "kev_count": 0, "critical_count": 0, "terms": ["fastapi", "react", "..."]},
  "last_reviewed": "2026-07-13",
  "tiles": [
    {"id": "components", "label": "System Components", "value": 20,
     "help": "...", "section": "components", "filter": {"type": "components"}},
    "... 5 more (endpoints, scheduler_jobs, db_tables, open_risks, critical_open_risks)",
    {"id": "controls", "label": "Controls Active", "value": "10/10",
     "help": "...", "section": "controls", "filter": {}},
    {"id": "review_freshness", "label": "Review Freshness", "value": 0, "unit": "days",
     "help": "...", "section": "reviews", "filter": {}},
    {"id": "mitre_detection_coverage", "label": "MITRE Detection Coverage", "value": "3/12",
     "help": "...", "section": "mitre_attack", "filter": {}},
    {"id": "self_cve_exposure", "label": "Self CVE Exposure", "value": 0,
     "help": "...", "section": "risks", "filter": {"origin": "live"}},
    {"id": "unreviewed_endpoints", "label": "Unreviewed Endpoints", "value": 0,
     "help": "...", "section": "attack_surface", "filter": {}},
    {"id": "stale_records", "label": "Stale Records", "value": 0,
     "help": "...", "section": "stale", "filter": {}}
  ]
}
```

Counts and ratios only — no scoring, no letter grades, per spec's "no arithmetic
invented for this module" tile rule (§5.1). Each tile's `section`/`filter` is the exact
drill-through target for `GET /section/{id}` below (`stale_records`'s target is
`GET /stale`, TM-5). `mitre_detection_coverage` is `"<covered>/<total>"` (techniques
with a hunt pack or bundled template, out of every technique mapped to a CVE, global —
not stack-scoped) or `"—"` when no technique is mapped yet. `self_cve_exposure` is the
live self-stack KEV/critical CVE count (§4.5). `controls` (TM-5) is
`"<active>/<total>"` — live-flag-verified active controls out of total, **excluding
stale controls from both sides** (spec §5.1, §4.1 staleness decay).

### GET /api/security-architecture/mitre

**Query params:** `stack` (optional, comma-separated terms, same matching as `/api/cves`).

ATT&CK coverage matrix. Reuses `routers.forge.build_coverage_map` — the exact query and
status logic `GET /api/forge/coverage` uses, not a reimplementation, so this endpoint's
output is byte-identical to Forge's for the same `stack`. **Response:** see
`GET /api/forge/coverage` above (`meta.counts.{gap,community,yours}`, `techniques[]`
with `technique_id`, `name`, `tactic`, `cve_count`, `kev_count`, `pack_count`, `status`).

### GET /api/security-architecture/threat-scenarios

**Query params:**

| Param | Effect |
|-------|--------|
| `stack` | Comma-separated stack terms (Forge parity — same as `/api/threat-model/scenarios`) |
| `self_stack` | `true` → ignores `stack`, uses the generated self-stack terms (§4.5) instead |

Wraps `threat_model.scenarios.build_threat_scenarios` — output is identical in shape to
`GET /api/threat-model/scenarios` for the same effective stack (plus `meta.catalog`:
`"stack"` or `"self-stack"`). No new matching/scoring code. The self-stack is computed
once at corpus-generation time (`scripts/generate_security_corpus.py`), never
recomputed per request.

### GET /api/security-architecture/frameworks/{framework_id}

Analyst framework workspace over the user's live threat surface (TM-6). `framework_id` ∈
`cwe | owasp | capec | stride` (any other value → 404).

**Query params:**

| Param | Effect |
|-------|--------|
| `scope` | Live CVE set: `all` (default), `stack`, `watchlist`, `kev` |
| `stack` | Comma-separated terms overriding the saved stack for `scope=stack` (same matching as `/api/cves`) |
| `severity` | Narrow to one of `CRITICAL`/`HIGH`/`MEDIUM`/`LOW` |

For `scope=stack` with no saved stack (resolved softly from the `briefr_at` cookie) and no
`stack=` override, the response is empty with `unavailable: true` and a `reason` — never a
silent whole-corpus fallback. Aggregation is bounded (KEV + most-recent first); the
response reports `sample_size` vs `total_in_scope` and a `truncated` flag so a capped
count is visibly capped.

**Response (shape varies by framework):**

```json
{
  "framework": "owasp",
  "owasp_version": "2021",
  "items": [
    {"id": "A03", "title": "A03:2021 – Injection", "summary": "...",
     "cve_count": 210, "kev_count": 8, "cwe_ids": ["CWE-79", "CWE-89"],
     "example_cves": [{"cve_id": "CVE-2024-0001", "is_kev": true, "severity": "CRITICAL"}]}
  ],
  "unmapped": {"cve_count": 12, "kev_count": 0, "example_cves": ["..."], "note": "..."},
  "scope": "all", "terms": [], "total_in_scope": 5031, "sample_size": 5031,
  "cve_with_cwe": 4400, "truncated": false, "unavailable": false, "reason": null
}
```

`cwe` items carry `cwe_id`/`name`/`owasp`/`stride`; `capec` items carry `capec_id`/`name`/
`cwe_ids`; `stride` adds `mapping: "heuristic"`. The `unmapped` bucket is present on
owasp/capec/stride (CVEs whose CWEs have no mapping in the reference set).

### GET /api/security-architecture/graph/architecture

System architecture graph (spec §5.2, TM-4). Returns `graphs/architecture.json`
verbatim — no read-time filtering, so the response's node set always matches the
generator's output exactly.

**Response:**

```json
{
  "version": 1,
  "clusters": [{"id": "api", "label": "API Routers", "kind": "component"}, "..."],
  "nodes": [
    {"id": "routers-cves", "label": "routers.cves", "kind": "component", "cluster": "api",
     "endpoint_count": 22, "source_refs": [{"type": "file", "ref": "backend/routers/cves/"}]},
    {"id": "table:cves", "label": "cves", "kind": "table", "cluster": "database",
     "source_refs": [{"type": "table", "ref": "cves"}]},
    {"id": "job:nvd_incremental_sync", "label": "NVD Incremental Sync", "kind": "job",
     "cluster": "scheduler", "source_refs": [{"type": "job", "ref": "nvd_incremental_sync"}]}
  ],
  "edges": [
    {"id": "routers-cves->table:cves", "source": "routers-cves", "target": "table:cves",
     "kind": "references_table"}
  ]
}
```

No `x`/`y` layout coordinates — presentation isn't a code fact, so it's excluded from
the drift-checked generated file. The frontend (`ArchitectureGraphSection.jsx`) computes
a deterministic cluster+index grid layout at render time.

### GET /api/security-architecture/graph/attack-surface

Attack surface = generated endpoint inventory × linked controls, **counts only** — no
composite score (spec §8 TM-4). Read-time join of `api_inventory.yaml` against curated
`controls.yaml`'s `related_apis` glob patterns (exact path, `<prefix>/*`, or `*`).

**Response:**

```json
{
  "total_endpoints": 151,
  "reviewed_endpoints": 151,
  "unreviewed_endpoints": 0,
  "endpoints": [
    {"method": "GET", "path": "/api/cves", "component_id": "routers-cves",
     "linked_control_count": 1, "linked_control_ids": ["parameterized-sql"]}
  ]
}
```

### GET /api/security-architecture/context/{node_id}

Context-rail payload for a selected architecture-graph node selection (spec §5.2, TM-4).
`node_id` is the graph's own node id (`routers-cves`, `table:cves`,
`job:nvd_incremental_sync`).

**Response (component node):** node fields + `summary`, `owner`, `endpoints[]` (from
`api_inventory`, filtered by `component_id`), `controls[]` (glob-matched via the same
logic as `/graph/attack-surface`), `tables[]` (outbound `references_table` edges),
`outbound`/`inbound` edge lists.

**Response (table node):** node fields + `referenced_by[]` (reverse of `outbound` — every
component with an edge into this table), `outbound`/`inbound`.

**Response (job node):** node fields + `outbound`/`inbound` (always empty today — no
generated job→table edge exists yet).

404 when `node_id` isn't in the current architecture graph.

### GET /api/security-architecture/section/{section_id}

**TM-2 shell convenience** — a generic read of any manifest data section's corpus rows,
added so Overview tile clicks land on real pre-filtered rows without building typed
endpoints ahead of the sections that need them. Superseded per-section by spec §4.4's
typed endpoints as later phases ship live sections — an intentional, documented
divergence, not the final API shape.

**Path:** `section_id` — one of manifest.yaml's `sections[]` excluding `overview`,
`mitre_attack`, `system_architecture`, and `attack_surface` (which have their own typed
endpoints above): `components`, `trust_boundaries`, `controls`, `abuse_cases`,
`threat_scenarios`, `security_decisions`, `risks`, `reviews`. None of these has a
dedicated typed endpoint — TM-5's frontend components (`RiskRegisterSection.jsx`,
`DecisionsSection.jsx`, `AbuseCasesSection.jsx`, `ReviewHistorySection.jsx`,
`TrustBoundariesSection.jsx`) each render this generic read's rows with their own
typed table/timeline/card layout instead of a plain list.

**Query params (all optional):**

| Param | Applies to | Effect |
|-------|------------|--------|
| `type` | `components` only | Switches generated collection: `components` (default) \| `endpoints` \| `jobs` \| `tables` |
| `status` | any | Exact match on record `status` field |
| `severity` | any | Exact match on record `severity` field |
| `origin` | any | Exact match on record `origin` field (`generated` \| `curated` \| `live`) |
| `stale` | any | `true` → only curated records past `review_date + 90d` |

**TM-3 live enrichment:**

- `controls` rows gain a live `active: boolean` flag (`security_architecture/merge.py::resolve_control_active`)
  resolved from each control's `live_flag` (e.g. `BACKUP_ENABLED`) against the current
  runtime environment; a control with no `live_flag` is structural and always reads
  `active: true`.
- `risks` rows gain live-derived entries (`origin: "live"`) auto-computed from KEV/
  critical CVE hits on the generated self-stack (§4.5) — each carries `matched_term`,
  `cve_id`, `is_kev`, and the CVE's real `severity` (never synthesized). These rows
  can't be closed by hand; they disappear when the underlying query stops matching.
  `?stale=true` never includes them (only curated rows carry a `review_date`).
  Risks responses also include additive `live_self_stack` stats:
  `candidate_rows` (query candidates before score filter), `scored_matches` (rows scoring
  55/100), `admitted` (rows returned after cap), and `cap` (`50`).

**TM-5 live enrichment:**

- Every row is annotated with `stale: boolean` (`security_architecture/merge.py::
  annotate_stale`) — `true` for curated rows whose `review_date` is more than 90 days
  in the past; always `false` for generated/live rows. This is the single source of
  truth the frontend STALE badge, the Overview "Controls Active" ratio, and the PDF
  export disclaimer all read — computed once, never re-derived client-side.
- `reviews` rows gain live-derived entries (`origin: "live"`) from `audit_log`, filtered
  to security-relevant action prefixes (`auth.`, `backup.`, `database.`,
  `diagnostics.integrity`, `config.apply`, `system.restart`, `scheduler.`) and reusing
  `redact.mask_audit_log_target` — the same table and masking rule as the Admin Audit
  Log view (`routers/admin/diagnostics.py::get_audit_log`), not a duplicate.

**Response:** `{ "section": "...", "type": "...", "available_types": [...], "count": N, "items": [...], "live_self_stack": { "candidate_rows": 0, "scored_matches": 0, "admitted": 0, "cap": 50 } }`

`live_self_stack` is present on `section_id=risks` only.

404 when `section_id` isn't a manifest section.

### GET /api/security-architecture/stale

**TM-5** (spec §5.1 "Stale Records" tile drill-through, §9.6 acceptance). Every curated
record across every section past the 90-day review window, each tagged with the
`section`/`type` it belongs to. Not a manifest nav section of its own — reached only via
the Overview tile (`StaleRecordsSection.jsx`), same convention as `components` fanning
across the generated collections.

**Response:** `{ "count": N, "items": [{ ...record, "section": "controls", "type": "" }, ...] }`

### GET /api/security-architecture/search

**TM-5** (spec §5.17). Global search over the corpus (components, endpoints, jobs,
tables, trust boundaries, controls, abuse cases, threat scenarios, decisions, risks,
reviews) plus live MITRE technique names — a bounded scan over the already
mtime-cached corpus (`security_architecture/merge.py::search_corpus`) plus one MITRE
query, not an index subsystem.

**Query params:** `q` (required for non-empty results; empty/missing → `{"count": 0}`).

**Response:** `{ "query": "...", "count": N, "results": [{ "id": "...", "title": "...", "summary": "...", "type": "controls", "section": "controls" }, ...] }`

---

## AI Summary

### POST /api/ai/summary

**Description:** Executive summary for PDF export only.

**Auth:** Required (`require_user` session cookie). Unauthenticated callers get `401`.

**Body:**

```json
{
  "cves": [],
  "iocs": [],
  "actors": [],
  "investigation_duration": 1
}
```

**Response:**

```json
{
  "executive_summary": "...",
  "key_findings": ["..."],
  "confidence": "high",
  "source": "groq"
}
```

`source` is the provider that produced the summary (`groq`, `gemini`, `cerebras`, `openrouter`) or `template`. Never raises — always returns usable text.

---

### GET /api/ai/summary

**Description:** Discovery hint for POST usage.

**Response:** `{"detail": "Use POST /api/ai/summary with JSON body: ..."}`

---

### POST /api/investigation/summary

**Description:** Legacy investigation PDF summary. Maps `items[]` to CVE/IOC/actor payloads and delegates to the same multi-provider LLM router (template fallback) as `POST /api/ai/summary`.

**Auth:** Required (`require_user` session cookie). Unauthenticated callers get `401`.

**Request body:** `{ "items": [{ "type": "cve|ioc|actor|technique", "id": "...", "description": "...", "pivotFrom": null }], "duration_minutes": 1 }`  
**Validation:** `duration_minutes` must be `1`–`10080` (same range as `POST /api/ai/summary` `investigation_duration`).

**Response:** Same shape as `POST /api/ai/summary` (`executive_summary`, `key_findings`, `confidence`, `source`).

**Notes:** Prefer `POST /api/ai/summary` for new integrations; this route exists for backward compatibility.

---

## Scheduler & Admin

**Authentication:** all `POST /api/refresh*` routes require an authenticated session (`briefr_at` cookie) with the `admin` role — 401 without a session, 403 for non-admin roles. The legacy admin-key header was removed (Sprint A0).

**Audit:** each accepted refresh writes an `audit_log` row (`action` = `refresh.full|nvd|kev|epss|mitre`; `actor` is the logged-in username).

**Rate limiting:** all `POST /api/refresh*` routes share one token bucket per client IP (`RATE_LIMIT_REFRESH_PER_MINUTE`, default 10/min). Over the limit → `429` with `Retry-After` (seconds). The bucket is consumed before the auth check, so unauthenticated bursts cannot bypass it.

### POST /api/refresh

**Description:** Full ingest (NVD → KEV → EPSS) in background.

**Response:** `{"status": "ok", "message": "..."}`

**Error responses:** `401` — not authenticated; `403` — admin role required; `409` — ingest already running; `429` — rate limit exceeded (`Retry-After` header)

---

### POST /api/refresh/nvd

### POST /api/refresh/kev

### POST /api/refresh/epss

**Error responses:** `401` — not authenticated; `403` — admin role required; `409` — ingest already running; `429` — rate limit exceeded (`Retry-After` header)

---

### POST /api/refresh/mitre

**Description:** Background MITRE ATT&CK + ATLAS refresh.

**Response:** `{"status": "ok", "message": "MITRE ATT&CK + ATLAS refresh started in background"}`

**Error responses:** `401` — not authenticated; `403` — admin role required; `429` — rate limit exceeded (`Retry-After` header)

---

### GET /api/kev/deadlines

| Param | Type | Default | Description |
|---|---|---|---|
| `sort` | str | `recent` | `recent` (date_added DESC) or `urgent` (due_date ASC) |

**Response:** `{"data": [ kev_deadlines rows ]}` — each row includes `vendor_project`, `vulnerability_name`, `known_ransomware` (`Known` / `Unknown` / empty), `ransomware_use` (boolean convenience flag), and `cwes` (array of CWE IDs).

**Frontend:** Sidebar KEV deadline list uses `sort=urgent` (soonest `due_date` first) with left accent bars matching feed cards (full `--red` only for overdue / due today / due tomorrow; dim red/amber for later buckets). CVE cards show a **Due in N days** chip when `kev_due_date` is present on the list payload (same urgency tiers). `BriefCharts.jsx` builds a clickable due-date histogram (Overdue / 0–7d / 8–14d / 15–30d / 31d+) from the same endpoint; bar clicks emit `onBucketClick({ bucket, start, end })` (date range in UTC, not wired to filters yet).

---

### GET /api/version

**Description:** Deployed application version. `commit` and `built_at` are stamped into `backend/.build-info.json` by `deploy/briefr-update.sh` at deploy time (both `null` in dev).

**Response:** `{"version": "1.5.0", "commit": "abc1234", "built_at": "2026-06-10T19:00:00Z"}`

---

### GET /api/usage/ioc

**Description:** IOC Lookup outbound quota counters (VT, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus). Full ingest-provider quota (`GET /api/usage`) was removed in AKH-2 — no UI consumed it; see AI Operations and IOC Lookup for operator-facing quota.

---

## Config

### GET /api/config/risk

**Description:** Returns the v1.1b risk score component weights. The frontend
fetches this once at startup to keep weights single-sourced from
`backend/scoring/risk.py`; it falls back to its bundled constants if the
request fails.

**Auth:** Required (`briefr_at`; enforced by `require_user` middleware).

**Response:**

```json
{
  "version": "1.1b",
  "weights": {
    "asset":    0.35,
    "kev":      0.25,
    "epss":     0.15,
    "exploit":  0.10,
    "cvss":     0.10,
    "momentum": 0.05
  }
}
```

**Invariant:** `sum(weights.values()) == 1.0`. The backend validates this at
the source (`scoring/risk.py`); the frontend rejects any payload where the
sum deviates by more than 1 × 10⁻⁶.

---

## Health & Stats

### GET /api/health

| Param | Type | Default | Description |
|---|---|---|---|
| `tz` | str | `DEFAULT_TIMEZONE` env | IANA timezone for display |

**Response:** `status`, `cve_count`, `last_updated`, `nvd_sync_watermark`, `refresh_in_progress`, `ingest`, `feeds.incidents` (`last_refresh`, `stale` — Incidents snapshot freshness), `feeds.sources` (per outbound source: `last_success`, `last_failure`, `last_error`, `consecutive_failures`, `circuit_open` — includes scheduler intel keys `vulnrichment` and `cvelistv5` after their first run; webhook delivery keys `webhook.discord` / `webhook.telegram` / `webhook.generic` after the first alert attempt), schedule hints, server time.

**Note:** webhook destination URLs/tokens are env-configured; admin config masks secrets. Use `GET /api/admin/webhooks/destinations` for enable/event-type state.

---

### GET /api/time

**Response:** UTC and local time objects with epoch.

---

### GET /api/stats

| Param | Type | Default | Description |
|---|---|---|---|
| `frameworks` | str | null | Comma-separated AI/ML tokens (e.g. `tensorflow,pytorch`) for `ai_ml_alerts` count |

**Response:** `critical`, `high`, `kev_count`, `patched`, `last_24h`, `ai_ml_alerts` (0 when `frameworks` omitted). Delta fields (`critical_delta`, `high_delta`, `kev_delta`, `patched_delta`) compare CVE publications in the last 24h vs the prior 24h window.

---

### GET /api/stats/timeline

| Param | Type | Default | Description |
|---|---|---|---|
| `days` | int | 90 | 1–365 |

**Response:** Raw array of `{date, count, critical, kev}` per calendar day (UTC).

---

### GET /api/stats/top-vendors

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 10 | 1–25 vendors returned |

**Response:** `{data: [{vendor, kev_count}], total_kev}` — aggregates `kev_deadlines` by `vendor_project` (falls back to `product`, then `Unknown vendor`). Cached 45s.

**Frontend:** `BriefCharts.jsx` horizontal bar chart (replaces KEV due-date histogram).

---

**Frontend:** `TimelineHeatmap.jsx` (90-day SVG heatmap; all seven weekday row labels S–S). Chart views use Recharts 3 via shared `rechartsTheme` helpers (`BriefCharts.jsx`, admin ops/resource charts); no Chart.js runtime is current.

---

### GET /api/techniques/top

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 10 | 1–50 |

**Response:** `{"data": [ {technique_id, name, cve_count}, ... ]}`

---

## Admin Dashboard — `/api/admin/*`

All admin endpoints require an authenticated session (`briefr_at` cookie) with the `admin` role — 401 without a session, 403 for non-admin roles (Sprint A0). Admin `GET`s use the `RATE_LIMIT_ADMIN_READ_PER_MINUTE` bucket; mutating admin requests share the refresh bucket (`RATE_LIMIT_REFRESH_PER_MINUTE`).

### GET /api/admin/catchup
Returns Catch-up mode status for Admin → Scheduler. Key fields: `active`, `started_at`, `ends_at`, `duration_hours`, `started_by`, `cleared_reason`, `in_wind_down`, `should_start_new_work`, and `api_queue` (`total_queued`, `total_active`, `has_pending`).

### POST /api/admin/catchup/start
Starts a time-boxed Catch-up window. Body accepts either `{ "duration_hours": 6 }` (default 6h, max 24h) or `{ "ends_at": "2026-07-20T23:00:00Z" }`; supplying both is rejected. Response is the status object without `api_queue`. Errors: `400` invalid window; `409` Catch-up already active.

### POST /api/admin/catchup/stop
Ends the active Catch-up window early. Body may be `{}`. Response is the status object with `active: false` and `cleared_reason: "ended_early"`.

### GET /api/admin/retrieval/health
Ops honesty for the live hybrid/embeddings index (Admin → AI operations). Returns flags (`embeddings_enabled`, `auto_on_ingest`, `pgvector_writes`), `model`, `extension_vector` (`present` \| `absent` \| `n/a` on SQLite), `counts` by `entity_type` from the **`embeddings`** table **for the active model**, `pending` (cheap SQL: missing/`migrated:` only — excludes hash-drift), `last_backfill` from `scheduler.last_run.embeddings_backfill`, `last_ingest_tail` from `embeddings.ingest_tail.last` (auto-on-ingest success/error), and optional `degraded.reason` (`disabled` \| `no_vector_extension` \| `cold_index`). No model inference on this path.

### GET /api/admin/system
Returns system health: CVE count, NVD sync age, backup age, DB integrity, scheduler jobs (with `status`, `last_error_message`, `run_history`), feed sources, active locks, recent errors, open circuit count.

### GET /api/admin/correlation/status
Operator diagnostics for the correlation engine: `last_run`, `build_watermark`, campaign totals (`by_lifecycle`, `avg_members`), CVE campaign coverage %, OTX pulse IOC coverage %, IOC sync backlog (`ioc_sync_pending_pulses`), `suppressions_count`, and **`metrics`** (latest nightly `correlation_metrics` row when present: confirmation/rejection rates, orphan ratio, evidence age, etc.). `features.feed_campaign_sort_boost_gated` is true when pinned-peer feed boost requires campaign confidence ≥ MEDIUM and lifecycle ∈ {active, emerging} (CORR-PR-13 / D9).

### GET /api/admin/api-keys/health
Configured external API provider keys (suffix only — never full secrets) and last health-ping results from the `api_key_health_check` scheduler job. Response: `{providers: [{provider, env_key, configured, key_suffix, healthy, status_code, latency_ms, error, last_checked_at}], checked_at}`.

### POST /api/admin/api-keys/health/run
Trigger an immediate health ping sweep for all configured providers. Returns `{ok, stats, providers, checked_at}`. Audit: `api_keys.health.run`.

### GET /api/admin/notifications
Durable operator notification feed for the admin StatusBar panel (#439). Params: `limit` (1–100, default 40). Response: `{events: [{type, summary, created_at, ...}], counts: {audit, api_key_alerts, job_errors}}`. Event types include `audit`, `api_key_unhealthy`, and `job_error` (from `sync_state` job last-run JSON).

### GET /api/admin/storage
Returns disk partition info (`db_partition`, `backup_partition` with free/total/used bytes), DB file size, table row counts, per-table size estimates (`table_sizes`), growth estimate (`growth_estimate`), host disk I/O counters (`disk_io` when available), archive count.

### GET /api/admin/resources
Query `window` = `1d` | `3d` | `7d` | `30d` (default `1d`). Returns utilization telemetry from `resource_metrics` (RB-1 collector, 60s samples):

```json
{
  "window": "7d",
  "sample_count": 1200,
  "postgres_backend": true,
  "degraded": { "code": "ok|empty|sqlite|remote_pg", "message": "..." },
  "series": [ { "ts": "...", "briefr_cpu_pct": 1.2, ... } ],
  "summary": {
    "briefr_cpu_pct": { "peak": 5.1, "peak_at": "...", "avg": 2.0, "low": 0.4 }
  }
}
```

`series` is downsampled server-side to ≤500 points (bucket-average). `summary` aggregates raw rows in the window (peaks are real peaks). On SQLite dev, `pg_*` SQL-derived fields are NULL and `degraded.code` is `sqlite`. When Postgres runs remotely/in a container, process metrics (`pg_cpu_pct`, etc.) may be NULL while SQL stats remain live (`degraded.code` = `remote_pg`).

### POST /api/admin/storage/purge
Body `{target, confirm_text, days_back?}`. Targets: `ioc_cache` (confirm `"clear"`), `feed_cache` (confirm `"clear"`), `epss_history_old` (confirm `"prune"`), `change_history_old` (confirm `"prune"`), `rejected_cves` (confirm `"purge"`), `nvd_watermark` (confirm `"backfill"`), `epss_backfill_reset` (no confirm).
Response: `{ok, rows_deleted, target}`.

### GET /api/admin/storage/export
Streams a consistent SQLite snapshot (`briefr.db`) via `VACUUM INTO` for dev/test. **Not exposed in the admin UI** (removed #429 — use Postgres backups in production). Audit: `storage.db_export`.

### GET /api/admin/db-explorer/tables
Read-only allowlist catalog: `{read_only: true, tables: [{name, label, tier, row_count, columns, filter_columns, required_filter, order_by}]}`. Denied tables are omitted (not 403). Rate limit: 30/min (`db_explorer` bucket) in addition to admin read limits.

### GET /api/admin/database/migrate/status
Migration progress for the SQLite→Postgres one-shot copy. `status` is `idle` | `running` | `done` | `error` | `interrupted`, plus `current_table`, `tables_done`, `tables_total`, `rows_copied`, `started_at`, `finished_at`, `error`, `verification`. PR-R4: every transition is snapshotted to `sync_state` (`migration.last_status`); when the in-memory state is idle the persisted snapshot is returned with `persisted: true`, and a persisted `running` from a process that died mid-migration is reported as `interrupted` with an actionable `error` message.

### GET /api/admin/db-explorer/tables/{table_name}/rows
Paginated read-only rows for one allowlisted table. Params: `limit` (1–100, default 50), `offset` (0–10000), optional `filter_column` + `filter_value` (single-column equality only — no client SQL). `cves` requires `filter_column=cve_id` with a valid CVE ID. Large text/JSON fields may truncate (~2 KB); Tier-2 tables mask sensitive columns (`audit_log.target`, `webhook_delivery_log.error`). Unknown or forbidden tables return **404**. Audit: `db.explorer.browse.{table}` with filter summary — no row bodies.

### GET /api/admin/jobs/outbound

List recent **Procrastinate** durable jobs (Q1). Admin auth required.

**Query:** `limit` (1–200, default 50).

**Response:**
```json
{
  "enabled": false,
  "count": 0,
  "jobs": [
    {
      "id": 1,
      "queue": "briefr",
      "task": "jobs:health_ping",
      "status": "succeeded",
      "scheduled_at": null,
      "attempts": 1,
      "priority": 0,
      "lock": null,
      "queueing_lock": null
    }
  ]
}
```

When `PROCRASTINATE_ENABLED=0` (default), `enabled` is false and `jobs` is empty. No args/payloads are returned (allowlisted fields only).

**UI consumer:** Admin → Data refresh schedule (`SchedulerPage`) renders `OutboundJobsPanel`, which calls this endpoint on mount (limit 50), refreshes manually, and polls every ~15s while the page is visible.

### POST /api/admin/jobs/outbound/ping

Admin-only canary for the durable queue. Defers the no-op `jobs:health_ping` task with a singleton `queueing_lock` so operators can verify queue writes from Admin without running a real sync job. `AlreadyEnqueued` is treated as success. Returns `503` when `PROCRASTINATE_ENABLED=0` or the durable app is unavailable.

Response: `{ok, task, queueing_lock, already_enqueued, message}`. Audit: `jobs.outbound.ping`.

### GET /api/admin/api-usage/metering
Params: `hours` (1–168, default 24). Returns outbound call metering from `api_call_events` (Q2): `{ok, hours, by_source: [{source, calls, ok_calls, last_called_at}], by_actor: [{actor_type, calls}], usage_rollups}`. Every `resilient_request` **attempt** is counted (retries included). Disable with `API_CALL_EVENTS_ENABLED=0`. Events retained 30 days via `cache_retention_cleanup`.

### POST /api/admin/scheduler/run
Body `{job_id}`. Triggers a scheduler job immediately. Returns `409` if job lock is held, `400` if job_id unknown. For `job_id="llm_product_extraction"`, `PROCRASTINATE_ENABLED=1` defers `jobs:llm_product_extraction` with `trigger="manual"` and elevated priority; disabled/unavailable durable queue falls back to the existing scheduler path.
Audit: `scheduler.run.{job_id}`.

### GET /api/admin/config/schema
Returns field metadata for every writable config key: `section`, `type`, bounds, `help_text`, `restart_required`, `apply_strategy` (`immediate` | `scheduler_reschedule` | `restart`), `display_label`, and `unit` (e.g. `h`, `min` for scheduler intervals). Includes `WALLBOARD_TOKEN` under section `security` (kiosk gate — `restart` apply strategy), `RATE_LIMIT_WALLBOARD_PER_MINUTE` under `app` (kiosk polling limit — `restart` apply strategy), and Admin-visible boolean toggles for `CORRELATION_PRECOMPUTE_ENABLED`, `DETECTION_CONTEXT_SYNC_ENABLED`, `DETECTION_CONTEXT_LLM_ENABLED`, and `DETECTION_CONTEXT_NUCLEI_ENABLED`.

### GET /api/admin/config
Returns the current Admin config values grouped by section, with secrets masked. The `ml` section includes env-backed runtime booleans for correlation precompute and detection-context sync/LLM/Nuclei toggles so operators can see the same flags exposed by `/config/schema`.

### POST /api/admin/config
Body `{key, value}`. Writes one key to `.env` and `os.environ`. For `scheduler_reschedule` keys, reschedules affected APScheduler jobs without a full restart. Response includes `apply_strategy`, `warning_restart_required` (when strategy is `restart`), `rescheduled_jobs`, and `message`. Use `POST /config/apply-all` for keys that require a backend restart (including `WALLBOARD_TOKEN`).

### POST /api/admin/config/apply-all
Body `[{key, value}, ...]`. Writes all keys to `.env`, reschedules scheduler interval/cron jobs when applicable, and triggers a graceful backend restart when any changed key has `apply_strategy: restart` (includes `ALLOWED_ORIGINS` / CORS). Returns `400` if any key is not in the allowlist. Response: `{ok, changed_keys, restart_required, rescheduled_jobs, message}`. Audit: `config.apply`.

### GET /api/admin/webhooks/log
Params: `event_type`, `limit`, `offset`. Returns dedupe log `{rows: [{alert_type, target, alerted_at}], total}`. `event_type` accepts canonical names (`kev_alert`, `backup_failure`, `watchlist_alert`, `kev_backlog`, `ioc_watchlist_hit`) and legacy aliases.

### GET /api/admin/webhooks/destinations
Returns `{destinations: [{id, kind, label, enabled, event_types, source, health_source, config}]}` — merged env + DB config. `config` is **masked** (URLs/tokens never returned in full).

### POST /api/admin/webhooks/destinations
Body `{kind, config, id?, label?, enabled?, event_types?}`. Creates a **database-backed** destination (`source: db`). `kind` is `discord`, `telegram`, or `generic`. `id` optional — generated as `{kind}-{uuid}` when omitted; custom ids must match `^[a-z0-9-]{3,64}$` and cannot use reserved env ids (`discord`, `telegram`, `generic`). Config URLs validated with SSRF checks on write. Cap: 20 destinations per kind. Audit: `webhook.destination.create.{id}`.

### PATCH /api/admin/webhooks/destinations/{destination_id}
Body `{enabled?: bool, event_types?: string[], label?: string, config?: object}`. Updates enable flag, subscriptions, and label. **`config` only for `source: db`** destinations (env bootstrap destinations keep secrets in `.env`). Audit: `webhook.destination.update.{id}`.

### DELETE /api/admin/webhooks/destinations/{destination_id}
Query `confirm_text=delete` (see `GET /api/admin/destructive-actions`). Deletes **database-backed** destinations only; env bootstrap ids cannot be deleted (disable via PATCH). Audit: `webhook.destination.delete.{id}`.

### GET /api/admin/webhooks/delivery-log
Params: `destination_id`, `event_type`, `limit`, `offset`. Returns `{rows: [{id, destination_id, event_type, dedupe_key, status, error, attempted_at}], total}`. `error` values are masked on read (URLs and token-like substrings redacted).

### GET /api/admin/webhooks/health
Returns per-destination delivery health merged with destination config: `{destinations: [{id, kind, label, enabled, source, last_status, last_event_type, last_attempt_at, last_success_at, last_failure_at, last_error, ok_24h, failed_24h}]}`. Derived from `webhook_delivery_log` (24h counts, latest attempt). Destinations with no deliveries show zero counts and null timestamps. `last_error` is masked like delivery-log.

### GET /api/admin/ai/operations/models
Read-only model catalog SSOT for LLM task failover chains. Returns `{providers: string[], tasks: {task: [{provider, model, order}]}, env_keys: object}` — no secrets.

### GET /api/admin/ai/operations/overview
Summary for the Admin AI Operations page: recording flag, configured provider count, active LLM circuits, 24h/7d usage rollups from `ai_operations`, feature enablement flags, embeddings vector count, `quota_warnings` (#432). No secrets. Each usage window includes token sums (`input_tokens`, `output_tokens`, `total_tokens`) and `tokens_recorded` (true once a provider that reports usage runs in the window). Cost is not estimated.

### GET /api/admin/ai/operations/providers
Per-provider health snapshot (`circuit_open`, `last_success`, `last_failure`, `last_error`, `consecutive_failures`) plus `configured` from env keys. Each row includes advisory `quota` from rate-limit response headers when available (#432). Sources: `resilient_client` + `get_configured_providers()`.

### GET /api/admin/ai/operations/activity
Params: `limit`, `offset`, optional `task_class`, `provider`. Paginated redacted rows from `ai_operations` — `{rows, total, limit, offset}`. Each row includes `input_tokens`/`output_tokens`/`total_tokens` (null for providers that don't report usage). No prompt text.

### GET /api/admin/ai/operations/{operation_id}/payload
Returns the stored failure payload for a recorded LLM attempt (Program E Task 2): `{operation_id, messages, response_excerpt, task_class, provider, model, created_at}`. `messages` is the redacted parsed message array from `ai_operation_payloads.messages_json`. `404` when no payload row exists for the operation id.

### POST /api/admin/ai/operations/{operation_id}/retry
Manual replay of a stored failure payload through the normal LLM router/recording path. Optional JSON body: `{force?: boolean}` (`false` default).

Response: `{replay_operation_id, success, provider, model, error_class}` from the newly recorded replay row in `ai_operations`.

Behavior:
- Replays use `context_type="replay"` and `context_id=<original operation_id>` for traceability in Activity.
- If the original payload provider circuit is open and `force` is not true, returns `409` with operator guidance (`force=true` bypass).
- Records audit action `ai.operations.retry` (target = original `operation_id`) with replay metadata.

### POST /api/admin/config/webhook-test
Body `{destination_id}` or legacy `{channel}` (`discord` / `telegram` / `generic`). Sends a test message via the SSRF-safe webhook client. **Works on disabled destinations** (connectivity check before enable). Audit: `webhook.test.{destination_id}`.

### POST /api/admin/diagnostics/smoke
Runs in-process smoke checks: CVE count > 0, KEV count > 0, DB integrity, feed health, backup dir writable.
Response: `{ok, checks: [{name, passed, detail}], duration_ms}`.

### POST /api/admin/diagnostics/integrity
Runs the dialect-aware DB integrity probe from `db.integrity`: SQLite uses `PRAGMA integrity_check` + `PRAGMA foreign_key_check`; Postgres uses `pg_catalog` probes for invalid indexes, unvalidated constraints, and FK violations.
Response: `{ok, integrity_ok, foreign_keys_ok, message, foreign_key_violations, backend, method, checks}`.

### POST /api/admin/diagnostics/corpus-drift
Regenerates the security architecture **generated** corpus layer (`components.yaml`, `api_inventory.yaml`, scheduler/DB/self-stack YAML, `graphs/architecture.json`) into a temp directory and diffs against the committed files. Read-only — does not modify the repo.

Response: `{ok, drifted_files: [string], regenerate_command}`. When `ok` is false, `drifted_files` lists paths that differ; run `python scripts/generate_security_corpus.py` and commit. Audit: `diagnostics.corpus_drift` with target `pass` or `fail`.

### GET /api/admin/diagnostics/support-pack
Admin-gated export of a redacted operator support pack (health + logs, no secrets). Suitable for attaching to support tickets or saving via `deploy/briefr-doctor.sh --support-pack`.

Params: `log_limit` (1–500, default 200) — number of ring-buffer log lines to include.

Response: JSON attachment (`Content-Disposition: attachment`) with `{support_pack_version, generated_at, version, environment, health, database, security, correlation, diagnostics: {smoke, integrity}, scheduler, logs}`. Database URLs and log `extra` fields matching secret patterns are redacted. Audit: `diagnostics.support_pack`.

### GET /api/admin/onboarding
First-hour operator checklist with live completion state. Response: `{items: [{id, title, detail, done, hint}], done_count, total_count, complete, dismissed, dismissed_at}`.

### POST /api/admin/onboarding/dismiss
Hide the checklist banner (stored in `sync_state`). Response: `{ok, dismissed_at}`. Audit: `onboarding.dismiss`.

### POST /api/admin/restart
Body `{drain?: bool}`. When `drain=true`: waits up to 120s for all job locks to clear before restarting. Returns `{status: "draining"|"restarting"}`.

### GET /api/admin/logs
Admin-gated read-only tail of the in-process ring buffer (last 500 JSON log lines captured at emit time — no `journalctl` or shell). Shares the refresh token-bucket rate limit.

Params: `limit` (1–500, default 100), `level` (exact match, e.g. `ERROR`), `logger` (exact logger name), `request_id` (exact match), `job_id` (scheduler job id, exact match), `run_id` (scheduler run id from last-run history, exact match), `category` (`Application` | `Scheduler` | `Backup` | `Webhooks` | `Security`), `search` (case-insensitive substring over message, exc_info, job_id, run_id, error_type), `since` / `until` (ISO-8601 UTC bounds, inclusive — lexicographic against entry timestamps).

Response: `{logs: [{ts, level, logger, message, request_id, category, job_id?, run_id?, error_type?, exc_info?, ...}], known_loggers: [...], categories: [...], buffer_capacity: 500}`. Secret-like `extra` fields are redacted to `[REDACTED]` in buffer entries.

### GET /api/admin/audit-log
Params: `limit`, `offset`, `action`, `action_prefix`, `actor`, `q` (substring over action, target, and `metadata_json`). Response rows include optional `metadata` object (parsed from `metadata_json`; secrets masked on read). Append-only — no mutation endpoints.

### GET /api/admin/security
Security panel readout. Response: `{failed_auth_last_24h, environment, posture_warnings: [{flag, message}], rate_limit_enabled, rate_limit_ioc_per_minute, rate_limit_refresh_per_minute, rate_limit_admin_read_per_minute, rate_limit_login_per_minute, rate_limit_auth_refresh_per_minute, top_rate_limit_consumers}`.

`posture_warnings` (Sprint A6) lists every unsafe flag in the current config — `RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, `WALLBOARD_TOKEN unset` — regardless of environment; at startup the same list is logged as one warning per flag when `BRIEFR_ENV=production`.

### `POST /api/admin/feeds/epss/force-resync`

Clears stored EPSS CSV file identity (`sync_state.epss_csv_file_identity`) so the
next scheduled or triggered EPSS sync re-parses and applies scores even if the
remote FIRST CSV.GZ bytes are unchanged. Admin session required.
Returns `{ok, cleared, message}`.

**All other admin endpoints** (`GET/DELETE /api/admin/watchlist*`, `GET/DELETE /api/admin/ioc-cache*`, `GET/DELETE /api/admin/hunt-packs*`, `GET/POST /api/admin/config`, `POST /api/admin/config/webhook-test`, `GET/POST /api/admin/scheduler/*`, `GET/POST /api/admin/feeds/*`, `POST /api/admin/backups/*`, `GET /api/admin/backups`) remain as documented in V1.3; scheduler jobs now include `status` field (ACTIVE/PAUSED/LOCKED/DISABLED), `last_error_message`, and `run_history` (array of last 5 runs).

---

## Wallboard (read-only kiosk — V1.4 Theme 4)

### GET /api/wallboard

Aggregated intel posture payload for the `/wallboard` kiosk view. Built from existing DB state and cached snapshots (`feed_cache` key `wallboard:snapshot`, ~45s TTL). No outbound HTTP on the request path; no admin data or secrets in the response.

**Auth:** when `WALLBOARD_TOKEN` is set, require header `X-BRIEFR-Wallboard-Token` (read-only scope; the `?token=` query param was removed in Sprint A7 — query strings leak into access logs). When unset, the endpoint is open (optional gate — read-only kiosk data only).

**Rate limit:** token bucket (`rate_limit_wallboard`) — default `RATE_LIMIT_WALLBOARD_PER_MINUTE=60` per client IP; 429 + `Retry-After` over the limit.

**Response (additive):**

```json
{
  "meta": {
    "generated_at": "2026-06-19T12:00:00Z",
    "timezone": "Asia/Kolkata",
    "stack_terms": ["log4j"],
    "cached": false
  },
  "kev_on_stack": {
    "count": 3,
    "stack_configured": true,
    "stack_terms": ["log4j"]
  },
  "changes_24h": {
    "since_hours": 24,
    "section_counts": {"epss_movers": 2, "new_kev": 1, "kev_due_soon": 0, "stack_matches": 4},
    "action_queue_count": 6,
    "highlights": [{"cve_id": "CVE-…", "severity": "HIGH", "summary": "…", "reasons": ["epss_mover"], "is_kev": false}]
  },
  "top_risk": {
    "items": [{
      "cve_id": "CVE-…",
      "threat_score": 87.4,
      "op_band": "P1",
      "risk_score": 87.4,
      "severity": "CRITICAL",
      "summary": "…",
      "is_kev": true,
      "epss_score": 0.91
    }]
  },
  "ingest_health": {
    "status": "ok",
    "cve_count": 15234,
    "last_updated": "…",
    "refresh_in_progress": false,
    "open_circuit_count": 0,
    "never_synced_source_count": 1,
    "feeds": {"incidents": {"last_refresh": "…", "stale": false}, "sources": {}},
    "ingest": {}
  },
  "coverage_gaps": {
    "counts": {"yours": 2, "community": 40, "gap": 12},
    "gap_count": 12,
    "top_gaps": [{"technique_id": "T1190", "name": "…", "tactic": "Initial Access", "cve_count": 5, "kev_count": 1}],
    "stack_terms": ["log4j"]
  },
  "headlines": {
    "items": [{"title": "…", "source": "The Hacker News", "published_at": "…"}],
    "meta": {"refreshed_at": "…", "stale": false, "warming": false, "refresh_interval_minutes": 30},
    "error_count": 0
  }
}
```

**`top_risk` ranking (W2):** items are ordered by Operational Priority band (P1 first), then Threat score descending — **not** by legacy v1.1b blend total. Fields: `threat_score` (ADR-002 Threat 0–100), `op_band` (`P1`–`P4`, wallboard uses UNKNOWN environment / no profile), `risk_score` (**alias of `threat_score`** for backward-compatible kiosk clients — no longer the v1.1b total).

---

## OpenAPI / Swagger

FastAPI auto-generates OpenAPI spec at runtime. It is exposed at `/api/openapi.json` outside production only; `BRIEFR_ENV=production` sets `openapi_url=None`, `docs_url=None`, and `redoc_url=None`.

To export:

1. Start backend with `BRIEFR_ENV` unset or set to `development`: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
2. `curl http://localhost:8000/api/openapi.json > docs/openapi.json`
3. Import `openapi.json` into Postman or Swagger UI for interactive docs

The `/api/docs` endpoint (Swagger UI) is available at `http://localhost:8000/api/docs` when running locally.

**NOTE:** `/api/docs`, `/api/redoc`, and `/api/openapi.json` are intentionally unprotected in development; production disables them in `main.py`.

---

## Frontend smoke (CI — no new endpoints)

Beta V1.2 adds Chromium Playwright coverage in GitHub Actions (`playwright-smoke` job). The suite seeds SQLite via `scripts/seed_screenshot_data.py`, serves the built SPA, and exercises existing routes only — for example `GET /api/cves`, `GET /api/stats`, `GET /api/case-studies/feed`, and drawer detail fetches. No request/response shapes change; see `backend/tests/test_playwright_smoke.py`.

