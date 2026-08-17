# Security Advisory & Research Intelligence — Architecture Proposal

> **Status:** architecture **approved for implementation** (2026-08-17) — discovery complete; UI direction locked (§18). No code until Milestone A tasks in §30.  
> **Date:** 2026-08-17 (rev. b — tab shell + sub-nav)  
> **Repo inspected:** `briefr` at current checkout (Alembic head **040** `infra_classifications`; investigation graph APIs **planned, not implemented**).  
> **Related living docs:** `docs/PRODUCT.md`, `docs/PRODUCT_STATUS.md`, `docs/SYSTEM_DESIGN.md`, `docs/DATA_SNAPSHOT.md`, `backend/db/schema_inventory.py`.  
> **Related plans:** `docs/plans/2026-08-04-001-feature-multi-source-ti-corroboration-plan.md`, `docs/plans/2026-08-11-003-audit-stabilization-release-report.md`, `docs/plans/2026-08-13-investigation-platform-roadmap.md`.  
> **Missing files (UNKNOWN):** `docs/plans/2026-08-11-001-correlation-source-independence-plan.md` and `docs/plans/2026-08-11-002-data-utilization-future-findings.md` are **cited by 003 but not present in this tree**. Source-independence findings below are taken from **003 Part 2** plus live `backend/correlation/` code.

**Implementation entry point:** §30 task sequence. Execute **Milestone A** (backend + CVE drawer) then **Milestone B** (tab shell + sub-nav). Do not skip A to build UI-only publications.

---

## 0. Verdict (read this first)

BRIEFR already has a **CVE spine** (NVD/KEV/EPSS), **community relationship graph** (OTX + TI mirrors), **headline news** (RSS Incidents & News), **exploit URL cards**, **Sigma YAML**, and a **correlation/confidence engine**. It does **not** have: CSAF/CVRF, a publication store, researcher identity, advisory events, per-source TOU ledger, or object storage for raw HTML/PDF.

The right move is **not** a second correlation engine, not a second search engine, not a sixth “research RSS tab,” and not a hardcoded researcher taxonomy.

**Recommended architecture:** a **configured source registry** + **intel-schema publication records** (metadata + deterministic entity links + provenance receipts) that **cite** existing CVEs/IOCs/techniques. Raw bodies optional and short-lived. Authors/orgs **discovered** with source-qualified IDs. Expertise **aggregated later** from those links. Publications **must not** increment `corroboration_k` until a real `source_group` model exists (audit P0, not shipped).

**Do not copy** `TAG_HINTS` in `backend/feeds/incident_news.py` (hardcoded vendor/product name list). That is the anti-pattern this feature exists to avoid.

---

## 1. Current BRIEFR capabilities relevant to this feature

| Capability | What it actually is | Fit |
|------------|---------------------|-----|
| CVE corpus | `cves` from NVD; CVE JSON 5 via `feeds/cve_record_v5.py`, `feeds/cvelistv5.py`, `feeds/vulnrichment.py` | Spine. Advisories **link to** CVEs; they do not replace NVD. |
| “Vendor Advisory” | NVD reference **tag** used for `patch_available` (`feeds/nvd.py`) | Not a document store. |
| CISA Advisories | RSS id `cisa-news` in `feeds/incident_sources.py` → headline cards, 24 CVE IDs max, HTML stripped | Closest existing advisory ingest; **not** structured CSAF. |
| Incidents & News | `feeds/incident_news.py` + `feed_cache` `incident_rss:*` / `incident_feed:snapshot`; UI `CaseStudies.jsx` | Generic news reader. Keep it. Do not grow it into this subsystem. |
| Exploit/PoC | `cve_exploits` UNIQUE `(cve_id, url)`; GitHub/ExploitDB/Metasploit/Nuclei; Sploitus on-demand | URL cards, not writeup bodies. |
| Detection research | SigmaHQ full YAML in `detection_rules` (DRL-1.1); Forge hunt packs | Detection artifacts, not blogs. |
| TI / IOC | OTX tables + `ti_mirror_iocs`; `correlation/ioc_normalize.py` keeps exact URL + `host_ioc` | Exact-vs-host rules must apply to extracted IOCs from publications. |
| Correlation / confidence | `backend/correlation/` (`engine.py`, `confidence.py`, `source_evidence.py`) | Reuse receipts + factors; do not fork. |
| Provenance UI | `intel/provenance.py` — per **drawer section**, not per claim | Too coarse for publications; extend receipt shape instead. |
| Search | FEED query language + `GET /api/search/semantic` (hybrid LIKE + optional pgvector). **No Postgres FTS.** | Extend entity types later; no new engine. |
| LLM | PDF summary, optional product fill (`affected_products_source='llm'`), optional detection_ctx | Narrate/classify only; never authority. |
| Identity | MITRE groups durable; OTX `correlation_actor` is **name strings**; no researcher/org tables | Must not pretend names are IDs. |
| Investigation graph | Planned `GraphPage` in `docs/plans/2026-08-13-investigation-platform-roadmap.md` — **code not in tree** | Publications should become **edge targets** after that API exists. |
| CSAF / CVRF | **UNKNOWN / absent** (repo grep empty) | Phase 2+ connector type, not core schema. |
| Object storage | **None.** Backups are filesystem `BACKUP_DIR`. | Raw evidence = local hashed files or skip. |

