# BRIEFR Textbook — Design Spec

**Date:** 2026-08-20  
**Status:** Awaiting user approval of chapter outline  
**Audience:** (1) cybersecurity/threat-intel learners; (2) engineers tracing this codebase  
**Source of truth:** `/agent/repos/briefr` code + `docs/PRODUCT_STATUS.md` (runtime wins over older docs)

---

## Goal

Produce a comprehensive, textbook-style PDF that teaches BRIEFR from the ground up — both the security concepts and the actual architecture of this repository as it exists on `main` today (v1.5.0 per PRODUCT_STATUS). Every major component must answer: **What / Why / How / Where / When**, with threat-intel concepts woven in next to the relevant BRIEFR module (not a separate glossary dump).

---

## Approaches considered

| # | Approach | Pros | Cons | Verdict |
|---|----------|------|------|---------|
| **A (recommended)** | Modular Markdown chapters under `docs/textbook/` → merge script → Playwright PDF (extend `scripts/generate_system_design_pdf.mjs`) | Matches existing repo tooling; version-controlled; Mermaid renders; easy chapter-by-chapter review | Large single artifact needs merge step | **Recommended** |
| B | One monolithic `docs/BRIEFR_TEXTBOOK.md` | Simplest authoring | Hard to review/revise; merge conflicts | Rejected |
| C | Publish to `briefr-docs` Docusaurus only | Good web UX | User asked for PDF-ready textbook; docs portal lags code | Supplement only |

**Recommendation:** Approach A — one file per chapter, shared front matter, `scripts/generate_briefr_textbook_pdf.mjs` concatenates + renders via Playwright (same stack as SYSTEM_DESIGN PDF).

---

## Document properties

| Property | Value |
|----------|-------|
| Format | Markdown source → PDF (A4, print CSS) |
| Diagrams | Mermaid (rendered at PDF build) + ASCII where Mermaid is overkill |
| Code citations | File paths with line anchors where helpful; short inline excerpts only |
| Tone | Textbook: precise, no filler; dual-audience sidebars ("Concept" vs "Code trace") |
| Honesty | Document quirks, default-off flags, half-finished pieces (STIX excluded, Investigation Score orphaned, correlation OP merge still client-side, etc.) |
| Self-check | 5–8 questions per chapter + 2–3 "trace it yourself" file pointers |

---

## Global constraints

- Trust **code over README** when they disagree; cite PRODUCT_STATUS for operator-visible truth.
- PostgreSQL-first production; SQLite dev fallback documented accurately.
- No invented features; STIX export, full docker-compose platform, saved investigation cases = **not shipped**.
- LLM chain per `ai/model_catalog.py` (Groq → Cerebras → OpenRouter → Gemini; Anthropic removed).
- Scoring per ADR-002: Threat asset-independent; OP primary; SSVC parallel annotation.
- Schema split per ADR-001: `intel.*` vs `app.*`.

---

## Proposed table of contents

### Front matter

- **About this book** — dual audience, how chapters are structured (What/Why/How/Where/When boxes)
- **How BRIEFR differs from a generic CVE dashboard** — single-server, deterministic scoring, no live correlation API calls, optional keys
- **Reading map** — analyst workflow vs backend trace vs admin ops

---

### Part I — Foundations

#### Chapter 1: The vulnerability intelligence problem

- What analysts need (exploitability, relevance, detection, context)
- Key concepts introduced lightly: CVE, CVSS, CWE, CPE, vendor/advisory
- Why aggregation tools exist; BRIEFR's scope boundary (not a SIEM)
- **Where:** `docs/PRODUCT.md`, `docs/SYSTEM_DESIGN.md` §1
- **Self-check:** Define CVE vs CWE; why CVSS alone is insufficient

#### Chapter 2: Threat signals — KEV, EPSS, PoC, and momentum

