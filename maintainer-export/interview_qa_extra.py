"""Additional interview segments for issue #498 priority areas."""

from __future__ import annotations

# Insert positions are resolved in merge_segments().


def nvd_segment() -> dict:
    return {
        "slug": "iv-nvd-pipeline",
        "page_id": "iv-nvd-pipeline",
        "chapter_num": "Interview · 4",
        "title": "NVD ingestion & feed pipeline",
        "dek": "Resilient client, incremental sync, transaction boundaries, and operator refresh paths.",
        "questions": [
            {
                "category": "overview",
                "q": "What is the NVD pipeline's job in BRIEFR?",
                "a": "Pull modified CVE JSON from NIST NVD into the canonical <code>cves</code> table, then commit before optional enrichments (CIRCL, Sploitus, etc.). Watermarks in <code>sync_state</code> make incremental runs idempotent. Analyst FEED and DetailDrawer read only persisted rows—never live NVD on every page view.",
            },
            {
                "category": "overview",
                "q": "Which modules own NVD ingest end-to-end?",
                "a": "Scheduler job <code>nvd_incremental_sync</code> in <code>scheduler.py</code> calls ingest helpers under <code>ingest/nvd/</code> (and related feed code). HTTP uses <code>services/resilient_client.py</code> via <code>api_queue</code> pacing. Persistence is <code>db/cves.py</code> with <code>db/txn_boundaries.py</code> separating writer transactions from slow enrich.",
            },
            {
                "category": "implementation",
                "q": "How does incremental NVD sync choose what to fetch?",
                "a": "The job reads the last successful modified cursor/window from <code>sync_state</code>, requests CVEs changed since that point through the NVD 2.0 API, upserts core fields, then advances the watermark only after a successful commit. Full bootstrap on empty DB (&lt;10 rows) uses a broader initial pull from lifespan startup.",
            },
            {
                "category": "implementation",
                "q": "What does the resilient HTTP client add beyond requests?",
                "a": "<code>resilient_request</code> applies per-source retry policy, records failures for circuit health, respects Retry-After, and logs attempts to <code>api_call_events</code> when metering is enabled. Non-retryable 4xx fail fast without tripping the circuit; repeated 5xx/open circuit fails fast until cooldown.",
            },
            {
                "category": "implementation",
                "q": "How is NVD API key usage handled?",
                "a": "<code>NVD_API_KEY</code> from process env (wins over <code>.env</code>) is sent on outbound NVD calls for higher rate limits. Missing key still works—slower pacing. API key health probes are separate from the traffic circuit so a bad probe does not poison real ingest.",
            },
            {
                "category": "implementation",
                "q": "Why commit NVD core rows before enrichments?",
                "a": "<code>txn_boundaries.py</code> prevents CIRCL/Sploitus enrich from holding the same long writer connection as bulk NVD upsert. Slow enrich cannot exhaust the pool and block feed reads. This is a structural fix for 'ingest wedged the app' incidents, not a retry band-aid.",
            },
            {
                "category": "integration",
                "q": "How does NVD ingest connect to scoring and OP?",
                "a": "Upserted CVSS, CWE, affected products, and publication dates feed <code>POST /api/cves/{id}/risk</code> on next read. KEV/EPSS jobs are separate schedulers but join on <code>cve_id</code>. FEED cards do not recompute Threat client-side—they display API fields after NVD+satellite data lands.",
            },
            {
                "category": "integration",
                "q": "How do admin Feed Health actions trigger NVD sync?",
                "a": "Feed Health 'Sync' and Scheduler 'Run now' for <code>nvd_incremental_sync</code> call the same async lock as cron via <code>_JOB_RUN_MAP</code>. Operators cannot double-run NVD concurrently with cron or another manual run.",
            },
            {
                "category": "integration",
                "q": "How does stack backfill relate to NVD?",
                "a": "<code>STACK_BACKFILL_ENABLED</code> triggers historical NVD+KEV+EPSS pulls per product checkpoint. When NVD rate-limits, Procrastinate can defer resume. Backfill shares resilient client and metering but uses its own run gate (<code>claim_run_running</code>).",
            },
            {
                "category": "failure",
                "q": "What happens when NVD returns 503?",
                "a": "Transient 503s are retried per resilient client policy; sustained failures increment circuit health and surface on Feed Health with circuit-open state. FEED continues serving last committed Postgres rows—no empty wipe. Operators retry after cooldown or use admin reset-circuit when upstream recovers.",
            },
            {
                "category": "failure",
                "q": "How do you debug a stuck NVD job?",
                "a": "Scheduler table links to Application logs filtered by <code>job_id=nvd_incremental_sync</code> and <code>run_id</code>. Check <code>api_queue</code> depth on <code>/api/health</code>, verify lock not held by dead task, inspect <code>sync_state</code> watermark, and confirm Postgres pool not saturated.",
            },
            {
                "category": "failure",
                "q": "What if the watermark advances but rows are missing?",
                "a": "RCA path: compare NVD API response count vs upsert count in logs, check for transaction rollback after partial batch, verify Alembic schema matches ingest expectations. Recovery is forward-only re-sync or targeted admin force paths—not editing applied migrations.",
            },
            {
                "category": "performance",
                "q": "How does api_queue protect NVD rate limits?",
                "a": "Outbound NVD calls serialize through the per-source queue so concurrent drawer refreshes and cron do not stampede the API. Health exposes waiting vs active tasks; Background sync UI groups by provider.",
            },
            {
                "category": "performance",
                "q": "What DB patterns keep NVD ingest fast?",
                "a": "Batch upserts, short transactions for core CVE rows, separate connections for parallel read paths, KEV join indexes, and keyset pagination on feed endpoints. Long enrich runs outside the critical NVD commit path.",
            },
            {
                "category": "security",
                "q": "What trust boundary applies to NVD data?",
                "a": "NVD JSON is treated as untrusted input: parsed into typed fields, size-bounded HTTP, no eval. SSRF protections apply to other outbound fetches; NVD uses fixed NIST endpoints. No operator-supplied URL in the NVD path.",
            },
            {
                "category": "tradeoff",
                "q": "Why not fetch NVD live per CVE in the drawer?",
                "a": "Request-path NVD would couple analyst latency to NIST availability, break rate limits, and bypass scoring consistency. Persisted ingest with honest stale indicators matches self-hosted ops reality—one scheduler owner, predictable DB reads.",
            },
            {
                "category": "implementation",
                "q": "What is cvelistV5 sync vs NVD incremental?",
                "a": "<code>cvelistv5_incremental_sync</code> mirrors the CVEList v5 git corpus for fields/auxiliary metadata NVD may lag on. It is a sibling job with its own watermark—not a replacement for NVD modified feed.",
            },
            {
                "category": "implementation",
                "q": "How does vulnrichment snapshot sync fit?",
                "a": "<code>vulnrichment_snapshot_sync</code> ingests CISA vulnrichment SSVC snapshots into satellite tables consumed by <code>/risk</code> SSVC paths. Scheduled separately from NVD modified API with its own health row.",
            },
            {
                "category": "integration",
                "q": "How does FEED footer refresh honesty relate to NVD?",
                "a": "Footer next refresh reflects <code>nvd_incremental_sync</code> schedule only—orphaned <code>CACHE_REFRESH_*</code> env vars are not wired. Health <code>refresh_schedule</code> null when disabled so UI does not promise phantom auto-refresh.",
            },
            {
                "category": "failure",
                "q": "How does catch-up mode affect NVD?",
                "a": "Catch-up raises caps for embeddings/correlation/LLM—not a bypass of NVD rate limits. NVD still obeys <code>api_queue</code> and circuit breaker; catch-up tick nudges eligible backlog jobs without duplicating cron owners.",
            },
            {
                "category": "performance",
                "q": "How is API metering used for NVD ops?",
                "a": "<code>API_CALL_EVENTS_ENABLED</code> logs each <code>resilient_request</code> with source=nvd, latency, actor job id. Admin API usage page shows 24h breakdowns to spot quota burn vs circuit trips.",
            },
            {
                "category": "tradeoff",
                "q": "Why incremental sync instead of nightly full export?",
                "a": "Full export is network- and CPU-heavy for small VPS targets. Incremental modified feed plus bootstrap on empty DB balances freshness with operator hardware. Stack backfill is opt-in for historical depth.",
            },
            {
                "category": "implementation",
                "q": "Where are NVD field mappings maintained?",
                "a": "Ingest parsers map NVD 2.0 JSON into <code>cves</code> columns and JSON blobs (CPE, references). Changes require pytest coverage on sample fixtures and Postgres apply for any new columns via Alembic.",
            },
            {
                "category": "integration",
                "q": "How do embeddings auto-on-ingest interact with NVD?",
                "a": "When <code>EMBEDDINGS_AUTO_ON_INGEST</code> is on, new/changed CVE rows from NVD enqueue embed work on ingest path—capped per run. Semantic search stays retrieval-only; NVD text is not sent to LLM providers for scoring.",
            },
            {
                "category": "security",
                "q": "Can analysts trigger arbitrary NVD replay?",
                "a": "Only admin role can Run Now or Feed Health sync. Analyst routes are read-only on CVE tables. Rate limits and job locks prevent abuse of operator actions.",
            },
            {
                "category": "failure",
                "q": "What regression tests guard NVD ingest?",
                "a": "<code>test_resilient_client.py</code> (circuit/retry), NVD txn boundary tests, scheduler job map tests, and feed health routes. Any <code>db/</code> SQL change needs SQLite default + Postgres <code>--full</code> run before merge.",
            },
            {
                "category": "implementation",
                "q": "How does metering attribute NVD calls to jobs vs users?",
                "a": "<code>resilient_request</code> passes actor metadata—scheduler jobs include <code>job_id</code>/<code>run_id</code> in logs and <code>api_call_events</code> when enabled. Analyst-triggered paths use request context. Admin usage page breaks down by actor.",
            },
            {
                "category": "tradeoff",
                "q": "Why not use Procrastinate for all NVD pulls?",
                "a": "NVD incremental is cron-shaped with in-process locks—operators already understand APScheduler + Feed Health. Procrastinate adds value for durable resume (stack backfill) where retry semantics justify Postgres queue overhead.",
            },
            {
                "category": "integration",
                "q": "How does MITRE weekly refresh interact with NVD CPE data?",
                "a": "<code>weekly_mitre_refresh</code> updates ATT&amp;CK/ATLAS corpora used by Forge and technique embeddings—not a substitute for per-CVE NVD upsert. Technique links in drawer consume both corpora and CVE affected-product fields.",
            },
        ],
    }