---

## 2. Existing components to reuse (do not rebuild)

| Component | Path | Reuse how |
|-----------|------|-----------|
| Catalog source descriptor | `backend/sources/registry.py` `SourceDescriptor` | Pattern for **publication sources**: `source_key`, pacing, enable env, retention, fetch fn. Generalize; do not only serve IOC mirrors. |
| Outbound pacing / circuits | `source_rate_limits.py`, `resilient_client.py` | New connectors use a pacing key (`rss`, `github`, or new `advisory`). Circuit-open → `source_unavailable`, no silent empty. |
| Scheduler + locks | `scheduler.py`, `scheduler_locks.py` | One job e.g. `publication_source_sync`; lock id must land in admin `_JOB_RUN_MAP`. |
| CVE / ATT&CK regex | `feeds/incident_news.py` `CVE_RE`, `TECHNIQUE_RE`, `extract_cve_ids` | Lift to a shared deterministic extractor module (do not duplicate; do not keep `MAX_CVE_IDS_PER_CARD=24` as a graph cap). |
| IOC normalize | `correlation/ioc_normalize.py` | Hashes/IPs/URLs/domains from publication text; preserve `raw_value`. |
| Evidence receipts | `correlation/source_evidence.py` `corroboration_receipt`; blocklist `_evidence_row` | Publication facts: `source_key:publication_id:field`. |
| Confidence factors | `correlation/confidence.py` | Optional **display** of extraction confidence as factors — not a new engine. |
| Exploit URL merge | `cve_exploits` `(cve_id, url)` unique | If a writeup URL is a PoC, link; do not duplicate the exploit row. |
| CPE / catalog | `matching/cpe.py`, `db/software_catalog.py`, `cves.cpe_matches` | Product impact **after** CVE link exists; do not guess products from titles. |
| Feed cache + retention | `db/cache.py`, `db/cache_retention.py` | Connector working set only; durable publications are **not** `feed_cache`. |
| Schema inventory | `db/schema_inventory.py` | New durable intel tables **must** be classified `INTEL_TABLES` or they cannot exist (raises). Author merge reviews may be `APP_TABLES`. |
| Auth | session `require_user` | Same as other analyst GETs. |
| Intel snapshot | `docs/DATA_SNAPSHOT.md` | Derived structured intel may publish; raw HTML/PDF and TOU-restricted copies must **not**. |
| LLM router | `ai/llm_router.py` | Optional classify/summarize with `ai_operations` provenance; template fallback. |
| File identity | `feeds/file_identity.py` | Content-address skip (same pattern as SigmaHQ/EPSS watermarks). |

---

## 3. Missing components

| Gap | Notes |
|-----|--------|
| Unified **all-feeds** source registry | Only TI trio is data-driven; NVD/RSS/Sigma are hard-wired modules. |
| `publications` / `publication_sources` tables | Does not exist. |
| Author / org identity + alias + merge | Does not exist. Closest: `otx_cve_pulses.author`, `detection_rules.author`. |
| Security **event** (Patch Tuesday-class) | Does not exist. |
| Per-source license/TOU/retain/export flags | Only SigmaHQ DRL-1.1 is stored on rows. |
| Claim-level provenance | `intel/provenance.py` is section-level. |
| `source_group` / independence | Documented in 003; **not implemented**. Campaign `independent_sources` always written as `1`. |
| CSAF/CVRF parser | Absent. |
| Raw object store | Absent. |
| Publication embeddings | Semantic index is CVE/technique/campaign only. |
| Researcher UI / search facet | Absent. |
| Data-utilization register file 002 | **UNKNOWN** (missing from repo); use 003 Part 2. |

---

## 4. Recommended architecture

**Principle (unchanged):** sources configured → entities discovered → relationships derived → expertise calculated.

```text
publication_sources (config)
        │  scheduler + resilient_get + pacing
        ▼
connector (rss | atom | json | github_release | csaf | html_allowlist)
        │  normalize → PublicationRecord
        ▼
intel.publications  (metadata, hashes, provenance)
        │  deterministic extractors
        ▼
publication_entity_links  (CVE, technique, IOC, …)  ──► existing tables
        │
        ├── publication_actors (discovered, source-qualified)
        ├── publication_events (optional grouping, not vendor enum)
        └── raw_objects (optional, hashed files, short TTL)
```

**Three layers — separate data and separate UI lanes (do not merge into one list):**

1. **Headline news** — ephemeral RSS cards (`feed_cache`, existing `incident_news.py`). UI: sub-nav **Headlines**.  
2. **Structured publications** — durable metadata + links (`publications` tables). UI: sub-nav **Advisories**.  
3. **ATLAS case studies** — MITRE ATLAS corpus (`atlas_case_studies`). UI: sub-nav **ATLAS**.  
4. **CVE/TI facts** (NVD, KEV, OTX, mirrors) — scoring / `corroboration_k`; not shown as a fourth sub-nav.

