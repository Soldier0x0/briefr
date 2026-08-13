# Investigation-Oriented Vulnerability and Threat Intelligence Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve BRIEFR from a strong CVE-centric intelligence application into an evidence-backed, investigation-oriented vulnerability and threat-intelligence platform without replacing the existing PostgreSQL architecture.

**Architecture:** Preserve the current FastAPI + PostgreSQL 16 + React/Vite design, and add a typed investigation projection over existing CVE, IOC, ATT&CK, campaign, correlation, detection, and embedding data. Introduce durable assertions/evidence and canonical identity only where the current schema cannot explain or persist a relationship; use bounded SQL expansion and lazy frontend loading instead of a graph database.

**Tech Stack:** FastAPI, PostgreSQL 16, Alembic, pgvector, APScheduler, optional Procrastinate, React 19, Vite, Recharts, existing Radix UI components, existing source registry/correlation engine, pytest, Node unit tests, and the repository merge gate `./scripts/verify-local.sh`.

## Global Constraints

- PostgreSQL remains the production database; SQLite remains a development/test fallback only.
- Do not introduce Neo4j, Memgraph, ArangoDB, or another graph database unless measured Postgres limits demonstrate a concrete requirement.
- Do not flatten source disagreements, inferred relationships, semantic similarity, or analyst feedback into confirmed facts.
- Every new relationship API must expose relationship class, provenance, confidence, freshness, and evidence references.
- Investigation expansion must be bounded, paginated, lazy, and filterable; it must never render the intelligence corpus.
- Existing source-specific tables and ingestion paths remain valid; new shared projections must be additive and reversible.
- Free/open-source deployment must remain possible with optional paid/API sources disabled.
- LLM output is advisory and must never silently become authoritative intelligence or scoring evidence.
- Implementation follows test-first changes and the repository merge gate before a PR is considered ready.

---

## 1. Repository-grounded architecture baseline

### Backend

BRIEFR is a FastAPI service assembled in [backend/main.py](../../backend/main.py). Routers cover CVE feed/detail/enrichment, IOC lookup and watchlists, risk, correlation, detection, Forge/hunt packs, search, ATLAS/case-study news, notifications, threat-intel exports, authentication, user stack/preferences, and admin/operations. Database access is split between [backend/db](../../backend/db), the compatibility facade [backend/database.py](../../backend/database.py), and source/domain services.

Production defaults are PostgreSQL-first (`BRIEFR_REQUIRE_POSTGRES=1`) with `intel` and `app` schemas. The authoritative table classification is [backend/db/schema_inventory.py](../../backend/db/schema_inventory.py). Alembic migrations define the schema; there is no ORM model layer that should be treated as the data-model source of truth.

### Frontend

The React application is routed from [frontend/src/App.jsx](../../frontend/src/App.jsx). The analyst surface consists of BRIEF, FEED, CVE DetailDrawer, IOC Lookup, Incidents/News, Forge, and an in-memory investigation panel. Admin pages expose scheduler, feed health, storage, backups, AI operations, webhooks, security, and database diagnostics. Reusable primitives are under [frontend/src/components/ui](../../frontend/src/components/ui).

### Ingestion and jobs

APScheduler in [backend/scheduler.py](../../backend/scheduler.py) coordinates NVD, CVEListV5, CPE, KEV, EPSS, Vulnrichment, MITRE ATT&CK/ATLAS, OTX, exploit sources, RSS/news, catalog IOC mirrors, embeddings, detection context, SigmaHQ indexing, correlation precomputation, backups, notifications, and retention. Outbound provider calls are paced and circuit-protected. Procrastinate is optional for durable outbound work.

### Security and access

Built-in session/JWT-cookie authentication protects analyst APIs; admin and refresh routes require role checks. Search service tokens are scoped to retrieval endpoints. IOC and threat-intel endpoints have dedicated rate limits. This access model should be reused for investigation APIs; no second authentication mechanism is required.

### Current external sources

| Area | Current sources |
|---|---|
| Vulnerabilities | NVD, CVEListV5, CISA KEV, FIRST EPSS, CISA Vulnrichment, OSV, CIRCL |
| Exploitation | GitHub PoC, ExploitDB, Metasploit, Nuclei, Sploitus, optional VulnCheck |
| Threat intelligence | OTX, ThreatFox, URLhaus, MalwareBazaar, VirusTotal, AbuseIPDB, optional GreyNoise |
| Adversary/context | MITRE ATT&CK, MITRE ATLAS, OTX pulse metadata, RSS/case-study feeds |
| Detection | SigmaHQ local index, Elastic fallback, generated Sigma/SIEM/YARA/Nuclei artifacts |
| AI/retrieval | pgvector embeddings, optional multi-provider LLM router |

