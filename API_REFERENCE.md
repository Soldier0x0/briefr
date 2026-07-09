# BRIEFR API Reference

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Base URL:** `/api` (proxied from Vite dev server at `http://localhost:5173/api` → `http://localhost:8000/api`)  
**Auth:** built-in app login (`briefr_at` session cookie); admin and refresh routes additionally require the `admin` role — see the per-section auth notes below (Sprint A0)  
**Interactive docs:** `GET /api/docs` (Swagger UI), `GET /api/redoc` (ReDoc) — **unprotected; disable in production**

Default error shape (FastAPI): `{"detail": "<message>"}`

**Request IDs:** every response carries an `X-Request-ID` header (echoed from the request when a well-formed `X-Request-ID` is supplied, generated otherwise). The same ID appears as `request_id` in the backend's JSON log lines.

**Rate limiting:** `POST /api/ioc/lookup` and all `POST /api/refresh*` routes are token-bucket rate limited per client IP (defaults: 30/min and 10/min — `RATE_LIMIT_IOC_PER_MINUTE`, `RATE_LIMIT_REFRESH_PER_MINUTE`; `RATE_LIMIT_ENABLED=0` disables). Over the limit → `429` with a `Retry-After` header (whole seconds).

---

## CVE Feed

### GET /api/cves

**Description:** Paginated CVE feed with filters.

**Auth:** None

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

**Error responses:**

- `400` — invalid `severity`, `technique`, or `published_on`
- `422` — invalid query param types (FastAPI validation)

**Notes:** Pinned CVEs sort first (`watchlist.state = 'pin'`), then `published DESC`, severity, EPSS. Active snoozes (`state = 'snooze'` with `snooze_until > now`) are excluded from the default feed; `watchlist_only=true` shows the watchlist including snoozed rows. Stack filter re-sorts page by relevance.

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

**Validation:** `font_scale` ∈ `xsmall|small|medium|large|xlarge`; `density` ∈ `compact|comfortable|spacious`; `poll_interval_seconds` ∈ `15|30|60|120`; booleans for `show_technical_ids`, `utc_time`, `reduce_motion`, `remember_profile_on_server`; `timezone` must be a valid IANA zone. Invalid values → `422`.

**Notes:** `PUT /api/me/stack` updates `profile` only when the `profile` field is present in the body; omitting it preserves the saved inventory. Send `"profile": null` to clear.

---

### GET /api/changes

**Description:** Recent tracked field changes (`cvss_score`, `epss_score`, `is_kev`, `has_poc`).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | 1–500 |
| `field` | str | null | Filter to one tracked field |
| `since_hours` | int | 24 | 1–168 |

**Response:** `{"data": [...], "count": N}` — each change row: `id`, `cve_id`, `field_name`, `old_value`, `new_value`, `detected_at`.

**EPSS noise:** `update_epss_scores` only writes history when the score would display differently at **0.1%** precision (matching the What changed panel). Sub-threshold float jitter (e.g. `0.0001` → `0.0002`, both shown as `0.0%`) is ignored.

**Frontend:** BRIEF tab **What changed** panel (`WhatChangedPanel.jsx`) — field + time-window filter chips; row click opens the CVE drawer; rows with identical formatted old/new values are hidden (legacy noise). `BriefCharts.jsx` uses `field=epss_score&since_hours=168` for the **Top EPSS movers** compact table (top 10 positive deltas, 7-day sparklines per row via `GET /api/cves/{id}/epss-history`, row click opens the drawer). On viewports **≥901px** wide, the panel sits beside the 90-day activity heatmap in a flex row (`brief-intel-row` in `App.jsx`); below 900px they stack full-width (heatmap above). Alternating row shading uses `--surface-sunken`.

**Error responses:** `400` — invalid `field`

---

## CVE Detail & Enrichment

### GET /api/cves/{cve_id}

**Description:** Full CVE detail with live enrichment (scheduler-fed exploits, Sploitus fallback, GreyNoise, OTX, OSV, CIRCL).

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