**Tab shell (agreed):** keep **one** header tab (no sixth tab). Rename **INCIDENTS & NEWS** → **ADVISORIES & INTEL**. Internal id stays `atlas` (`?tab=atlas`) for deep-link compatibility. Replace monolithic `CaseStudies` hero (“Case Studies”) with sub-nav **Headlines | Advisories | ATLAS** (Radix `Tabs` like Forge — `hidden` panels, not unmount).

**Rejected alternatives:**

| Approach | Why not |
|----------|---------|
| Grow `incident_rss` / `CaseStudies` into research intel | Wrong retention, no provenance, 24-CVE cap, hardcoded `TAG_HINTS`. |
| New graph DB | Forbidden by `PRODUCT.md`; investigation plan already Postgres projection. |
| New confidence engine | Forbidden; audit already fighting double-count. |
| Hardcoded researcher/vendor lists | Breaks the discovery principle; `TAG_HINTS` is the cautionary tale. |

---

## 5. Data model (directional — not a migration)

Classify **intel** unless noted. Names are directional.

### 5.1 `publication_sources` (configured)

Operator/config rows **or** frozen descriptors (start as code registry like `CATALOG_SOURCES`, promote to DB when operators must add feeds without deploy).

Fields: `source_key`, `display_name`, `source_kind` (vendor_advisory | cert | research_blog | github | gov | other), `connector`, `endpoint_url`, `pacing_key`, `enabled`, `poll_interval`, `auth_ref` (env key name only), `license_url`, `license_id`, `retain_raw` (bool, default false), `export_derived_only` (bool, default true), `source_group` (provider identity, e.g. same org multiple feeds), `reliability_note` (human text, **not** a score), `parser_id`.

**No vendor enum in core.** Microsoft vs Apple is a **configured source_key**, not a column of allowed vendors.

### 5.2 `publications` (discovered documents)

`publication_id` (internal), `source_key`, `canonical_url`, `url_hash`, `content_sha256` (of retrieved bytes if any), `title`, `document_kind` (advisory | writeup | exploit_disclosure | detection_research | incident_report | unknown), `published_at`, `updated_at`, `retrieved_at`, `canonical_external_id` (CSAF tracking id, GHSA, etc. when present), `language`, `knowledge_state` (`known|partial|stale`), `extraction_status`.

**Do not** store full HTML in this row.

### 5.3 `publication_entity_links`

`publication_id`, `entity_type`, `entity_id`, `extractor` (`regex_cve` | `regex_attack` | `metadata_author` | `cpe_via_cve` | `llm_topic` | …), `evidence_field` (title | summary | metadata.author | body_offset), `confidence` (reuse correlation vocabulary `high|medium|low` **for extraction**, never IOC malice), `observed_at`/`retrieved_at`.

Entity types that may **point at existing rows:** `cve`, `technique`, `ioc`, `campaign`, `detection_rule`.  
Entity types that are **publication-native until durable identity exists:** `actor_ref`, `org_ref`, `malware_label` (source-qualified strings).

### 5.4 `publication_actors` / `actor_aliases` (discovered people/teams)

See §8. Not a famous-people table.

### 5.5 `publication_events` (optional, phase 2)

See §6. Event is a **grouping**, not an article.

### 5.6 Out of first milestone

Expertise profiles, embeddings, LLM topic tables, co-author graph.

---

## 6. Source model

**Start from `SourceDescriptor`, not from `INCIDENT_RSS_SOURCES`.** RSS is one connector, not the product.

**Feasible connectors (P1+):**

| Connector | Feasible now? | Notes |
|-----------|---------------|--------|
| RSS/Atom | Yes | Same stack as `incident_news.py` + `resilient_get`. Metadata only. |
| JSON/API | Yes if documented + paced | e.g. GitHub releases API with `GITHUB_TOKEN` pacing `github`. |
| CVE JSON 5 / OSV / GHSA | Partial | `cve_record_v5.py`, `feeds/osv.py` already parse aliases — **link**, don’t re-ingest NVD. |
| CSAF | Not in repo | Add only when a **configured** CSAF endpoint exists; parser is a connector, not a vendor list. |
| GitHub repo crawl | Risky | Rate limits + ToS; prefer releases/atom. |
| Arbitrary HTML scrape | **Default no** | Legal + brittleness. Allowlist parser per `parser_id` only. |

Every source must declare: identity, connector, poll, 429 behavior (wait, never drop — existing `resilient_client` policy), watermark (`sync_state` key), dedup key, `retain_raw`, export policy, error → circuit.

**Do not assume** public pages are redistributable (`PRODUCT.md` community-source honesty).

---

## 7. Publication / advisory model

`document_kind` is a **small closed enum** for UI filters, filled by:

1. Source default (CISA feed → `advisory`)  
2. Deterministic hints (filename `.pdf` CSAF, GitHub `Security Advisory`)  
3. Optional LLM **suggestion** stored separately with model provenance  

Patch Tuesday is **not** a document_kind. It is an **event** (next section) that **has many** publications and CVEs.

Minimum stored: canonical URL, source, title, kind, authors (as actor refs), org ref, timestamps, hashes, tags from **source metadata only**, provenance, extraction links. Summary only if derived and labeled.

---

## 8. Researcher / entity model

**There is no existing entity model for researchers.** Do not overload `correlation_actor` (PK `cve_id, actor_name`).

**Identity rule:** `actor_id = {source_key}:{source_native_id}`  
Examples: `rss:schneier:author:bruce-schneier` (slug from feed), `github:user:12345`.  
Display name is **not** the key.

Support: individual, team, vendor_psirt, cert, org, contributor, `anonymous`, `pseudonym` (flag, not a specialty).

**Merge:** `actor_merge` table: `winner_id`, `loser_id`, `method` (`human` | `same_profile_url` | `same_github_id`), `confidence`, `created_by`. **Forbidden method:** `same_display_name`.

Human review UI is **app** schema (operator action), like `correlation_feedback`.

Aliases: extra rows, never deleted when merged.

---

## 9. Relationship model

Reuse investigation `edge_class` vocabulary **when that API exists**:

| Link | edge_class | Why |
|------|------------|-----|
| CVE ID in title/body regex | `direct_fact` or `reported` | Deterministic mention, still not NVD membership |
| Author metadata | `reported` | Source-claimed authorship |
| “this URL is the same advisory as that URL” (canonical + hash) | `direct_fact` (same document) | Dedup |
| “this writeup discusses CVE already in NVD” | `reported` | Citation |
| “quotes vendor advisory” (same canonical event) | **not independent corroboration** | `derived` / `references` |
| LLM “about kernel exploits” | `semantic` | `include_semantic` only |
| Co-author | `reported` | From metadata |

**Do not** call `confidence_for_ioc_edge` because a blog mentioned an IP.

**Do not** add publication rows to `k_sources` for IOC edges.

Join to existing graph:

```text
Publication --mentions--> CVE --(existing)--> technique / OTX IOC / campaign / Sigma
Publication --authored_by--> ActorRef
Publication --part_of--> Event
Publication --references--> Publication (same event vs independent)
```

---

## 10. Expertise model

**Phase 3 only.** Not a column on the actor.

Compute from `publication_entity_links` + `publications.published_at`:

- counts by entity_type / id  
- two windows: `all_time` vs `last_N_days` (N configurable, default 365)  
- output: ranked **topics** with counts and last-seen — never a single label “Windows researcher”

Deterministic. LLM may **name** a cluster (“identity platforms”) as a **caption** with model provenance, not as the stored specialty.

If a “reliability” metric is desired: **recommend against** for v1. Source `reliability_note` is enough. Researcher “credibility scores” become a second scoring system and will be gamed by volume. **UNKNOWN** whether operators even want it; default **omit**.

---

## 11. Storage architecture

**Recommend option B:** PostgreSQL structured intel + **optional** local hashed files for raw bytes. Not everything in Postgres. No S3 client in-tree today — do not invent cloud object storage for v1 (`BACKUP_DIR` pattern: local disk).

| Tier | Store | What |
|------|-------|------|
| A Structured | Postgres `intel` | §5 tables |
| B Raw evidence | Filesystem `{PUBLICATION_RAW_DIR}/{sha256[:2]}/{sha256}` + pointer column | HTML/PDF **only if** `retain_raw=true` |
| C Derived | Postgres or `ai_operation_payloads` (already 7-day) | Summaries, LLM classify |
| D Cache | `feed_cache` | Connector scratch; existing retention |

SigmaHQ YAML in Postgres is an **exception** (detection product). Do not use it as a precedent to dump blog HTML into `TEXT`.

---

## 12. Retention strategy

Follow `db/cache_retention.py` philosophy (explicit TTLs, scheduled `cache_retention_cleanup`).

| Artifact | Default |
|----------|---------|
| Publication metadata + entity links | Durable (intel), until source retract / operator purge |
| RSS connector cache | Keep existing 48h pattern for **news**; publications themselves are not cache |
| Raw bytes | **Off** by default. If on: 7–30 days, then delete file, keep `content_sha256` |
| LLM payloads | Existing 7 days |
| Embeddings | **Do not generate** for publications in v1 |
| OTX/TI | Unchanged (7-day IOC mirrors) — publications must not depend on those rows surviving |

Tiered: hot metadata forever (cheap); raw cold/delete; embeddings never-by-default.

---

## 13. Deduplication strategy

Distinguish **same document** vs **same event** vs **independent research**.

| Signal | Meaning |
|--------|---------|
| Identical `canonical_url` (normalized) | Same document |
| Identical `content_sha256` | Same bytes (mirror/syndicated) → `same_document` |
| CSAF / GHSA / vendor tracking id | Same advisory object |
| Same CVE set + same `source_group` + close time | **Candidate** same event — do not auto-merge |
| Similar title only | **Not** a merge |