- **KEV (CISA Known Exploited Vulnerabilities)** — catalog, deadlines, `is_kev` floor in Threat Score
- **EPSS** — probabilistic exploitation; CSV identity skip; history for sparklines/momentum
- **VulnCheck** — secondary exploited flag (no Threat floor 80)
- **PoC / exploit indexes** — GitHub, ExploitDB, Metasploit, Nuclei
- **Where:** `feeds/kev.py`, `feeds/epss.py`, `feeds/vulncheck_kev.py`, `feeds/exploit_sync.py`, `cves` columns
- **When:** `kev_metadata_sync` (15m), `epss_score_sync` (6h), `exploit_sources_sync` (24h, default on)
- **Self-check:** Why KEV dominates EPSS in OP; what happens when EPSS is missing

#### Chapter 3: MITRE ATT&CK, Sigma, and detection engineering basics

- ATT&CK tactics/techniques; CVE→technique mapping
- **Sigma rules** — community YAML, SigmaHQ index vs BRIEFR templates
- YARA, SIEM queries, Nuclei templates — roles in BRIEFR Detect tab
- **DetectionContext** — cached artifacts for class-aware rules
- **Where:** `feeds/mitre.py`, `detection/sigma_generator.py`, `detection/sigmahq_index.py`, `detection/class_router.py`
- **Self-check:** Difference between SigmaHQ index hit and BRIEFR-generated template

#### Chapter 4: Threat intel primitives — IOCs, pulses, campaigns, evidence

- IOC types (IP, domain, hash, URL); refanging/normalization
- OTX pulses; pulse families; corroboration across mirrors
- **Evidence graph** — shared IOC edges between CVEs (not a graph DB)
- Campaign clustering vs infrastructure peers vs actor/sector vs temporal
- **Where:** `correlation/ioc_graph.py`, `correlation/campaigns.py`, `correlation/source_evidence.py`, `db/ti_mirror.py`
- **Self-check:** What "same_pulse" vs "shared_indicator" means in correlation receipts

---

### Part II — Platform architecture

#### Chapter 5: System shape — four layers and schema split

- Ingest → PostgreSQL → FastAPI → React
- **intel vs app schemas** (ADR-001): what lives where; `sync_state` routing
- asyncpg pool, SQLite fallback, pgvector for embeddings
- Auth layers (edge optional + session cookie); API-only workers
- **Where:** `main.py`, `db/schema_inventory.py`, `db/schema_split.py`, `docs/decisions/ADR-001-*`
- **Diagram:** four-layer + schema split mermaid
- **Self-check:** Name three tables in each schema

#### Chapter 6: The scheduler — when work actually runs

- APScheduler job catalog (~27+ jobs); locks; manual admin runs
- Startup bootstrap (`<10` CVEs → full NVD ingest; deferred maintenance)
- Catch-up mode; `BRIEFR_SCHEDULER_ENABLED`; orphaned `CACHE_REFRESH_*` env vars
- Procrastinate durable jobs (default off)
- **Where:** `scheduler.py`, `scheduler_locks.py`, `routers/admin/jobs.py` (`_JOB_RUN_MAP`)
- **Diagram:** ingest timeline (NVD → KEV → EPSS tail → enrichment)
- **Self-check:** Which jobs are opt-in vs opt-out defaults

#### Chapter 7: Resilience — API queue, circuits, caches, rate limits

- `resilient_client.py`; per-source circuit breakers
- In-memory `api_queue` vs Procrastinate outbound
- `feed_cache` vs `ioc_cache` TTLs; correlation 6h cache
- Token buckets; `BRIEFR_RATE_LIMIT_STORE=db`
- **Where:** `resilient_client.py`, `rate_limit.py`, `db/cache.py`, `tracking.py`
- **Self-check:** Why correlation makes no outbound calls at request time

---

### Part III — Ingestion and normalization

#### Chapter 8: NVD and the core CVE record

- Incremental sync (`lastMod`); rejected CVE purge
- Normalization pipeline: `feeds/nvd.py` → `cve_record_v5.py` → `upsert_cves`
- Fields landed on `cves`; MITRE hint; post-sync tail (Sploitus/CIRCL, embeddings)
- **When:** `nvd_incremental_sync` (1h default)
- **Quirk:** FEED "next refresh" = NVD incremental only
- **Self-check:** Trace one CVE from NVD JSON to DB row

