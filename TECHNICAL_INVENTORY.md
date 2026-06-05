# BRIEFR Technical Inventory

**Generated**: 2026-06-05  
**Repository**: Soldier0x0/briefr  
**Current Branch**: main

---

## Table of Contents

1. [Frontend Technologies](#1-frontend-technologies)
2. [Backend Technologies](#2-backend-technologies)
3. [Database Layer](#3-database-layer)
4. [Infrastructure](#4-infrastructure)
5. [Security Components](#5-security-components)
6. [External Integrations](#6-external-integrations)
7. [Technology Stack Summary](#7-technology-stack-summary)
8. [Architecture Diagram](#8-architecture-diagram)
9. [Unused Dependencies](#9-unused-dependencies-or-technologies)
10. [Key Findings](#10-key-findings)

---

## 1. Frontend Technologies

### Frameworks & Build Tools

| Technology | Version | Purpose | Location |
|-----------|---------|---------|----------|
| React | 18.3.1 | UI framework (hooks-based) | `frontend/package.json` |
| Vite | 5.4.1 | Build tool & dev server | `frontend/vite.config.js` |
| @vitejs/plugin-react | 4.3.1 | Vite React integration | `frontend/vite.config.js` |
| React Router DOM | 7.16.0 | SPA client-side routing | `frontend/src/App.jsx` |

**Dev Server Config**: Port 5173, proxy to `/api` → `http://localhost:8000`

### UI & Export Libraries

| Library | Version | Purpose | Location |
|---------|---------|---------|----------|
| jsPDF | 4.2.1 | PDF generation | `frontend/src/utils/investigationPdf.js` |
| html2canvas | 1.4.1 | DOM to canvas rendering | `frontend/src/utils/investigationPdf.js` |
| ExcelJS | 4.4.0 | Excel/CSV export | `frontend/src/utils/exportXlsx.js` |

### Visualization

- **Timeline Heatmap**: Custom SVG implementation in `frontend/src/utils/heatmapGrid.js`
- **CVE Trend Chart**: Canvas-based rendering
- **No External Chart Library**: Built-in solutions using Canvas/SVG

### State Management

| Pattern | Usage | Location |
|---------|-------|----------|
| Context API | Investigation thread tracking | `frontend/src/context/InvestigationContext.jsx` |
| useState Hooks | Filter state, modals, panel states | Throughout components |
| useRef Hooks | Item tracking, sheet state | `InvestigationContext.jsx` |
| useMemo | Performance optimization | All major components |
| useCallback | Event handler memoization | All major components |

### Core Components

Located in `frontend/src/components/`:

| Component | Purpose |
|-----------|---------|
| **CVEFeed.jsx** | Main CVE list with filtering & sorting |
| **DetailDrawer.jsx** | CVE detail view with MITRE mapping |
| **IOCLookup.jsx** | IOC enrichment interface |
| **AIThreats.jsx** | AI threat analysis panel |
| **InvestigationPanel.jsx** | Investigation thread tracking |
| **FilterBar.jsx** | Search, severity, technique, stack filtering |
| **TimelineHeatmap.jsx** | CVE publication trend heatmap |
| **PdfExportModal.jsx** | PDF report generation UI |
| **DigestModal.jsx** | CVE digest export |
| **Header.jsx** | Navigation & theme toggle |
| **Sidebar.jsx** | Collapsible navigation panel |
| **StatsRow.jsx** | Feed statistics display |

---

## 2. Backend Technologies

### Framework & API Architecture

| Technology | Version | Purpose | Config |
|-----------|---------|---------|--------|
| FastAPI | 0.136.3 | Async REST API framework | `backend/main.py` |
| Uvicorn | 0.48.0 | ASGI application server | Port 8000 |
| Pydantic | 2.13.4 | Request/response validation | `backend/main.py` |
| httpx | 0.28.1 | Async HTTP client | All feed modules |

**API Design**: RESTful, JSON request/response, fully async/await

### Middleware & Security

```python
# CORS Middleware
- Allowed origins: environment-configurable
- Credentials: enabled
- Methods: GET, POST, OPTIONS

# Security Headers Middleware (added to all responses)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
```

### Background Job Scheduler

| Job | Interval | Timezone | Config |
|-----|----------|----------|--------|
| NVD incremental sync | Hourly (configurable) | Asia/Kolkata | `NVD_SYNC_INTERVAL_HOURS` |
| CISA KEV fetch | 15 minutes (configurable) | Asia/Kolkata | `KEV_SYNC_INTERVAL_MINUTES` |
| EPSS score update | 6 hours (configurable) | Asia/Kolkata | `EPSS_SYNC_INTERVAL_HOURS` |
| MITRE/ATLAS refresh | Weekly (Sunday 02:00) | Asia/Kolkata | `MITRE_REFRESH_HOUR/MINUTE` |
| AI context refresh | On-demand | — | Manual trigger |

**Implementation**: APScheduler 3.11.2 with AsyncIOScheduler  
**Concurrency Control**: Async locks (`asyncio.Lock`) prevent concurrent execution  
**Watermark Tracking**: NVD `lastMod` timestamp stored in `sync_state` table

### Core Modules

#### `backend/main.py` - FastAPI Application
- App initialization with lifespan context manager
- All REST endpoint definitions
- CORS & security middleware configuration
- Request/response Pydantic models
- Timezone-aware response formatting

#### `backend/database.py` - Data Access Layer
- SQLite schema initialization (`init_db()`)
- Async connection management (`aiosqlite`)
- Query helpers for all entity types
- Index definitions for performance

#### `backend/scheduler.py` - Job Scheduling
- APScheduler configuration & startup/shutdown
- Job definitions for all ingestion tasks
- Lock management for concurrent prevention
- Refresh status queries

#### `backend/tracking.py` - Usage Analytics
- API call recording per service/date
- IOC usage statistics
- Monthly aggregation queries

#### `backend/feeds/` - Data Ingestion Modules

| Module | Source | Refresh | Implementation |
|--------|--------|---------|-----------------|
| **nvd.py** | NVD REST API | Hourly incremental | Watermark-based (lastMod) |
| **kev.py** | CISA KEV CSV | 15 minutes | Download & parse CSV |
| **epss.py** | FIRST.org EPSS | 6 hours | Download gzip CSV stream |
| **mitre.py** | MITRE ATT&CK XML | Weekly | GitHub raw XML file |
| **atlas.py** | ATLAS YAML | Weekly | PyYAML parsing |
| **osv.py** | OSV.dev API | On-demand | Package vulnerability lookup |
| **extended.py** | GreyNoise, Sploitus, CIRCL | On-demand | Multi-source enrichment |
| **ai_context.py** | Local AI framework tagging | On-demand | Regex pattern matching |

#### `backend/enrichment/` - Data Enhancement

| Module | Service | Cache | Implementation |
|--------|---------|-------|-----------------|
| **ioc.py** | VirusTotal, AbuseIPDB | 6 hours | Async HTTP requests |
| **cve.py** | CVE metadata extraction | None | Regex parsing |

#### `backend/scoring/` - Risk Calculation
- **risk.py**: Asset-based CVE risk scoring with tech stack matching

#### `backend/ai/` - LLM Integration
- **summary.py**: Executive summary generation (Groq primary, Anthropic fallback)

#### `backend/templates/` - Intelligence Templates
- **intelligence.py**: Sentence generators for CVE intelligence (KEV, EPSS, exploit, severity, patches)

---

## 3. Database Layer

### Database Engine

```
Engine:        SQLite (aiosqlite 0.22.1)
Location:      briefr.db (configurable via DB_PATH)
Write Mode:    WAL (Write-Ahead Logging)
Foreign Keys:  Enforced
```

### Schema & Tables

| Table | Purpose | Key Indexes |
|-------|---------|------------|
| **cves** | Core CVE records with CVSS, EPSS, KEV status | severity, published, is_kev, epss_score |
| **kev_deadlines** | CISA KEV metadata & remediation dates | due_date, date_added |
| **mitre_techniques** | MITRE ATT&CK framework techniques | (FK only) |
| **cve_technique_map** | Junction: CVE → MITRE technique | technique_id, cve_id |
| **atlas_techniques** | ATLAS AI-focused technique variants | tactic |
| **atlas_case_studies** | ATLAS case study metadata | date |
| **cve_atlas_map** | Junction: CVE → ATLAS technique | cve_id |
| **epss_history** | Historical EPSS score snapshots | (composite PK) |
| **ioc_cache** | IOC enrichment cache (6-hour TTL) | cached_at |
| **api_usage** | Usage metrics per service/date | month_utc, date_utc |
| **sync_state** | Sync watermarks (NVD lastMod, etc.) | (none) |

### Data Access Pattern

- **Language**: Raw SQL (no ORM)
- **Driver**: aiosqlite (async SQLite3)
- **Connection Management**: Async context managers
- **Migration**: Schema initialization on startup (no migration framework)

---

## 4. Infrastructure

### Web Server & Reverse Proxy

**Nginx Configuration** (`deploy/nginx-briefr.conf`):

```nginx
Frontend Routing:
  /                     → /opt/briefr/frontend/dist (SPA)
  /privacy, /terms      → index.html (client-side routing)
  /cve/*                → index.html (CVE detail pages)

Backend Proxy:
  /api/*                → http://127.0.0.1:8000 (FastAPI)

Security:
  SSL/TLS               → Let's Encrypt + certbot
  HSTS                  → max-age=31536000
  Security Headers      → X-Frame-Options: DENY, etc.
  HTTP→HTTPS            → 301 redirect

Performance:
  proxy_read_timeout    → 60s
  client_max_body_size  → 1m
```

### Deployment Model

- **No Docker**: Systemd services instead
- **Hosting**: Bare metal Debian 11/12/13

**Systemd Services** (`deploy/`):

| Service | Purpose | Config |
|---------|---------|--------|
| `briefr-backend.service` | Uvicorn process manager | Python 3.11+ |
| `briefr-frontend.service` | Static asset server | Node.js (dev only) |
| `briefr.target` | Target unit grouping services | Dependency management |

**Helper Scripts**:

| Script | Purpose |
|--------|---------|
| `setup.sh` | Installation for Debian 11/12/13 (auto Python version detection) |
| `briefr-update.sh` | Update + restart services |
| `check-backend.sh` | Health check script |
| `refresh-*.sh` | Manual feed refresh triggers |

### Database

- **Engine**: SQLite (file-based)
- **Backup**: Manual (no automated backups)
- **Concurrency Model**: Single-node (WAL mode for readers)
- **Scaling Limitation**: APScheduler locks prevent multi-instance deployment

### CI/CD

- **Git**: `.git/` present
- **Pipelines**: None found (no GitHub Actions, GitLab CI, Jenkins)
- **Deployment**: Manual or via `briefr-update.sh`

---

## 5. Security Components

### Authentication

- **Type**: None (public API)
- **By Design**: "No account required. No cookies. No tracking."
- **Access**: All endpoints publicly accessible

### Authorization

- **Mechanism**: None
- **CORS Control**: Allowed origins via `ALLOWED_ORIGINS` environment variable

### JWT Handling

- **Status**: Not used

### Password Hashing

- **Status**: Not applicable (no user accounts)

### Rate Limiting

| Layer | Implementation | Coverage |
|-------|-----------------|----------|
| **External API** | Delay between requests | NVD: 35-sec wait |
| **HTTP Response Handling** | 429 error detection | VirusTotal, AbuseIPDB |
| **Job Scheduler** | Async locks | Prevent concurrent job runs |
| **Server-Level** | None | ⚠️ No DDoS protection |

### Input Validation

- **Framework**: Pydantic 2.13.4
- **Models**: All request bodies validated
  - `InvestigationSummaryRequest`
  - `AiSummaryRequest`
  - `IocLookupRequest`
- **Query Parameters**: Type-checked (int, str, float)

### Security Headers

**Nginx Layer**:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

**FastAPI Layer** (duplicate):
```python
app.add_middleware(...same headers...)
```

**Frontend**: No explicit CSP; script execution restricted by SPA model

### Data Privacy

| Component | Privacy Measure |
|-----------|-----------------|
| **IOC Cache** | 6-hour local cache to minimize external API calls |
| **User Tracking** | No logging of IOC values with user associations |
| **External Services** | Privacy policy documents data shared with VirusTotal, AbuseIPDB, GreyNoise |
| **Cookies** | None; fully stateless |

---

## 6. External Integrations

### Primary Data Sources (Scheduled Ingestion)

| API | Endpoint | Refresh Rate | Auth | Module |
|-----|----------|--------------|------|--------|
| **NVD** | `services.nvd.nist.gov/rest/json/cves/2.0` | Hourly incremental | `NVD_API_KEY` | `feeds/nvd.py` |
| **CISA KEV** | CSV feed (public) | Every 15 min | None | `feeds/kev.py` |
| **FIRST EPSS** | `api.first.org/data/v1/epss/...` | Every 6 hours | None (gzip) | `feeds/epss.py` |
| **MITRE ATT&CK** | GitHub raw XML | Weekly | None | `feeds/mitre.py` |
| **ATLAS** | GitHub raw YAML | Weekly | None | `feeds/atlas.py` |
| **OSV.dev** | `api.osv.dev` | On-demand | None | `feeds/osv.py` |

### Enrichment Services (On-Demand, 6h Cache)

| Service | Use Case | API Key | Module |
|---------|----------|---------|--------|
| **VirusTotal** | IP/hash/domain reputation | `VIRUSTOTAL_API_KEY` | `enrichment/ioc.py` |
| **AbuseIPDB** | IP abuse reputation | `ABUSEIPDB_API_KEY` | `enrichment/ioc.py` |
| **GreyNoise** | CVE scan metadata | `GREYNOISE_API_KEY` | `feeds/extended.py` |
| **Sploitus** | Public exploit availability | None | `feeds/extended.py` |
| **CIRCL CVE** | Extended CVE intelligence | None | `feeds/extended.py` |
| **abuse.ch** | Malware/URL hash lookups | `ABUSECH_AUTH_KEY` | `feeds/extended.py` |

### LLM Services (PDF Export Only)

| Provider | Model | Temperature | Purpose | Module |
|----------|-------|-------------|---------|--------|
| **Groq** | llama-3.3-70b-versatile | (default) | Primary summary generation | `ai/summary.py` |
| **Anthropic** | claude-haiku-4-5 | (default) | Fallback summary generation | `ai/summary.py` |

**Note**: LLM calls only triggered during PDF export, never on page load.

---

## 7. Technology Stack Summary

### Frontend Stack

| Technology | Purpose | Version | Location |
|-----------|---------|---------|----------|
| React | UI framework | 18.3.1 | `frontend/src/` |
| React Router DOM | SPA routing | 7.16.0 | `frontend/src/App.jsx` |
| Vite | Build tool | 5.4.1 | `frontend/vite.config.js` |
| jsPDF | PDF generation | 4.2.1 | `frontend/src/utils/investigationPdf.js` |
| html2canvas | Canvas rendering | 1.4.1 | `frontend/src/utils/investigationPdf.js` |
| ExcelJS | Excel/CSV export | 4.4.0 | `frontend/src/utils/exportXlsx.js` |
| Context API | State management | native | `frontend/src/context/` |

### Backend Stack

| Technology | Purpose | Version | Location |
|-----------|---------|---------|----------|
| FastAPI | API framework | 0.136.3 | `backend/main.py` |
| Uvicorn | ASGI server | 0.48.0 | `backend/requirements.txt` |
| APScheduler | Job scheduling | 3.11.2 | `backend/scheduler.py` |
| aiosqlite | Async SQLite | 0.22.1 | `backend/database.py` |
| httpx | HTTP client | 0.28.1 | `backend/feeds/` |
| Pydantic | Validation | 2.13.4 | `backend/main.py` |
| PyYAML | YAML parsing | 6.0.2 | `backend/feeds/atlas.py` |
| python-dotenv | Env loading | 1.2.2 | `backend/main.py` |

### Infrastructure Stack

| Technology | Purpose | Version | Location |
|-----------|---------|---------|----------|
| SQLite | Database | 3.x | `briefr.db` |
| Nginx | Reverse proxy | latest | `deploy/nginx-briefr.conf` |
| Systemd | Process management | native | `deploy/*.service` |
| Debian | OS | 11/12/13 | `deploy/setup.sh` |
| Let's Encrypt | SSL/TLS | certbot | `deploy/nginx-briefr.conf` |

---

## 8. Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                                 │
│                     (React 18.3 + Vite 5.4)                            │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ HTTP/HTTPS (TLS 1.3+)
                               │
          ┌────────────────────┴────────────────────┐
          │   NGINX Reverse Proxy (port 443)        │
          │  - SPA routing (/ → index.html)         │
          │  - Security headers & SSL/TLS           │
          │  - Static asset caching                 │
          │  - CORS origin validation               │
          └────────────────────┬────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
    ┌───────────▼──────────┐      ┌──────────▼─────────────┐
    │  /api/* endpoints    │      │  / (static SPA files)  │
    │  proxy to 8000       │      │  /opt/briefr/frontend/ │
    │                      │      │  /dist/*               │
    └───────────┬──────────┘      └────────────────────────┘
                │
    ┌───────────▼──────────────────────────────────────────────────┐
    │         FastAPI App (Uvicorn, port 8000)                     │
    │  - Async request handling (asyncio)                           │
    │  - CORS + security header middleware                          │
    │  - Pydantic request/response validation                       │
    ├──────────────────────────────────────────────────────────────┤
    │  CVE Feed Endpoints:                                          │
    │   • GET /api/cves (search, filter, sort)                     │
    │   • GET /api/cves/{id} (detail view)                         │
    │   • POST /api/ioc/lookup (IOC enrichment)                    │
    │   • POST /api/ai/summary (PDF LLM summary)                   │
    │   • POST /api/investigation/summary (thread analysis)        │
    │  Health & Metadata:                                          │
    │   • GET /api/health (status, refresh times, metrics)         │
    │   • GET /api/stats (feed statistics)                         │
    │  Refresh Control:                                            │
    │   • GET /api/refresh/status (ingest status)                  │
    │   • GET/POST /api/refresh/* (manual triggers)                │
    └──────┬───────────────────────────────┬──────────────────────┘
           │                               │
    ┌──────▼──────────────────────┐  ┌────▼────────────────────────┐
    │   SQLite Database (.db)      │  │  APScheduler (AsyncIO)      │
    │ ────────────────────────────│  │ ─────────────────────────────│
    │ Tables:                     │  │ Jobs:                       │
    │ • cves (CVE records)        │  │  • NVD sync (hourly)        │
    │ • kev_deadlines (CISA)      │  │  • KEV sync (15 min)        │
    │ • mitre_techniques          │  │  • EPSS sync (6 hr)         │
    │ • cve_technique_map (FK)    │  │  • MITRE/ATLAS refresh      │
    │ • atlas_techniques          │  │    (weekly Sunday 02:00)    │
    │ • cve_atlas_map (FK)        │  │  • AI context refresh       │
    │ • epss_history (snapshots)  │  │                             │
    │ • ioc_cache (6h TTL)        │  │ Concurrency Control:        │
    │ • api_usage (metrics)       │  │  • Async locks prevent      │
    │ • sync_state (watermarks)   │  │    concurrent job runs      │
    │                             │  │  • Single-node (no Redis)   │
    │ Indexes:                    │  │                             │
    │ • severity, published       │  │ Timezone: Asia/Kolkata      │
    │ • is_kev, epss_score        │  │ (environment-configurable)  │
    └──────┬──────────────────────┘  └────────────────────────────┘
           │
           │ (aiosqlite async access + WAL mode)
           │
    ┌──────▼──────────────────────────────────────────────────────┐
    │          External Data Feeds & APIs                          │
    ├──────────────────────────────────────────────────────────────┤
    │ Scheduled Ingest (via APScheduler):                          │
    │  • NVD (hourly) — watermark-based incremental               │
    │  • CISA KEV (15 min) — CSV feed                             │
    │  • FIRST EPSS (6 hr) — gzip CSV stream                      │
    │  • MITRE ATT&CK (weekly) — GitHub XML                       │
    │  • ATLAS (weekly) — GitHub YAML                             │
    │                                                              │
    │ On-Demand Enrichment (with 6h cache):                       │
    │  • OSV.dev (package vulns)                                  │
    │  • GreyNoise (CVE scans)                                    │
    │  • Sploitus (exploits)                                      │
    │  • CIRCL CVE (extended data)                                │
    │  • VirusTotal (IP/hash/domain reputation)                   │
    │  • AbuseIPDB (IP abuse reputation)                          │
    │  • abuse.ch (MalwareBazaar/URLhaus)                         │
    │                                                              │
    │ LLM (PDF export only, not on page load):                    │
    │  • Groq llama-3.3-70b (primary) — $GROQ_API_KEY             │
    │  • Anthropic claude-haiku-4-5 (fallback)                    │
    │    — $ANTHROPIC_API_KEY                                     │
    └──────────────────────────────────────────────────────────────┘
```

### Data Flow

**1. Feed Ingest Loop**
```
APScheduler Job Trigger
  ↓
Fetch External API (with rate limiting)
  ↓
Transform/Parse Data
  ↓
Check Watermark (NVD) or Date (others)
  ↓
SQLite Upsert (atomic transactions)
  ↓
Update sync_state watermark
```

**2. User CVE Query**
```
React Component (useState + fetch)
  ↓
GET /api/cves?search=...&severity=...&stack=...
  ↓
FastAPI Endpoint Handler
  ↓
SQLite Query (with indexes)
  ↓
Pydantic Response Model
  ↓
JSON Response
  ↓
React State Update + Re-render
```

**3. IOC Enrichment**
```
User Clicks IOC Value
  ↓
React Component dispatches lookup
  ↓
POST /api/ioc/lookup
  ↓
Check ioc_cache (expired?)
  ↓
If expired: VirusTotal/AbuseIPDB async call
  ↓
Store result in cache (6h TTL)
  ↓
Return result (display immediately)
```

**4. PDF Export with AI Summary**
```
User Clicks "Export PDF"
  ↓
React collects CVE + IOC + actor data
  ↓
POST /api/ai/summary with investigation data
  ↓
FastAPI calls Groq API (primary)
  ↓
Parse JSON response (summary + findings)
  ↓
Call jsPDF + html2canvas on React component
  ↓
Generate PDF with LLM summary
  ↓
Download file (browser)
```

**5. Investigation Thread Tracking**
```
User Clicks CVE/IOC/Technique
  ↓
InvestigationContext.recordItem() called
  ↓
Item added to Context state (Redux-like)
  ↓
InvestigationPanel displays thread
  ↓
User clicks "Summarize Thread"
  ↓
POST /api/investigation/summary with all items
  ↓
Backend aggregates CVE/IOC data
  ↓
Return aggregated investigation summary
```

---

## 9. Unused Dependencies or Technologies

### Potentially Minimal Usage

| Technology | Usage | Status |
|-----------|-------|--------|
| **Uvicorn `[standard]`** | HTTP/2 support (Nginx handles SSL) | Underutilized |
| **frontend CSS** | 18+ CSS modules (one per component) | May have unused selectors |
| **ABUSECH_AUTH_KEY** | Malware hash lookups (optional enrichment) | Conditional |
| **Pydantic Field Ranges** | `investigation_duration: ge=1, le=10080` | Validated but not strictly enforced |

### Missing Technologies

| Gap | Impact | Recommendation |
|-----|--------|-----------------|
| **TypeScript** | Frontend lacks type safety | Add ts/tsx support |
| **ORM** | Raw SQL error-prone | Consider SQLAlchemy |
| **Test Runner in CI** | Tests exist but not in pipeline | Add pytest to CI/CD |
| **Distributed Scheduler** | Single-node only; breaks with multiple instances | Add Redis + distributed locks |
| **Cache Layer** | No Redis; all queries hit SQLite | Add Redis for hot data |
| **API Rate Limiting** | No DDoS protection | Implement rate limiter middleware |
| **Secrets Management** | Hardcoded .env file | Use HashiCorp Vault or AWS Secrets Manager |

### Architecture-Specific Unused

- **No Docker/Kubernetes**: Systemd-only limits container deployments
- **No GraphQL**: REST-only API
- **No WebSockets**: HTTP polling only for refresh status
- **No Message Queue**: APScheduler as single-node, no Celery/RabbitMQ
- **No Distributed Caching**: IOC cache is single-node (SQLite)

---

## 10. Key Findings

### Architecture Strengths

✅ **Fully Async**: FastAPI + Uvicorn + aiosqlite + httpx = non-blocking I/O  
✅ **Stateless Backend**: All state in SQLite; horizontally scalable (with shared DB)  
✅ **Public-First Design**: No authentication reduces attack surface  
✅ **Modular Feeds**: One Python file per data source (easy to extend)  
✅ **Clean Separation**: Frontend (React), Backend (FastAPI), Database (SQLite)  
✅ **Privacy-Focused**: No user tracking, local IOC cache, transparent data flows  
✅ **Real-Time Feeds**: Hourly NVD sync, 15-minute KEV updates  

### Architecture Weaknesses

⚠️ **Single-Node Scheduler**: APScheduler locks break with multiple instances  
⚠️ **No TypeScript**: Frontend is untyped (JSX only)  
⚠️ **No ORM**: Raw SQL increases risk of injection/errors  
⚠️ **SQLite Scalability**: Not suitable for multi-node deployments  
⚠️ **No Test Pipeline**: Tests exist but not in CI/CD  
⚠️ **No Redis**: All caches stored in SQLite (slower for hot data)  
⚠️ **No Rate Limiting**: Vulnerable to API abuse  

### Security Posture

✅ **Input Validation**: All requests validated with Pydantic  
✅ **Security Headers**: HSTS, X-Frame-Options, CORS enforcement  
✅ **No Authentication Needed**: Public API by design  
✅ **Privacy-Aware**: IOC lookups cached locally, external services documented  

⚠️ **No DDoS Protection**: No server-level rate limiting  
⚠️ **Secrets in .env**: No secrets manager integration  
⚠️ **Public Endpoints**: All /api/* exposed (by design)  

### Deployment Model

- **Hosting**: Bare metal Debian 11/12/13 with Systemd
- **No Containerization**: Systemd services, Nginx reverse proxy
- **Database**: File-based SQLite (WAL mode for concurrency)
- **Scaling**: Limited to single node (APScheduler + SQLite)
- **SSL/TLS**: Let's Encrypt + certbot managed

### Data Flow Highlights

1. **Feed Ingestion**: Watermark-based NVD sync → hourly incremental updates
2. **Enrichment**: 6-hour cache for IOC lookups (VirusTotal, AbuseIPDB)
3. **LLM Integration**: Groq primary, Anthropic fallback (PDF export only)
4. **Investigation Threads**: Context API tracks CVE/IOC/actor pivot chains
5. **Risk Scoring**: Asset-based matching against user tech stacks

### Recommended Next Steps

1. **TypeScript Migration**: Add ts/tsx support for type safety
2. **Distributed Scheduler**: Integrate Redis for multi-node deployments
3. **CI/CD Pipeline**: GitHub Actions or GitLab CI with test coverage
4. **ORM Integration**: SQLAlchemy for safer database queries
5. **Rate Limiting**: Implement middleware-level request throttling
6. **Secrets Management**: Vault or AWS Secrets Manager for API keys

---

## Environment Configuration

**File**: `backend/.env.example`

```bash
# API Keys (Required)
NVD_API_KEY=your_nvd_api_key_here
VIRUSTOTAL_API_KEY=your_vt_api_key_here
ABUSEIPDB_API_KEY=your_abuseipdb_key_here
GREYNOISE_API_KEY=your_greynoise_api_key_here
ABUSECH_AUTH_KEY=your_abusech_auth_key_here

# CORS
ALLOWED_ORIGINS=http://localhost:5173,https://projectjupiter.in

# Scheduler Configuration
CACHE_REFRESH_HOUR=6
CACHE_REFRESH_MINUTE=0
MITRE_REFRESH_HOUR=2
MITRE_REFRESH_MINUTE=0

# Ingest Intervals (APScheduler)
NVD_SYNC_INTERVAL_HOURS=1
KEV_SYNC_INTERVAL_MINUTES=15
EPSS_SYNC_INTERVAL_HOURS=6
NVD_SYNC_OVERLAP_MINUTES=15

# Timezone
SCHEDULER_TIMEZONE=Asia/Kolkata
DEFAULT_TIMEZONE=Asia/Kolkata

# Fetch Limits
MAX_CVES_PER_FETCH=2000
NVD_DAYS_BACK=14

# Features
KEV_CROSS_FETCH_NVD=1

# Optional: LLM (PDF export only)
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

---

## Quick Reference: File Locations

### Frontend
- **Main App**: `frontend/src/App.jsx`
- **Context**: `frontend/src/context/InvestigationContext.jsx`
- **Components**: `frontend/src/components/`
- **Utils**: `frontend/src/utils/` (exports, filters, timezone, etc.)
- **Build Config**: `frontend/vite.config.js`

### Backend
- **API Server**: `backend/main.py`
- **Database**: `backend/database.py`
- **Scheduler**: `backend/scheduler.py`
- **Feeds**: `backend/feeds/` (nvd.py, kev.py, epss.py, etc.)
- **Enrichment**: `backend/enrichment/` (ioc.py, cve.py)
- **Scoring**: `backend/scoring/risk.py`
- **AI**: `backend/ai/summary.py`
- **Requirements**: `backend/requirements.txt`

### Infrastructure
- **Nginx**: `deploy/nginx-briefr.conf`
- **Systemd**: `deploy/briefr-backend.service`, `deploy/briefr-frontend.service`
- **Setup**: `deploy/setup.sh`
- **Environment**: `backend/.env.example`

---

**Document Version**: 1.0  
**Last Updated**: 2026-06-05  
**Repository**: [Soldier0x0/briefr](https://github.com/Soldier0x0/briefr)