Independent researcher writeup about the same CVE = **new publication**, `references` the vendor advisory if URL overlap, **does not** raise corroboration.

Reuse `cve_exploits` URL uniqueness when the URL is an exploit card.

---

## 14. Provenance model

Every stored fact answers: source_key, publication_id, canonical_url, published_at, retrieved_at, evidence_field, extractor, deterministic vs inferred.

Receipt string: `{source_key}:{publication_id}:{extractor}:{entity_id}`

Never collapse URL → hostname on the publication row (`ioc_normalize` already keeps URL + `host_ioc` for IOC links).

Do not overwrite `raw` fields on refresh; append retrieval or update `updated_at` with previous hash in history **only if needed** (v1: last-write metadata + immutable sha256 list optional).

`intel/provenance.py` can later grow a `derive_publication_provenance` **section banner**; it must not replace per-link receipts.

---

## 15. LLM boundaries

Already product law (`docs/PRODUCT.md`): deterministic core; LLM narrates/extracts at edges.

| Allowed | Forbidden |
|---------|-----------|
| Suggest `document_kind` when source default is `unknown` | IOC malice, scoring, OP/SSVC, corroboration_k |
| Executive summary for **operator PDF** (existing `/api/ai/summary` pattern) | Silent fact rows without `extractor=llm_*` |
| Topic captions for expertise UI (phase 3) | Identity merge |
| Ambiguous “PSIRT” → org_kind suggestion | Authoritative author identity |

Store `model`, `provider`, `prompt_hash` via existing `ai_operations`. Template fallback when keys missing.

---

## 16. Correlation integration

Publications **join** the graph as citations. They **do not** produce campaign/infra edges.

Until `source_group` exists (003 P0, files 001/002 **UNKNOWN** in tree):

- A blog that copies a vendor advisory is **one narrative source**, not a second confirmation.  
- abuse.ch dual feeds already double-count — do not add blogs into that math.  
- `independent_sources` on campaigns is already a lie (`1` always) — do not extend it.

When investigation `GraphPage` ships: add hops `cve → publication` as `reported` with `source_key=publication:{source_key}`.

---

## 17. Confidence integration

Reuse `confidence_factors` **shape** for extraction quality (`regex_cve` = high, `llm_topic` = low).

Do **not** create researcher reputation scores in v1.

Freshness: `retrieved_at` / `published_at` on the publication; do not mix with IOC half-lives unless the link is an IOC.

---

## 18. UI / UX proposal (locked)

**Do not add a sixth header tab.** Reorganize the existing `atlas` tab. FORGE and future INVESTIGATE graph stay separate.

### 18.1 Header tab rename

| Surface | Before | After |
|---------|--------|-------|
| `Header.jsx` label | INCIDENTS & NEWS | **ADVISORIES & INTEL** |
| `mobile-tab-bar` | same | same |
| Command palette (`App.jsx`) | Go to INCIDENTS & NEWS | Go to ADVISORIES & INTEL (keep keywords `incidents`, `news`, `atlas`) |
| `TutorialOverlay.jsx` | INCIDENTS & NEWS | ADVISORIES & INTEL |
| `RelatedTab.jsx` link text | IN INCIDENTS & NEWS | IN ADVISORIES & INTEL (or “in intel feed”) |
| URL `tab=` | `atlas` | **`atlas` unchanged** — do not break `?tab=atlas` bookmarks |

Component file may remain `CaseStudies.jsx` initially; rename to `AdvisoriesIntel.jsx` optional in B.

### 18.2 In-tab sub-navigation

Use the same pattern as `Forge.jsx` + `Tabs` from `frontend/src/components/ui/`:

| Sub-nav id | Label | Content | Data source |
|------------|-------|---------|-------------|
| `headlines` | **HEADLINES** | Latest security news river (scan speed) | Existing `GET /api/case-studies/feed` **news cards only** (`kind !== 'atlas'`) via `loadCaseStudyFeed()` |
| `advisories` | **ADVISORIES** | Structured publications list + filters | New `GET /api/publications` (paginated) after Milestone A backend |
| `atlas` | **ATLAS** | MITRE ATLAS case study cards | Existing feed **atlas cards only** + optional `GET /api/atlas/casestudies` for full list |

**URL:** `?tab=atlas&view=headlines|advisories|atlas`  
Default `view=headlines` when `tab=atlas` and `view` missing.  
`view` on this tab is **disjoint** from Forge (`coverage`, `scenarios`, …). Extend `shellUrlState.js`: when leaving `tab=forge`, clear forge `view`; when entering `tab=atlas`, default `view=headlines` if absent; when leaving `atlas`, clear `view` (or leave for back-nav — match Forge hygiene in `navHistory.js`).

**Do not** render headlines and advisories in one scrolling list. Three `TabsContent` panels, `hidden` when inactive (design-system tab persistence rule).

### 18.3 Panel behavior

**Headlines** (Milestone B — rehome existing UI)