## 2. Capability map

| Capability | Exists? | Where | Implementation quality | Relevant data available? | Missing pieces |
|---|---:|---|---|---:|---|
| CVE intelligence | Yes | `intel.cves`, CVE routers, NVD/CVEListV5/Vulnrichment | Strong | Yes | Normalize product/vendor identities later |
| Vulnerability scoring | Yes | `backend/scoring` and `POST /api/cves/{id}/risk` | Strong, explainable | Yes | Persist score snapshots if historical replay is required |
| EPSS | Yes | `cves.epss_score`, `epss_history`, momentum | Strong | Yes | Retention currently bounds long-term history |
| KEV | Yes | `kev_deadlines`, KEV sync | Strong | Yes | No general assertion history for membership changes |
| CVSS/CWE/CPE | Yes | CVE columns and JSON fields | Good but denormalized | Yes | Product/version graph and vendor entities |
| Asset-aware prioritization | Yes | user stack, profile, CPE matching, OP/SSVC | Good | Partial | No live asset inventory/CMDB telemetry |
| Attack-stack matching | Yes | `software_catalog`, stack filters, asset matching | Good | Partial | Version certainty and installed-state evidence |
| Related CVEs | Yes | product heuristic and embeddings | Useful | Yes | No durable typed relationship/evidence record |
| IOC lookup | Yes | `/api/ioc/lookup`, `enrichment/ioc.py` | Good for IP/hash/domain | Partial | URL/email first-class support and durable profile |
| IOC enrichment | Yes | VT, AbuseIPDB, GreyNoise, OTX, URLhaus, MalwareBazaar | Good but cache/on-demand | Partial | Observation history and source assertions |
| Threat actors | Partial | `mitre_groups`, `correlation_actor`, OTX adversary | Useful inference | Partial | Canonical aliases, actor profile, competing attribution |
| Malware | Partial | OTX pulse/mirror `malware` fields | Source attributes only | Partial | Malware entity, family/sample relationships, timeline |
| Campaigns | Partial | `correlation_campaigns`, pulse clustering | Explainable derived clusters | Yes for OTX-backed clusters | Source-native campaign identity and assertion history |
| Infrastructure | Partial | OTX IOCs, `ti_mirror_iocs`, classifications, shared-IOC correlation | Good bounded CVE correlation | Yes | Canonical infra entities and lifecycle |
| Security advisories | Partial | KEV, OSV, CIRCL, references, RSS | Fragmented | Partial | Advisory/patch/workaround entity |
| Zero-day intelligence | Partial | KEV/exploit/news signals | Indirect | Partial | Explicit zero-day assertion and evidence |
| Patch Tuesday | No | No dedicated source/model | Not determinable as a product capability | No durable dataset | Vendor bulletin ingestion/model |
| Researcher intelligence | Partial | RSS/case-study author/source fields | Basic | Partial | Researcher identity, citations, reliability |
| News | Partial | `case_study_feed`, RSS snapshot | Good feed, limited archive | Yes | Full-text provenance and durable article entity |
| MITRE ATT&CK | Yes | `mitre_techniques`, groups, maps | Strong | Yes | Universal evidence on mappings |
| Sigma | Yes | `detection_rules`, joins, SigmaHQ sync | Strong | Yes | Validation/outcome lifecycle |
| YARA | Partial | detection composer/generator | Useful generated content | Partial | Durable curated rules and test evidence |
| Detection queries | Yes | SIEM query generation and hunt packs | Good | Yes | Environment validation and deployment state |
| Threat-intelligence feeds | Yes | source registry and scheduled feeds | Mature | Yes | Unified source assertion contract |
| Source provenance | Partial | `intel/provenance.py`, correlation receipts, cache/source fields | Strong in selected paths | Partial | Universal provenance/evidence table |
| Evidence | Partial | correlation evidence/factors, references, audit log | Explainable in correlation | Partial | First-class evidence objects and attachments |
| Confidence | Partial | correlation confidence engine | Good for correlation | Partial | Shared confidence semantics across all edges |
| Historical changes | Partial | `cve_change_history`, `epss_history`, timestamps | Good for CVE fields/EPSS | Partial | Relationship/entity history and valid-time semantics |
| Entity relationships | Partial | association tables and derived queries | Strong around CVE | Yes | Universal typed relationship projection |
| Semantic search | Yes | `/api/search/semantic`, `services/semantic_search.py` | Strong | Yes for CVE/technique/campaign | Actor/malware/advisory/IOC indexing |
| PGVector | Yes | `embeddings`, HNSW, embedding services | Good | Yes | More entity types and semantic-edge governance |
| Search/indexing | Yes | trigram, keyword, hybrid, vector | Good | Yes | Cross-entity canonical search |
| Reporting | Yes, limited | PDF/CSV/XLSX, investigation PDF | Useful | Yes | Server-side case/report persistence and sharing |
| Notifications | Yes | `user_notifications`, webhooks, watchlists | Good | Yes | Saved-query/investigation subscriptions |
| Investigations/cases | Partial | `InvestigationContext`, PDF export | Session-only | No durable case data | Persistent case/evidence/notes/findings |
| Notes | No | No analyst note entity | Not determinable from current codebase | No | Case notes and relationship annotations |
| Saved searches | No | Search tokens are access credentials, not saved searches | Not determinable | No | Saved query model and scheduler |
| Saved investigations | No | In-memory context only | Not determinable | No | Persistent investigation model |
| Export | Yes | CSV/XLSX/PDF, intel snapshots, blocklist | Good but fragmented | Yes | Evidence-aware graph/case export, STIX later |
| API access | Yes | REST endpoints and scoped search tokens | Good | Yes | Entity/relationship investigation API |