**Description:** Related CVEs. Default: shared-product heuristic (last 30 days). When `EMBEDDINGS_ENABLED=1` and both the target and candidates have stored vectors, returns semantically similar CVEs instead (NumPy brute-force cosine over `cve_embeddings` vectors).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 5 | 1–20 |

**Response:** `{"data": [ related CVE summaries ], "meta": {"method": "product_heuristic" | "embeddings"}}`

**Notes (additive — added in V1.3):**

- `meta.method` reports which path produced the results. Embeddings disabled/absent, target CVE not yet embedded, or zero semantic hits → automatic fallback to `product_heuristic` (the pre-V1.3 response shape, plus `meta`).
- When `meta.method` is `"embeddings"`, each item additionally carries `similarity` (cosine, 0–1, higher = closer). Heuristic items have no `similarity` field.

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

**Response (v2):**

```json
{
  "cve_id": "CVE-2024-0001",
  "campaigns": [
    {
      "campaign_id": "camp_abc123",
      "label": "Ransomware wave",
      "members": ["CVE-2024-0001", "CVE-2024-0002"],
      "confidence": "medium",
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
  "otx_status": "ok",
  "meta": {"engine_version": "2.0", "cache_hit": false},
  "computed_at": "2024-01-01T00:00:00+00:00"
}
```

Per-campaign `boosters` reflect KEV/exploit signals among that campaign's members (excluding the anchor CVE) and bump campaign confidence one level (capped at `high`) when present; the top-level `boosters` is the union across all campaigns. `actor` matches require MITRE ATT&CK technique overlap ≥ `CORRELATION_MITRE_MIN_OVERLAP` (default 0.25); `technique_overlap` is `matched / total CVE techniques`, and confidence is `medium` at ≥0.5 else `low`.

Cached 6 hours in `feed_cache` (`correlation:v2:{cve}:{sector}`). On engine error, returns empty arrays + `"error"` string.

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

### GET /api/correlation/clusters

| Param | Type | Default | Description |
|---|---|---|---|
| `stack` | str | `null` | Comma-separated stack terms (same matching as `/api/cves`) |
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
      "members_on_stack": ["CVE-2024-0001", "CVE-2024-0002"],
      "watchlisted_members": ["CVE-2024-0002"]
    }
  ]
}
```

Clusters rank by stack overlap, then watchlisted members, then size and lifecycle.

---

## Detection

### GET /api/cves/{cve_id}/detection

| Param | Type | Default | Description |
|---|---|---|---|
| `product` | str | `""` | Product name for generated Sigma title |

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "technique_ids": ["T1190"],
  "sigma_rules": [],
  "elastic_rules": [],
  "has_community_rules": false,
  "generated_sigma": "...",
  "siem_queries": { }
}
```