- Reuse `FeedCard`, search, skeleton, error/retry from `CaseStudies.jsx`.
- Drop sidebar layout; ATLAS moves to its own sub-nav panel.
- **Active campaigns** sidebar (`isCampaignArticle`) → keep as a **strip or filter chip** on Headlines only, or a small “Campaign headlines” block at top of Headlines — not a fourth sub-nav.
- Hero copy: replace “Case Studies” with **Advisories & intel** kicker explaining headlines vs structured advisories.
- Search: client filter on loaded headline cards (existing). Advisories panel has its own filters (source, kind, CVE chip).

**Advisories** (Milestone B — new panel)

- Table or dense card list: title, source badge, `document_kind`, `published_at`, CVE chips (open drawer), external link (canonical URL).
- Row expand or side detail: provenance line (`source_key`, `retrieved_at`, `extractor`), entity link list — **no full article body** in v1.
- Empty states (distinct copy):
  - sync never run / flag off
  - sync ran, zero rows
  - filters too narrow
- Stale: `knowledge_state` + feed-health style hint if source circuit open.

**ATLAS** (Milestone B)

- Full-width feed of `kind === 'atlas'` cards (not only “latest 3” sidebar).
- Keep external ATLAS links and technique chips.

### 18.4 DetailDrawer (Milestone A — ship before or with B)

- New Intel subsection **Advisories & research** (or dedicated mini-tab if Intel is crowded): publications mentioning **this CVE** via `GET /api/publications?cve_id=…` or `GET /api/cves/{id}/publications`.
- Distinct from **Related** tab headline mentions (`get_related_news_for_cve`) — keep both; label Related block “News mentions” vs drawer intel “Advisories & research.”

### 18.5 Out of scope for tab shell

- INVESTIGATE graph canvas (separate header tab later).
- Researcher profile pages (Milestone C).
- Forge, IOC, correlation scoring UI.

### 18.6 Visual reference

```text
[ BRIEF | FEED | IOC LOOKUP | ADVISORIES & INTEL | FORGE ]  ← header (5 tabs)

ADVISORIES & INTEL tab
├── [ HEADLINES | ADVISORIES | ATLAS ]   ← sub-nav (Radix Tabs)
├── Headlines panel → RSS cards (ephemeral)
├── Advisories panel → publication rows (durable)
└── ATLAS panel → case study cards
```

---

## 19. Search integration

Do **not** add FTS or a new engine.

Milestone A: CVE drawer fetch by `cve_id` (index on `publication_entity_links`).  
Later: extend `db/embeddings_search.py` keyword `LIKE` to publication title (same as campaigns).  
Embeddings: new `entity_type=publication` **only** if `EMBEDDINGS_ENABLED` and operator opts in — default off.

Researcher search = lookup by alias table, not semantic “find experts.”

---

## 20. Export design

Public/intel snapshot: **derived rows** (title, source_key, canonical_url, published_at, entity links, extractors).  
**Not** raw HTML/PDF.  
**Not** full article text.  
Honor `export_derived_only`.

Blocklist JSON already flagged for legal review of upstream fields (003 §1.3) — same bar: no silent republication.

PDF: link list + provenance, existing jsPDF path; LLM summary optional and labeled.

---

## 21. Security model

- Analyst session on all new GETs (middleware).  
- Admin-only source enable / `retain_raw` / purge.  
- SSRF: reuse resilient client allow/deny; **do not** fetch operator-supplied URLs without the same blocks as other outbound (`100.64.0.0/10` etc. in PRODUCT_STATUS).  
- Raw dir: not served as static public files; authenticated download if ever.  
- Secrets: env key names on sources, never in logs (`CONTRIBUTOR_RULES.md`).  
- Rate limit: analyst GET class, not IOC lookup bucket.

---

## 22. Legal / provenance considerations

Not legal advice.

Track per source: `license_url`, `license_id`, `retain_raw`, `export_derived_only`, attribution text.

Internal fetch ≠ public redistribute. Prefer BRIEFR-derived structured links (CVE mentioned in source X at URL Y) over copying body text.

SigmaHQ DRL-1.1 is the only in-repo model of **storing** upstream protected text with license on the row — use that discipline if a connector must keep YAML/CSAF JSON.

---

## 23. Expected storage growth (order-of-magnitude, not measured production)

**UNKNOWN:** live publication volume (no such table). Estimates assume **operator configures ~20 feeds**, ~5 new items/feed/day ≈ **100 documents/day**.

| Store | Rough annual | Notes |
|-------|----------------|-------|
| Metadata + links (~3 KB/doc) | ~100 MB | Cheap; Postgres is fine |
| Raw HTML ~100 KB × 100/day | ~3.6 GB/year if kept forever | **Why default retain_raw=false** |
| Raw, 14-day window | ~140 MB | Acceptable on 16 GB box if enabled |
| Embeddings 384-d float32 × 36k docs | ~50 MB/year | Still opt-in |
| Duplication | High among vendor + CISA + news | Hash dedup avoids most raw copies |