## 3. Actual data model and relationship map

The schema is migration-defined. Core tables are introduced in [001_initial_schema.py](../../backend/alembic/versions/001_initial_schema.py), correlation snapshots in [025_correlation_cve_snapshot.py](../../backend/alembic/versions/025_correlation_cve_snapshot.py), pgvector in [032_embeddings_pgvector.py](../../backend/alembic/versions/032_embeddings_pgvector.py), SigmaHQ in [035_detection_rules_sigmahq.py](../../backend/alembic/versions/035_detection_rules_sigmahq.py), catalog IOC mirroring in [038_ti_mirror_iocs.py](../../backend/alembic/versions/038_ti_mirror_iocs.py), and infrastructure classifications in [040_infra_classifications.py](../../backend/alembic/versions/040_infra_classifications.py).

```text
CVE
├── KEV deadline / required action
├── EPSS score history and CVE field-change history
├── exploit references
├── ATT&CK technique map / ATLAS map
├── OTX pulse ── pulse IOC
├── derived campaign membership ── member CVEs
├── derived actor correlation
├── correlation snapshot
├── Sigma rule ── CVE / ATT&CK joins
├── hunt pack / detection context
└── vector embedding

IOC value/type
├── OTX pulse IOC
├── ThreatFox / URLhaus / MalwareBazaar mirror row
├── on-demand IOC cache result
└── derived shared-CVE / infrastructure relation

MITRE group ── group technique map ── ATT&CK technique ── CVE technique map
Campaign ── campaign member CVEs
User ── session / preferences / stack / IOC watchlist / notifications
```

The model supports direct relations, derived relations, and semantic similarity, but not with a single common representation. Product/vendor values are JSON/text inside CVE rows. Actor and malware values are source strings. Correlation outputs are persisted as projections, while their evidence is assembled by code. The smallest architectural addition is therefore a shared assertion/evidence projection, not a new database.

## 4. Analyst questionnaire

The answers below are deliberately limited to observable repository behavior.