#### Chapter 9: Additive enrichers — cvelistV5 and Vulnrichment

- GitHub snapshot sync; additive-only merge (NVD wins on conflict)
- SSVC/CVSS/CWE/CPE gap-filling
- **When:** `cvelistv5_incremental_sync` (30m), `vulnrichment_snapshot_sync` (6h)
- **Where:** `feeds/cvelistv5.py`, `feeds/vulnrichment.py`, `db/enrichment.py`

#### Chapter 10: Threat-intel mirrors and blocklist context

- Catalog registry: ThreatFox, URLhaus, MalwareBazaar, Feodo, PhishTank
- IOC normalize → `ti_mirror_iocs`; 7-day window clamp
- Tranco top-1M → `infra_classifications` (LEGITIMATE_DOMAIN)
- API key gates (`ABUSECH_AUTH_KEY`, etc.)
- **When:** daily mirror jobs (+90s boot delay)
- **Quirk:** ThreatFox URLs stored as domain type with host extraction

#### Chapter 11: OTX — pulses, IOC prefetch, and nightly correlation

- Nightly CVE↔pulse sync vs continuous budget sync
- `otx_cve_pulses`, `otx_pulse_iocs`, stale-serve on upstream 4xx/5xx
- IOC prefetch + `ioc_degree` hub suppression
- **When:** `otx_nightly_correlation` (02:00 Asia/Kolkata), `otx_continuous_sync` (5m if enabled)
- **Where:** `feeds/otx.py`, `feeds/otx_continuous.py`, `correlation/engine.py`

#### Chapter 12: News, publications, and non-CVE intel

- Incidents & News RSS snapshot (ephemeral `feed_cache`) vs durable publications (`PUBLICATION_SYNC_ENABLED=0`)
- RSS↔CVE linking; ATLAS case studies
- Pilot CISA advisories connector (RSS only; other connectors "not implemented")
- **Where:** `feeds/incident_news.py`, `feeds/publication_rss.py`, `publications/registry.py`

---

### Part IV — Scoring and prioritization

#### Chapter 13: Threat Score — asset-independent danger

- Formula (`threat-1.0`); renormalized weights; KEV floor 80
- Component raw scores in `scoring/risk.py`
- **Why (ADR-002):** separating danger from relevance
- **When:** on-demand `POST /api/cves/{id}/risk`
- **Where:** `scoring/threat.py`, `docs/decisions/ADR-002-*`

#### Chapter 14: Environment Relevance and asset matching

- Tiers: CONFIRMED → NO_MATCH; UNKNOWN vs NO_MATCH semantic fix
- CPE matching via `matching/cpe.py`; fuzzy graduation
- My Stack profile; optional W5 flags (`internet_facing`, `criticality`)
- **Where:** `scoring/environment.py`, `scoring/asset_match.py`

#### Chapter 15: Operational Priority and SSVC

- OP table (Threat band × Environment tier); escalation rules (EPSS, rising EPSS, W5, correlation)
- **Temporary quirk:** correlation OP escalation merged client-side in drawer
- SSVC outcomes (Act/Attend/Track*/Track); parallel to OP, never replaces it
- Legacy v1.1b as `legacy_risk_v11b`; orphaned Investigation Score noted
- **Where:** `scoring/priority.py`, `scoring/ssvc.py`, `frontend/src/scoring/riskScore.js`

#### Chapter 16: Momentum and change history

- EPSS trend, OTX pulse recency, KEV recency signals
- `epss_history`, `cve_change_history`; BRIEF tab movers
- **Where:** `scoring/risk.py` (`calculate_momentum`), `db/` change history helpers

---

### Part V — Correlation engine

#### Chapter 17: Correlation architecture — four lanes