Production full dump cited ~115 MB in schema-split plan (2026-07-26). Metadata-only publications will not dominate. **Raw-forever will.**

---

## 24. Implementation phases

| Milestone | Scope | Depends on |
|-----------|--------|------------|
| **A — Backend + CVE drawer** | Source registry (code), `publications` + `publication_entity_links`, RSS connector for **publication sources** (not replacing `incident_news.py`), CVE+ATT&CK extract, provenance receipts, `GET` APIs, drawer section, tests, `schema_inventory` | Nothing |
| **B — Tab shell + sub-nav** | Header rename; `CaseStudies` → sub-nav shell; **Headlines** / **Advisories** / **ATLAS** panels; `view=` URL sync; Advisories list UI wired to A APIs; tutorial/command palette copy | **A** APIs exist |
| **C** | Events grouping, actor discovery, publication detail drawer, dedup UX (same URL in Headlines + Advisories — show badge) | B |
| **D** | Human merge UI, expertise histograms, optional LLM classify/summary, keyword search on publications | C |
| **E** | Investigation graph hops, embeddings opt-in, CSAF connector, structured exports | Investigation P0; legal review |
| **Parallel (do not block A)** | Correlation `source_group` (003 P0) | Missing 001/002 docs |

**CISA dual-run (resolved):** during A+B, CISA RSS stays in **Headlines** and **also** ingests into **publications** when CVEs extracted. Advisories panel may show the same story as a headline — show “Also in headlines” or dedupe badge by `canonical_url` in B, not silent merge.

---

## 25. Testing strategy

Follow existing patterns: pytest fixtures like OTX/correlation tests; `verify-local.sh` merge gate.

Must include:

- Deterministic CVE extract (reuse/extend `extract_cve_ids` tests).  
- Dedup: same URL, same hash, different writeups same CVE.  
- No increment of `corroboration_k` when a publication is inserted (regression).  
- Exact URL not collapsed on publication row.  
- Name-collision: two authors `"Alex Chen"` from different `source_key` remain two `actor_id`s.  
- `retain_raw=false` → no file written.  
- Unauthenticated 401 on new GETs.  
- `schema_inventory` classification.  
- Connector 429/circuit: no crash, `knowledge_state`/`source_unavailable`.  
- License flag: export omits body even if raw exists.

---

## 26. Migration / rollback

Forward-only Alembic (next free after 040, likely **041** if assertions did not take it — **coordinate** with investigation Task 5).  

Rollback: restore encrypted backup (existing ops). Feature flag `PUBLICATION_SYNC_ENABLED` default off. Drawer hides section when table empty / flag off. Dropping tables is a later migration, not a rollback.

---

## 27. Risks

| Risk | Mitigation |
|------|------------|
| Becomes RSS tab #2 | Separate tables + **Advisories** sub-nav (not blended list) |
| Double-count corroboration | No publication → `k_sources`; wait for source_group |
| Legal scrape | Default metadata RSS; no HTML scrape; retain_raw off |
| Identity merges | Source-qualified IDs; forbid name-only merge |
| Disk blowup | No raw-by-default; retention job |
| Hardcoded vendors | Registry only; ban `TAG_HINTS`-style lists in extractors |
| Scope swallows investigation/Forge | Tab = inbound narrative only; Milestone B after A APIs |
| Missing 001/002 plans | Treat independence as **unimplemented**; don’t invent claims |

---

## 28. Open questions (resolved + remaining)

**Resolved (2026-08-17):**

1. **Tab vs drawer?** Both. A = drawer per CVE; B = reorganized `atlas` tab with sub-nav. No sixth header tab.  
2. **Replace Case Studies?** **No** — rename tab, split content across Headlines | Advisories | ATLAS.  
3. **CISA dual-run?** Yes during A+B; dedupe badge in B optional.  
4. **Sub-nav labels?** HEADLINES | ADVISORIES | ATLAS (header: ADVISORIES & INTEL).  
5. **Operators add sources in A?** Code registry only (like `CATALOG_SOURCES`).

**Still UNKNOWN:**

1. CSAF in year-one? **Recommendation:** no until a configured endpoint exists.  
2. Researcher profiles in public intel snapshot? **Recommendation:** no.  
3. Where is `2026-08-11-002`? Rebase before claiming independence metrics.  
4. Keep **Active campaigns** strip on Headlines vs drop? **Recommendation:** keep as Headlines subsection until publications cover campaign-class docs.

---

## 29. Milestone definitions

### Milestone A (backend + drawer)

**Ship:** publication source registry, tables, sync job, CVE/ATT&CK links, GET APIs, DetailDrawer **Advisories & research** section, tests, docs.

**Do not ship:** tab rename, sub-nav, Advisories panel, researcher graph, LLM, raw archive, CSAF.

**Success:** From a CVE drawer, analyst sees structured publication rows with provenance. Empty states honest.

### Milestone B (tab shell — user-visible reorg)

**Ship:** ADVISORIES & INTEL header label; sub-nav; three panels; Advisories list bound to A APIs; Headlines = existing RSS without ATLAS sidebar; ATLAS full panel; URL `view=` sync; copy updates.

