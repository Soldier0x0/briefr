# BRIEFR Application Execution Map

**Purpose**: Complete trace of application flow from startup through all operations  
**Audience**: Developers and security auditors  
**Date**: 2026-06-05

---

## Table of Contents

1. [Backend Startup Sequence](#1-backend-startup-sequence)
2. [Frontend Startup Sequence](#2-frontend-startup-sequence)
3. [API Request Flow - CVE Search](#3-api-request-flow---cve-search)
4. [API Request Flow - IOC Lookup](#4-api-request-flow---ioc-lookup)
5. [API Request Flow - PDF Export with AI Summary](#5-api-request-flow---pdf-export-with-ai-summary)
6. [Database Operation Flow](#6-database-operation-flow)
7. [Scheduled Job Execution](#7-scheduled-job-execution)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [External API Integration](#9-external-api-integration)
10. [Complete Request Lifecycle](#10-complete-request-lifecycle)

---

## 1. Backend Startup Sequence

### Step-by-Step Execution

```
PROCESS: python -m uvicorn main:app --host 0.0.0.0 --port 8000
↓
```

### Phase 1: Python Import & Initialization

**File**: `backend/main.py`  
**Line**: 1-80

```python
# Step 1: Load environment variables
from dotenv import load_dotenv
load_dotenv()  # Reads .env file from current directory

# Step 2: Import FastAPI and dependencies
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Step 3: Import all internal modules
from database import (init_db, get_db, get_cve_count, ...)
from scheduler import (start_scheduler, stop_scheduler, ...)
from enrichment.ioc import lookup_ioc
from feeds.* import (fetch_nvd_cve_updates, fetch_kev, ...)
from ai.summary import generate_executive_summary
```

### Phase 2: Lifespan Context Manager Startup

**File**: `backend/main.py`  
**Lines**: 82-90

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP PHASE ↓
    
    # Step 1: Initialize database
    await init_db()
    # Location: backend/database.py:async def init_db()
    # Action: Creates tables if they don't exist
    
    # Step 2: Start background scheduler
    start_scheduler()
    # Location: backend/scheduler.py:def start_scheduler()
    # Action: Initializes APScheduler with jobs
    
    # Step 3: Run startup-only tasks
    await maybe_run_on_startup()
    # Location: backend/scheduler.py:async def maybe_run_on_startup()
    # Action: Runs scheduled jobs if configured
    
    yield  # Application now running
    
    # SHUTDOWN PHASE ↓
    stop_scheduler()
    # Location: backend/scheduler.py:def stop_scheduler()
```

### Detailed Breakdown of `init_db()`

**File**: `backend/database.py`

```python
async def init_db() -> None:
    db = await get_db()  # Connect to SQLite
    
    try:
        # Execute CREATE TABLE IF NOT EXISTS for all tables
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS cves (
                cve_id TEXT PRIMARY KEY,
                description TEXT,
                cvss_score REAL,
                ...
            );
            CREATE TABLE IF NOT EXISTS kev_deadlines (...);
            CREATE TABLE IF NOT EXISTS mitre_techniques (...);
            CREATE TABLE IF NOT EXISTS cve_technique_map (...);
            CREATE TABLE IF NOT EXISTS atlas_techniques (...);
            CREATE TABLE IF NOT EXISTS atlas_case_studies (...);
            CREATE TABLE IF NOT EXISTS cve_atlas_map (...);
            CREATE TABLE IF NOT EXISTS epss_history (...);
            CREATE TABLE IF NOT EXISTS ioc_cache (...);
            CREATE TABLE IF NOT EXISTS api_usage (...);
            CREATE TABLE IF NOT EXISTS sync_state (...);
        """)
        
        # Create indexes for performance
        await db.executescript("""
            CREATE INDEX IF NOT EXISTS idx_cves_severity ON cves(severity);
            CREATE INDEX IF NOT EXISTS idx_cves_published ON cves(published);
            CREATE INDEX IF NOT EXISTS idx_cves_is_kev ON cves(is_kev);
            CREATE INDEX IF NOT EXISTS idx_cves_epss ON cves(epss_score);
            CREATE INDEX IF NOT EXISTS idx_kev_due_date ON kev_deadlines(due_date);
        """);
        
        await db.commit()
    finally:
        await db.close()
```

### Detailed Breakdown of `start_scheduler()`

**File**: `backend/scheduler.py`

```python
_scheduler: AsyncIOScheduler | None = None  # Global reference

def start_scheduler() -> None:
    global _scheduler
    
    # Create AsyncIOScheduler with timezone
    _scheduler = AsyncIOScheduler(
        timezone=get_scheduler_timezone()  # Asia/Kolkata (default)
    )
    
    # Add scheduled jobs
    intervals = get_ingest_intervals()  # Read from environment
    
    # Job 1: NVD incremental sync
    _scheduler.add_job(
        run_nvd_incremental_sync,
        IntervalTrigger(hours=intervals["nvd_hours"]),  # Default: 1 hour
        id="nvd_incremental_sync",
        name="NVD Incremental CVE Sync"
    )
    
    # Job 2: CISA KEV sync
    _scheduler.add_job(
        run_kev_sync,
        IntervalTrigger(minutes=intervals["kev_minutes"]),  # Default: 15 min
        id="kev_sync",
        name="CISA KEV Sync"
    )
    
    # Job 3: EPSS sync
    _scheduler.add_job(
        run_epss_sync,
        IntervalTrigger(hours=intervals["epss_hours"]),  # Default: 6 hours
        id="epss_sync",
        name="EPSS Score Sync"
    )
    
    # Job 4: MITRE/ATLAS weekly refresh
    _scheduler.add_job(
        run_weekly_mitre_refresh,
        CronTrigger(
            day_of_week="sun",  # Sunday
            hour=int(os.environ.get("MITRE_REFRESH_HOUR", "2")),
            minute=int(os.environ.get("MITRE_REFRESH_MINUTE", "0")),
            timezone=get_scheduler_timezone()
        ),
        id="mitre_weekly_refresh",
        name="Weekly MITRE/ATLAS Refresh"
    )
    
    # Start the scheduler
    _scheduler.start()
    logger.info("APScheduler started with %d jobs", len(_scheduler.get_jobs()))
```

### Fastapi App Initialization

**File**: `backend/main.py`  
**Lines**: 93-116

```python
app = FastAPI(
    title="BRIEFR CVE Intelligence API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan  # Hook startup/shutdown
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Add security header middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

### Phase 3: Application Ready

**Status**: Backend listening on `http://0.0.0.0:8000`

```
Backend Ready:
✅ Database initialized with schema
✅ All 10 tables created
✅ Scheduler started with 4 scheduled jobs
✅ CORS configured
✅ Security headers middleware active
✅ All endpoints registered
```

---

## 2. Frontend Startup Sequence

### Step-by-Step Execution

```
Browser requests: https://projectjupiter.in/
        ↓
Nginx serves: /opt/briefr/frontend/dist/index.html
        ↓
Browser executes JavaScript
        ↓
React initialization
```

### Phase 1: HTML Load

**File**: `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>BRIEFR</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <!-- Target element for React -->
    <div id="root"></div>
    
    <!-- Load main React bundle -->
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### Phase 2: React Entry Point

**File**: `frontend/src/main.jsx`

```javascript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './App.css'

// Step 1: Find root element
const rootElement = document.getElementById('root')

// Step 2: Create React root
const root = ReactDOM.createRoot(rootElement)

// Step 3: Render App with routing
root.render(
  <React.StrictMode>
    {/* BrowserRouter enables client-side routing */}
    <BrowserRouter>
      {/* Main application component */}
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

### Phase 3: App Component Initialization

**File**: `frontend/src/App.jsx`

```javascript
import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { InvestigationProvider } from './context/InvestigationContext.jsx'
import { fetchStats, fetchHealth } from './api.js'

function App() {
  // Step 1: Initialize state
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [cves, setCves] = useState([])
  const [timezone, setTimezone] = useState('UTC')
  const [darkMode, setDarkMode] = useState(false)
  
  // Step 2: Fetch initial data on mount
  useEffect(() => {
    async function initializeApp() {
      try {
        // Call API endpoint
        const health = await fetchHealth(timezone)
        // Location: frontend/src/api.js:fetchHealth()
        
        const stats = await fetchStats()
        // Location: frontend/src/api.js:fetchStats()
        
        // Set state with data
        setAppStatus(health)
        setStatistics(stats)
      } catch (error) {
        console.error('Failed to initialize app:', error)
      }
    }
    
    initializeApp()
  }, [])  // Empty dependency array = run once on mount
  
  // Step 3: Render components
  return (
    <InvestigationProvider>
      <Header />
      <Hero />
      <StatsRow stats={stats} />
      <TimelineHeatmap />
      <CVEFeed cves={cves} filters={filters} />
      <Sidebar />
      <InvestigationPanel />
      <DetailDrawer />
      <IOCLookup />
      <AIThreats />
    </InvestigationProvider>
  )
}
```

### API Calls During Frontend Initialization

**File**: `frontend/src/api.js`

```javascript
const BASE = '/api'  // Relative URL → same origin (backend)

async function request(path, options = {}) {
  try {
    // Step 1: Fetch from backend
    const res = await fetch(`${BASE}${path}`, options)
    
    // Step 2: Check response status
    if (!res.ok) {
      const body = await res.json()
      throw new Error(body.detail || `HTTP ${res.status}`)
    }
    
    // Step 3: Return JSON
    return res.json()
  } catch (err) {
    console.error(`API error on ${path}:`, err)
    throw err
  }
}

// Fetch health status
export function fetchHealth(tz = 'UTC') {
  return request(`/health?tz=${tz}`)
  // Backend endpoint: GET /api/health
  // Handler: backend/main.py:@app.get("/api/health")
}

// Fetch statistics
export function fetchStats(aiFrameworks = '') {
  return request(`/stats${aiFrameworks ? `?ai_frameworks=${aiFrameworks}` : ''}`)
  // Backend endpoint: GET /api/stats
  // Handler: backend/main.py:@app.get("/api/stats")
}
```

### Frontend Ready

**Status**: Application rendered with initial data

```
Frontend Ready:
✅ React app mounted in #root element
✅ BrowserRouter initialized for SPA routing
✅ Initial API calls to /health and /stats completed
✅ UI rendered with CVE data
✅ Event listeners attached
```

---

## 3. API Request Flow - CVE Search

### User Action: Search CVEs

```
User types "apache" in search box
    ↓
CVEFeed component detects input change
    ↓
Calls fetchCVEs({ search: 'apache' })
    ↓
```

### Step-by-Step Flow

**File**: `frontend/src/components/CVEFeed.jsx`

```javascript
function CVEFeed({ filters }) {
  const [cves, setCves] = useState([])
  
  // When search filter changes
  useEffect(() => {
    async function searchCVEs() {
      try {
        // Step 1: Call API with filters
        const results = await fetchCVEs({
          search: filters.search,           // "apache"
          severity: filters.severity,       // null
          kev_only: filters.kev_only,       // false
          poc_only: filters.poc_only,       // false
          epss_min: filters.epss_min,       // null
          stack: filters.stack,             // user tech stack
          technique: filters.technique,     // attack technique filter
          page: 1,
          limit: 50
        })
        
        // Step 2: Update state with results
        setCves(results.data)
      } catch (error) {
        console.error('Search failed:', error)
      }
    }
    
    searchCVEs()
  }, [filters])  // Runs when filters change
  
  // Step 3: Render results
  return (
    <div>
      {cves.map(cve => (
        <CVECard key={cve.cve_id} cve={cve} />
      ))}
    </div>
  )
}
```

### API Call from Frontend

**File**: `frontend/src/api.js`

```javascript
export function fetchCVEs(params = {}) {
  // Step 1: Build query string
  const qs = new URLSearchParams()
  if (params.search)     qs.set('search', params.search)
  if (params.severity)   qs.set('severity', params.severity)
  if (params.kev_only)   qs.set('kev_only', 'true')
  if (params.poc_only)   qs.set('poc_only', 'true')
  if (params.technique)  qs.set('technique', params.technique)
  if (params.stack)      qs.set('stack', params.stack)
  if (params.page)       qs.set('page', String(params.page))
  if (params.limit)      qs.set('limit', String(params.limit))
  
  const query = qs.toString()
  
  // Step 2: Make request
  return request(`/cves${query ? `?${query}` : ''}`)
  // HTTP GET /api/cves?search=apache&page=1&limit=50
}
```

### Backend Endpoint Handler

**File**: `backend/main.py`

```python
@app.get("/api/cves")
async def search_cves(
    search: str | None = Query(None),
    severity: str | None = Query(None),
    kev_only: bool = Query(False),
    poc_only: bool = Query(False),
    epss_min: float | None = Query(None),
    stack: str | None = Query(None),
    vendors: str | None = Query(None),
    technique: str | None = Query(None),
    published_on: str | None = Query(None),
    summary_only: bool = Query(False),
    ai_context_only: bool = Query(False),
    ai_profile: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Step 1: Parse and validate query parameters
    - Pydantic automatically validates types
    - Query() defines parameter rules (ge, le = greater/less equal)
    """
    
    # Step 2: Build WHERE clause based on filters
    filters = []
    params = {}
    
    if search:
        filters.append("(cves.cve_id LIKE ? OR cves.description LIKE ?)")
        params["search_1"] = f"%{search}%"
        params["search_2"] = f"%{search}%"
    
    if severity:
        filters.append("cves.severity = ?")
        params["severity"] = severity
    
    if kev_only:
        filters.append("cves.is_kev = 1")
    
    if poc_only:
        filters.append("cves.has_poc = 1")
    
    if epss_min is not None:
        filters.append("cves.epss_score >= ?")
        params["epss_min"] = epss_min
    
    if stack:
        # Tech stack matching (user provided "Apache, MySQL")
        # This calls scoring/risk.py function
        filters.append("user_stack_matches(cves.affected_products, ?)")
        params["stack"] = stack
    
    if technique:
        # Join with cve_technique_map for MITRE technique
        filters.append("""
            EXISTS (
                SELECT 1 FROM cve_technique_map ctm
                WHERE ctm.cve_id = cves.cve_id
                AND ctm.technique_id = ?
            )
        """)
        params["technique"] = technique
    
    # Step 3: Get connection from pool
    db = await get_db()
    # Location: backend/database.py:async def get_db()
    
    try:
        # Step 4: Execute query with pagination
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        query = f"""
            SELECT * FROM cves
            WHERE {where_clause}
            ORDER BY cves.published DESC
            LIMIT ? OFFSET ?
        """
        
        offset = (page - 1) * limit
        
        cursor = await db.execute(query, [*params.values(), limit, offset])
        rows = await cursor.fetchall()
        
        # Step 5: Convert rows to dictionaries
        cves = [_row_to_cve_dict(row) for row in rows]
        
        # Step 6: Return response
        return {"data": cves, "page": page, "limit": limit}
        
    finally:
        await db.close()
```

### Database Query Execution

**File**: `backend/database.py`

```python
async def get_db() -> aiosqlite.Connection:
    # Step 1: Open connection
    db = await aiosqlite.connect(DB_PATH)
    # DB_PATH = os.environ.get("DB_PATH", "briefr.db")
    
    # Step 2: Configure connection
    db.row_factory = aiosqlite.Row  # Return rows as dict-like objects
    await db.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    await db.execute("PRAGMA foreign_keys=ON")   # Foreign key constraints
    
    # Step 3: Return connection
    return db
```

### Response Returns to Frontend

```
Backend Response:
{
  "data": [
    {
      "cve_id": "CVE-2024-1234",
      "description": "Apache vulnerability...",
      "cvss_score": 9.8,
      "severity": "CRITICAL",
      "is_kev": true,
      "has_poc": true,
      "epss_score": 0.87,
      ...
    },
    ...
  ],
  "page": 1,
  "limit": 50
}
        ↓
Browser receives JSON
        ↓
React component updates state
        ↓
CVE list re-renders
```

---

## 4. API Request Flow - IOC Lookup

### User Action: Look Up IOC

```
User enters IOC: "1.2.3.4" (IP address)
        ↓
IOCLookup component detects input
        ↓
Calls lookupIOC("1.2.3.4", "ip")
        ↓
```

### Frontend Request

**File**: `frontend/src/components/IOCLookup.jsx`

```javascript
function IOCLookup() {
  const [iocValue, setIocValue] = useState('')
  const [iocType, setIocType] = useState('ip')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  
  async function handleLookup() {
    try {
      // Step 1: Detect IOC type if needed
      const detectedType = detectIOCType(iocValue)  // "ip", "hash", "domain", "url"
      
      // Step 2: Call API
      const result = await lookupIOC(iocValue, detectedType)
      // Location: frontend/src/api.js:lookupIOC()
      
      // Step 3: Display result
      setResult(result)
    } catch (error) {
      console.error('IOC lookup failed:', error)
    }
  }
  
  return (
    <div>
      <input value={iocValue} onChange={e => setIocValue(e.target.value)} />
      <button onClick={handleLookup}>Lookup</button>
      {result && <IOCResultCard result={result} />}
    </div>
  )
}
```

### API Call

**File**: `frontend/src/api.js`

```javascript
export function lookupIOC(value, type) {
  // Step 1: Build request body
  const body = JSON.stringify({
    value: value,  // "1.2.3.4"
    type: type     // "ip"
  })
  
  // Step 2: Make POST request
  return request('/ioc/lookup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body
  })
  // HTTP POST /api/ioc/lookup
  // Body: { "value": "1.2.3.4", "type": "ip" }
}
```

### Backend Endpoint Handler

**File**: `backend/main.py`

```python
class IocLookupRequest(BaseModel):
    value: str
    type: str


@app.post("/api/ioc/lookup")
async def ioc_lookup(req: IocLookupRequest):
    """
    Step 1: Pydantic automatically validates request body
    - Checks value is string
    - Checks type is string
    - Returns 422 error if invalid
    """
    
    # Step 2: Validate IOC type
    if req.type not in ("ip", "hash", "domain", "url"):
        raise HTTPException(status_code=400, detail="Invalid IOC type")
    
    try:
        # Step 3: Call IOC enrichment function
        result = await lookup_ioc(req.value, req.type)
        # Location: backend/enrichment/ioc.py:async def lookup_ioc()
        
        # Step 4: Return result
        return {
            "value": req.value,
            "type": req.type,
            "result": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Enrichment Function with Cache Check

**File**: `backend/enrichment/ioc.py`

```python
async def lookup_ioc(value: str, ioc_type: str) -> dict:
    """
    Step 1: Check local cache (6-hour TTL)
    """
    db = await get_db()
    try:
        # Check if IOC already cached
        cached = await get_ioc_cache(db, value, ioc_type)
        
        if cached and not is_cache_expired(cached["cached_at"]):
            logger.info(f"IOC cache hit: {value}")
            return json.loads(cached["result"])
        
    finally:
        await db.close()
    
    """
    Step 2: If not cached or expired, query external APIs
    """
    
    # Get API keys from environment
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY")
    abuseipdb_key = os.environ.get("ABUSEIPDB_API_KEY")
    
    result = {}
    
    # Call appropriate lookup based on type
    if ioc_type == "ip":
        # Step 2a: Call VirusTotal IP lookup
        result_vt = await _lookup_vt_ip(value, vt_key)
        # Function: backend/enrichment/ioc.py:async def _lookup_vt_ip()
        
        # Step 2b: Call AbuseIPDB lookup
        result_abuseipdb = await _lookup_abuseipdb(value, abuseipdb_key)
        # Function: backend/enrichment/ioc.py:async def _lookup_abuseipdb()
        
        # Merge results
        result = merge_ip_results(result_vt, result_abuseipdb)
    
    elif ioc_type == "hash":
        result_vt = await _lookup_vt_hash(value, vt_key)
        result_abusech = await _lookup_abusech_hash(value, abuseipdb_key)
        result = merge_hash_results(result_vt, result_abusech)
    
    # ... handle other types ...
    
    """
    Step 3: Cache result in database
    """
    db = await get_db()
    try:
        await set_ioc_cache(
            db,
            value=value,
            ioc_type=ioc_type,
            result=json.dumps(result),
            cached_at=datetime.now(timezone.utc).isoformat()
        )
        await db.commit()
    finally:
        await db.close()
    
    # Record API usage
    await record_api_call("virustotal", service="vt")
    await record_api_call("abuseipdb", service="abuse")
    
    return result
```

### External API Calls

**File**: `backend/enrichment/ioc.py`

```python
async def _lookup_vt_ip(client: httpx.AsyncClient, ip: str, api_key: str) -> dict:
    """
    Step 1: Build request
    """
    url = "https://www.virustotal.com/api/v3/ip_addresses/{ip}"
    headers = {"x-apikey": api_key}
    
    try:
        """
        Step 2: Make HTTP request to VirusTotal
        """
        response = await client.get(
            url,
            headers=headers,
            timeout=30.0
        )
        
        """
        Step 3: Handle response
        """
        if response.status_code == 404:
            return {}  # IP not in VirusTotal
        
        if response.status_code == 401:
            logger.warning("VirusTotal auth failed - bad API key")
            return {}
        
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit hit")
            return {}  # Caller will retry later
        
        # Raise exception for other errors
        response.raise_for_status()
        
        """
        Step 4: Parse response
        """
        data = response.json()
        
        return {
            "malicious_votes": data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {}).get("malicious", 0),
            "total_votes": sum(data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {}).values()),
            "country": data.get("data", {}).get("attributes", {}).get("country"),
            "tags": data.get("data", {}).get("attributes", {}).get("tags", []),
            "last_seen": data.get("data", {}).get("attributes", {}).get("last_analysis_date")
        }
    
    except httpx.HTTPStatusError as exc:
        logger.error(f"VirusTotal HTTP error for {ip}: {exc}")
        return {}
    except Exception as exc:
        logger.error(f"VirusTotal lookup error for {ip}: {exc}")
        return {}
```

---

## 5. API Request Flow - PDF Export with AI Summary

### User Action: Export PDF with AI Summary

```
User selects CVEs in investigation panel
        ↓
Clicks "Export as PDF"
        ↓
PdfExportModal component opens
        ↓
User clicks "Include AI Summary"
        ↓
Sends API request
        ↓
```

### Frontend Request

**File**: `frontend/src/components/PdfExportModal.jsx`

```javascript
function PdfExportModal({ investigationItems }) {
  async function handleExport() {
    try {
      // Step 1: Collect investigation data
      const cves = investigationItems
        .filter(item => item.type === 'cve')
        .map(item => ({...item.data}))
      
      const iocs = investigationItems
        .filter(item => item.type === 'ioc')
        .map(item => ({...item.data}))
      
      const actors = investigationItems
        .filter(item => item.type === 'actor')
        .map(item => ({...item.data}))
      
      // Step 2: Calculate duration in minutes
      const startTime = getInvestigationStartTime()
      const durationMinutes = Math.floor((Date.now() - startTime) / 60000)
      
      // Step 3: Call API
      const aiSummary = await generateAiSummary({
        cves: cves,
        iocs: iocs,
        actors: actors,
        investigation_duration: durationMinutes
      })
      // Location: frontend/src/api.js:generateAiSummary()
      
      // Step 4: Generate PDF locally with summary
      const pdf = await generatePDF(cves, aiSummary)
      // Location: frontend/src/utils/investigationPdf.js:generatePDF()
      
      // Step 5: Download PDF
      downloadFile(pdf, 'investigation.pdf')
      
    } catch (error) {
      console.error('PDF export failed:', error)
    }
  }
}
```

### API Call to Backend

**File**: `frontend/src/api.js`

```javascript
export function generateAiSummary(data) {
  // Step 1: Build request
  const body = JSON.stringify({
    cves: data.cves,                           // Array of CVE objects
    iocs: data.iocs,                           // Array of IOC objects
    actors: data.actors,                       // Array of actor objects
    investigation_duration: data.investigation_duration  // Minutes
  })
  
  // Step 2: Make POST request
  return request('/ai/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body
  })
  // HTTP POST /api/ai/summary
}
```

### Backend Endpoint Handler

**File**: `backend/main.py`

```python
class AiSummaryRequest(BaseModel):
    cves: list[dict[str, Any]] = Field(default_factory=list)
    iocs: list[dict[str, Any]] = Field(default_factory=list)
    actors: list[dict[str, Any]] = Field(default_factory=list)
    investigation_duration: int = Field(default=1, ge=1, le=10080)


@app.post("/api/ai/summary")
async def ai_summary(req: AiSummaryRequest):
    """
    Step 1: Pydantic validates request
    - Checks all fields are correct type
    - investigation_duration between 1-10080 minutes (1 week max)
    """
    
    try:
        # Step 2: Call AI summary generation
        summary = await generate_executive_summary(
            cves=req.cves,
            iocs=req.iocs,
            actors=req.actors,
            investigation_duration=req.investigation_duration
        )
        # Location: backend/ai/summary.py:async def generate_executive_summary()
        
        # Step 3: Return result
        return {
            "executive_summary": summary["executive_summary"],
            "key_findings": summary["key_findings"],
            "confidence": summary["confidence"]
        }
    
    except Exception as e:
        logger.error(f"AI summary generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary")
```

### AI Summary Generation Function

**File**: `backend/ai/summary.py`

```python
async def generate_executive_summary(
    cves: list[dict],
    iocs: list[dict],
    actors: list[dict],
    investigation_duration: int
) -> dict:
    """
    Step 1: Format investigation data for LLM
    """
    cves_block = "\n".join([
        f"- {cve.get('cve_id')}: {cve.get('description')[:200]} (CVSS {cve.get('cvss_score')})"
        for cve in cves
    ])
    
    iocs_block = "\n".join([
        f"- {ioc.get('value')} ({ioc.get('type')})"
        for ioc in iocs
    ])
    
    actors_block = "\n".join([
        f"- {actor.get('name')} ({actor.get('country', 'Unknown')})"
        for actor in actors
    ])
    
    """
    Step 2: Build system and user prompts
    """
    system_prompt = "You are a senior threat intelligence analyst..."
    
    user_prompt = f"""
    Investigation duration: ~{investigation_duration} minutes
    CVE records:
    {cves_block}
    IOC records:
    {iocs_block}
    Threat actors:
    {actors_block}
    """
    
    """
    Step 3: Try Groq API (primary)
    """
    try:
        summary = await _call_groq_api(system_prompt, user_prompt)
        logger.info("Generated summary via Groq")
        return summary
    
    except Exception as groq_error:
        logger.warning(f"Groq failed: {groq_error}")
        
        """
        Step 4: Fallback to Anthropic
        """
        try:
            summary = await _call_anthropic_api(system_prompt, user_prompt)
            logger.info("Generated summary via Anthropic (fallback)")
            return summary
        
        except Exception as anthropic_error:
            logger.error(f"Both Groq and Anthropic failed: {anthropic_error}")
            
            """
            Step 5: Final fallback to template
            """
            return _generate_template_summary(cves, iocs, actors)
```

### Groq API Call

**File**: `backend/ai/summary.py`

```python
async def _call_groq_api(system_prompt: str, user_prompt: str) -> dict:
    """
    Step 1: Get API key
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    
    """
    Step 2: Prepare request
    """
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    """
    Step 3: Call Groq API
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        
        # Handle errors
        if response.status_code == 401:
            raise ValueError("Invalid Groq API key")
        if response.status_code == 429:
            raise ValueError("Groq rate limit exceeded")
        
        response.raise_for_status()
        
        """
        Step 4: Parse response
        """
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        """
        Step 5: Parse JSON from LLM response
        """
        summary_json = json.loads(content)
        
        return {
            "executive_summary": summary_json.get("executive_summary"),
            "key_findings": summary_json.get("key_findings", []),
            "confidence": summary_json.get("confidence", "medium")
        }
```

### Response Returns to Frontend

```
Backend Response:
{
  "executive_summary": "This investigation reveals active exploitation 
    of Apache vulnerability affecting government agencies...",
  "key_findings": [
    "CVE-2024-1234 is being actively exploited",
    "Attack chain indicates advanced threat actor",
    "Recommend immediate patch deployment"
  ],
  "confidence": "high"
}
        ↓
Frontend receives JSON
        ↓
Adds to PDF document
        ↓
User downloads PDF
```

---

## 6. Database Operation Flow

### Generic Database Pattern

```
Any Backend Function Needing Data:
    ↓
1. Open connection: db = await get_db()
    ↓
2. Execute query: await db.execute(sql, params)
    ↓
3. Fetch results: rows = await cursor.fetchall()
    ↓
4. Convert to objects: [convert_row(r) for r in rows]
    ↓
5. Close connection: await db.close()
    ↓
6. Return data
```

### Example: CVE Upsert During NVD Sync

**File**: `backend/database.py`

```python
async def upsert_cves(db: aiosqlite.Connection, cves: list[dict]) -> int:
    """
    Called from: backend/scheduler.py:_run_nvd_incremental_sync()
    Input: List of CVE dictionaries from NVD API
    Output: Number of CVEs inserted/updated
    """
    
    count = 0
    for cve in cves:
        # Step 1: Extract fields
        cve_id = cve.get("cve_id")
        description = cve.get("description")
        cvss_score = cve.get("cvss_score")
        severity = cve.get("severity")
        published = cve.get("published")
        modified = cve.get("modified")
        affected_products = json.dumps(cve.get("affected_products", []))
        
        # Step 2: INSERT or UPDATE (upsert)
        query = """
            INSERT INTO cves (
                cve_id, description, cvss_score, severity,
                published, modified, affected_products, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            
            ON CONFLICT(cve_id) DO UPDATE SET
                description = excluded.description,
                cvss_score = excluded.cvss_score,
                severity = excluded.severity,
                modified = excluded.modified,
                affected_products = excluded.affected_products,
                updated_at = datetime('now')
        """
        
        # Step 3: Execute
        await db.execute(query, [
            cve_id, description, cvss_score, severity,
            published, modified, affected_products
        ])
        
        count += 1
    
    # Step 4: Commit all changes atomically
    await db.commit()
    
    return count
```

### Query Execution Pattern

```
Query Pattern:

1. Build SQL with ? placeholders:
   "SELECT * FROM cves WHERE severity = ? AND is_kev = ?"

2. Prepare parameters as tuple:
   params = ("CRITICAL", 1)

3. Execute:
   cursor = await db.execute(sql, params)

4. Fetch results:
   rows = await cursor.fetchall()  # List of Row objects

5. Convert rows to dict:
   [dict(row) for row in rows]

6. Return to caller
```

---

## 7. Scheduled Job Execution

### Job Scheduler Initialization

**File**: `backend/scheduler.py:start_scheduler()`

```python
def start_scheduler() -> None:
    global _scheduler
    
    _scheduler = AsyncIOScheduler(
        timezone=get_scheduler_timezone()  # Asia/Kolkata
    )
    
    # Add jobs...
    _scheduler.start()
```

### NVD Incremental Sync Job

**Trigger**: Every 1 hour (configurable via `NVD_SYNC_INTERVAL_HOURS`)

```
Scheduled Time (every hour):
    ↓
APScheduler fires job: run_nvd_incremental_sync()
    ↓
File: backend/scheduler.py
```

**Execution Flow**:

```python
async def run_nvd_incremental_sync() -> bool:
    """
    Step 1: Check if already running (prevent concurrent execution)
    """
    if _nvd_lock.locked():
        logger.warning("NVD sync already in progress — skipping")
        return False
    
    """
    Step 2: Acquire lock and run
    """
    async with _nvd_lock:  # asyncio.Lock - prevents concurrent runs
        await _run_nvd_incremental_sync()
    
    return True


async def _run_nvd_incremental_sync() -> None:
    """
    Step 1: Setup
    """
    logger.info("NVD incremental sync started at %s")
    
    nvd_api_key = os.environ.get("NVD_API_KEY")
    max_cves = int(os.environ.get("MAX_CVES_PER_FETCH", "2000"))
    
    """
    Step 2: Get last watermark (lastMod timestamp)
    """
    db = await get_db()
    try:
        watermark = await get_nvd_sync_watermark(db)
        # Read from sync_state table
    finally:
        await db.close()
    
    """
    Step 3: Fetch NEW/UPDATED CVEs only (since watermark)
    """
    cves, mod_end_iso, used_incremental = await fetch_nvd_cve_updates(
        nvd_api_key,
        watermark=watermark,
        days_back=14,
        overlap_minutes=15
    )
    # Location: backend/feeds/nvd.py:async def fetch_nvd_cve_updates()
    # Calls: NVD API with ?lastModStartDate=<watermark>
    
    """
    Step 4: Cap results if needed
    """
    if len(cves) > max_cves:
        logger.warning(f"Capping {len(cves)} CVEs at {max_cves}")
        cves = cves[:max_cves]
    
    """
    Step 5: Upsert CVEs to database
    """
    db = await get_db()
    try:
        await upsert_cves(db, cves)
        # Inserts or updates cves table
        
        """
        Step 6: Post-process CVEs
        """
        updated_ids = [cve.get("cve_id") for cve in cves]
        
        # Strip auto-generated summaries (if new data available)
        await strip_auto_generated_summaries(db, updated_ids)
        
        # Fill display fields (MITRE technique, PoC status)
        await backfill_display_fields(db, updated_ids)
        
        # Mark PoC availability
        await backfill_has_poc(db, updated_ids)
        
        """
        Step 7: Update watermark
        """
        new_watermark = mod_end_iso or last_modified_of_last_cve
        await set_nvd_sync_watermark(db, new_watermark)
        # Store in sync_state table
        
        await db.commit()
        
    finally:
        await db.close()
    
    logger.info(f"NVD sync complete: {len(cves)} CVEs upserted")
```

### CISA KEV Sync Job

**Trigger**: Every 15 minutes (configurable via `KEV_SYNC_INTERVAL_MINUTES`)

```python
async def run_kev_sync() -> None:
    """
    Step 1: Acquire lock (prevent concurrent runs)
    """
    async with _kev_lock:
        
        """
        Step 2: Fetch CISA KEV CSV
        """
        kev_data = await fetch_kev()
        # Location: backend/feeds/kev.py:async def fetch_kev()
        # Downloads: CSV from CISA
        
        """
        Step 3: Parse CSV and extract fields
        """
        # cve_id, product, short_description, required_action, due_date
        
        """
        Step 4: Mark matching CVEs as KEV
        """
        db = await get_db()
        try:
            # Insert into kev_deadlines table
            await upsert_kev(db, kev_data)
            
            # Mark cves.is_kev = 1 for matching CVE IDs
            await mark_cves_as_kev(db, [k["cve_id"] for k in kev_data])
            
            await db.commit()
        finally:
            await db.close()
```

### EPSS Score Sync Job

**Trigger**: Every 6 hours (configurable via `EPSS_SYNC_INTERVAL_HOURS`)

```python
async def run_epss_sync() -> None:
    async with _epss_lock:
        
        # Step 1: Fetch EPSS data (gzip CSV)
        epss_scores = await fetch_epss()
        # Location: backend/feeds/epss.py:async def fetch_epss()
        
        # Step 2: Update cves.epss_score
        db = await get_db()
        try:
            await update_epss_scores(db, epss_scores)
            
            # Step 3: Create snapshot for trending
            await snapshot_epss_scores(db)
            
            await db.commit()
        finally:
            await db.close()
```

### MITRE/ATLAS Weekly Refresh

**Trigger**: Weekly on Sunday at 02:00 IST (configurable)

```python
async def run_weekly_mitre_refresh() -> None:
    async with _mitre_refresh_lock:
        
        # Step 1: Fetch MITRE ATT&CK framework
        mitre_data = await fetch_mitre()
        # Location: backend/feeds/mitre.py:async def fetch_mitre()
        
        # Step 2: Refresh mitre_techniques table
        db = await get_db()
        try:
            await replace_mitre_techniques(db, mitre_data)
            
            # Step 3: Fetch ATLAS data
            atlas_data = await fetch_atlas()
            # Location: backend/feeds/atlas.py:async def fetch_atlas()
            
            # Step 4: Refresh atlas_techniques table
            await replace_atlas_techniques(db, atlas_data)
            await replace_atlas_case_studies(db, atlas_data)
            
            await db.commit()
        finally:
            await db.close()
```

---

## 8. Authentication & Authorization

### Authentication Status

**Current Implementation**: ✅ **NO AUTHENTICATION**

**Why**: 
- BRIEFR is designed as a public API
- No user accounts or passwords
- No JWT or OAuth tokens
- By design: "No account required. No cookies. No tracking."

### CORS Configuration (Only Form of Access Control)

**File**: `backend/main.py`

```python
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,    # List of domains allowed to call API
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Only these HTTP methods
    allow_headers=["Content-Type", "Authorization"],  # Allowed headers
)
```

**How It Works**:
```
Browser Request from https://example.com:
    ↓
Browser sends Origin: https://example.com header
    ↓
Nginx → FastAPI receives request
    ↓
CORS Middleware checks:
  Is https://example.com in ALLOWED_ORIGINS?
    ↓
If YES: Add response header Access-Control-Allow-Origin: https://example.com
  Browser allows JavaScript access to response
    ↓
If NO: Omit header
  Browser blocks JavaScript access (CORS error)
```

### Where CORS is Set

**Default**: `ALLOWED_ORIGINS=http://localhost:3000` (frontend dev server)

**Production Example**: `ALLOWED_ORIGINS=https://projectjupiter.in,https://api.projectjupiter.in`

### No Per-Endpoint Authorization

```
Every endpoint is PUBLIC (no auth checks):

✅ GET /api/cves?search=apache          → Anyone can search
✅ GET /api/health                       → Anyone can check status
✅ POST /api/ioc/lookup                  → Anyone can look up IOCs
✅ POST /api/ai/summary                  → Anyone can get AI analysis
✅ POST /api/refresh/nvd                 → Anyone can trigger refresh
```

**Security Implication**:
- ⚠️ No rate limiting at application level
- ⚠️ No quota per user
- ⚠️ Anyone with access to API can query all data
- ✅ But no sensitive data (all public CVE information)
- ✅ External API keys protected (not exposed in responses)

---

## 9. External API Integration

### All External API Calls in Application

| API | Called From | When | Purpose | Auth |
|-----|----------|------|---------|------|
| **NVD** | `backend/feeds/nvd.py` | Hourly | Fetch CVE data | API key |
| **CISA KEV** | `backend/feeds/kev.py` | Every 15 min | Exploited vulns | None |
| **FIRST EPSS** | `backend/feeds/epss.py` | Every 6 hr | Risk scores | None |
| **MITRE ATT&CK** | `backend/feeds/mitre.py` | Weekly | Attack techniques | None |
| **ATLAS** | `backend/feeds/atlas.py` | Weekly | AI techniques | None |
| **OSV.dev** | `backend/feeds/osv.py` | On-demand | Package vulns | None |
| **GreyNoise** | `backend/feeds/extended.py` | On-demand | CVE scans | API key |
| **Sploitus** | `backend/feeds/extended.py` | On-demand | Public exploits | None |
| **CIRCL CVE** | `backend/feeds/extended.py` | On-demand | Extended data | None |
| **VirusTotal** | `backend/enrichment/ioc.py` | On-demand (cache) | IP/hash/domain lookup | API key |
| **AbuseIPDB** | `backend/enrichment/ioc.py` | On-demand (cache) | IP reputation | API key |
| **abuse.ch** | `backend/enrichment/ioc.py` | On-demand (cache) | Malware/URL hashes | API key |
| **Groq** | `backend/ai/summary.py` | PDF export | AI summary (primary) | API key |
| **Anthropic** | `backend/ai/summary.py` | PDF export (fallback) | AI summary (fallback) | API key |

### NVD API Call Pattern

**File**: `backend/feeds/nvd.py`

```python
async def fetch_nvd_cve_updates(
    api_key: str,
    watermark: str | None = None,
    days_back: int = 14,
    overlap_minutes: int = 15
) -> tuple[list[dict], str, bool]:
    """
    Step 1: Build request parameters
    """
    params = {
        "pageSize": 2000,  # Max results per page
        "sort": "lastModified:desc"
    }
    
    # Use watermark if available (incremental sync)
    if watermark:
        # Query: lastModStartDate <= watermark < lastModEndDate
        params["lastModStartDate"] = watermark
        params["lastModEndDate"] = (
            datetime.fromisoformat(watermark) + timedelta(hours=1)
        ).isoformat()
    else:
        # Full sync: last N days
        params["pubStartDate"] = (
            datetime.now() - timedelta(days=days_back)
        ).isoformat()
    
    if api_key:
        params["apiKey"] = api_key  # Use API key if provided (higher quota)
    
    """
    Step 2: Make requests with pagination
    """
    all_cves = []
    page = 0
    
    async with httpx.AsyncClient() as client:
        while True:
            params["startIndex"] = page * 2000
            
            # Step 3: Make HTTP request
            response = await client.get(
                NVD_BASE_URL,  # https://services.nvd.nist.gov/rest/json/cves/2.0
                params=params,
                timeout=30.0
            )
            
            # Step 4: Handle response
            if response.status_code == 404:
                break  # No more results
            
            response.raise_for_status()  # Raise on error
            
            data = response.json()
            
            # Step 5: Extract CVEs
            cves = data.get("vulnerabilities", [])
            all_cves.extend(cves)
            
            # Step 6: Check if more pages
            if len(cves) < 2000:
                break  # Last page
            
            page += 1
            
            # Step 7: Rate limiting
            await asyncio.sleep(RATE_LIMIT_WAIT)  # 35 seconds
            
            # Record API call
            await record_api_call("nvd", service="nvd")
    
    return all_cves, mod_end_iso, used_incremental
```

### VirusTotal API Call Pattern

**File**: `backend/enrichment/ioc.py`

```python
async def _lookup_vt_ip(client: httpx.AsyncClient, ip: str, api_key: str) -> dict:
    """
    Step 1: Build URL
    """
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
    
    """
    Step 2: Build headers
    """
    headers = {
        "x-apikey": api_key,  # Authentication via header
        "Accept": "application/json"
    }
    
    try:
        """
        Step 3: Make request
        """
        response = await client.get(
            url,
            headers=headers,
            timeout=30.0
        )
        
        """
        Step 4: Handle errors
        """
        if response.status_code == 404:
            logger.info(f"IP {ip} not in VirusTotal")
            return {}
        
        if response.status_code == 401:
            logger.error("VirusTotal auth failed - check API key")
            return {}
        
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit - retry later")
            return {}
        
        # Raise for other 4xx/5xx errors
        response.raise_for_status()
        
        """
        Step 5: Parse response
        """
        data = response.json()
        
        attributes = data.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})
        
        return {
            "malicious_votes": stats.get("malicious", 0),
            "total_votes": sum(stats.values()),
            "country": attributes.get("country"),
            "tags": attributes.get("tags", []),
            "last_seen": attributes.get("last_analysis_date")
        }
    
    except httpx.HTTPStatusError as exc:
        logger.error(f"VT HTTP error for {ip}: {exc.status_code}")
        return {}
    except Exception as exc:
        logger.error(f"VT lookup error for {ip}: {exc}")
        return {}
```

### Groq API Call Pattern

**File**: `backend/ai/summary.py`

```python
async def _call_groq_api(system_prompt: str, user_prompt: str) -> dict:
    """
    Step 1: Get API key from environment
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    """
    Step 2: Build request payload (OpenAI-compatible)
    """
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
        "response_format": { "type": "json_object" }
    }
    
    """
    Step 3: Build headers
    """
    headers = {
        "Authorization": f"Bearer {api_key}",  # Bearer token auth
        "Content-Type": "application/json"
    }
    
    """
    Step 4: Make request
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
        )
        
        """
        Step 5: Handle errors
        """
        if response.status_code == 401:
            raise ValueError("Invalid Groq API key")
        
        if response.status_code == 429:
            raise ValueError("Groq rate limit exceeded")
        
        response.raise_for_status()
        
        """
        Step 6: Parse response
        """
        result = response.json()
        
        # Extract text from response
        content = result["choices"][0]["message"]["content"]
        
        # Parse JSON from LLM response
        summary_json = json.loads(content)
        
        return {
            "executive_summary": summary_json["executive_summary"],
            "key_findings": summary_json["key_findings"],
            "confidence": summary_json["confidence"]
        }
```

---

## 10. Complete Request Lifecycle

### Full Example: User Searches CVEs with Custom Stack

```
┌─────────────────────────────────────────────────────────────────┐
│ USER ACTION: Enters "apache" in search, sets stack to "nginx"  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │ FRONTEND (frontend/src/)     │
        └──────────────┬──────────────┘
                       │
      ┌────────────────▼──────────────┐
      │ CVEFeed.jsx:                  │
      │ 1. Detects filter change      │
      │ 2. Calls fetchCVEs()          │
      └────────────────┬──────────────┘
                       │
     ┌─────────────────▼──────────────┐
     │ api.js:fetchCVEs()            │
     │ 1. Builds query parameters    │
     │    ?search=apache&stack=nginx │
     │ 2. Calls request()            │
     │ 3. Makes HTTP GET             │
     └─────────────────┬──────────────┘
                       │
       HTTP GET /api/cves?search=apache&stack=nginx
                       │
        ┌──────────────▼──────────────┐
        │ BACKEND (backend/)           │
        └──────────────┬──────────────┘
                       │
     ┌─────────────────▼──────────────┐
     │ main.py:@app.get("/api/cves") │
     │ 1. Pydantic validates query   │
     │ 2. Calls search_cves()        │
     └─────────────────┬──────────────┘
                       │
    ┌──────────────────▼──────────────┐
    │ main.py:search_cves()           │
    │ 1. Build WHERE clause:          │
    │    - LIKE '%apache%'            │
    │    - user_stack_matches(stack)  │
    │ 2. Get database connection      │
    │ 3. Execute SQL query            │
    └──────────────────┬──────────────┘
                       │
      ┌────────────────▼──────────────┐
      │ database.py:get_db()          │
      │ 1. Connect to SQLite          │
      │ 2. Enable WAL, FK constraints │
      │ 3. Return connection          │
      └────────────────┬──────────────┘
                       │
      ┌────────────────▼──────────────┐
      │ DATABASE: /opt/briefr/db      │
      │ 1. SELECT * FROM cves         │
      │    WHERE:                     │
      │    - description LIKE         │
      │      '%apache%'               │
      │    - affected_products        │
      │      matches 'nginx'          │
      │    ORDER BY published DESC    │
      │ 2. Return 50 rows             │
      └────────────────┬──────────────┘
                       │
      ┌────────────────▼──────────────┐
      │ Backend processes results:    │
      │ 1. Convert rows to dicts      │
      │ 2. Serialize JSON             │
      │ 3. Return response            │
      └────────────────┬──────────────┘
                       │
    HTTP 200 OK:
    [{
      "cve_id": "CVE-2024-1234",
      "description": "Apache RCE...",
      "cvss_score": 9.8,
      "affected_products": ["apache:2.4.x"]
    }, ...]
                       │
        ┌──────────────▼──────────────┐
        │ FRONTEND receives response  │
        └──────────────┬──────────────┘
                       │
     ┌─────────────────▼──────────────┐
     │ api.js:request()              │
     │ 1. Check response.ok (200)    │
     │ 2. Parse JSON                 │
     │ 3. Return data                │
     └─────────────────┬──────────────┘
                       │
    ┌────────────────▼──────────────┐
    │ CVEFeed.jsx:                  │
    │ 1. Receives results array     │
    │ 2. setCves(results)           │
    │ 3. React re-renders component │
    └────────────────┬──────────────┘
                       │
    ┌────────────────▼──────────────┐
    │ CVEFeed renders CVECards      │
    │ User sees filtered results    │
    └────────────────────────────────┘
```

---

## Summary Table: Function Call Chain

| Layer | File | Function | Called By | Calls | Purpose |
|-------|------|----------|-----------|-------|---------|
| **Frontend** | CVEFeed.jsx | (component) | React | fetchCVEs() | Detect filter change |
| **Frontend** | api.js | fetchCVEs() | CVEFeed.jsx | request() | Build query params |
| **Frontend** | api.js | request() | fetchCVEs() | fetch() | Make HTTP request |
| **Backend** | main.py | @app.get("/api/cves") | Nginx | search_cves() | HTTP handler |
| **Backend** | main.py | search_cves() | @app.get() | get_db() | Get connection |
| **Backend** | database.py | get_db() | search_cves() | aiosqlite | Open SQLite |
| **Backend** | database.py | execute() | search_cves() | SQLite | Execute query |
| **Database** | briefr.db | SQL | execute() | (storage) | Query data |

---

**Document Complete**  
**Last Updated**: 2026-06-05  
**For Questions**: Reference the specific section above with filenames and function signatures