| Analyst question | Current answer | Data/source | Relevant code/API | Gap |
|---|---|---|---|---|
| Does this CVE affect me? | Yes, when stack/profile/CPE evidence matches; otherwise unknown/provisional. | CPE, products, user stack/profile | `scoring/asset_match.py`, `/risk` | No installed-asset telemetry |
| Is this CVE being exploited? | Partially: KEV, VulnCheck flag, public PoC/exploit signals. | KEV, exploit feeds, EPSS | `scoring/threat.py`, exploit sync | Claims are not unified assertions |
| Who is exploiting it? | Partially: ATT&CK overlap or OTX adversary strings. | MITRE groups, OTX | `correlation/engine.py` | No canonical attribution dossier |
| What malware is associated? | Partially: source-provided OTX/catalog strings. | OTX, mirror rows | `otx.py`, `ti_mirror_iocs` | No malware entity/profile |
| What infrastructure is associated? | Partially: shared OTX IOCs and catalog corroboration. | OTX, URLhaus, ThreatFox, MalwareBazaar | `correlation/ioc_graph.py` | No canonical infrastructure entity |
| What IOCs should I hunt? | Partially: OTX pulse IOCs and extracted indicators. | Pulse IOC tables, CVE references | `extractIndicatorsFromCve`, OTX routes | No curated hunt bundle lifecycle |
| What ATT&CK techniques are involved? | Yes when mappings exist. | MITRE/ATLAS maps | `cve_technique_map`, `/detection` | Mapping evidence is inconsistent |
| Do I have detections for those techniques? | Yes/partially: SigmaHQ, generated Sigma, SIEM, YARA/hunt packs. | Detection index/composer | `detection/*`, `/api/cves/{id}/detection` | No validation/deployment state |
| What changed since yesterday? | Partially: CVE field changes and EPSS history. | `cve_change_history`, `epss_history` | `/api/changes`, `/epss-history` | No relationship/entity-wide timeline |
| What is the newest evidence? | Partially: source/cache timestamps are shown in selected panels. | fetched/observed/published fields | provenance/correlation responses | No common freshness policy |
| Which sources corroborate this? | Yes for correlation edges. | mirror receipts and factors | `correlation/source_evidence.py` | Not universal |
| Which sources disagree? | Partially: attribution conflict and analyst feedback. | correlation output/audit | `correlation/attribution.py`, feedback | No competing assertion store |
| How confident should I be? | Partially: strong correlation confidence; source-specific IOC scores. | confidence factors | `correlation/confidence.py` | No shared confidence scale |
| What should I investigate first? | Yes for CVEs: OP/Threat/Environment/SSVC. | scoring signals | `scoring/*`, `/risk` | No cross-entity queue |
| What should I patch first? | Yes for CVEs in a stack. | OP, KEV, CPE/profile | `/risk`, FEED | No remediation ownership/status |
| What should I hunt for? | Partially: IOC, ATT&CK, Sigma/SIEM/YARA outputs. | detection context and OTX | Forge/Detect | No validated hunt result |
| What should I block? | Partially: token-gated domain-candidate blocklist. | TI mirrors/classifications | `blocklist/*`, threat-intel API | Not generalized response policy |
| What should I monitor? | Partially: CVE watchlist, IOC watchlist, notifications. | watchlist tables | watchlist/webhooks | No saved query/case subscriptions |
| What do I not know yet? | Only through empty/error/degraded UI states. | response metadata | drawer/health UX | No explicit unknown state |
| Can I start from an IOC? | Lookup yes; investigation root no. | on-demand enrichment/cache | `IOCLookup.jsx`, `/api/ioc/lookup` | No IOC-root graph endpoint |
| Can I start from malware? | No dedicated root. | source strings only | OTX/catalog fields | No malware identity |
| Can I start from an actor? | UI pivot exists from CVE/ATLAS. | MITRE group/OTX strings | `InvestigationContext.jsx` | No actor-first API |
| Can I start from a campaign? | Search and CVE pivot exist. | campaign table | semantic search/correlation | No campaign evidence dossier |
| Can I start from a technique? | Yes in Forge/ATLAS/search. | MITRE/ATLAS | `/api/atlas`, Forge, search | No unified technique investigation |
| Can I inspect related CVEs? | Yes by product heuristic or vectors. | CVE fields/embeddings | `/related` | Relationship not evidence-bearing |
| Can I inspect advisories and patches? | Partially via KEV/OSV/CIRCL/references. | feed enrichment | detail routes | No advisory model |
| Can I inspect news/research? | Partially via RSS/ATLAS case studies. | incident snapshot | case-study feed | No durable research corpus |
| Can I see historical campaign membership? | No reliable answer. | current campaign projections | correlation tables | No valid-time relationship history |
| Can I distinguish reported vs inferred? | Only in selected correlation metadata. | correlation method/source | correlation modules | Need universal edge classes |
| Can I distinguish stale vs current? | Partially via cache/fetched timestamps. | cache and source timestamps | read/cache services | Need common freshness semantics |
| Can I save notes? | No. | none | Not determinable from current codebase | Persistent case notes required |
| Can I save an investigation? | No; browser context only. | React state | `InvestigationContext.jsx` | Persistent investigation tables/API |
| Can I share a case? | No. | PDF download only | `investigationPdf.js` | Case permissions/share links |
| Can I export evidence? | Partially: PDF/CSV/XLSX snapshots. | current API payloads | report/export utilities | Evidence appendix and provenance links |
| Can I query BRIEFR through an API token? | Yes for scoped search/detail routes. | search tokens | auth/search routers | No graph/entity API |
| Can I receive alerts? | Yes for watchlists, IOC hits, jobs, health. | notifications/webhooks | notifications/webhooks | No saved investigation alerts |

## 5. Investigation model

### Proposed root contract

Introduce a read-model contract, not a replacement domain model:

```json
{
  "entity_type": "cve|ioc|technique|campaign|actor|malware|infrastructure|advisory",
  "entity_id": "stable canonical or source-qualified identifier",
  "display_name": "human-readable label",
  "source_status": "known|partial|unknown|stale|disputed"
}
```