- Campaign / Infrastructure / Actor / Temporal + boosters
- Priority score 0–100 with explainable components
- Engine version; no outbound at request time
- **Where:** `correlation/engine.py`, `correlation/priority.py`, `correlation/config.py`

#### Chapter 18: Infrastructure graph and IOC edges

- `find_shared_infrastructure_v2`; hub IOC cap; confidence per edge
- Mirror corroboration (`source_evidence.py`)
- **Where:** `correlation/ioc_graph.py`, `correlation/confidence.py`

#### Chapter 19: Campaigns and pulse families

- `build_campaigns_from_pulses`; lifecycle; member caps
- Display normalization vs matching normalization
- **When:** nightly `nightly_correlation` (01:00) + optional precompute slices
- **Where:** `correlation/campaigns.py`, `correlation/pulse_families.py`

#### Chapter 20: Precompute, snapshots, and CORRELATION_PRECOMPUTE_ENABLED

- Default off (ADR-004); `correlation_cve_snapshot` table
- Drawer bundle parallel fetch; cache invalidation
- **Where:** `correlation/engine.py`, `db/correlation.py`, `docs/decisions/ADR-004-*`

---

### Part VI — Detection, Forge, and proof

#### Chapter 21: DetectionContext and the class router

- Cache key `detection_ctx:{cve_id}`; static vs LLM vs Nuclei enrich paths
- CWE/ATT&CK → class slug; unified router for Sigma/SIEM/log patterns
- Feature flags (most default off except Nuclei enrich)
- **Where:** `detection/context.py`, `detection/class_router.py`, scheduler jobs

#### Chapter 22: Generating Sigma, SIEM, and YARA

- Template-based Sigma; suppression when SigmaHQ hits exist
- SIEM query templates per technique/class
- YARA from OTX pulse hashes
- Composer (DC-1/DC-2): evidence pack + emit
- **API:** `GET /api/cves/{id}/detection`
- **Where:** `detection/composer.py`, `detection/sigma_generator.py`, `detection/siem_queries.py`

#### Chapter 23: SigmaHQ local index

- Weekly tarball mirror; watermark; CVE-exact matching
- Admin force-resync; Forge attachment
- **When:** `sigmahq_index_sync` (168h, default on)
- **Where:** `detection/sigmahq_index.py`, `detection_rules` tables

#### Chapter 24: Forge — hunt packs, coverage, backlog

- MITRE navigator; stack-aware coverage
- Hunt pack generate/list; KEV detection backlog
- Proof bench (`POST /api/proof/run`)
- **Where:** `routers/forge.py`, `detection/backlog.py`, `proof/bench.py`

---

### Part VII — IOC enrichment and investigation

#### Chapter 25: IOC lookup path

- On-demand VT / AbuseIPDB / optional GreyNoise
- MalwareBazaar/URLhaus for hash/domain; quotas and 6h cache
- **Where:** `enrichment/ioc.py`, `routers/ioc.py`, `db/cache.py`

#### Chapter 26: Watchlist, retro-match, and notifications

- CVE watchlist vs IOC watchlist
- `ioc_retro_match` job; webhook `watchlist_alert`
- **Where:** `ioc/retro_match.py`, `webhooks/`, scheduler jobs

#### Chapter 27: Investigation graph (INVESTIGATE tab)

- Resolve API; bounded SQL projection (no graph DB)
- Edge classes; caps (200 nodes / 300 edges)
- No saved cases; thread PDF overlay separate
- **Where:** `investigations/projection.py`, `routers/investigations.py`

---

### Part VIII — LLM, embeddings, and retrieval

#### Chapter 28: LLM router and failover chain

- Task types; provider order; custom slot
- Pacing, circuit breakers, empty-response degradation
- AI operations admin; payload replay
- **Where:** `ai/llm_router.py`, `ai/model_catalog.py`, `routers/admin/ai_ops.py`

#### Chapter 29: LLM workloads in BRIEFR