**Do not ship:** researcher profiles, events UI, LLM summaries in list.

**Success:** Analyst opens ADVISORIES & INTEL → switches Headlines vs Advisories vs ATLAS without confusion; Advisories rows match drawer data for same CVE.

**Non-success:** One blended feed; “Case Studies” title remains; Advisories panel empty while backend has data.

---

## 30. Implementation sequence (execute in order)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Merge gate each milestone: `./scripts/verify-local.sh`.

### Milestone A — Backend + CVE drawer

- [ ] **A1** Shared extractors: move `CVE_RE`, `TECHNIQUE_RE`, `extract_cve_ids` to `backend/publications/extract.py` (or `feeds/text_extract.py`); tests; **remove `TAG_HINTS` dependency** from publication path (do not copy to new code).
- [ ] **A2** `publication_sources` registry module (code descriptors); start with **one** pilot source (recommend `cisa-news` RSS URL already in `incident_sources.py`).
- [ ] **A3** Alembic: `publications`, `publication_entity_links` (+ indexes on `cve_id` via links); register in `schema_inventory.py` `INTEL_TABLES`.
- [ ] **A4** `publication_rss` connector: fetch → normalize row → dedup by `canonical_url` / `content_sha256` → insert → run extractors → write links. **Do not** modify `incident_feed_refresh` job behavior.
- [ ] **A5** Scheduler: `publication_source_sync` job + lock + admin run map entry; env `PUBLICATION_SYNC_ENABLED` default `0`.
- [ ] **A6** APIs: `GET /api/publications` (list, filters: `cve_id`, `source_key`, `document_kind`, cursor); `GET /api/publications/{id}`; optional `GET /api/cves/{cve_id}/publications`.
- [ ] **A7** Drawer: Intel subsection listing publications for open CVE; provenance + external link; empty states.
- [ ] **A8** Tests: extractors, dedup, no `corroboration_k` change, 401, router_split append, fixture publication row.
- [ ] **A9** Docs: `API_REFERENCE.md`, `PRODUCT_STATUS.md` one row.

### Milestone B — Tab shell + sub-nav

- [ ] **B1** `Header.jsx` + mobile tab bar: **ADVISORIES & INTEL**; keep `id: 'atlas'`.
- [ ] **B2** `shellUrlState.js`: `view=headlines|advisories|atlas` when `tab=atlas`; default `headlines`; clear forge `view` on tab switch; tests.
- [ ] **B3** Refactor `CaseStudies.jsx` into shell: Radix `Tabs` sub-nav; hero copy (drop “Case Studies” title).
- [ ] **B4** `HeadlinesPanel`: news cards only (`kind !== 'atlas'`); retain search, errors, campaign strip; reuse `FeedCard`.
- [ ] **B5** `AdvisoriesPanel`: fetch `GET /api/publications`; filters; CVE chips → `onOpenCve`; empty when A flag off or zero rows.
- [ ] **B6** `AtlasPanel`: atlas cards full list (`kind === 'atlas'`).
- [ ] **B7** Copy pass: `TutorialOverlay`, command palette, `RelatedTab.jsx` link text.
- [ ] **B8** Frontend tests: sub-nav switches panels; URL `view` sync; Advisories empty state.

Stop after B for user validation before Milestone C (events, actors).

---

## Appendix A — What not to treat as “already the feature”

- Incidents & News RSS (`incident_sources.py` / `CaseStudies.jsx`)  
- NVD Vendor Advisory **tags**  
- `cve_exploits` URL index  
- OTX pulse `author`  
- Related news in the drawer  
- Investigation pin overlay  

## Appendix B — Files by milestone

**Milestone A:** `backend/publications/`, `backend/feeds/publication_rss.py`, `backend/routers/publications.py`, Alembic `041+`, `schema_inventory.py`, `scheduler.py`, `scheduler_locks.py`, `routers/admin/jobs.py`, `main.py`, `tests/test_router_split.py`, `DetailDrawer/IntelTab.jsx`, `frontend/src/api.js`, `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`, `tests/test_publication_*.py`.

**Milestone B:** `Header.jsx`, `CaseStudies.jsx` (or `AdvisoriesIntel.jsx`), `advisories/*Panel.jsx`, `CaseStudies.css`, `shellUrlState.js`, `App.jsx`, `TutorialOverlay.jsx`, `RelatedTab.jsx`, `caseStudyFeed.js` (split helpers), frontend unit tests.

---

## Appendix C — Approaches considered

1. **Recommended:** publication intel layer + **ADVISORIES & INTEL** tab with Headlines | Advisories | ATLAS sub-nav; drawer-first backend (A), tab shell (B).  
2. **Extend Incidents RSS only:** faster, wrong model (cache TTL, no identity, TAG_HINTS). Reject as the product.  
3. **Full researcher graph + LLM expertise + canvas in one epic:** conflicts with investigation P0, source-independence P0, and storage/legal. Reject as first delivery.