Existing CVE, technique, campaign, OTX pulse, and IOC records can populate this immediately. Actor, malware, infrastructure, and advisory roots should initially be projections over source-qualified values; canonical tables are justified only once aliases, lifecycle, or analyst curation need persistence.

### Investigation lifecycle

```text
Choose root → expand bounded relationships → inspect evidence → pivot
     → pin evidence → add notes/findings → save case → export/share/alert
```

The current [InvestigationContext.jsx](../../frontend/src/context/InvestigationContext.jsx) and [InvestigationPanel.jsx](../../frontend/src/components/InvestigationPanel.jsx) provide the UI seed but are session-only. P0 should preserve the current lightweight mode while adding optional server persistence.

## 6. Relationship and graph assessment

PostgreSQL is sufficient for the first investigation graph because current traversals are low-hop and already indexed. The first API should be a bounded expansion/read model over existing tables.

### Existing graph-ready edges

- CVE → ATT&CK/ATLAS technique: direct association tables.
- ATT&CK technique → MITRE group: `group_technique_map`.
- CVE → OTX pulse → IOC: direct OTX tables.
- CVE → campaign → member CVE: correlation campaign tables.
- CVE ↔ CVE via shared IOC: derived, indexed joins with hub suppression.
- CVE → Sigma rule → ATT&CK technique: local detection-rule joins.
- CVE → semantically related CVE/technique/campaign: pgvector search.
- CVE → news/research: incident-feed matching, not a durable FK relationship.

### Required edge metadata

Every projected edge should include:

```text
subject, predicate, object
edge_class = direct_fact | reported | derived | analyst_assertion | semantic
source_key, source_url, source_ref
confidence, confidence_factors
observed_at, published_at, ingested_at, valid_from, valid_to
evidence_refs[], method, method_version
```

Semantic edges must be visually and semantically distinct from asserted facts. Derived edges must expose the deterministic rule or correlation factors that produced them. Conflicting source claims must remain separate edges until an analyst or a transparent reconciliation policy resolves them.

### API shape

The planned read API should support:

```text
GET /api/investigations/entities/{entity_type}/{entity_id}
GET /api/investigations/entities/{entity_type}/{entity_id}/relationships
GET /api/investigations/entities/{entity_type}/{entity_id}/timeline
```

Required query controls: `depth` (default 1, max 2), `limit`, `cursor`, `entity_type`, `edge_class`, `min_confidence`, `source`, `observed_after`, `observed_before`, `include_semantic`, and `include_stale`.

The backend must batch-hydrate nodes, use keyset pagination, cap total returned nodes/edges, and cache only stable projection results. The frontend must lazy-expand nodes and never request an unbounded graph.

## 7. Provenance, evidence, temporal intelligence, and knowledge gaps

Current provenance is uneven: [intel/provenance.py](../../backend/intel/provenance.py) handles selected CVE/exploit/detection/correlation views; [correlation/source_evidence.py](../../backend/correlation/source_evidence.py) creates corroboration receipts; `cve_change_history` and `epss_history` provide limited historical retention.

P0 should add an append-oriented assertion/evidence projection with:

- source identity, source type, URL/reference, and source reliability metadata;
- claim class (`direct_fact`, `reported`, `derived`, `analyst_assertion`, `semantic`);
- confidence and explainable factors;
- publication, observation, ingestion, and validity timestamps;
- contradiction/retraction linkage;
- evidence payload/reference without storing secrets;
- deterministic method/version for derived and semantic claims.

This enables explicit `known`, `partial`, `unknown`, `unverified`, `disputed`, `stale`, `retracted`, `inferred`, and `semantic` states. It also enables “what changed?” queries for assertion additions, updates, retractions, confidence changes, and relationship membership—not merely CVE column changes.

## 8. Intelligence-to-detection and intelligence-to-action assessment

The current chain is strongest for a CVE root:

```text
CVE → CWE/ATT&CK → detection context → Sigma/SIEM/YARA/Nuclei → hunt pack
```

It breaks at actor/malware/IOC roots because those entities lack canonical identity and durable detection relationships. P1 should reuse the existing detection composer and context tables after relationship projection rather than creating another rule engine.

Current action support:

- Patch: CVE OP/SSVC/KEV/profile prioritization.
- Hunt: OTX IOCs, detection context, Sigma/SIEM/YARA, hunt packs.
- Block: curated malicious-domain candidate exports.
- Monitor: CVE/IOC watchlists, notifications, webhooks.
- Investigate: session thread and PDF only.

