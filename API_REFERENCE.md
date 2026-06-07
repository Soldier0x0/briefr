# BRIEFR API Reference

**Base URL:** `/api` (proxied from Vite dev server at `http://localhost:5173/api` → `http://localhost:8000/api`)  
**Auth:** None on any endpoint (v1.1 beta)  
**Interactive docs:** `GET /api/docs` (Swagger UI), `GET /api/redoc` (ReDoc) — **unprotected; disable in production**

Default error shape (FastAPI): `{"detail": "<message>"}`

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
| `epss_min` | float | null | Minimum EPSS (0.0–1.0) |
| `search` | str | null | CVE ID exact match or description/summary substring (max 200) |
| `stack` | str | null | Comma-separated product/CVE terms (max 500) |
| `vendors` | str | null | Comma-separated vendor/product terms (max 500) |
| `technique` | str | null | ATT&CK technique ID e.g. `T1190` (max 32) |
| `published_on` | str | null | `YYYY-MM-DD` calendar day filter |
| `summary_only` | bool | false | Only CVEs with enriched plain-English summary |

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
      "updated_at": "2024-01-02 12:00:00"
    }
  ]
}
```

**Error responses:**

- `400` — invalid `severity`, `technique`, or `published_on`
- `422` — invalid query param types (FastAPI validation)

**Notes:** Sorted by `published DESC`, severity, EPSS. Stack filter re-sorts page by relevance.

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

### GET /api/changes

**Description:** Recent tracked field changes (`cvss_score`, `epss_score`, `is_kev`, `has_poc`).

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | 1–500 |
| `field` | str | null | Filter to one tracked field |
| `since_hours` | int | 24 | 1–168 |

**Response:** `{"data": [...], "count": N}`

**Error responses:** `400` — invalid `field`

---

## CVE Detail & Enrichment

### GET /api/cves/{cve_id}

**Description:** Full CVE detail with live enrichment (Sploitus, GreyNoise, OTX, OSV, CIRCL).

**Response:** Bare CVE object (no `data` wrapper), including:

- Core fields from `cves` table
- `kev_date_added`, `techniques[]`, `public_exploits[]`, `greynoise_scans[]`, `otx_pulses[]`, `otx_configured`, `osv_packages[]`

**Error responses:**

- `400` — invalid CVE ID format
- `404` — CVE not found

**Notes:** Does **not** include `atlas_techniques`, `atlas_case_studies`, or `has_ai_context` (known wiring gap). Enrichment failures return `200` with empty arrays.

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

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 5 | 1–20 |

**Response:** `{"data": [ related CVE summaries ]}`

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

## Risk & Correlation

### GET /api/cves/{cve_id}/correlation

| Param | Type | Default | Description |
|---|---|---|---|
| `sector` | str | `""` | User industry for actor sector matching |

**Response:**

```json
{
  "cve_id": "CVE-2024-0001",
  "infrastructure": [],
  "actor": [],
  "temporal": [],
  "computed_at": "2024-01-01T00:00:00+00:00"
}
```

Cached 6 hours in `feed_cache`. On engine error, returns empty arrays + `"error"` string.

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

**Description:** Legacy investigation PDF summary.

**Status:** **BROKEN** — calls undefined `generate_investigation_summary` (`main.py:1331`). Returns 500. Use `POST /api/ai/summary`.

---

## Scheduler & Admin

### POST /api/refresh

**Description:** Full ingest (NVD → KEV → EPSS) in background.

**Response:** `{"status": "ok", "message": "..."}`

**Error responses:** `409` — ingest already running

---

### POST /api/refresh/nvd

### POST /api/refresh/kev

### POST /api/refresh/epss

**Error responses:** `409` — ingest already running

---

### POST /api/refresh/mitre

**Description:** Background MITRE ATT&CK + ATLAS refresh.

**Response:** `{"status": "ok", "message": "MITRE ATT&CK + ATLAS refresh started in background"}`

---

### GET /api/kev/deadlines

| Param | Type | Default | Description |
|---|---|---|---|
| `sort` | str | `recent` | `recent` (date_added DESC) or `urgent` (due_date ASC) |

**Response:** `{"data": [ kev_deadlines rows ]}`

---

### GET /api/usage

**Description:** API quota counters for ingest/enrichment services.

**Response:** `{"as_of_utc": "...", "today_date_utc": "...", "this_month_utc": "...", "services": {...}}`

---

### GET /api/usage/ioc

**Description:** IOC Lookup quota counters (VT, AbuseIPDB, GreyNoise, OTX, MalwareBazaar, URLhaus).

---

## Health & Stats

### GET /api/health

| Param | Type | Default | Description |
|---|---|---|---|
| `tz` | str | `DEFAULT_TIMEZONE` env | IANA timezone for display |

**Response:** `status`, `cve_count`, `last_updated`, `nvd_sync_watermark`, `refresh_in_progress`, `ingest`, schedule hints, server time.

---

### GET /api/time

**Response:** UTC and local time objects with epoch.

---

### GET /api/stats

**Response:** Flat object: `critical`, `high`, `kev_count`, `patched`, `last_24h` (counts).

---

### GET /api/stats/timeline

| Param | Type | Default | Description |
|---|---|---|---|
| `days` | int | 90 | 1–365 |

**Response:** Raw array of `{date, count, critical, kev}` per calendar day (UTC).

---

### GET /api/techniques/top

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 10 | 1–50 |

**Response:** `{"data": [ {technique_id, name, cve_count}, ... ]}`

---

## OpenAPI / Swagger

FastAPI auto-generates OpenAPI spec at runtime.

To export:

1. Start backend: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
2. `curl http://localhost:8000/openapi.json > docs/openapi.json`
3. Import `openapi.json` into Postman or Swagger UI for interactive docs

The `/api/docs` endpoint (Swagger UI) is available at `http://localhost:8000/api/docs` when running locally.

**NOTE:** `/api/docs` and `/api/redoc` are unprotected — disable or restrict in production (`docs_url=None` in FastAPI constructor).
