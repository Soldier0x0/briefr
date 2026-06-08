# BRIEFR Technical Inventory

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Version:** 1.1 beta · **Date:** 2026-06-07

---

## 1. Tech Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| API framework | FastAPI | 0.136.3 | REST API, OpenAPI, validation |
| ASGI server | uvicorn | 0.48.0 | Production HTTP server |
| HTTP client | httpx | 0.28.1 | Async external API calls |
| Scheduler | APScheduler | 3.11.2 | 7 background ingest/correlation jobs |
| Database | SQLite + aiosqlite | 0.22.1 | Local persistence (`briefr.db`) |
| Validation | Pydantic | 2.13.4 | Request/response models |
| Config | python-dotenv | 1.2.2 | `.env` loading |
| YAML | PyYAML | 6.0.2 | ATLAS feed parsing |
| Spreadsheet generation | openpyxl | 3.1.5 | `TECHNICAL_INVENTORY.xlsx` generator script |
| UI framework | React | 18.3.1 | Analyst SPA |
| Build tool | Vite | 5.4.1 | Dev server and production bundle |
| Routing | react-router-dom | 7.16.0 | `/privacy`, `/terms` routes |
| PDF export | jsPDF + html2canvas | 4.2.1 / 1.4.1 | Client-side CVE PDF reports |
| Spreadsheet export | exceljs | 4.4.0 | CVE XLSX export from feed |
| Reverse proxy | nginx | (deploy configs) | TLS termination, static + API proxy |
| CI | GitHub Actions | — | `backend-tests.yml` pytest |

---

## 2. Database Schema

Source: `database.py:init_db()` (lines 20–277) plus inline migrations (280–304).  
`cpe_matches` column on `cves` added via migration `ALTER TABLE cves ADD COLUMN cpe_matches`.

ERD: [`docs/diagrams/schema.mermaid`](docs/diagrams/schema.mermaid)

### cves

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | PRIMARY KEY | CVE identifier |
| description | TEXT | | NVD English description |
| cvss_score | REAL | | CVSS v3 base score |
| severity | TEXT | | CRITICAL/HIGH/MEDIUM/LOW |
| published | TEXT | | ISO publish timestamp |
| modified | TEXT | | ISO last-modified |
| affected_products | TEXT | DEFAULT `'[]'` | JSON array vendor:product |
| mitre_technique | TEXT | | Primary ATT&CK ID from refs |
| summary | TEXT | | Plain-English summary (KEV/OSV) |
| is_kev | INTEGER | DEFAULT 0 | CISA KEV flag |
| epss_score | REAL | | Latest EPSS probability |
| has_poc | INTEGER | DEFAULT 0 | Public PoC/exploit flag |
| patch_available | INTEGER | DEFAULT 0 | Patch reference detected |
| has_ai_context | INTEGER | DEFAULT 0 | AI/ML relevance flag |
| source_urls | TEXT | DEFAULT `'[]'` | JSON reference URLs |
| cwe_ids | TEXT | DEFAULT `'[]'` | JSON CWE list |
| updated_at | TEXT | DEFAULT datetime('now') | Row update time |
| cpe_matches | TEXT | DEFAULT `'[]'` | JSON CPE match objects (migration) |

Indexes: `severity`, `published`, `is_kev`, `epss_score`, `has_poc`

### ioc_cache

| Column | Type | Constraints | Description |
|---|---|---|---|
| value | TEXT | PRIMARY KEY | Normalized IOC value |
| ioc_type | TEXT | NOT NULL | ip/hash/domain |
| result | TEXT | NOT NULL | JSON enrichment result |
| cached_at | TEXT | DEFAULT datetime('now') | TTL anchor (6h reads) |

### kev_deadlines

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | PRIMARY KEY | CVE ID |
| product | TEXT | | KEV product name |
| short_description | TEXT | | CISA short text |
| required_action | TEXT | | Remediation action |
| due_date | TEXT | | Federal due date |
| date_added | TEXT | | KEV catalog add date |
| updated_at | TEXT | DEFAULT datetime('now') | Sync timestamp |

### api_usage

| Column | Type | Constraints | Description |
|---|---|---|---|
| service | TEXT | NOT NULL | Service slug e.g. `nvd` |
| date_utc | TEXT | NOT NULL | YYYY-MM-DD |
| month_utc | TEXT | NOT NULL | YYYY-MM |
| count | INTEGER | DEFAULT 0 | Calls that day |
| | | PRIMARY KEY (service, date_utc) | |

### sync_state

| Column | Type | Constraints | Description |
|---|---|---|---|
| key | TEXT | PRIMARY KEY | e.g. `nvd_last_mod_end` |
| value | TEXT | NOT NULL | Watermark value |
| updated_at | TEXT | DEFAULT datetime('now') | |