The roadmap should add persistent case actions and evidence links before adding automated remediation or blocking. Automation without confidence, freshness, and analyst review would increase false-positive risk.

## 9. Architecture changes and implementation tasks

The following tasks are the dependency-aware implementation sequence. Each task is independently testable and should be implemented with a failing test first.

### Task 1: Define shared entity, edge, and intelligence-state contracts

**Files:**

- Create: `backend/investigations/contracts.py`
- Create: `backend/tests/test_investigation_contracts.py`
- Modify: `docs/API_REFERENCE.md`

**Interfaces:**

- Produce typed enums/literals for entity types, edge classes, confidence bands, and knowledge states.
- Produce validation for `EntityRef`, `RelationshipRef`, `EvidenceRef`, and pagination/filter inputs.

- [ ] Add failing tests for valid/invalid entity types, edge classes, confidence, and state combinations.
- [ ] Implement immutable Pydantic contracts with explicit serialization names.
- [ ] Document the contract and examples in the API reference.
- [ ] Run `cd backend && pytest tests/test_investigation_contracts.py -q`.
- [ ] Commit `feat: define investigation relationship contracts`.

### Task 2: Build a read-only relationship projection over existing tables

**Files:**

- Create: `backend/investigations/projection.py`
- Create: `backend/tests/test_investigation_projection.py`
- Modify: existing correlation/search/db modules only where batch helpers are required

**Interfaces:**

- `async def get_entity(db, entity_type: str, entity_id: str) -> EntityRef | None`
- `async def expand_relationships(db, root: EntityRef, filters: RelationshipFilters) -> RelationshipPage`
- `async def get_entity_timeline(db, root: EntityRef, filters: TimelineFilters) -> TimelinePage`

- [ ] Add fixture-backed tests for CVE→technique, CVE→pulse→IOC, CVE→campaign, technique→group, CVE→Sigma, related-CVE, and campaign search paths.
- [ ] Implement bounded, typed projections using existing indexed tables and source-qualified identifiers.
- [ ] Batch hydrate nodes and return edge classes plus current provenance fields where available.
- [ ] Return explicit `partial`/`unknown` metadata when a projection cannot establish a relation.
- [ ] Run targeted projection tests and the existing correlation/search tests.
- [ ] Commit `feat: add bounded intelligence relationship projection`.

### Task 3: Add bounded investigation APIs with auth and pagination

**Files:**

- Create: `backend/routers/investigations.py`
- Create: `backend/tests/test_investigation_routes.py`
- Modify: `backend/main.py`, `docs/API_REFERENCE.md`

**Interfaces:**

- `GET /api/investigations/entities/{entity_type}/{entity_id}`
- `GET /api/investigations/entities/{entity_type}/{entity_id}/relationships`
- `GET /api/investigations/entities/{entity_type}/{entity_id}/timeline`

- [ ] Add tests for analyst-session auth, scoped search-token auth where appropriate, invalid roots, caps, cursor pagination, and filter combinations.
- [ ] Implement default depth 1/max depth 2, hard node/edge limits, and keyset cursors.
- [ ] Return stable response metadata: `method`, `source_status`, `truncated`, `next_cursor`, and `generated_at`.
- [ ] Add rate limiting consistent with existing analyst/search routes.
- [ ] Run route tests and `./scripts/verify-local.sh`.
- [ ] Commit `feat: expose bounded investigation relationship APIs`.

### Task 4: Add assertion/evidence storage and provenance adapters

**Files:**

- Create: `backend/alembic/versions/041_intel_assertions.py`
- Create: `backend/db/assertions.py`
- Create: `backend/intel/assertions.py`
- Create: `backend/tests/test_assertions.py`
- Modify: `backend/db/schema_inventory.py`, snapshot export/merge verification, `docs/DATA_SNAPSHOT.md`

**Interfaces:**

- `upsert_assertion(db, assertion: AssertionCreate) -> AssertionRecord`
- `list_assertions(db, subject: EntityRef, object_ref: EntityRef | None = None) -> list[AssertionRecord]`
- `retract_assertion(db, assertion_id: str, reason: str) -> AssertionRecord`
- `build_provenance(assertion: AssertionRecord) -> ProvenanceView`

- [ ] Add migration tests for primary keys, uniqueness, source/reference indexes, validity timestamps, and contradiction/retraction links.
- [ ] Implement append-friendly source assertions without duplicating existing CVE tables.
- [ ] Add adapters for existing correlation receipts, exploit provenance, detection provenance, and selected direct source fields.
- [ ] Keep operator/app tables out of intel snapshot publication unless explicitly classified as intel.
- [ ] Run migration, snapshot, and assertion tests.
- [ ] Commit `feat: persist intelligence assertions and evidence provenance`.