def campaign_ioc_segment() -> dict:
    return {
        "slug": "iv-campaign-ioc",
        "page_id": "iv-campaign-ioc",
        "chapter_num": "Interview · 8",
        "title": "Campaign, IOC & graph logic",
        "dek": "OTX pulses, correlation campaigns, IOC enrichment, shared infrastructure, and analyst IOC tab.",
        "questions": [
            {
                "category": "overview",
                "q": "What is the campaign layer in BRIEFR?",
                "a": "Nightly/on-demand correlation clusters OTX pulses and related intel into <code>correlation_campaigns</code> and lane artifacts—temporal, actor/sector, infrastructure. Intel tab and semantic search surface campaigns; OP may escalate one band when linkage is HIGH/MED after client merge.",
            },
            {
                "category": "overview",
                "q": "What is the IOC tab vs campaign graph?",
                "a": "IOC tab is live operator lookup (IP/domain/hash) against VT, AbuseIPDB, GreyNoise with rate limits and <code>ioc_cache</code>. Campaign graph is persisted correlation over pulses/IOCs—no live external call inside the correlation engine run itself.",
            },
            {
                "category": "implementation",
                "q": "How are pulse titles normalized for clustering?",
                "a": "<code>normalize_pulse_name</code> (stronger than display <code>formatIntelLabel</code>) collapses vendor noise so related OTX pulses group. Active Campaigns UI shows humanized titles but matching uses the normalized base title.",
            },
            {
                "category": "implementation",
                "q": "What does find_shared_infrastructure_v2 do?",
                "a": "In <code>correlation/ioc_graph.py</code>, it finds shared IOCs across pulses/CVEs for infrastructure lanes—used in corroboration tests with ThreatFox and OTX fixtures. Outputs structured lane factors for explainability, not opaque scores.",
            },
            {
                "category": "implementation",
                "q": "How is OTX data stored?",
                "a": "Pulses mirror into Postgres tables plus TTL <code>feed_cache</code> JSON. <code>otx_continuous_sync</code> is registration-gated. Upstream errors serve stale mirror rows without deleting cached intel.",
            },
            {
                "category": "implementation",
                "q": "How does the IOC lookup API work?",
                "a": "Authenticated analyst POST/GET routes call outbound providers through resilient client + dedicated IOC rate bucket. Results cache in <code>ioc_cache</code> with retention cleanup job. Missing API keys return honest empty states, not fake scores.",
            },
            {
                "category": "integration",
                "q": "How do campaigns appear in the DetailDrawer?",
                "a": "Intel tab loads campaign clusters from correlation tables—primary card plus related count, collapsed by default. Drawer bundle may parallel-fetch intel slice; OP hero can render before correlation finishes loading.",
            },
            {
                "category": "integration",
                "q": "How does semantic search include campaigns?",
                "a": "<code>/api/search/semantic</code> embeds non-retracted <code>correlation_campaigns</code> (E8) and returns a Campaigns section alongside CVEs and techniques when embeddings enabled.",
            },
            {
                "category": "integration",
                "q": "What webhooks fire on IOC/watchlist events?",
                "a": "<code>ioc_watchlist_hit</code>, watchlist KEV/EPSS change alerts, and KEV backlog events use database-backed destinations with dedupe keys and delivery logs—configured in admin Webhooks.",
            },
            {
                "category": "failure",
                "q": "What happens when OTX is down?",
                "a": "Serve any-age stale pulses from mirror/cache; Feed Health shows freshness vs circuit separately. Correlation job uses persisted data only—no live OTX inside engine run.",
            },
            {
                "category": "failure",
                "q": "How does IOC rate limiting behave?",
                "a": "Token bucket per minute; drained bucket returns 429 with Retry-After. Tests in <code>test_rate_limit.py</code> cover IOC path. <code>BRIEFR_RATE_LIMIT_STORE=db</code> needed for multi-worker consistency.",
            },
            {
                "category": "failure",
                "q": "What if correlation precompute is disabled?",
                "a": "<code>CORRELATION_PRECOMPUTE_ENABLED=0</code> (default): <code>/risk</code> does not block on correlation snapshot; escalation merges when correlation API data arrives. Avoids drawer open latency regression.",
            },
            {
                "category": "performance",
                "q": "Why no live API inside nightly_correlation?",
                "a": "Engine run reads Postgres only—bounded runtime, no external rate-limit coupling. Fresh OTX is the ingest job's responsibility; correlation consumes stable snapshots.",
            },
            {
                "category": "performance",
                "q": "How is ioc_cache retention managed?",
                "a": "<code>cache_retention_cleanup</code> sweeps stale IOC cache entries alongside <code>feed_cache</code> and aged mirrors—prevents unbounded disk growth on busy IOC tabs.",
            },
            {
                "category": "security",
                "q": "What data leaves the network on IOC lookup?",
                "a": "Operator-typed IOC values go to configured third-party APIs (VT, etc.) over HTTPS. Keys are env/encrypted settings; responses are cached locally. No anonymous public IOC proxy endpoint.",
            },
            {
                "category": "security",
                "q": "How are webhook IOC events scoped?",
                "a": "Admin configures destinations and subscribed events; delivery errors masked on read. Test POST allowed on disabled destinations for validation without enabling production spam.",
            },
            {
                "category": "tradeoff",
                "q": "Why client-side OP escalation from correlation?",
                "a": "Temporary documented compromise: hero OP renders from cheap signals immediately; campaign linkage may arrive later. Server-side merge in <code>/risk</code> is the future hardening—today honesty prefers fast shell over blocking drawer.",
            },
            {
                "category": "implementation",
                "q": "What is ThreatFox corroboration?",
                "a": "Tests and ingest paths can corroborate OTX IOCs with ThreatFox mirrors—shared infrastructure lane gets stronger evidence when both sources agree on domain/hash overlap.",
            },
            {
                "category": "implementation",
                "q": "How does wallboard use campaigns?",
                "a": "Campaign counts and intel tiles read <code>correlation_campaigns</code> with active filters—kiosk token auth, ranked CVE tiles still use OP then Threat, not campaign score alone.",
            },
            {
                "category": "integration",
                "q": "How does Forge overlay campaigns?",
                "a": "When enabled, navigator/hunt context can reference correlated campaigns for technique selection—must not claim 'ranked for your stack' without stack pins (honesty PRs).",
            },
            {
                "category": "failure",
                "q": "Empty Active Campaigns—what does UI show?",
                "a": "Distinct empty state: never-synced OTX vs no matches vs retracted campaigns filtered. No fabricated campaign cards.",
            },
            {
                "category": "performance",
                "q": "How are pulse families tested?",
                "a": "<code>test_pulse_families.py</code> exercises <code>normalize_pulse_name</code> edge cases—vendor suffix stripping, unicode, duplicate collapse—guarding clustering stability.",
            },
            {
                "category": "tradeoff",
                "q": "Why persist campaigns instead of query OTX per CVE?",
                "a": "Same rationale as NVD: predictable latency, explainable factors, offline degradation. Clustering is compute-heavy—belongs in scheduler, not request path.",
            },
            {
                "category": "implementation",
                "q": "What YARA generator inputs use IOCs?",
                "a": "<code>test_yara_generator.py</code> shows IOC structs (type/value) feeding detection emit paths—deterministic from structured intel, not LLM guesses.",
            },
            {
                "category": "security",
                "q": "Can IOC lookup be abused for scanning?",
                "a": "Session auth + per-user rate limits + operator-only keys. Not a public DNS walker; each lookup is user-initiated with audit-friendly logging metadata.",
            },
            {
                "category": "integration",
                "q": "How do watchlist pins interact with IOC graph?",
                "a": "Pins drive <code>watchlist_monitor_alerts</code> on KEV/EPSS changes—not continuous IOC graph polling. Snooze removed; pin/watchlist remains.",
            },
            {
                "category": "implementation",
                "q": "How are retracted campaigns filtered?",
                "a": "Embedding backfill and semantic search skip retracted <code>correlation_campaigns</code> rows (E8). UI must not show stale campaign cards after retraction—tests guard empty vs active states.",
            },
            {
                "category": "performance",
                "q": "Does IOC tab block the feed thread?",
                "a": "No—IOC lookups are async API calls with loading/error states per lookup. Rate limits bound concurrent external queries; cache hits avoid repeat provider calls.",
            },
            {
                "category": "failure",
                "q": "What if GreyNoise/VT keys are missing?",
                "a": "Routes return structured empty/missing-key states; UI explains which provider is unconfigured. Core CVE workflows unaffected—IOC is enrichment, not gate.",
            },
        ],
    }