### mitre_techniques

| Column | Type | Constraints | Description |
|---|---|---|---|
| technique_id | TEXT | PRIMARY KEY | e.g. T1190 |
| name | TEXT | NOT NULL | Technique name |
| description | TEXT | DEFAULT '' | |
| tactic | TEXT | DEFAULT '' | Tactic name |
| url | TEXT | NOT NULL | attack.mitre.org URL |
| platforms | TEXT | DEFAULT `'[]'` | JSON platforms |
| detection | TEXT | DEFAULT '' | Detection guidance |

### cve_technique_map

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | NOT NULL | |
| technique_id | TEXT | NOT NULL | FK → mitre_techniques |
| | | PRIMARY KEY (cve_id, technique_id) | |

### atlas_techniques

| Column | Type | Constraints | Description |
|---|---|---|---|
| technique_id | TEXT | PRIMARY KEY | e.g. AML.T0051 |
| name | TEXT | NOT NULL | |
| description | TEXT | DEFAULT '' | |
| tactic | TEXT | DEFAULT '' | |
| tactic_id | TEXT | DEFAULT '' | |
| url | TEXT | NOT NULL | atlas.mitre.org URL |

### atlas_case_studies

| Column | Type | Constraints | Description |
|---|---|---|---|
| study_id | TEXT | PRIMARY KEY | |
| name | TEXT | NOT NULL | |
| summary | TEXT | DEFAULT '' | |
| summary_full | TEXT | DEFAULT '' | |
| techniques | TEXT | DEFAULT `'[]'` | JSON technique IDs |
| target | TEXT | DEFAULT '' | |
| date | TEXT | DEFAULT '' | |
| study_type | TEXT | DEFAULT '' | |
| cve_ids | TEXT | DEFAULT `'[]'` | JSON CVE IDs |

### cve_atlas_map

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | NOT NULL | |
| technique_id | TEXT | NOT NULL | FK → atlas_techniques |
| | | PRIMARY KEY (cve_id, technique_id) | |

### epss_history

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | NOT NULL | |
| score | REAL | NOT NULL | EPSS at snapshot |
| recorded_date | TEXT | NOT NULL | |
| | | PRIMARY KEY (cve_id, recorded_date) | |

### cve_exploits

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| cve_id | TEXT | NOT NULL | |
| title | TEXT | NOT NULL DEFAULT '' | |
| type | TEXT | NOT NULL DEFAULT 'poc' | |
| source | TEXT | NOT NULL DEFAULT '' | |
| url | TEXT | NOT NULL DEFAULT '' | |
| published_date | TEXT | DEFAULT '' | |
| fetched_at | TEXT | DEFAULT datetime('now') | |

### feed_cache

| Column | Type | Constraints | Description |
|---|---|---|---|
| cache_key | TEXT | PRIMARY KEY | e.g. `sploitus:CVE-...` |
| result | TEXT | NOT NULL | JSON blob |
| cached_at | TEXT | DEFAULT datetime('now') | TTL checked at read |

### cve_change_history

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| cve_id | TEXT | NOT NULL | |
| field_name | TEXT | NOT NULL | Tracked field |
| old_value | TEXT | NOT NULL DEFAULT '' | |
| new_value | TEXT | NOT NULL DEFAULT '' | |
| detected_at | TEXT | DEFAULT datetime('now') | |

### otx_cve_pulses

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | NOT NULL | |
| pulse_id | TEXT | NOT NULL | |
| pulse_name | TEXT | NOT NULL DEFAULT '' | |
| author | TEXT | DEFAULT '' | |
| created_date | TEXT | DEFAULT '' | |
| adversary | TEXT | DEFAULT '' | |
| malware_families | TEXT | DEFAULT `'[]'` | JSON |
| ioc_count | INTEGER | DEFAULT 0 | |
| tags | TEXT | DEFAULT `'[]'` | JSON |
| fetched_at | TEXT | DEFAULT datetime('now') | |
| | | PRIMARY KEY (cve_id, pulse_id) | |

### otx_pulse_iocs

| Column | Type | Constraints | Description |
|---|---|---|---|
| pulse_id | TEXT | NOT NULL | |
| ioc_type | TEXT | NOT NULL DEFAULT '' | |
| ioc_value | TEXT | NOT NULL | |
| description | TEXT | DEFAULT '' | |
| fetched_at | TEXT | DEFAULT datetime('now') | |
| | | PRIMARY KEY (pulse_id, ioc_type, ioc_value) | |