### Task 5: Add canonical aliases and source-qualified identity projections

**Files:**

- Create: `backend/alembic/versions/042_intel_entity_aliases.py`
- Create: `backend/db/entity_aliases.py`
- Create: `backend/investigations/identity.py`
- Create: `backend/tests/test_entity_identity.py`

- [ ] Add tests proving source-qualified actor/malware/infrastructure values never merge solely on display-name equality.
- [ ] Implement alias records with canonical type, canonical ID, alias, source, confidence, and validity timestamps.
- [ ] Project MITRE groups, OTX adversaries, malware strings, campaign IDs, and infrastructure hosts without changing existing source rows.
- [ ] Add deterministic normalization and collision reporting rather than silent merging.
- [ ] Run identity and migration tests.
- [ ] Commit `feat: add source-qualified intelligence entity identity`.

### Task 6: Persist investigations, notes, evidence pins, and findings

**Files:**

- Create: `backend/alembic/versions/043_investigations.py`
- Create: `backend/db/investigations.py`
- Create: `backend/routers/investigations_cases.py`
- Create: `backend/tests/test_investigation_cases.py`
- Modify: `frontend/src/context/InvestigationContext.jsx`, `frontend/src/components/InvestigationPanel.jsx`

- [ ] Add tests for create/update/archive, owner/member access, root/item ordering, notes, evidence pins, findings, and export authorization.
- [ ] Implement case, case-item, note, evidence-pin, and finding records with user ownership and timestamps.
- [ ] Add APIs for create, add/remove item, note, evidence pin, finding, list, archive, and export.
- [ ] Keep the existing in-memory investigation usable when persistence is unavailable; surface the state honestly.
- [ ] Update the panel to offer save/resume and show persistence status.
- [ ] Run backend tests, frontend unit tests, and `npm run build`.
- [ ] Commit `feat: persist analyst investigations and evidence`.

### Task 7: Add CVE and IOC-root investigation UX

**Files:**

- Modify: `frontend/src/components/DetailDrawer/*`, `frontend/src/components/IOCLookup.jsx`, `frontend/src/context/InvestigationContext.jsx`
- Create: `frontend/src/components/investigation/RelationshipExplorer.jsx`
- Create: `frontend/src/components/investigation/RelationshipExplorer.test.js`

- [ ] Add component tests for root selection, lazy expansion, type/edge/confidence/time filters, truncation messaging, and evidence drawer behavior.
- [ ] Implement CVE-root and IOC-root views using the bounded APIs; preserve existing CVE drawer tabs and IOC lookup results.
- [ ] Render direct, reported, derived, analyst, and semantic edges with distinct labels and evidence availability.
- [ ] Prevent recursive auto-expansion and cap rendered nodes independently of API limits.
- [ ] Run frontend unit tests, build, and browser smoke checks where available.
- [ ] Commit `feat: add bounded CVE and IOC investigation exploration`.

### Task 8: Add temporal intelligence and explicit knowledge gaps

**Files:**

- Create: `backend/investigations/timeline.py`
- Create: `backend/tests/test_investigation_timeline.py`
- Modify: change-history/correlation ingestion adapters, frontend timeline components, `docs/API_REFERENCE.md`

- [ ] Add tests for added/changed/retracted assertions, EPSS/KEV changes, campaign membership changes, stale evidence, and disputed relationships.
- [ ] Project existing `cve_change_history` and `epss_history` into timeline responses, then add assertion and relationship events.
- [ ] Compute freshness from source/observation/ingestion timestamps with explicit stale thresholds.
- [ ] Add UI states for known, partial, unknown, unverified, disputed, stale, inferred, retracted, and semantic.
- [ ] Run targeted tests and the full merge gate.
- [ ] Commit `feat: expose intelligence timelines and knowledge gaps`.

### Task 9: Extend actor, malware, campaign, advisory, and detection pivots

**Files:**

- Modify: `backend/services/semantic_search.py`, detection/correlation adapters, investigation projection
- Create: `backend/tests/test_investigation_entity_pivots.py`
- Modify: Forge/Detect/ATLAS frontend views and API docs

- [ ] Add tests for source-separated actor/malware/campaign pivots and advisory/detection relationships.
- [ ] Reuse existing MITRE, OTX, campaign, SigmaHQ, and detection-context data before adding new feeds.
- [ ] Add advisory projections from KEV/OSV/CIRCL/reference data with explicit `partial` status where no canonical bulletin exists.
- [ ] Add actor/malware/campaign/technique entity search results to the investigation explorer.
- [ ] Keep Patch Tuesday and full researcher intelligence marked unsupported until a source and durable model are selected.
- [ ] Run backend/frontend tests and document source limitations.
- [ ] Commit `feat: extend investigation pivots across intelligence domains`.