def tests_docs_segment() -> dict:
    return {
        "slug": "iv-tests-docs",
        "page_id": "iv-tests-docs",
        "chapter_num": "Interview · 14",
        "title": "Tests, docs & roadmap",
        "dek": "verify-local gates, PRODUCT_STATUS truth, planning docs, and how to keep the repo interview-ready.",
        "questions": [
            {
                "category": "overview",
                "q": "What is the documentation hierarchy in BRIEFR?",
                "a": "<code>docs/PRODUCT_STATUS.md</code> is runtime truth; <code>docs/SYSTEM_DESIGN.md</code> structure; <code>docs/API_REFERENCE.md</code> endpoints; <code>docs/planning/SPRINT_2026-07.md</code> active queue; <code>docs/HANDOVER.md</code> session context. Archives under <code>docs/archive/</code> are historical—never resurrected.",
            },
            {
                "category": "overview",
                "q": "Where does the maintainer study guide live?",
                "a": "Private <code>briefr-maintainer</code> repo (<code>docs/study-guide/</code>) after PR #751 migrated it out of public <code>briefr</code>. This interview pack ships as <code>maintainer-export/</code> drop-in until pushed to maintainer.",
            },
            {
                "category": "implementation",
                "q": "What does verify-local.sh run by default?",
                "a": "SQLite pytest, frontend dependency audit, <code>npm run build</code>, frontend unit tests, scoped ESLint (scoring + admin), backend ruff F/E9. Mirrors CI merge gate; green local suffices when GitHub Actions quota exhausted.",
            },
            {
                "category": "implementation",
                "q": "What does verify-local --full add?",
                "a": "Postgres pytest, gitleaks (known red), Playwright smoke when available. Required for <code>db/</code> DDL changes and scheduler lock map edits before production merge.",
            },
            {
                "category": "implementation",
                "q": "Why default pytest on SQLite?",
                "a": "Zero-config CI/dev on cloud VMs without Docker. <code>db/pg_adapt.py</code> keeps parallel SQL constants. Production is Postgres-only—operators must run Postgres path before merging dangerous SQL.",
            },
            {
                "category": "implementation",
                "q": "What frontend tests exist?",
                "a": "<code>npm run test:unit</code> (Vitest) for scoring helpers and admin patterns. Playwright smoke behind <code>PLAYWRIGHT_SMOKE=1</code>. Design-token lint and native-control grep gates in verify-local.",
            },
            {
                "category": "integration",
                "q": "How do docs stay aligned with API changes?",
                "a": "Same PR updates PRODUCT_STATUS, SYSTEM_DESIGN, API_REFERENCE when behavior changes. Admin corpus drift check compares generated security architecture to committed files.",
            },
            {
                "category": "integration",
                "q": "How does HANDOVER relate to SPRINT?",
                "a": "HANDOVER is newest-first session log for agents/operators; SPRINT is the checked work queue. Agents execute next unchecked SPRINT item without stopping at wave boundaries per AGENTS.md.",
            },
            {
                "category": "failure",
                "q": "What tests fail on SQLite-only CI that are expected?",
                "a": "Postgres-only tests: stack backfill, NVD txn boundary, API metering, CPE catalog, Procrastinate—attempt <code>127.0.0.1:5432</code> and fail without container. Not regressions on default path.",
            },
            {
                "category": "failure",
                "q": "How do you RCA a CI failure vs local pass?",
                "a": "Compare env: DATABASE_URL, Node/Python versions, missing Playwright browsers. Re-run failing file with same env vars as CI job log. RCA-first: reproduce → trace → class fix → regression test.",
            },
            {
                "category": "performance",
                "q": "Why scoped lint not whole-repo?",
                "a": "Incremental hygiene: ESLint on scoring + admin where type complexity matters; ruff F/E9 on backend. Full-repo lint deferred—verify-local stays fast enough for solo maintainer loop.",
            },
            {
                "category": "security",
                "q": "What security tests ship?",
                "a": "Rate limit tests, SSRF blocks, session refresh dedupe, admin DB explorer allowlist, structured log redaction tests, security architecture corpus generation tests.",
            },
            {
                "category": "tradeoff",
                "q": "Why graphify/study-guide vs only README?",
                "a": "README orients users; study guide and graphify orient contributors across hundreds of modules. Maintainer-private guide can go deeper than public onboarding without bloating product repo.",
            },
            {
                "category": "implementation",
                "q": "What is test_scheduler job map guard?",
                "a": "Tests assert <code>scheduler.py</code> job <code>id=</code> strings match <code>routers/admin/jobs.py</code> <code>_JOB_RUN_MAP</code>—danger zone #2. Drift breaks Run Now and locks.",
            },
            {
                "category": "implementation",
                "q": "How are Alembic revisions tested?",
                "a": "<code>test_alembic_revisions.py</code> scans for reserved-word quoting bugs. Forward-only migrations; Postgres apply in --full before merge.",
            },
            {
                "category": "integration",
                "q": "How does CLAUDE.md relate to AGENTS.md?",
                "a": "CLAUDE.md is the rulebook (danger zones, UI, PR workflow). AGENTS.md points agents to read order and cloud caveats without duplicating rules.",
            },
            {
                "category": "integration",
                "q": "What planning docs track roadmap?",
                "a": "<code>docs/planning/BACKLOG.md</code>, specs under <code>docs/planning/specs/</code>, ROADMAP.md compatibility promise, OPERATIONS.md for live box procedures.",
            },
            {
                "category": "failure",
                "q": "dependency-audit and gitleaks red in CI?",
                "a": "Known non-blockers per CLAUDE.md until fixed. Do not ignore new failures in test job—those are merge blockers.",
            },
            {
                "category": "performance",
                "q": "How do golden query tests help embeddings?",
                "a": "Contract tests for semantic search shapes prevent silent retrieval regressions without recomputing OP math in frontend.",
            },
            {
                "category": "security",
                "q": "How is secrets leakage tested?",
                "a": "Structured logging tests ensure <code>*_KEY</code> fields redact in extra dicts; gitleaks in --full (known red) for committed secrets.",
            },
            {
                "category": "tradeoff",
                "q": "Why issue #498 output in maintainer not public repo?",
                "a": "Interview prep is maintainer-facing depth; public repo stays product-focused after study guide migration #751. Portable <code>maintainer-export/</code> bridges until private push.",
            },
            {
                "category": "implementation",
                "q": "How do you add a regression test for a user-reported bug?",
                "a": "RCA reproduce → minimal pytest or Vitest asserting fixed behavior → run verify-local. Note operator-visible changes in HANDOVER.md.",
            },
            {
                "category": "overview",
                "q": "What is ADR-003 and why interviewers care?",
                "a": "UI design system decision: semantic tokens, Radix primitives, no Tailwind runtime. Violations (native selects, hardcoded hex) are explicit amateur defects gated in verify-local.",
            },
            {
                "category": "overview",
                "q": "What is ADR-005?",
                "a": "Approved component libraries (Radix + sanctioned headless). Mantine/MUI/Chakra prohibited until ADR updated—explains frontend dependency discipline.",
            },
            {
                "category": "integration",
                "q": "How does PRODUCT_STATUS differ from planning specs?",
                "a": "PRODUCT_STATUS records what is true in production now; specs describe intended work. When they conflict, PRODUCT_STATUS and code win.",
            },
            {
                "category": "failure",
                "q": "What happens when docs claim a removed feature?",
                "a": "Interview trap: Investigation Score, snooze UI, light theme, admin API key—removed with documented non-goals. Always cross-check PRODUCT_STATUS.",
            },
            {
                "category": "tradeoff",
                "q": "Why keep SQLite dev fallback on main while PR #752 removes it?",
                "a": "Launch caution: Postgres-only draft needs full validation. README documents both paths; production uses Postgres; CI uses SQLite for speed until removal merges.",
            },
            {
                "category": "implementation",
                "q": "What playwright smoke covers?",
                "a": "Optional UI smoke in <code>test_playwright_smoke.py</code>—login shell, basic navigation—gated behind <code>PLAYWRIGHT_SMOKE=1</code>. Not default on every dev machine; complements unit tests.",
            },
            {
                "category": "integration",
                "q": "How does issue #498 map to this section?",
                "a": "Issue asks repo-wide categorized questions by subsystem. Part VII chapters mirror priority areas (NVD, correlation, campaign/IOC, detection, API, scheduler, DB, tests/docs) with hundreds of concrete Q&amp;A—generated from <code>interview_qa_data.py</code> + <code>interview_qa_extra.py</code>.",
            },
            {
                "category": "overview",
                "q": "What is the danger zones list in CLAUDE.md?",
                "a": "Six areas agents must read before editing: Postgres-native SQL, scheduler lock map, forward-only migrations, secrets in logs, deploy script compatibility, no heavy work on request path. Interviewers use it to probe whether you know where bugs become outages.",
            },
        ],
    }