### correlation_infrastructure

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id_a | TEXT | NOT NULL | |
| cve_id_b | TEXT | NOT NULL | |
| shared_ip_count | INTEGER | DEFAULT 0 | |
| confidence | TEXT | DEFAULT 'low' | |
| detected_at | TEXT | DEFAULT datetime('now') | |
| | | PRIMARY KEY (cve_id_a, cve_id_b) | |

### correlation_actor

| Column | Type | Constraints | Description |
|---|---|---|---|
| cve_id | TEXT | NOT NULL | |
| actor_name | TEXT | NOT NULL | |
| actor_sectors | TEXT | DEFAULT `'[]'` | JSON |
| user_sector_match | INTEGER | DEFAULT 0 | |
| confidence | TEXT | DEFAULT 'low' | |
| detected_at | TEXT | DEFAULT datetime('now') | |
| | | PRIMARY KEY (cve_id, actor_name) | |

### correlation_temporal

| Column | Type | Constraints | Description |
|---|---|---|---|
| vendor | TEXT | PRIMARY KEY | |
| current_week_count | INTEGER | DEFAULT 0 | |
| average_weekly_count | REAL | DEFAULT 0 | |
| anomaly_score | REAL | DEFAULT 0 | |
| detected_at | TEXT | DEFAULT datetime('now') | |

### mitre_groups

| Column | Type | Constraints | Description |
|---|---|---|---|
| group_id | TEXT | PRIMARY KEY | e.g. G0016 |
| name | TEXT | NOT NULL | |
| aliases | TEXT | DEFAULT `'[]'` | JSON |
| description | TEXT | DEFAULT '' | |
| sectors | TEXT | DEFAULT `'[]'` | JSON targeted sectors |
| url | TEXT | DEFAULT '' | |

### group_technique_map

| Column | Type | Constraints | Description |
|---|---|---|---|
| group_id | TEXT | NOT NULL | |
| technique_id | TEXT | NOT NULL | |
| | | PRIMARY KEY (group_id, technique_id) | |

---

## 3. Scheduler Jobs

All registered in `scheduler.py:start_scheduler()` (lines 546–660). Default timezone: `SCHEDULER_TIMEZONE=Asia/Kolkata` unless noted.

| Job ID | Schedule | Fetches from | Writes to | Failure behaviour | Idempotent? |
|---|---|---|---|---|---|
| `nvd_incremental_sync` | Every `NVD_SYNC_INTERVAL_HOURS` (default 1h) | NVD API | `cves`, `sync_state`, `cve_change_history`, `feed_cache`, `cve_exploits` | Log error; watermark not advanced if commit fails | Yes — upsert + lock skip |
| `kev_metadata_sync` | Every `KEV_SYNC_INTERVAL_MINUTES` (default 15m) | CISA KEV JSON | `kev_deadlines`, `cves.is_kev` | Log error; prior data retained | Yes — upsert |
| `epss_score_sync` | Every `EPSS_SYNC_INTERVAL_HOURS` (default 6h) | EPSS CSV/API | `cves.epss_score`, `epss_history` | Log error | Yes — upsert history |
| `weekly_mitre_refresh` | Cron Sun `MITRE_REFRESH_HOUR:MINUTE` (default 02:00 sched TZ) | MITRE STIX, CTID CSV, ATLAS YAML | `mitre_*`, `atlas_*`, `cve_*_map`, `has_ai_context` | Log error; partial commit possible | Mostly — replace atlas tables |
| `otx_nightly_correlation` | Cron `OTX_CORRELATION_HOUR:MINUTE` in `OTX_CORRELATION_TIMEZONE` (default 02:00 IST) | OTX API | `otx_*`, `feed_cache` | Skipped if no key; log on error | Yes — replace per CVE |
| `incident_news_refresh` | Every 4 hours | 6 RSS feeds | `feed_cache` (`incident_rss:*`) | Per-source errors logged | Yes — cache overwrite |
| `nightly_correlation` | Cron `CORRELATION_HOUR:MINUTE` in `CORRELATION_TIMEZONE` (default 01:00 IST) | OTX IOCs + local DB | `correlation_*`, `feed_cache` | Log error; lock skip | Yes — upsert/delete patterns |

---

## 4. External APIs

