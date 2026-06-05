# BRIEFR Repository Structure - Complete Folder-by-Folder Guide

**Target Audience**: Cybersecurity professionals with minimal software development experience  
**Document Version**: 1.0  
**Date**: 2026-06-05

---

## Quick Navigation

- [Root Level](#root-level-files)
- [Backend Folder](#backendroot-directory)
  - [backend/feeds](#backendfeeds)
  - [backend/ai](#backendai)
  - [backend/enrichment](#backendenrichment)
  - [backend/scoring](#backendscoring)
  - [backend/templates](#backendtemplates)
  - [backend/scripts](#backendscripts)
  - [backend/tests](#backendtests)
- [Frontend Folder](#frontendroot-directory)
  - [frontend/src](#frontendsrc)
  - [frontend/src/components](#frontendsrccomponents)
  - [frontend/src/context](#frontendsrccontext)
  - [frontend/src/pages](#frontendsrcpages)
  - [frontend/src/utils](#frontendsrcutils)
- [Deploy Folder](#deploydirectory)
- [Screenshots Folder](#screenshotsdirectory)

---

## Root Level Files

### `/workspaces/briefr/.git/`
**Purpose**: Version control history and metadata  
**Security Level**: ⚠️ HIGH SENSITIVITY  
**What It Contains**:
- Complete history of every code change ever made
- Author information and timestamps
- All branches and commits

**Why It Matters for Security**:
- Can reveal old secrets or misconfigurations that were later removed
- Shows development decisions and security fixes applied over time
- If exposed publicly, allows attackers to see the entire development history

**Who Accesses It**: Git version control system (developers and CI/CD)

---

### `/workspaces/briefr/.gitignore`
**Purpose**: Tells Git which files NOT to track/upload  
**Security Level**: 🔴 CRITICAL FOR SECURITY  
**What It Contains**:
```
__pycache__/        ← Python compiled files (not needed, bulky)
*.py[cod]           ← Python bytecode files
.env                ← LOCAL ENVIRONMENT VARIABLES (SECRETS!)
*.db                ← SQLite database file (user data)
*.db-wal, *.db-shm  ← Database temporary files
.venv/, venv/       ← Python virtual environment (dependencies)
dist/, build/       ← Compiled frontend/backend packages
```

**Why It Matters for Security**:
- The `.env` file is explicitly ignored - this protects API keys from being accidentally uploaded
- If someone removes this file from `.gitignore`, secrets would be exposed
- Database files are ignored to prevent committing live data

**What Could Go Wrong**:
- If developer edits `.gitignore` and removes `.env`, all API keys get uploaded to GitHub
- Database with sensitive CVE data gets committed

---

### `/workspaces/briefr/README.md`
**Purpose**: Main documentation for the project  
**Security Level**: 🟢 LOW (PUBLIC INFORMATION)  
**What It Contains**:
- Project description and features
- Setup instructions
- Technology stack
- Data sources and refresh rates
- Prerequisites and API key requirements

**How It Interacts**:
- Read by new developers or security auditors to understand the project
- Lists all external services and their data refresh frequencies

---

### `/workspaces/briefr/TECHNICAL_INVENTORY.md`
**Purpose**: Detailed technical architecture documentation (created earlier)  
**Security Level**: 🟢 LOW (TECHNICAL REFERENCE)  
**How It Interacts**:
- Reference document for understanding component interactions
- Lists all dependencies and external APIs

---

### `/workspaces/briefr/backend/.env.example`
**Purpose**: Template showing what environment variables are needed  
**Security Level**: 🟢 LOW (EXAMPLE ONLY - NO REAL SECRETS)  
**What It Contains**:
```
NVD_API_KEY=your_nvd_api_key_here
VIRUSTOTAL_API_KEY=your_vt_api_key_here
ABUSEIPDB_API_KEY=your_abuseipdb_key_here
GREYNOISE_API_KEY=your_greynoise_api_key_here
ABUSECH_AUTH_KEY=your_abusech_auth_key_here
ALLOWED_ORIGINS=http://localhost:5173
...
```

**Why It Matters for Security**:
- Safe to commit because it has placeholder values
- Shows developers what secrets they need to provide
- Never put actual keys here

**How It's Used**:
1. Developer copies to `.env` (which is ignored)
2. Fills in with real API keys
3. Backend reads from `.env` file on startup

---

### `/workspaces/briefr/backend/.python-version`
**Purpose**: Specifies Python version requirement  
**What It Contains**:
```
3.13
```

**Why It Matters**:
- Tells developers and CI/CD which Python version to use
- Prevents compatibility issues from older Python versions

---

### `/workspaces/briefr/backend/requirements.txt`
**Purpose**: List of Python dependencies (libraries)  
**Security Level**: 🔴 IMPORTANT FOR SECURITY REVIEW  
**What It Contains**:
```
fastapi==0.136.3              ← Web server framework
uvicorn[standard]==0.48.0     ← Application server
httpx==0.28.1                 ← HTTP client for API calls
apscheduler==3.11.2           ← Job scheduler
python-dotenv==1.2.2          ← Reads .env files
pydantic==2.13.4              ← Data validation
aiosqlite==0.22.1             ← Database driver
PyYAML==6.0.2                 ← Config file parser
```

**Why It Matters for Security**:
- Each library could have vulnerabilities
- Version numbers locked = reproducible builds (security best practice)
- Attackers sometimes look for outdated dependencies

**How It's Used**:
```bash
pip install -r requirements.txt  # Installs all dependencies
```

---

## backend/ Root Directory

**Purpose**: The entire backend server application  
**Entry Point**: `backend/main.py`  
**Startup Command**: `uvicorn main:app --host 0.0.0.0 --port 8000`

### Startup Process Flow

```
1. System starts backend service
   ↓
2. Python executes main.py
   ↓
3. FastAPI app initializes with lifespan() function
   ↓
4. Databases initialized (tables created if needed)
   ↓
5. APScheduler starts with scheduled jobs
   ↓
6. Uvicorn listens on port 8000
   ↓
7. Ready to accept requests from nginx proxy
```

---

### `backend/main.py`
**Security Level**: 🔴 CRITICAL  
**What It Does**:
- Defines all REST API endpoints (the "brain" of the app)
- Sets up security middleware (CORS, security headers)
- Loads environment variables
- Initializes database connection on startup
- Validates incoming requests

**Key Responsibilities**:
1. **API Endpoints** (what clients can ask for):
   - `/api/health` - Status check
   - `/api/cves` - Search CVEs with filters
   - `/api/cves/{id}` - Get single CVE details
   - `/api/ioc/lookup` - Check if an IP/hash/domain is malicious
   - `/api/ai/summary` - Generate AI threat analysis (for PDF export)
   - `/api/investigation/summary` - Analyze investigation threads
   - `/api/refresh/*` - Manual data refresh triggers

2. **Security Middleware**:
   - CORS (Cross-Origin Resource Sharing) - allows frontend to call backend
   - Security headers - prevents browser exploits
   - Input validation - ensures requests follow expected format

3. **Pydantic Models** (request/response definitions):
   - Define what data clients can send
   - Automatically validate and reject invalid requests
   - Example: `AiSummaryRequest` specifies exact fields needed for AI summary

**Security-Sensitive Elements**:
- ✅ CORS middleware - controls which origins can access (environment variable)
- ✅ Security header middleware - adds HTTP security headers
- ✅ `load_dotenv()` - reads secrets from `.env` file
- ⚠️ No authentication on endpoints (by design - public API)
- ⚠️ No rate limiting at application level

**How It Interacts**:
- Calls functions from `database.py` to query data
- Calls functions from all `feeds/` modules for data refresh
- Calls functions from `enrichment/` for IOC lookups
- Calls functions from `ai/` for LLM summaries
- Receives requests from nginx (frontend proxy)

---

### `backend/database.py`
**Security Level**: 🔴 CRITICAL (Contains data access layer)  
**What It Does**:
- Manages SQLite database connection
- Defines database schema (table structure)
- Provides helper functions to query data
- Initializes database on startup

**Key Responsibilities**:

1. **Schema Initialization** (creates tables if they don't exist):
   ```
   cves              ← CVE records (vulnerability data)
   kev_deadlines     ← CISA KEV remediation deadlines
   mitre_techniques  ← MITRE ATT&CK attack techniques
   cve_technique_map ← Links CVEs to techniques
   atlas_techniques  ← AI-focused attack techniques
   atlas_case_studies← Historical AI attack examples
   epss_history      ← Historical exploit probability scores
   ioc_cache         ← Cached IOC enrichment results (6-hour TTL)
   api_usage         ← Usage statistics per service
   sync_state        ← Watermarks for incremental updates
   ```

2. **Database Settings**:
   - WAL Mode: Allows readers while writer is active
   - Foreign Keys Enabled: Prevents orphaned data
   - Row Factory: Returns results as dict-like objects

3. **Query Helpers** (examples):
   - `get_cves()` - Search/filter CVEs
   - `get_cve_by_id()` - Fetch single CVE
   - `upsert_cve()` - Insert or update CVE
   - `get_ioc_cache()` - Check if IOC already looked up
   - `set_ioc_cache()` - Store IOC lookup result

**Security-Sensitive Elements**:
- ✅ Uses parameterized queries (prevents SQL injection)
- ⚠️ Database file on disk (`briefr.db`) - physical access could expose all data
- ⚠️ No encryption of database at rest

**How It Interacts**:
- Called by `main.py` for all data queries
- Called by scheduler jobs in `scheduler.py` for data updates
- Called by IOC lookup functions in `enrichment/ioc.py`

---

### `backend/scheduler.py`
**Security Level**: 🟡 MEDIUM (Manages background jobs)  
**What It Does**:
- Uses APScheduler library to run tasks on schedule
- Starts jobs when backend starts
- Stops jobs when backend shuts down
- Prevents duplicate jobs from running simultaneously

**Scheduled Jobs**:

| Job Name | Schedule | What It Does | Fails If |
|----------|----------|------------|----------|
| `nvd_incremental_sync` | Every 1 hour (configurable) | Fetches new/updated CVEs from NVD | NVD API unreachable |
| `kev_sync` | Every 15 minutes | Downloads CISA KEV list | Network error |
| `epss_sync` | Every 6 hours | Gets exploit probability scores | FIRST.org unreachable |
| `mitre_weekly_refresh` | Weekly (Sunday 02:00) | Updates MITRE ATT&CK techniques | GitHub unreachable |
| `atlas_weekly_refresh` | Weekly (as part of MITRE) | Updates AI attack techniques | GitHub unreachable |
| `ai_context_refresh` | On-demand (manual trigger) | Tags CVEs by AI framework affected | Groq/Anthropic unreachable |

**Lock System**:
- Each job uses an `asyncio.Lock` to prevent concurrent runs
- If job A is running, job B waits until A completes
- Prevents database corruption from simultaneous updates

**Timezone Configuration**:
- Default: `Asia/Kolkata` (environment-configurable)
- Affects when weekly jobs run
- Used for displaying refresh times to users

**Security-Sensitive Elements**:
- ✅ Locks prevent race conditions (data corruption)
- ⚠️ Single-node only - breaks if multiple server instances run
- ⚠️ In-memory locks don't work with load balancing

**How It Interacts**:
- Calls functions in `feeds/` modules to fetch data
- Calls database functions to store results
- Checked by `main.py` for status queries
- Sends notifications back to frontend via `/api/refresh/status`

---

### `backend/tracking.py`
**Security Level**: 🟡 MEDIUM (Analytics)  
**What It Does**:
- Records when external APIs are called
- Tracks IOC lookup usage (not the IOC values themselves)
- Provides usage statistics

**Data Tracked**:
```
service: VirusTotal, AbuseIPDB, NVD, EPSS, etc.
date: YYYY-MM-DD (UTC)
month: YYYY-MM (for monthly aggregation)
count: How many times API was called
```

**Why It Matters for Security**:
- ✅ Tracks API call counts (can detect abuse)
- ✅ Doesn't log actual IOC values (privacy-preserving)
- ⚠️ If database accessed by attacker, reveals usage patterns

**How It Interacts**:
- Called by functions in `enrichment/ioc.py` to log IOC lookups
- Called by functions in `feeds/` modules to log API calls
- Results shown in `/api/stats` endpoint

---

### `backend/investigation_summary.py`
**Security Level**: 🟡 MEDIUM (Data aggregation)  
**What It Does**:
- Aggregates related CVEs, IOCs, and threat actors
- Answers: "If I investigate this CVE, what else should I check?"
- Used when user clicks "Summarize Investigation" in frontend

**Process**:
1. Receives list of CVEs/IOCs/actors
2. Queries database for relationships
3. Groups related items
4. Returns structured summary

**How It Interacts**:
- Called by `/api/investigation/summary` endpoint in `main.py`
- Uses database queries from `database.py`
- Results displayed in InvestigationPanel component

---

## backend/feeds/ Directory

**Purpose**: Modules that fetch data from external sources  
**Overall Role**: "Data ingestion layer"  

Each file handles one data source and follows same pattern:
```
1. Fetch data from external API/file
2. Transform to standardized format
3. Store in database via database.py
4. Update watermark/timestamp
```

---

### `backend/feeds/nvd.py`
**Purpose**: Fetch CVE data from National Vulnerability Database  
**Security Level**: 🟡 MEDIUM (Fetches from NIST, handles API key)  

**What It Does**:
- Queries NVD REST API: `services.nvd.nist.gov/rest/json/cves/2.0`
- Fetches only NEW/UPDATED CVEs (not all 200,000+ CVEs)
- Extracts: CVE ID, description, CVSS score, severity, affected products
- Stores in `cves` table

**Watermark System** (clever optimization):
- Keeps track of last `lastMod` timestamp checked
- Next run starts from that timestamp
- Prevents re-downloading same data

**Error Handling**:
- 35-second delay between requests (NVD rate limit)
- Continues on individual CVE errors
- Logs failures for debugging

**Security-Sensitive Elements**:
- ✅ Uses `NVD_API_KEY` from environment
- ⚠️ If API key leaked, attacker could consume API quota
- ⚠️ No authentication to NVD itself (key just identifies your quota)

**How It Interacts**:
- Called by `scheduler.py` every hour
- Called by `main.py` for manual `/api/refresh/nvd` trigger
- Stores results in database via `database.py`

---

### `backend/feeds/kev.py`
**Purpose**: Fetch CISA Known Exploited Vulnerabilities list  
**Security Level**: 🟢 LOW (Public data, no API key)  

**What It Does**:
- Downloads CSV file from CISA: `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.csv`
- Parses CSV and extracts fields
- Marks matching CVEs as `is_kev=1` in database

**Data Extracted**:
- CVE ID
- Product name
- Remediation deadline
- Required action

**Why It Matters**:
- KEV list = vulnerabilities ACTIVELY BEING EXPLOITED
- Critical for prioritization
- 15-minute refresh = nearly real-time

**Error Handling**:
- Continues if individual rows malformed
- Entire file cached in memory during parse

**How It Interacts**:
- Called by `scheduler.py` every 15 minutes
- Marks matching CVEs in `kev_deadlines` table
- Used by frontend to show "KEV only" filter

---

### `backend/feeds/epss.py`
**Purpose**: Fetch FIRST.org EPSS (Exploit Prediction Scoring System)  
**Security Level**: 🟢 LOW (Public data)  

**What It Does**:
- Downloads compressed CSV from EPSS API
- Parses gzip stream (efficient for large files)
- Updates `epss_score` field in `cves` table
- Creates historical snapshot in `epss_history` table

**Data Extracted**:
- CVE ID
- EPSS score (0.0 to 1.0, probability of exploitation)
- Percentile ranking

**Why It Matters**:
- EPSS = likelihood a vulnerability will be exploited
- Higher score = more likely to be exploited
- Helps prioritize which CVEs to patch first

**Performance Optimization**:
- Asyncio streaming - doesn't load entire file in memory
- Batch inserts to database

**How It Interacts**:
- Called by `scheduler.py` every 6 hours
- Creates snapshots for trending analysis
- Used by frontend to show "EPSS score" filter

---

### `backend/feeds/mitre.py`
**Purpose**: Fetch MITRE ATT&CK framework (attack techniques)  
**Security Level**: 🟡 MEDIUM (External XML parsing)  

**What It Does**:
- Downloads XML/JSON from MITRE ATT&CK GitHub: `github.com/mitre/cti`
- Extracts technique information: name, description, tactic, platforms
- Links CVEs to techniques via `cve_technique_map` junction table
- Creates matrix of techniques

**Key Concepts**:
- **Tactic**: Goal of attack (e.g., "Execution", "Persistence")
- **Technique**: Method to achieve goal (e.g., "Command Line Interface")
- **Sub-technique**: Specific variation (e.g., "PowerShell")

**Data Extracted**:
- Technique ID (T1234 format)
- Name and description
- Tactic classification
- Detection methods
- Associated CVEs

**Why It Matters for Security**:
- Links vulnerabilities to attack techniques
- Allows filtering by attack type
- Helps understand exploitation chains

**Error Handling**:
- XML parsing with error recovery
- Skips malformed entries
- Logs parsing issues

**How It Interacts**:
- Called by `scheduler.py` weekly (Sunday 02:00 IST)
- Populates `mitre_techniques` table
- Frontend uses for technique-based filtering

---

### `backend/feeds/atlas.py`
**Purpose**: Fetch ATLAS (AI-focused attack techniques)  
**Security Level**: 🟡 MEDIUM (YAML parsing, external files)  

**What It Does**:
- Downloads ATLAS framework YAML from GitHub
- Similar to MITRE but focused on AI/ML attacks
- Extracts technique info and case studies
- Links to CVEs affecting AI frameworks

**Key Difference from MITRE**:
- MITRE ATT&CK = generic attack techniques
- ATLAS = techniques targeting AI systems specifically
- Example: "ML Model Extraction" attack

**Data Extracted**:
- Technique ID
- Name and description
- Associated case studies
- Affected AI platforms (PyTorch, TensorFlow, etc.)
- Historical attack examples

**Why It Matters**:
- Security for AI-based systems (rapidly growing threat)
- Tracks AI-specific vulnerabilities
- Helps assess risk for ML pipelines

**Security-Sensitive Elements**:
- ✅ YAML parsing (can be risky with untrusted input)
- ✅ Validates structure before storing
- ⚠️ If GitHub compromised, malicious YAML could be injected

**How It Interacts**:
- Called by `scheduler.py` weekly (same as MITRE)
- Populates `atlas_techniques` and `atlas_case_studies` tables
- Frontend shows "AI Threats" panel with ATLAS data

---

### `backend/feeds/osv.py`
**Purpose**: Fetch OSV.dev vulnerability database  
**Security Level**: 🟢 LOW (Public API)  

**What It Does**:
- On-demand lookup of open-source package vulnerabilities
- Queries `api.osv.dev` for specific package names
- Returns vulnerability info for installed dependencies

**Why It Matters**:
- Complements NVD (focused more on open source packages)
- Helps with supply chain vulnerability tracking
- Used when analyzing affected products

**Called When**:
- User clicks on a CVE affecting a package
- Frontend requests `/api/cves/{id}` endpoint
- `osv.py` fetches related package vulns

**How It Interacts**:
- Called by endpoints in `main.py`
- Not scheduled; on-demand only
- Results cached to avoid repeated requests

---

### `backend/feeds/extended.py`
**Purpose**: Fetch extended threat intelligence from multiple sources  
**Security Level**: 🔴 HIGH (Handles multiple API keys)  

**What It Does**:
```
For each CVE, fetches:
├─ GreyNoise: Active scans/exploitation
├─ Sploitus: Public exploits published
├─ CIRCL CVE: Extended CVE intelligence
└─ abuse.ch: Malware hash/URL reputation
```

**APIs Used**:

| Source | Endpoint | Auth | Cached? |
|--------|----------|------|---------|
| GreyNoise | api.greynoise.io | `GREYNOISE_API_KEY` | 6h |
| Sploitus | sploitus.com | None (public) | 6h |
| CIRCL CVE | www.circl.lu/api/v1/cve/ | None | 6h |
| abuse.ch | auth.abuse.ch | `ABUSECH_AUTH_KEY` | 6h |

**Why It Matters**:
- GreyNoise: Shows if vulnerability is actively scanned/exploited
- Sploitus: Public exploit availability (highest priority)
- CIRCL: Enriched CVE data
- abuse.ch: Malware/phishing linked to vulnerability

**Error Handling**:
- Continues if one source fails
- Returns partial results
- Caches failures to avoid repeated requests

**Security-Sensitive Elements**:
- 🔴 `GREYNOISE_API_KEY` - identifies your account
- 🔴 `ABUSECH_AUTH_KEY` - authentication
- ✅ 6-hour cache reduces API calls
- ⚠️ If keys leaked, attacker could consume quota/abuse credentials

**How It Interacts**:
- Called from endpoints in `main.py` for detail views
- Results cached in `ioc_cache` table
- Enhanced CVE details shown in DetailDrawer component

---

### `backend/feeds/ai_context.py`
**Purpose**: Tag CVEs by affected AI/ML frameworks  
**Security Level**: 🟡 MEDIUM (Local regex processing)  

**What It Does**:
- Analyzes CVE description text
- Uses regex patterns to find mentions of AI frameworks
- Tags: PyTorch, TensorFlow, Keras, Hugging Face, ONNX, etc.
- Stores tags in `cves.has_ai_context` field

**Process**:
```
For each CVE:
1. Extract affected products and description
2. Search for AI framework keywords (case-insensitive)
3. If found, mark has_ai_context=1
4. Store framework names as tags
```

**Frameworks Detected**:
- PyTorch, TensorFlow, Keras
- Hugging Face, JAX
- ONNX, scikit-learn
- And others based on vulnerability descriptions

**Why It Matters**:
- AI teams need to know which vulnerabilities affect their stack
- Helps with "AI profile" filtering in frontend
- Prioritizes vulnerabilities relevant to ML teams

**Error Handling**:
- Skips CVEs with no description
- Gracefully handles encoding issues
- Logs processing errors

**How It Interacts**:
- Called periodically from `scheduler.py`
- Results used by `ai_context_only` filter in frontend
- Component: AIThreats.jsx shows affected frameworks

---

## backend/enrichment/ Directory

**Purpose**: Enhance vulnerability data with additional context  
**Overall Role**: "Data augmentation and third-party lookups"

---

### `backend/enrichment/ioc.py`
**Purpose**: Look up Indicators of Compromise (IOCs)  
**Security Level**: 🔴 CRITICAL (Handles external API keys and user data)  

**What It Does**:
- Takes an IOC value: IP address, file hash, domain, URL
- Queries: VirusTotal, AbuseIPDB, abuse.ch (MalwareBazaar/URLhaus)
- Returns: malware scores, reputation, geographic data

**Supported IOC Types**:
- **IP Address**: Checked against VirusTotal + AbuseIPDB
- **File Hash** (MD5/SHA1/SHA256): Checked against VirusTotal + abuse.ch
- **Domain**: Checked against VirusTotal
- **URL**: Checked against VirusTotal + URLhaus

**Results Returned**:
```
{
  "value": "1.2.3.4",
  "type": "ip",
  "malicious_votes": 15,
  "total_votes": 80,
  "abuse_score": 75,
  "country": "CN",
  "tags": ["scanner", "botnet"],
  "last_seen": "2026-06-04T12:00:00Z"
}
```

**Caching System** (6-hour TTL):
- Stores results in `ioc_cache` table
- Within 6 hours: returns cached result
- After 6 hours: re-queries external APIs
- Prevents hammering external services + speeds up repeated lookups

**Privacy Protection**:
- ✅ IOC values never logged to files
- ✅ 6-hour cache is local only
- ⚠️ External services (VirusTotal, AbuseIPDB) receive the IOC value
- ⚠️ Those external services log the lookup (per their terms)

**Security-Sensitive Elements**:
- 🔴 `VIRUSTOTAL_API_KEY` - identifies account, subject to quota
- 🔴 `ABUSEIPDB_API_KEY` - identifies account
- 🔴 `ABUSECH_AUTH_KEY` - authentication for abuse.ch
- ✅ 6-hour cache reduces exposure
- ⚠️ If keys leaked, attacker could perform unlimited lookups

**Error Handling**:
```
API Returns 404: IOC not found in that service
API Returns 403/401: Authentication failed (bad key)
API Returns 429: Rate limited (too many requests)
Network timeout: Connection failed
```
All failures are cached to avoid repeated errors.

**How It Interacts**:
- Called by `/api/ioc/lookup` endpoint in `main.py`
- Stores results in `ioc_cache` table via `database.py`
- Frontend component IOCLookup.jsx displays results
- Results shown in DetailDrawer component

---

### `backend/enrichment/cve.py`
**Purpose**: Extract useful metadata from CVE records  
**Security Level**: 🟡 MEDIUM (Data parsing, no external calls)  

**What It Does**:
- Analyzes CVE references and metadata
- Extracts MITRE technique IDs from reference URLs
- Detects if Proof-of-Concept (PoC) code exists
- Identifies CWE (Common Weakness Enumeration) IDs
- Detects patch availability

**Key Functions**:

1. **`extract_mitre_technique(references)`**
   - Scans reference URLs for MITRE ATT&CK links
   - Extracts technique ID (e.g., T1234.005)
   - Used during CVE ingestion

2. **`has_public_poc(references)`**
   - Checks if reference URLs point to exploits
   - Looks for keywords: "poc", "exploit", "proof-of-concept"
   - Checks exploit-specific domains: Exploit-DB, Packetstorm, Metasploit

3. **URL Analysis**:
   - Looks for patterns: `poc.zip`, `proof_of_concept`, `/poc`
   - Checks GitHub/GitLab for exploit repositories
   - Identifies Metasploit modules

**Why It Matters for Security**:
- PoC existence = higher exploitation risk
- MITRE mapping = attack technique context
- CWE ID = root cause understanding

**Process Flow**:
```
NVD CVE Data
    ↓
extract_mitre_technique()  → Links to attack techniques
has_public_poc()           → Flags if exploit exists
extract_cwe_ids()          → Identifies weakness types
    ↓
Enhanced CVE stored in database
```

**How It Interacts**:
- Called during CVE ingestion in `feeds/nvd.py`
- Results stored in `cves.mitre_technique` and `cves.has_poc` fields
- Frontend uses flags to highlight risky CVEs

---

## backend/scoring/ Directory

**Purpose**: Calculate risk scores for vulnerabilities  

---

### `backend/scoring/risk.py`
**Security Level**: 🟡 MEDIUM (Algorithm could favor false positives/negatives)  

**What It Does**:
- Calculates contextual risk score for each CVE
- Considers: CVSS score, EPSS score, KEV status, PoC availability
- Matches CVE against user's technology stack
- Outputs 0-100 risk score

**Scoring Factors** (example):
```
Base CVSS Score (0.0-10.0)
    ↓
Multiplied by EPSS probability (0.0-1.0)
    ↓
Boosted if CVE in CISA KEV list
    ↓
Boosted if public PoC exists
    ↓
Boosted if matches user tech stack
    ↓
Final Risk Score (0-100)
```

**Tech Stack Matching** (Innovation):
- User provides: "We use Apache, MySQL, Node.js"
- System tokenizes this into keywords
- Searches CVE affected products for matching tokens
- If match found, increases risk score
- Example: CVE affecting Apache → higher score for users with Apache

**Why It Matters**:
- Same CVE = different risk for different organizations
- A database CVE = critical for DB team, irrelevant for web team
- Risk scoring helps prioritize patches

**How It Interacts**:
- Called from endpoints in `main.py`
- Uses data from `database.py` (CVSS, EPSS, KEV flag, PoC flag)
- Frontend uses scores for sorting/filtering

---

## backend/templates/ Directory

**Purpose**: Generate human-readable threat intelligence text  

---

### `backend/templates/intelligence.py`
**Security Level**: 🟡 MEDIUM (Text generation, could be inaccurate)  

**What It Does**:
- Generates intelligent text summaries for CVEs
- Creates one-sentence descriptions of threat factors
- Focuses on decision-critical information

**Template Functions**:

1. **`kev_sentence(kev_record)`**
   - Input: CVE in CISA KEV list
   - Output: "CISA KEV: Exploitation deadline June 15, 2026"

2. **`severity_sentence(cvss_score)`**
   - Input: CVSS score (0-10)
   - Output: "CVSS 9.8 CRITICAL: Remote unauthenticated code execution"

3. **`epss_sentence(epss_score)`**
   - Input: EPSS score (0-1.0)
   - Output: "EPSS 0.87: 87% probability of exploitation within 30 days"

4. **`exploit_sentence(has_poc, exploit_count)`**
   - Input: PoC availability
   - Output: "Public exploits available on Exploit-DB (5 variants)"

5. **`patch_sentence(patch_available)`**
   - Input: Patch status
   - Output: "Patches available from vendor"

**Why It Matters**:
- Condensed, scannable format for analysts
- Highlights critical facts in natural language
- Supports decision-making

**How It Interacts**:
- Called from endpoints in `main.py` when returning CVE details
- Results displayed in CVECard.jsx component
- Used in PDF reports

---

## backend/ai/ Directory

**Purpose**: AI/LLM integration for threat analysis  
**Security Level**: 🔴 CRITICAL (Sends data to external AI services)

---

### `backend/ai/summary.py`
**What It Does**:
- Generates executive summary of security incidents
- Called ONLY when user exports PDF (never on page load)
- Uses Groq API (primary) → Anthropic API (fallback)

**Process**:
```
User clicks "Export PDF with AI Summary"
    ↓
Collect: CVEs, IOCs, threat actors from investigation
    ↓
POST /api/ai/summary with investigation data
    ↓
FastAPI calls Groq API: "Analyze these threats"
    ↓
If Groq fails: Falls back to Anthropic
    ↓
AI returns JSON: executive_summary, key_findings, confidence
    ↓
Frontend adds to PDF
    ↓
Download PDF with AI analysis
```

**LLM Services Used**:

| Service | Model | Purpose | Cost | Used When |
|---------|-------|---------|------|-----------|
| Groq | llama-3.3-70b-versatile | Primary summary | $Free tier | PDF export |
| Anthropic | claude-haiku-4-5 | Fallback | Pay-per-call | If Groq fails |

**System Prompt** (instructions to AI):
```
"You are a senior threat intelligence analyst writing an 
executive summary for a security investigation report."

Required output:
- Executive summary (4 sentences, CISO-level audience)
- Key findings (3-5 bullet points)
- Confidence rating (high/medium/low)
```

**Security-Sensitive Elements**:
- 🔴 `GROQ_API_KEY` - API authentication
- 🔴 `ANTHROPIC_API_KEY` - API authentication
- 🔴 Sends investigation data to external LLMs
  - CVE details (public)
  - IOC values (could be sensitive)
  - Threat actor names (public)
- ✅ Only triggered on explicit user action (export)
- ✅ Not called on page load (no passive data transmission)

**Privacy Implications**:
- ⚠️ Groq and Anthropic receive investigation data
- ⚠️ External companies may log/store requests
- ✅ No user IP addresses sent
- ✅ No system identifiers sent

**How It Interacts**:
- Called by `/api/ai/summary` endpoint
- Takes investigation context from InvestigationContext
- Results sent to frontend for PDF generation
- Component: PdfExportModal.jsx

---

## backend/scripts/ Directory

**Purpose**: One-off utility scripts (not part of main application)  

---

### `backend/scripts/backfill_poc.py`
**What It Does**:
- Retroactively checks existing CVEs for PoC availability
- Used to populate `has_poc` field for older CVE records
- Run manually: `python scripts/backfill_poc.py`

**Why It Exists**:
- When adding PoC detection feature, existing data doesn't have this field
- This script fills in the gaps
- Prevents data inconsistency

**How It Works**:
1. Queries all CVEs without `has_poc` value
2. For each CVE, calls `enrichment/cve.py` functions
3. Updates database with PoC detection results
4. Reports progress and errors

---

## backend/tests/ Directory

**Purpose**: Automated tests to verify code works correctly  
**Security Level**: 🟡 MEDIUM (Might contain test data/secrets)

---

### Test Files
- `test_nvd.py` - Tests NVD feed parser
- `test_kev.py` - Tests KEV CSV parser
- `test_mitre_feed.py` - Tests MITRE XML parser
- `test_ai_context.py` - Tests AI framework detection
- `test_intelligence.py` - Tests template generation
- `test_risk_intelligence.py` - Tests risk scoring

**What Tests Do**:
```
1. Load sample CVE data
2. Run through parsing/processing
3. Verify output matches expected format
4. Check for error handling
```

**Why Tests Matter for Security**:
- ✅ Catch bugs before production
- ✅ Verify no data corruption during processing
- ⚠️ Test data sometimes has realistic values
- ⚠️ If tests leaked, might reveal data formats

**How They Run**:
```bash
pytest backend/tests/  # Run all tests
```

**Note**: Tests exist but CI/CD not configured (tests don't run automatically)

---

## frontend/ Root Directory

**Entry Point**: `frontend/src/main.jsx`  
**Build Process**: `npm run build` → generates `frontend/dist/`  
**Dev Server**: `npm run dev` → starts Vite on port 5173

### Startup Process Flow

```
1. Browser requests https://projectjupiter.in/
   ↓
2. Nginx serves frontend/dist/index.html
   ↓
3. JavaScript bundles load (compiled by Vite)
   ↓
4. main.jsx executes
   ↓
5. React components initialize
   ↓
6. Browser fetches /api/health for initial data
   ↓
7. CVE feed displays
```

---

### `frontend/package.json`
**Purpose**: Declares dependencies and build scripts  
**Security Level**: 🟡 MEDIUM (Dependency management)  

**What It Contains**:
```json
{
  "name": "briefr-frontend",
  "dependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "7.16.0",
    "jspdf": "4.2.1",
    "html2canvas": "1.4.1",
    "exceljs": "4.4.0"
  },
  "devDependencies": {
    "vite": "5.4.1",
    "@vitejs/plugin-react": "4.3.1"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview --port 3000"
  }
}
```

**Build Scripts**:
- `npm run dev` - Start development server (hot reload)
- `npm run build` - Compile for production (optimized, minified)
- `npm run preview` - Test production build locally

**Security Notes**:
- ✅ Versions locked (reproducible builds)
- ✅ No unused dependencies
- ⚠️ Dependency vulnerabilities possible (requires `npm audit`)

---

### `frontend/vite.config.js`
**Purpose**: Configure Vite build tool  
**What It Does**:
```javascript
export default defineConfig({
  plugins: [react()],        // Use React plugin
  server: {
    port: 5173,              // Dev server port
    host: '0.0.0.0',         // Listen on all interfaces
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // Proxy to backend
        changeOrigin: true
      }
    }
  }
})
```

**Why It Matters**:
- Routes `/api` calls to backend during development
- Prevents CORS issues in dev
- In production, Nginx handles this routing

---

### `frontend/index.html`
**Purpose**: Root HTML file served to browsers  
**Security Level**: 🟡 MEDIUM (Entry point for XSS attacks)  

**What It Contains**:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>BRIEFR</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

**Security-Sensitive**:
- ✅ No inline JavaScript (safer)
- ✅ No external script loading (reduces attack surface)
- ⚠️ If compromised, can inject malicious code into all users

---

### `frontend/public/` (if it exists)
**Contains**: Static assets (images, logos, favicons)  
**Served by**: Nginx directly (no processing)

---

## frontend/src/ Directory

**Purpose**: React source code  

---

### `frontend/src/main.jsx`
**Purpose**: React application entry point  
**What It Does**:
```javascript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

**Startup Steps**:
1. Finds HTML element with id="root"
2. Initializes React
3. Wraps App with BrowserRouter (for client-side routing)
4. Renders App component

**Security Notes**:
- ✅ Uses React.StrictMode (warns about unsafe practices in dev)
- ✅ BrowserRouter enables SPA routing

---

### `frontend/src/App.jsx`
**Purpose**: Main application component  
**Security Level**: 🟡 MEDIUM (Routes and initial data fetching)  

**What It Does**:
1. **Routing Setup**: Defines which components render at each URL
   - `/` - Main CVE feed
   - `/privacy` - Privacy policy
   - `/terms` - Terms of service
   - `/cve/:id` - CVE detail page

2. **State Management**:
   - Filters (severity, KEV only, tech stack)
   - Current timezone
   - Dark/light mode
   - Investigation panel open/closed

3. **API Calls on Load**:
   - `/api/health` - Check backend status
   - `/api/stats` - Get feed statistics
   - `/api/cves` - Fetch CVE list

4. **Event Handlers**:
   - Search queries
   - Filter changes
   - Investigation thread tracking

**How It Interacts**:
- Parent component for all other components
- Provides global state via React Context
- Initiates API calls via `api.js`

---

### `frontend/src/api.js`
**Purpose**: HTTP client for communicating with backend  
**Security Level**: 🟡 MEDIUM (Handles all backend communication)  

**What It Does**:
```javascript
// Example functions:
async function fetchStats() { /* GET /api/stats */ }
async function fetchCVE(cveId) { /* GET /api/cves/{id} */ }
async function lookupIOC(value, type) { /* POST /api/ioc/lookup */ }
async function exportPdf(investigationData) { /* POST /api/ai/summary */ }
```

**Security-Sensitive Elements**:
- ✅ Uses `fetch()` API (built-in, no external dependencies)
- ✅ All requests to same origin (backend)
- ⚠️ No client-side API key storage
- ⚠️ If XSS attack succeeds, attacker could make arbitrary API calls

**How It Interacts**:
- Called by all components needing backend data
- Handles JSON serialization/deserialization
- Provides error handling

---

## frontend/src/context/ Directory

**Purpose**: React Context for shared state  

---

### `frontend/src/context/InvestigationContext.jsx`
**Security Level**: 🟡 MEDIUM (Tracks user investigation thread)  

**What It Does**:
- Tracks CVEs, IOCs, threat actors user is investigating
- Maintains investigation timeline
- Provides state to components via Context

**State Tracked**:
```
items: [
  { type: 'cve', id: 'CVE-2026-1234', title: 'Apache RCE' },
  { type: 'ioc', id: '1.2.3.4', title: 'IP: Malicious' },
  { type: 'actor', id: 'APT-28', title: 'Fancy Bear' }
]
startTime: 2026-06-05T14:30:00Z
threadSummary: "3 CVEs · 2 IOCs · 1 actor"
```

**How It Works**:
```
User clicks CVE
  ↓
recordItem() adds to items[]
  ↓
InvestigationPanel displays thread
  ↓
User clicks related IOC
  ↓
recordItem() adds IOC to same thread
  ↓
User clicks "Summarize"
  ↓
API call with entire thread
```

**Privacy Notes**:
- ✅ State stored in browser memory only
- ✅ Not sent to backend until user clicks summarize
- ⚠️ If XSS attack succeeds, attacker sees investigation thread

---

## frontend/src/components/ Directory

**Purpose**: Reusable React UI components  

### Component Overview

| Component | Purpose | Importance |
|-----------|---------|-----------|
| **CVEFeed.jsx** | Main CVE list display | Core feature |
| **CVECard.jsx** | Single CVE card | Display component |
| **DetailDrawer.jsx** | CVE detail view | Core feature |
| **FilterBar.jsx** | Search/filter UI | Core feature |
| **Header.jsx** | Top navigation | UI |
| **Sidebar.jsx** | Left navigation panel | UI |
| **InvestigationPanel.jsx** | Investigation thread panel | Core feature |
| **IOCLookup.jsx** | IOC lookup interface | Core feature |
| **AIThreats.jsx** | AI threat analysis | Feature |
| **TimelineHeatmap.jsx** | CVE publication timeline | Feature |
| **PdfExportModal.jsx** | PDF export dialog | Feature |
| **DigestModal.jsx** | CVE digest export | Feature |
| **AboutModal.jsx** | About/help modal | UI |
| **ShortcutsPanel.jsx** | Keyboard shortcuts | UI |

**Security-Sensitive Components**:

1. **IOCLookup.jsx** - Sends IOC values to backend
2. **PdfExportModal.jsx** - Sends data to LLM services
3. **DetailDrawer.jsx** - Displays detailed CVE information
4. **FilterBar.jsx** - Processes user input

---

## frontend/src/pages/ Directory

**Purpose**: Full-page components (not reusable)  

### Pages

| Page | Purpose | Route |
|------|---------|-------|
| **PrivacyPage.jsx** | Privacy policy | `/privacy` |
| **TermsPage.jsx** | Terms of service | `/terms` |
| **LegalPage.jsx** | Legal information | `/legal` |

**Security Notes**:
- ✅ Static content (no dynamic data)
- ✅ Safe to expose publicly

---

## frontend/src/utils/ Directory

**Purpose**: Helper functions (not UI)  

### Utility Functions

| File | Purpose |
|------|---------|
| **api.js** | HTTP client for backend calls |
| **cveFilters.js** | Search/filter logic |
| **cveAge.js** | CVE publication date calculations |
| **riskScore.js** | Risk score calculations/display |
| **timezone.js** | Timezone conversion utilities |
| **exportCsv.js** | CSV export logic |
| **exportXlsx.js** | Excel export logic |
| **investigationPdf.js** | PDF generation core logic |
| **pdfReport.js** | PDF layout/formatting |
| **pdfAiSummary.js** | PDF with AI summary |
| **investigationActors.js** | Threat actor extraction |
| **extractIndicatorsFromCve.js** | IOC extraction from CVE text |
| **aiAssets.js** | AI framework detection |
| **epssSparkline.js** | EPSS score trending |
| **heatmapGrid.js** | Timeline heatmap rendering |

**Security-Sensitive**:
- **extractIndicatorsFromCve.js** - Regex patterns for IOC detection
- **investigationPdf.js** - Handles PDF data assembly
- **pdfAiSummary.js** - Embeds LLM results in PDF

---

## deploy/ Directory

**Purpose**: Deployment and operations scripts  
**Security Level**: 🔴 CRITICAL (System-level access)

---

### `deploy/setup.sh`
**What It Does**:
- Installs BRIEFR on Debian 11/12/13
- Creates system user "briefr"
- Installs Python dependencies
- Sets up systemd services
- Configures Nginx
- Sets up Let's Encrypt certificates

**Key Steps**:
```bash
1. Detect Debian version
2. Install Python 3.11+ (from backports if needed)
3. Clone repository
4. Install Python dependencies
5. Create briefr system user
6. Set up systemd services
7. Configure Nginx
8. Run initial database setup
9. Start services
```

**Security-Sensitive**:
- 🔴 Runs as root
- 🔴 Creates system user with specific permissions
- 🔴 Modifies Nginx configuration
- 🔴 Sets up SSL certificates
- ✅ Disables unnecessary services
- ✅ Sets strict file permissions

**Who Runs It**:
- System administrator during initial deployment

---

### `deploy/briefr-backend.service`
**Purpose**: Systemd service definition for backend  
**What It Does**:
```ini
[Unit]
Description=BRIEFR CVE Intelligence Backend
After=network.target

[Service]
Type=notify
User=briefr
ExecStart=/path/to/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
WorkingDirectory=/opt/briefr/backend

[Install]
WantedBy=multi-user.target
```

**Key Settings**:
- Runs as `briefr` user (not root)
- Restarts if process crashes
- Listens only on `127.0.0.1` (localhost, not exposed)
- Nginx proxies external requests to this

**Security Notes**:
- ✅ Runs with minimal privileges
- ✅ Not exposed directly to internet
- ✅ Auto-restarts on failure
- ⚠️ Logs go to systemd journal (readable by root)

---

### `deploy/briefr-frontend.service`
**Purpose**: Systemd service for frontend (if serving via Node)  
**How It Differs From Backend**:
- Frontend is static files (HTML, CSS, JS)
- Typically served directly by Nginx
- This service only needed for development

---

### `deploy/nginx-briefr.conf`
**Purpose**: Nginx reverse proxy configuration  
**Security Level**: 🔴 CRITICAL (HTTP security gateway)  

**What It Does**:
```nginx
# HTTP → HTTPS redirect (port 80 → 443)
server {
    listen 80;
    return 301 https://$host$request_uri;
}

# HTTPS server (port 443)
server {
    listen 443 ssl http2;
    
    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/projectjupiter.in/fullchain.pem;
    
    # Security headers
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # Frontend (SPA routing)
    location / {
        root /opt/briefr/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

**Key Security Features**:
- 🔴 SSL/TLS encryption (HTTPS)
- 🔴 HTTP → HTTPS redirect (forces encrypted connections)
- 🔴 Security headers added by Nginx
- ✅ Backend not exposed directly (proxied)
- ✅ Only frontend needed at :443
- ✅ Backend on localhost only

**How Requests Flow**:
```
User Browser (HTTPS) 
    ↓ (port 443)
Nginx (reverse proxy)
    ├─ /                → /opt/briefr/frontend/dist/index.html
    ├─ /static/*        → /opt/briefr/frontend/dist/static/*
    └─ /api/*           → http://127.0.0.1:8000 (proxy)
        ↓
FastAPI Backend (port 8000, localhost only)
```

---

### `deploy/briefr-update.sh`
**Purpose**: Safely update BRIEFR without downtime  
**What It Does**:
```bash
1. Stop backend service
2. Git pull latest changes
3. Run database migrations
4. Reinstall Python dependencies
5. Restart backend service
6. Verify health check passes
```

**Safety Features**:
- ✅ Backup database before update
- ✅ Rollback capability if update fails
- ✅ Health check before marking success

---

### `deploy/check-backend.sh`
**Purpose**: Health check script  
**What It Does**:
```bash
curl http://127.0.0.1:8000/api/health
# Expected response:
# {
#   "cve_count": 150000,
#   "last_updated": "2026-06-05T14:00:00Z",
#   "status": "operational"
# }
```

**Used By**:
- Uptime monitoring services
- Load balancers
- Alerting systems

---

### `deploy/refresh-*.sh` Scripts
**Purpose**: Manual data refresh triggers  

| Script | Purpose | When Used |
|--------|---------|-----------|
| **refresh-nvd.sh** | Force NVD data fetch | Emergency CVE update |
| **refresh-kev.sh** | Force CISA KEV fetch | Check latest exploited vulns |
| **refresh-epss.sh** | Force EPSS score update | Update risk scores |
| **refresh-mitre.sh** | Force MITRE ATT&CK update | New attack techniques |
| **refresh-atlas.sh** | Force ATLAS update | New AI attack techniques |

**Security Notes**:
- Only run during off-hours (don't impact users)
- Can consume significant bandwidth
- API rate limits may be hit

---

### `deploy/backfill-poc.py`
**Purpose**: Retroactively add PoC detection to existing CVEs  
**When Used**:
- After adding new PoC detection feature
- To fix missing PoC flags

---

### `deploy/fix-permissions.sh`
**Purpose**: Repair file permissions after issues  
**What It Does**:
```bash
chown -R briefr:briefr /opt/briefr/
chmod 750 /opt/briefr/backend
chmod 640 /opt/briefr/backend/.env
chmod 644 /opt/briefr/backend/*.py
```

**Why Needed**:
- After Git operations
- After config changes
- If permissions corrupted

---

## screenshots/ Directory

**Purpose**: Documentation screenshots  
**Security Level**: 🟢 LOW (Public images)  
**What It Contains**: Dashboard screenshots for README

---

## .gitignore Summary (for context)

**Files Git Ignores** (won't upload to GitHub):
```
__pycache__/          ← Python cache files
*.db                  ← Database file (user data)
.env                  ← ⚠️ CRITICAL - Local secrets
.venv/                ← Python virtual environment
dist/                 ← Built frontend
node_modules/         ← npm dependencies
```

**Why This Matters for Security**:
- ✅ `.env` ignored prevents accidental secret exposure
- ✅ Database not committed prevents data leaks
- ⚠️ If developer adds files to `.gitignore`, secrets could leak

---

## Security Summary by Folder

| Folder | Risk Level | Key Concerns |
|--------|-----------|--------------|
| `.git/` | 🟡 Medium | Version history, possible old secrets |
| `backend/` | 🔴 High | API keys, authentication logic, data access |
| `backend/feeds/` | 🟡 Medium | External API handling, data validation |
| `backend/enrichment/` | 🔴 High | Third-party API keys, IOC handling |
| `backend/ai/` | 🔴 High | LLM API keys, external data transmission |
| `backend/scoring/` | 🟡 Medium | Algorithm could have bias/errors |
| `frontend/` | 🟡 Medium | XSS vulnerability potential, CORS |
| `deploy/` | 🔴 Critical | System-level access, SSL configuration |

---

## Entry Points & Startup Files

**Backend Startup**:
1. `backend/main.py` (FastAPI app)
2. Called by: `backend/scheduler.py` during lifespan
3. Database initialized: `backend/database.py`
4. Starts services: `backend/scheduler.py` (APScheduler jobs)

**Frontend Startup**:
1. `frontend/src/main.jsx` (React entry)
2. Renders: `frontend/src/App.jsx` (main app)
3. Fetches data: `frontend/src/api.js`
4. Initializes state: `frontend/src/context/InvestigationContext.jsx`

**System Startup**:
1. `deploy/setup.sh` (initial installation)
2. `deploy/nginx-briefr.conf` (reverse proxy)
3. `deploy/briefr-backend.service` (systemd service)
4. `deploy/briefr-update.sh` (periodic updates)

---

## Data Flow Through Folders

```
External APIs
    ↓
backend/feeds/*    ← Fetches CVE data
    ↓
backend/database.py ← Stores in SQLite
    ↓
backend/main.py    ← Exposes via REST API
    ↓
frontend/src/api.js ← HTTP client
    ↓
frontend/src/components/ ← Display in UI
    ↓
Browser User
```

---

## Critical Security Files Checklist

**Must Protect**:
- ✅ `.env` (API keys) - Never commit
- ✅ `briefr.db` (user data) - Encrypt at rest
- ✅ `.git/` (version history) - Don't expose publicly
- ✅ `deploy/nginx-briefr.conf` (SSL certs) - Secure permissions
- ✅ `deploy/briefr-backend.service` (password fields) - Remove if any

**Must Review**:
- ✅ `backend/main.py` (CORS, security headers)
- ✅ `backend/enrichment/ioc.py` (API key handling)
- ✅ `backend/ai/summary.py` (external data transmission)
- ✅ `frontend/src/api.js` (request handling)
- ✅ `deploy/setup.sh` (initial permissions)

---

**Document Generated**: 2026-06-05  
**For Questions About**: Any specific folder or security concern