def merge_segments(base: list[dict]) -> list[dict]:
    """Insert priority segments and renumber chapter labels."""
    by_slug = {s["slug"]: s for s in base}
    ordered_slugs = [
        "iv-part",
        "iv-architecture",
        "iv-security",
        "iv-backend-db",
        "iv-nvd-pipeline",
        "iv-ingest-scheduler",
        "iv-correlation-scoring",
        "iv-campaign-ioc",
        "iv-ml-embeddings",
        "iv-detection-forge",
        "iv-frontend-ux",
        "iv-api-ops",
        "iv-devops-deploy",
        "iv-tests-docs",
        "iv-product-behavioral",
    ]
    extras = {
        "iv-nvd-pipeline": nvd_segment(),
        "iv-campaign-ioc": campaign_ioc_segment(),
        "iv-tests-docs": tests_docs_segment(),
    }
    merged: list[dict] = []
    chapter_idx = 0
    for slug in ordered_slugs:
        if slug == "iv-part":
            merged.append(by_slug[slug])
            continue
        if slug in extras:
            seg = extras[slug]
        else:
            seg = by_slug[slug]
        chapter_idx += 1
        seg = dict(seg)
        seg["chapter_num"] = f"Interview · {chapter_idx}"
        merged.append(seg)
    return merged