### Task 10: Add investigation-aware reporting, notifications, and exports

**Files:**

- Modify: existing report/PDF/export utilities and notification routers
- Create: `backend/tests/test_investigation_exports.py`
- Modify: `docs/API_REFERENCE.md`, `docs/DATA_SNAPSHOT.md`

- [ ] Add tests proving exports include root, edges, evidence references, confidence, freshness, notes, findings, and source URLs without secrets.
- [ ] Implement server-side PDF/CSV/JSON exports for persisted cases.
- [ ] Add optional saved-investigation notifications with dedupe and retention controls.
- [ ] Keep STIX/TAXII out of this task until assertion semantics and canonical identities stabilize.
- [ ] Run export, notification, and full verification tests.
- [ ] Commit `feat: export and notify on persisted investigations`.

## 10. Priorities and decision gates

### P0 — foundation

Tasks 1–4. These create shared semantics, a useful read projection, bounded APIs, and evidence/provenance. No graph UI should ship before these contracts exist.

### P1 — analyst value

Tasks 5–7. These make actor/malware/campaign values safe to pivot, persist investigations, and deliver CVE/IOC-root exploration using data already present.

### P2 — intelligence quality and action

Tasks 8–10. These add timelines, explicit knowledge gaps, broader pivots, case exports, and subscriptions.

### P3 — optional experiments

Only after production measurements: semantic relationship suggestions requiring analyst review, automated clustering beyond current explainable correlation, STIX/TAXII, and graph-database evaluation.

### Decision gates

- Do not add a graph database unless bounded Postgres expansion exceeds agreed latency/throughput targets under representative data.
- Do not merge source claims into canonical entities without alias evidence and collision reporting.
- Do not use semantic similarity as a factual relationship or scoring input without explicit labeling and review.
- Do not automate blocking or remediation from a relationship that lacks current evidence, confidence, and freshness.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OTX/source attribution is wrong or conflicting | Preserve source-qualified assertions and display conflicts |
| Shared infrastructure creates false correlations | Retain existing hub caps/noise handling and expose factors |
| Cached data is stale | Add freshness/state metadata and stale filters |
| Duplicate actor/malware identities | Require source-qualified IDs and alias review |
| Graph expansion explodes | Depth/node/edge caps, keyset pagination, lazy UI, caching |
| JSON/text fields make joins expensive | Use projection tables and targeted indexes; do not rewrite all CVE storage in P0 |
| Relationship evidence is lost on refresh | Append assertions and retractions rather than overwriting only current projections |
| Free deployment becomes impossible | Keep paid sources optional and support snapshot publication |
| Detection content is unvalidated | Label generated/community content and add validation state before action automation |
| Maintenance burden grows with each source | Require every adapter to emit the shared assertion/provenance contract |
| User investigation privacy is mishandled | Apply session/role authorization, owner/member checks, redaction, and export tests |

## 12. Final recommendation

Build the evidence-backed bounded investigation layer next. BRIEFR already has the difficult raw ingredients—CVE/KEV/EPSS scoring, CPE stack matching, ATT&CK/ATLAS, OTX IOC paths, source corroboration, campaigns, SigmaHQ indexing, pgvector search, notifications, exports, and a lightweight investigation UI. The highest-return architectural work is to make those relationships typed, explainable, time-aware, and persistable.

The recommended sequence is: contracts → read projection → bounded APIs → assertions/evidence → identity aliases → persistent cases → CVE/IOC investigation UX → timelines and knowledge gaps → broader pivots and reporting. This provides a credible path from “CVE detail page” to “analyst can investigate, collect evidence, understand uncertainty, decide, and share” while preserving PostgreSQL, open-source deployment, and explainable intelligence.

## 13. Verification checklist for implementation

- [ ] `cd backend && pytest tests/ -q`
- [ ] `cd frontend && npm run build`
- [ ] `cd frontend && npm run test:unit`
- [ ] `./scripts/verify-local.sh`
- [ ] Verify PostgreSQL migrations and SQLite fallback parity where applicable.
- [ ] Verify snapshot export/merge excludes app/operator data and preserves intel assertions.
- [ ] Verify all new routes require the intended analyst/search-token authorization.
- [ ] Verify API responses cap nodes/edges and include provenance/state metadata.
- [ ] Verify frontend does not auto-expand beyond one hop and communicates truncation.
- [ ] Verify exports redact secrets and preserve evidence references.