- Product extraction (default off); DetectionContext LLM (default off)
- PDF executive summary (on-demand, session-gated)
- Payload guard — no blank requests
- **Where:** `ml/product_extraction.py`, `detection/context_llm_sync.py`, `ai/summary.py`

#### Chapter 30: Embeddings and hybrid search

- pgvector; entity types (CVE, technique, campaign)
- Hybrid FEED search; retrieval health admin
- **When:** `embeddings_backfill` (6h, `EMBEDDINGS_ENABLED=0` default)
- **Where:** `ml/embeddings.py`, `services/semantic_search.py`

---

### Part IX — Analyst and operator surfaces

#### Chapter 31: Analyst shell — BRIEF, FEED, drawer

- Tab model; URL sync; drawer bundle parallel assembly
- FEED query language; keyset pagination
- DetailDrawer tabs; risk display-only from backend
- **Where:** `frontend/src/App.jsx`, `components/DetailDrawer.jsx`, `routers/cves/detail.py`

#### Chapter 32: Forge, Incidents, Advisories, Investigate

- Header IA; deep links
- Forge honesty patterns (empty states, no false personalization)
- Publications tab vs drawer Intel

#### Chapter 33: Admin operator plane

- Scheduler, Feed Health, AI ops, webhooks, storage/DB explorer
- Catch-up mode; support pack; corpus drift
- Config apply strategies (immediate / reschedule / restart)

#### Chapter 34: Wallboard and kiosk

- Token header auth; auto-token rotation
- Stack-aware KEV tile; top risk ranking

---

### Part X — Operations, gaps, and tracing the code

#### Chapter 35: Deployment and production posture

- Postgres requirement; backups; `BRIEFR_ENV=production` defaults
- Rate limits; JWT_SECRET fail-closed
- **Where:** `docs/SELF_HOST.md`, `docs/OPERATIONS.md`, `docs/POSTGRES.md`

#### Chapter 36: What's shipped vs planned (honest inventory)

- STIX excluded; docker-compose platform not shipped
- Client-side correlation OP merge temporary
- Double MITRE refresh quirk; OSV request-only
- Publications non-RSS connectors stubbed
- Investigation Score orphaned

#### Chapter 37: Codebase map and tracing exercises

- Module index by directory
- Five guided traces (NVD ingest, POST /risk, correlation nightly, detection pack, IOC lookup)
- `./scripts/verify-local.sh` as quality gate

---

### Back matter

- **Appendix A:** Scheduler job catalog (ID, cadence, flag, module)
- **Appendix B:** Key API routes by area
- **Appendix C:** ADR summaries (001, 002, 004, 006)
- **Appendix D:** Environment variable reference (ingest + scoring + LLM flags)
- **Index:** Concepts → chapters

---

## Chapter template (each chapter follows)

```markdown
## Chapter N: Title

> **Concept track:** ...
> **Code track:** ...

### What it does
### Why it exists
### How it works (step-by-step)
### Where in the codebase
### When it runs
### Diagram (optional)
### Quirks and tradeoffs
### Review questions
```

---

## PDF build pipeline (design)

1. Source: `docs/textbook/*.md` + `docs/textbook/_frontmatter.md`
2. Script: `scripts/generate_briefr_textbook_pdf.mjs` — concatenate in TOC order, preprocess Mermaid, Playwright print to A4
3. Output: `docs/textbook/BRIEFR_TEXTBOOK.pdf` (gitignored) or committed if user prefers
4. Optional: `npm run textbook:pdf` in root or frontend package.json

Reuse patterns from `scripts/generate_system_design_pdf.mjs` (Mermaid inline, print CSS, table wrapping).

---

## Out of scope

- Magic Patterns / inspiration UI concepts (not relevant to PDF textbook)
- Rewriting PRODUCT_STATUS or SYSTEM_DESIGN (textbook references them)
- briefr-demo fixture site (mention as static demo only)
- Maintainer repo study guide (lives in briefr-maintainer)

---

## Approval gate

User confirms the **Proposed table of contents** above (add/remove/reorder chapters) before full chapter authoring begins.