def merge_toc(base: list[list[str]]) -> list[list[str]]:
    extra_rows = [
        ["iv-nvd-pipeline.html", "4 · NVD ingestion & feed pipeline"],
        ["iv-campaign-ioc.html", "8 · Campaign, IOC & graph logic"],
        ["iv-tests-docs.html", "14 · Tests, docs & roadmap"],
    ]
    out: list[list[str]] = []
    n = 1
    for row in base:
        if row[0] == "iv-part.html":
            out.append(row)
            continue
        title = row[1]
        if " · " in title and title[0].isdigit():
            _, rest = title.split(" · ", 1)
            out.append([row[0], f"{n} · {rest}"])
        else:
            out.append(row)
        n += 1
        if row[0] == "iv-backend-db.html":
            out.append(extra_rows[0])
            n += 1
        elif row[0] == "iv-correlation-scoring.html":
            out.append(extra_rows[1])
            n += 1
        elif row[0] == "iv-devops-deploy.html":
            out.append(extra_rows[2])
            n += 1
    return out


def wire_prev_next(segments: list[dict]) -> list[dict]:
    wired: list[dict] = []
    for i, seg in enumerate(segments):
        row = dict(seg)
        if i == 0:
            row["prev"] = ("roadmap-future.html", "What's next & open gaps")
        else:
            p = segments[i - 1]
            row["prev"] = (f"{p['slug']}.html", p["title"])
        if i + 1 < len(segments):
            n = segments[i + 1]
            row["next"] = (f"{n['slug']}.html", n["title"])
        else:
            row["next"] = ("glossary.html", "Glossary")
        wired.append(row)
    return wired