| Service | Endpoint used | Key env var | Free tier limit | Fallback |
|---|---|---|---|---|
| NVD | `https://services.nvd.nist.gov/rest/json/cves/2.0` | `NVD_API_KEY` | 50/30s with key | Retry/backoff; anonymous fallback |
| CISA KEV | `known_exploited_vulnerabilities.json` | — | Unlimited | `[]` |
| EPSS | CSV gzip + `api.first.org/data/v1/epss` | — | Unlimited | `{}` |
| MITRE STIX | `enterprise-attack.json` + CTID CSV | — | Unlimited | Job fails |
| ATLAS | GitHub raw YAML + case-studies API | `ATLAS_YAML_URL` | Unlimited | Job fails |
| Sploitus | `sploitus.com` search API | — | Unpublished | `None`/`[]` |
| GreyNoise | `api.greynoise.io/v3/community` | `GREYNOISE_API_KEY` | 50/week | Unknown classification |
| VirusTotal | `virustotal.com/api/v3` | `VIRUSTOTAL_API_KEY` | 500/day | Empty fields |
| AbuseIPDB | `api.abuseipdb.com/api/v2/check` | `ABUSEIPDB_API_KEY` | 1000/day | Skipped |
| OTX | `otx.alienvault.com/api/v1` | `OTX_API_KEY` | 10k/month | `[]` |
| OSV | `api.osv.dev/v1/query` | — | Unlimited | `[]` |
| CIRCL | `cve.circl.lu/api/cve` | — | Unlimited | No merge |
| MalwareBazaar | `bazaar.abuse.ch/api` | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| URLhaus | `urlhaus-api.abuse.ch` | `ABUSECH_AUTH_KEY` | Fair use | `None` |
| Groq | `api.groq.com/openai/v1/chat/completions` | `GROQ_API_KEY` | Console quota | Anthropic/template |
| Anthropic | `api.anthropic.com/v1/messages` | `ANTHROPIC_API_KEY` | Console quota | Template |
| GitHub | `api.github.com/search/code` | `GITHUB_TOKEN` | 60/hr without token | `[]` rules |

---

## 5. Risk Scoring — v1.1b

**Active client implementation:** `frontend/src/scoring/riskScore.js`  
**Server momentum only:** `backend/scoring/risk.py`

| Component | Weight |
|---|---|
| Asset profile match | 0.35 |
| KEV status | 0.25 |
| EPSS score | 0.15 |
| Exploit availability | 0.10 |
| CVSS score | 0.10 |
| Momentum | 0.05 |

### Momentum signals (`calculate_momentum`)

| Signal | Source | Contribution logic |
|---|---|---|
| EPSS rising | `epss_history` last 14 snapshots | +0.10 to +0.50 based on delta |
| New OTX pulse | `otx_cve_pulses.fetched_at` | +0.50 if ≤24h; +0.30 if ≤7d |
| Recent KEV addition | `kev_deadlines.date_added` | +0.40 if ≤7 days |
| Rapid exploitation | `published` vs KEV date | +0.30 if exploited within 30 days of publish |

**Note:** Weights duplicated in Python and JavaScript — v1.2 will serve from single config endpoint.

**Deprecated:** `frontend/src/utils/riskScore.js` (v1.1a weights, no momentum, unused).

---

## 6. Feature Completion Matrix

| Feature | Status | Notes |
|---|---|---|
| NVD incremental ingest | Complete | Watermark, overlap, cap `MAX_CVES_PER_FETCH` |
| KEV sync + deadlines | Complete | 15m default interval |
| EPSS sync + history | Complete | Snapshot before update |
| MITRE ATT&CK mapping | Complete | Weekly Sunday job |
| MITRE ATLAS feed | Complete | Weekly with MITRE job |
| CVE feed + filters | Complete | Pagination max 50/page |
| CVE detail enrichment | Partial | Sploitus/GN/OTX/OSV/CIRCL wired; **ATLAS per-CVE not in API** |
| IOC lookup multi-source | Complete | 6h cache |
| Risk score v1.1b | Complete | Client-side; momentum lazy |
| Correlation engine | Complete | 3 levels; 6h on-demand cache |
| Detection engineering tab | Complete | Sigma/Elastic search + generator |
| Asset profile CPE match | Complete | POST-only; no server storage |
| Investigation panel | Complete | Cross-tab pivots |
| PDF export + AI summary | Complete | Groq→Anthropic→template |
| Case Studies / RSS | Complete | 6 feeds, 30min cache |
| API usage quotas UI | Complete | `/api/usage/ioc` |
| Authentication | Not implemented | By design v1.1 |
| `POST /api/investigation/summary` | Complete | Legacy alias → `generate_executive_summary` |
| Repository / DI layer | Not implemented | v1.2 backlog |
| Circuit breakers | Not implemented | Timeouts only |
| Structured logging | Not implemented | Plain text logs |

Spreadsheet export: [`TECHNICAL_INVENTORY.xlsx`](TECHNICAL_INVENTORY.xlsx)

### Regenerating the spreadsheet

```bash
pip install openpyxl
python3 scripts/generate_technical_inventory_xlsx.py
```

The generator writes six sheets (Tech Stack, Database Schema, Scheduler Jobs, External APIs, Risk Scoring, Feature Completion) and auto-sizes columns with a minimum width of 10 and maximum of 60.