Sigma/Elastic rules cached 24h. `generated_sigma` only when no community rules found.

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
      "status": "yours"
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
               "created_at": "...", "updated_at": "..." } ],
  "siem_queries": { "elastic_kql": {"query": "...", "notes": "..."}, "splunk_spl": {},
                    "sentinel_kql": {}, "qradar_aql": {} },
  "log_patterns": ["..."],
  "linked_cves": [ { "cve_id": "CVE-2021-44228", "severity": "CRITICAL",
                     "cvss_score": 10.0, "epss_score": 0.97, "is_kev": true,
                     "published": "..." } ]
}
```

`linked_cves` is capped at 20, ordered KEV first, then EPSS, then recency.

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

**Response:** `{ "pack": { ...same shape as packs[] above... }, "created": true }`

Pack priority is derived from the CVE: KEV → `critical`; CVSS ≥ 9.0 or
EPSS ≥ 0.5 → `high`; CVSS ≥ 7.0 or EPSS ≥ 0.1 → `medium`; else `low`.

---

## AI Summary

### POST /api/ai/summary

**Description:** Executive summary for PDF export only.

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

`source` is `groq`, `anthropic`, or `template`. Never raises — always returns usable text.

---

### GET /api/ai/summary

**Description:** Discovery hint for POST usage.

**Response:** `{"detail": "Use POST /api/ai/summary with JSON body: ..."}`

---

### POST /api/investigation/summary

**Description:** Legacy investigation PDF summary. Maps `items[]` to CVE/IOC/actor payloads and delegates to the same Groq → Anthropic → template pipeline as `POST /api/ai/summary`.

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

**Error responses:** `401` — invalid admin key (when configured); `409` — ingest already running; `429` — rate limit exceeded (`Retry-After` header)

---

### POST /api/refresh/nvd

### POST /api/refresh/kev

### POST /api/refresh/epss

**Error responses:** `401` — invalid admin key (when configured); `409` — ingest already running; `429` — rate limit exceeded (`Retry-After` header)

---

### POST /api/refresh/mitre

**Description:** Background MITRE ATT&CK + ATLAS refresh.

**Response:** `{"status": "ok", "message": "MITRE ATT&CK + ATLAS refresh started in background"}`

**Error responses:** `401` — invalid admin key (when configured); `429` — rate limit exceeded (`Retry-After` header)

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

**Response:** `{"version": "1.0.0", "commit": "abc1234", "built_at": "2026-06-10T19:00:00Z"}`

---

### GET /api/usage

**Description:** API quota counters for ingest/enrichment services.

**Response:** `{"as_of_utc": "...", "today_date_utc": "...", "this_month_utc": "...", "services": {...}}`

---

### GET /api/usage/ioc

**Description:** IOC Lookup quota counters (VT, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus).

---

## Config

### GET /api/config/risk

**Description:** Returns the v1.1b risk score component weights. The frontend
fetches this once at startup to keep weights single-sourced from
`backend/scoring/risk.py`; it falls back to its bundled constants if the
request fails.

**Auth:** None

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

**Frontend:** `TimelineHeatmap.jsx` (90-day SVG heatmap; all seven weekday row labels S–S). Chart.js is used only in `BriefCharts.jsx` for the KEV histogram (lazy-loaded Vite chunk; CSP `script-src 'self'` — no CDN).

---

### GET /api/techniques/top

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 10 | 1–50 |

**Response:** `{"data": [ {technique_id, name, cve_count}, ... ]}`

---

## Admin Dashboard — `/api/admin/*`

All admin endpoints require an authenticated session (`briefr_at` cookie) with the `admin` role — 401 without a session, 403 for non-admin roles (Sprint A0). All are rate-limited by the refresh bucket.

### GET /api/admin/system
Returns system health: CVE count, NVD sync age, backup age, DB integrity, scheduler jobs (with `status`, `last_error_message`, `run_history`), feed sources, active locks, recent errors, open circuit count.

### GET /api/admin/correlation/status
Operator diagnostics for the correlation engine: `last_run`, `build_watermark`, campaign totals (`by_lifecycle`, `avg_members`), CVE campaign coverage %, OTX pulse IOC coverage %, IOC sync backlog (`ioc_sync_pending_pulses`), and `suppressions_count`.

### GET /api/admin/storage
Returns disk partition info (`db_partition`, `backup_partition` with free/total/used bytes), DB file size, table row counts, archive count. **Fixes the NaN% bug from V1.3.**

### POST /api/admin/storage/purge
Body `{target, confirm_text, days_back?}`. Targets: `ioc_cache` (confirm `"clear"`), `feed_cache` (confirm `"clear"`), `epss_history_old` (confirm `"prune"`), `change_history_old` (confirm `"prune"`), `rejected_cves` (confirm `"purge"`), `nvd_watermark` (confirm `"backfill"`), `epss_backfill_reset` (no confirm).
Response: `{ok, rows_deleted, target}`.

### GET /api/admin/storage/export
Streams `briefr.db` as `application/octet-stream` download. Audit: `storage.db_export`.

### POST /api/admin/scheduler/run
Body `{job_id}`. Triggers a scheduler job immediately. Returns `409` if job lock is held, `400` if job_id unknown.
Audit: `scheduler.run.{job_id}`.

### POST /api/admin/config/apply-all
Body `[{key, value}, ...]`. Writes all keys to `.env` and triggers a restart. Returns `400` if any key is not in the allowlist. Audit: `config.apply`.

### GET /api/admin/webhooks/log
Params: `event_type`, `limit`, `offset`. Returns dedupe log `{rows: [{alert_type, target, alerted_at}], total}`. `event_type` accepts canonical names (`kev_alert`, `backup_failure`, `watchlist_alert`) and legacy aliases.

### GET /api/admin/webhooks/destinations
Returns `{destinations: [{id, kind, label, enabled, event_types, source, health_source}]}` — merged env + DB config (secrets not included).

### PATCH /api/admin/webhooks/destinations/{destination_id}
Body `{enabled?: bool, event_types?: string[], label?: string}`. Updates per-destination enable flag and event subscriptions. Audit: `webhook.destination.update.{id}`.

### GET /api/admin/webhooks/delivery-log
Params: `destination_id`, `event_type`, `limit`, `offset`. Returns `{rows: [{id, destination_id, event_type, dedupe_key, status, error, attempted_at}], total}`.

### POST /api/admin/config/webhook-test
Body `{destination_id}` or legacy `{channel}` (`discord` / `telegram` / `generic`). Sends a test message via the SSRF-safe webhook client. Audit: `webhook.test.{destination_id}`.

### POST /api/admin/diagnostics/smoke
Runs in-process smoke checks: CVE count > 0, KEV count > 0, DB integrity, feed health, backup dir writable.
Response: `{ok, checks: [{name, passed, detail}], duration_ms}`.

### POST /api/admin/diagnostics/integrity
Runs `PRAGMA integrity_check` and `PRAGMA foreign_key_check`.
Response: `{ok, integrity_ok, foreign_keys_ok, message, foreign_key_violations}`.

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

Params: `limit` (1–500, default 100), `level` (exact match, e.g. `ERROR`), `logger` (exact logger name), `request_id` (exact match), `category` (`Application` | `Scheduler` | `Backup` | `Webhooks` | `Security`).

Response: `{logs: [{ts, level, logger, message, request_id, category, ...}], known_loggers: [...], categories: [...], buffer_capacity: 500}`. Secret-like `extra` fields are redacted to `[REDACTED]` in buffer entries.

### GET /api/admin/audit-log
Params: `limit`, `offset`, `action`, `action_prefix`, `actor`. Use `action_prefix=backup.` for category filters.

### GET /api/admin/security
Security panel readout. Response: `{failed_auth_last_24h, environment, posture_warnings: [{flag, message}], rate_limit_enabled, rate_limit_ioc_per_minute, rate_limit_refresh_per_minute, rate_limit_admin_read_per_minute, rate_limit_login_per_minute, rate_limit_auth_refresh_per_minute, top_rate_limit_consumers}`.

`posture_warnings` (Sprint A6) lists every unsafe flag in the current config — `RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`, `WALLBOARD_TOKEN unset` — regardless of environment; at startup the same list is logged as one warning per flag when `BRIEFR_ENV=production`.

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
    "items": [{"cve_id": "CVE-…", "risk_score": 87.4, "severity": "CRITICAL", "summary": "…", "is_kev": true, "epss_score": 0.91}]
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
    "items": [{"title": "…", "source": "BleepingComputer", "published_at": "…"}],
    "meta": {"refreshed_at": "…", "stale": false, "warming": false, "refresh_interval_minutes": 30},
    "error_count": 0
  }
}
```

---

## OpenAPI / Swagger

FastAPI auto-generates OpenAPI spec at runtime.

To export:

1. Start backend: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
2. `curl http://localhost:8000/openapi.json > docs/openapi.json`
3. Import `openapi.json` into Postman or Swagger UI for interactive docs

The `/api/docs` endpoint (Swagger UI) is available at `http://localhost:8000/api/docs` when running locally.

**NOTE:** `/api/docs` and `/api/redoc` are unprotected — disable or restrict in production (`docs_url=None` in FastAPI constructor).

---

## Frontend smoke (CI — no new endpoints)

Beta V1.2 adds Chromium Playwright coverage in GitHub Actions (`playwright-smoke` job). The suite seeds SQLite via `scripts/seed_screenshot_data.py`, serves the built SPA, and exercises existing routes only — for example `GET /api/cves`, `GET /api/stats`, `GET /api/case-studies/feed`, and drawer detail fetches. No request/response shapes change; see `backend/tests/test_playwright_smoke.py`.
