# BRIEFR Correlation Engine v2 — Implementation Plan

**Status:** Implementation spec (ready for Claude Code / human implementers)  
**Last updated:** 2026-06-21  
**Scope:** Backend correlation engine, OTX ingest, API, UI, and product integrations  
**Companion docs:** `PRODUCT.md`, `docs/ADMIN_ANALYST_OPERATOR_MODE.md`, `SYSTEM_DESIGN.md`, `API_REFERENCE.md`

---

## How to use this document

1. Read this file end-to-end before writing code.
2. Read `backend/correlation/engine.py`, `backend/feeds/otx.py`, and `frontend/src/components/DetailDrawer.jsx` (`CorrelationFindings`).
3. **OTX is the spine, not the whole product.** This plan includes OTX-maximal work **and** local-signal fusion, UX, workflow wiring, ops, and tests.
4. Branch: `cursor/correlation-v2-<suffix>` off fresh `main`.
5. Ship in **phases** (below). One phase per PR where possible.
6. Before each PR: `cd backend && pytest tests/ -q`; `cd frontend && npm run build` if UI touched.

---

## 1. Purpose

BRIEFR correlation today is a **v1 research feature**: three explainable levels (shared OTX IPs, loose MITRE actor match, vendor volume spike) shown only in the CVE detail drawer. It rarely changes analyst behavior.

**Correlation v2** makes campaign context **actionable**:

- Analysts see **why** CVEs are linked (receipts, plain language).
- Operators can **diagnose** empty or stale correlation (OTX coverage, last run).
- The product **uses** clusters in brief, feed, risk, investigation, and (optionally) webhooks — not only in a drawer footer.

**Design principles** (from `PRODUCT.md`):

- Explainable only — no black-box ML correlation scores.
- Scheduler-side heavy work; request path reads precomputed data where possible.
- OTX community attribution labeled honestly; KEV/exploit/stack **confirm or downgrade** clusters.
- Works **degraded without OTX** (local signals still produce useful findings).

---

## 2. Current state (v1)

| Layer | Today |
|-------|--------|
| **Engine** | `backend/correlation/engine.py` — 3 levels, 6h `feed_cache` |
| **Level 1** | Shared **IPv4/IPv6** only via `otx_pulse_iocs` join |
| **Level 2** | MITRE groups sharing **any** technique + OTX adversary string (low) |
| **Level 3** | Vendor CVE count 7d vs 90d baseline (≥3×); CPE vendor token |
| **OTX ingest** | `otx_nightly_correlation` (pulses, last 7d CVEs); `nightly_correlation` IOC prefetch (**max 100** pulses) |
| **API** | `GET /api/cves/{cve_id}/correlation?sector=` |
| **UI** | `DetailDrawer.jsx` → `CorrelationFindings` (Intel tab) |
| **IOC pivot** | `lookup_ioc_in_otx` returns `related_cves` — **not unified** with correlation engine |
| **Persistence** | Writes `correlation_*` tables; API **recomputes** L1/L2 live; only L3 reads `correlation_temporal` |
| **Tests** | Route registration + CVE prefix only — **no** `test_correlation.py` |
| **Integrations** | **None** — risk, brief, feed, investigation, watchlist, webhooks ignore correlation |

**Known waste:** `_normalize_pulse` extracts `targeted_countries` but `otx_cve_pulses` does not store them. Pulse metadata exists in DB but correlation logic ignores `pulse_id` co-occurrence.

---

## 3. Goals

1. **OTX-maximal:** Pulse-first clusters, multi-IOC, prioritized ingest, full metadata.
2. **Local fusion:** KEV, exploits, EPSS/change history, CWE/package, embeddings — as boosters on clusters.
3. **One graph:** IOC lookup, correlation API, and nightly jobs read the **same** OTX link tables.
4. **Actionable:** Brief, feed badges, risk bump, investigation suggestions consume clusters.
5. **Honest:** Receipts on every finding; distinguish *no signal* vs *cannot compute* vs *OTX off*.
6. **Tested:** Fixtures + regression tests for clustering and confidence rules.
7. **Operator-visible:** Admin diagnostics for OTX IOC coverage and last correlation run.

---

## 4. Non-goals (v2)

- Black-box ML campaign scores (embeddings stay semantic **lane**, not replacement for evidence).
- Graph database (Neo4j) or STIX export (note for V1.5; optional stub only if trivial).
- Real-time per-request OTX API calls on drawer open (scheduler + cache + tables).
- Correlation on full NVD text via LLM per CVE (Groq is for product extraction / PDF only).
- Replacing enterprise TI platforms — stay an explainable analyst pane.

---

## 5. Target architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│ SCHEDULER (prioritized)                                          │
│  otx_pulse_sync  →  otx_cve_pulses (+ full pulse dimension)      │
│  otx_ioc_sync    →  otx_pulse_iocs (all types, tiered budget)    │
│  campaign_build  →  correlation_campaigns + members + edges      │
│  local_boosters  →  kev/exploit/epss/cwe/package/embeddings      │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ READ PATH                                                        │
│  GET /api/cves/{id}/correlation                                  │
│  GET /api/correlation/clusters (optional phase 4)                │
│  IOC lookup related_cves (same tables)                             │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ CONSUMERS                                                        │
│  DetailDrawer │ Brief │ Feed badge │ Risk │ Investigation │ Admin │
└─────────────────────────────────────────────────────────────────┘
```

**Spine:** OTX pulse membership → **campaign cluster**  
**Edges:** shared IOC (typed), same pulse, semantic neighbor (validated)  
**Annotations:** MITRE overlap %, KEV, ransomware, stack match, temporal vendor, EPSS delta

---

## 6. Signal model (all sources)

### 6.1 OTX-native (primary)

| Signal | Source | Role |
|--------|--------|------|
| **Pulse co-occurrence** | `otx_cve_pulses` | Two+ CVEs in same `pulse_id` → same campaign cluster |
| **Pulse metadata** | pulse row | name, author, created_date, adversary, malware_families, tags, targeted_countries |
| **Shared domain** | `otx_pulse_iocs` | Strong IOC edge |
| **Shared hash** | `otx_pulse_iocs` | Strongest IOC edge |
| **Shared URL** | `otx_pulse_iocs` | Medium edge |
| **Shared IP** | `otx_pulse_iocs` | Weaker edge; downrank RFC1918/CDN patterns where detectable |
| **IOC → CVE pivot** | same tables as `lookup_ioc_in_otx` | Reverse path from IOC tab |

### 6.2 Local boosters (no OTX required)

| Signal | Source | Role |
|--------|--------|------|
| **KEV co-week** | `cves.is_kev`, KEV dates | Cluster bump; ransomware field |
| **Exploit tooling** | `cve_exploits`, exploit sync | Same ExploitDB/Metasploit/Nuclei/PoC family |
| **EPSS / change** | `epss_history`, `cve_change_history` | Synchronized jumps in cluster |
| **CWE family** | CVE CWE fields | Same weakness class + vendor week |
| **Package** | OSV enrichment on detail | Shared library (e.g. `vendor:product`) |
| **Semantic** | `cve_embeddings`, `/related` | Level 4 — neighbor validated by pulse/IOC when possible |
| **MITRE actor** | `cve_technique_map`, `mitre_groups` | Technique **overlap %**, top 3 groups — not “any technique” |
| **Temporal vendor** | improved baseline table | Stack-aware vendor spike + KEV/exploit compound |

### 6.3 Degraded mode (no `OTX_API_KEY`)

- Pulse/IOC levels empty with explicit `otx_status: "not_configured"`.
- Local boosters + semantic + MITRE + temporal (stack-gated) still run.
- UI: “Infrastructure correlation requires OTX” — not generic “no signals.”

---

## 7. Confidence and receipts

Every finding returns:

```json
{
  "summary": "Human one-liner for analysts",
  "confidence": "high|medium|low",
  "evidence": [
    {"type": "same_pulse", "pulse_id": "...", "pulse_name": "..."},
    {"type": "shared_indicator", "ioc_type": "domain", "value": "..."}
  ],
  "why_not_higher": "Optional string when capped",
  "sources": ["otx", "mitre", "kev"],
  "attribution_disclaimer": "OTX community pulse — unverified attribution"
}
```

**Deterministic rules** (implement in `correlation/confidence.py`):

| Condition | Typical confidence |
|-----------|-------------------|
| Same pulse + shared hash/domain | high |
| Same pulse only | medium–high |
| Shared hash/domain across pulses | medium–high |
| Shared IP only | low–medium |
| MITRE group overlap ≥50% techniques | medium |
| OTX adversary string only | low |
| KEV + cluster membership | bump +1 level (cap high) |
| Pulse age > 12 months | downgrade |
| No exploit/KEV signal on IP-only edge | downgrade |

---

## 8. Data model changes

### 8.1 Extend / normalize OTX storage

**Option A (preferred):** dimension table `otx_pulses` + keep `otx_cve_pulses` as link table.

| Table | Purpose |
|-------|---------|
| `otx_pulses` | pulse_id PK, name, author, created_date, adversary, malware_families JSON, tags JSON, targeted_countries JSON, ioc_count, fetched_at |
| `otx_cve_pulses` | cve_id + pulse_id (FK), fetched_at |
| `otx_pulse_iocs` | unchanged PK; add optional `pulse_id` index coverage |

Migrate: backfill `otx_pulses` from existing `otx_cve_pulses` rows on upgrade.

**Store `targeted_countries`** — already parsed in `_normalize_pulse`, currently dropped.

### 8.2 Campaign cluster tables (new)

| Table | Purpose |
|-------|---------|
| `correlation_campaigns` | campaign_id, primary_pulse_id (nullable), label, adversary, malware JSON, confidence, member_count, computed_at |
| `correlation_campaign_members` | campaign_id, cve_id, role (optional) |
| `correlation_campaign_edges` | campaign_id, edge_type, evidence JSON |

Retain v1 tables during migration; deprecate after read path uses campaigns.

### 8.3 Baseline / ops

| Table | Purpose |
|-------|---------|
| `correlation_vendor_weekly` | vendor, week_start, cve_count — proper temporal baseline |
| `sync_state` keys | `correlation_last_run`, `otx_ioc_backlog_count` |

### 8.4 Cache keys

- Bump: `correlation:v2:{cve_id}:{sector_hash}`  
- Invalidate all `correlation:v2:*` when `nightly_correlation` or OTX IOC sync completes (scheduler hook).

---

## 9. OTX ingest strategy

### 9.1 Unify jobs

Replace fragmented mental model with ordered pipeline in `nightly_correlation` (or single orchestrator):

1. **Sync pulses** for prioritized CVE set  
2. **Sync IOCs** for prioritized pulse set  
3. **Build campaigns** (clustering)  
4. **Run local boosters** annotation pass  
5. **Invalidate correlation cache**

Keep `otx_nightly_correlation` as alias or merge into step 1 — **one operator-facing job**, not two confusing locks.

### 9.2 CVE priority tiers

| Tier | Criteria | Pulse refresh |
|------|----------|---------------|
| P0 | KEV + on stack + watchlisted | Every run |
| P1 | High EPSS / has_poc / changed last 7d | Every run |
| P2 | Published last 30d | Daily |
| P3 | Backlog | Weekly cap |

Use existing: `filter_cves_matching_stack`, watchlist table, `get_recent_cve_ids_for_otx` (extend window/config).

### 9.3 Pulse IOC priority

| Tier | Criteria |
|------|----------|
| P0 | Pulse links ≥2 CVEs OR adversary/malware set |
| P1 | Pulses for P0 CVEs |
| P2 | Remaining — budget per run from env `OTX_IOC_SYNC_MAX_PER_RUN` (default **500**, not 100) |

Expose backlog in admin: `GET /api/admin/correlation/status` (phase 5).

### 9.4 Quota discipline

- `resilient_request` source `otx` — retries=0 on IOC bulk (existing pattern).
- Throttle between pulse IOC pages if API paginates.
- Record counts in job stats log line.

---

## 10. Engine modules (backend layout)

| Module | Responsibility |
|--------|----------------|
| `correlation/engine.py` | Orchestrator: `get_correlation_for_cve`, `run_nightly_correlation` |
| `correlation/pulses.py` | Pulse co-occurrence, cluster seeding |
| `correlation/ioc_graph.py` | Multi-IOC edges, Jaccard, noise filters |
| `correlation/local.py` | KEV, exploit, CWE, package, EPSS boosters |
| `correlation/mitre.py` | Technique overlap %, actor normalization |
| `correlation/temporal.py` | Vendor weekly baseline, stack-gated anomalies |
| `correlation/semantic.py` | Embeddings neighbors + validation |
| `correlation/confidence.py` | Receipt builder, deterministic levels |
| `correlation/campaigns.py` | Nightly connected-components / pulse grouping |
| `correlation/copy.py` | Analyst-facing summary strings (catalog) |

Keep files focused; extract from monolithic `engine.py` as phases land.

---

## 11. API changes

### 11.1 `GET /api/cves/{cve_id}/correlation` (v2 response)

**Backward compatible:** keep `infrastructure`, `actor`, `temporal` arrays in v2.0 PR with mapped content OR add `v=2` query param. Prefer **additive** fields first:

```json
{
  "cve_id": "CVE-2024-0001",
  "computed_at": "...",
  "otx_status": "ok|not_configured|degraded",
  "campaigns": [ { "campaign_id", "label", "members", "findings", "confidence", "evidence" } ],
  "infrastructure": [],
  "actor": [],
  "temporal": [],
  "semantic": [],
  "boosters": { "kev": [], "exploit": [] },
  "meta": { "cache_hit": false, "engine_version": "2.0" }
}
```

Update `API_REFERENCE.md` in same PR as response shape stabilizes.

### 11.2 Optional phase 4

`GET /api/correlation/clusters?stack=1&limit=20` — brief/feed consumer.

### 11.3 Admin phase 5

`GET /api/admin/correlation/status` — last run, campaigns count, OTX IOC coverage %, backlog.

---

## 12. UI / UX

### 12.1 Detail drawer (`CorrelationFindings`)

- **Campaign-first** layout: pulse name, members, shared indicators, adversary/malware/countries.
- Plain language (use `correlation/copy.py` or frontend catalog mirror).
- **Receipts** expandable: “Show evidence.”
- Link: pivot IOC, open correlated CVE, “Add cluster to investigation” (phase 3).
- Top-of-drawer chip when findings exist: “Linked to N other CVEs” (phase 3).
- Empty states:
  - `otx_status: not_configured` → explain OTX key
  - `no_signals` → “No campaign links found”
  - `warming` → “OTX sync in progress”

### 12.2 IOC Lookup

- Reuse same cluster data for `related_cves` — consistent labels.

### 12.3 Brief / feed (phase 3)

- Brief card: “Campaign: {label} — {n} CVEs on your stack”
- Feed row badge: `Campaign` when `member_of_campaign` on list API (optional lightweight join or nightly marker column on `cves`).

### 12.4 PDF (`pdfReport.js`)

- Campaign paragraph + disclaimer; not actor bullet dump only.

### 12.5 Admin (operator)

- Correlation status widget on Overview or dedicated Observability row.
- Link from analyst Intel status when `open_circuits`-style correlation issues exist.

Align copy with `docs/ADMIN_ANALYST_OPERATOR_MODE.md` analyst register.

---

## 13. Product integrations

| Consumer | Behavior | Phase |
|----------|----------|-------|
| **Risk score** | Small explainable bump when correlated peer is KEV or stack-matched high EPSS | 3 |
| **Morning brief** | Surface top 1–3 active campaigns affecting stack | 3 |
| **Investigation thread** | Suggest correlated CVEs; add cluster on action | 3 |
| **Watchlist** | Optional prompt: “Correlated to pinned CVE-XXXX” | 4 |
| **Webhooks** | KEV-on-stack message includes campaign label if member | 4 |
| **Wallboard** | Optional tile: active campaign count | 5 |
| **Forge** | `detection_overlap` + hunt scope for cluster techniques | 4 |

Risk bump must remain **explainable** in risk breakdown text — no silent weight.

---

## 14. MITRE / actor v2

Replace “group uses any technique” with:

1. Load technique IDs for CVE.  
2. For each candidate group, compute `overlap = |CVE∩Group| / |CVE|`.  
3. Return top 3 groups where `overlap ≥ 0.25`.  
4. Merge OTX `adversary` via alias table (`correlation/actor_aliases.json` or DB table) → MITRE group when match ≥ fuzzy threshold.  
5. Sector match: use asset profile `environment.industry` + synonym map (extend `SECTOR_KEYWORDS`).

---

## 15. Temporal v2

1. Nightly: write `correlation_vendor_weekly` from CVE publish dates.  
2. Anomaly when current week / rolling avg ≥ threshold (config `CORRELATION_VENDOR_ANOMALY_RATIO`, default 3.0).  
3. **Gate:** only surface to analyst if vendor ∈ stack OR cluster has KEV/exploit booster.  
4. Per-CVE: attach vendor anomalies only for CVE’s vendors.

---

## 16. Semantic layer (Level 4)

1. Call existing embedding neighbor logic (do not re-embed on request path).  
2. For each neighbor, **validate**: same campaign OR shared IOC OR same CWE family.  
3. If validation fails, list under `semantic_unvalidated` with lower confidence or omit.  
4. Do not merge into risk score until validated neighbor.

---

## 17. Testing strategy

Create `backend/tests/test_correlation.py` + fixtures:

| Test | Covers |
|------|--------|
| Pulse co-occurrence → one campaign | Core OTX |
| Two pulses, shared hash links campaigns | IOC graph |
| IP-only edge downranked | Confidence |
| MITRE overlap ranking | Actor noise reduction |
| Temporal gated off stack | Product rule |
| No OTX key → `otx_status` + local only | Degraded |
| Cache invalidation on job complete | Staleness |
| IOC lookup + correlation same CVE set | Unified graph |

Use in-memory SQLite with seed rows in `tests/fixtures/correlation/`.

---

## 18. Implementation phases

### Phase 1 — Foundation (OTX data + pulse clusters)

- [ ] `otx_pulses` dimension + migrate `targeted_countries`
- [ ] Prioritized CVE/pulse IOC sync; raise IOC budget; merge job clarity
- [ ] `correlation/campaigns.py` nightly pulse clustering
- [ ] `correlation_campaigns` + members tables
- [ ] Read campaigns in `get_correlation_for_cve`; v2 cache key
- [ ] Tests for pulse clustering
- [ ] Invalidate cache after nightly job

**Exit:** Drawer shows pulse-centric campaign for CVEs with OTX data.

### Phase 2 — IOC graph + confidence + multi-IOC

- [ ] `ioc_graph.py` domain/hash/URL edges, Jaccard, noise filter
- [ ] `confidence.py` + evidence arrays
- [ ] Unified IOC lookup table usage
- [ ] Analyst copy catalog (backend or shared)
- [ ] Redesigned `CorrelationFindings` UI
- [ ] `API_REFERENCE.md` update

**Exit:** Findings have receipts; multi-IOC works; IOC tab agrees with drawer.

### Phase 3 — Local boosters + product wiring

- [ ] `local.py` KEV/exploit/CWE/package boosters on campaigns
- [ ] MITRE overlap refactor
- [ ] Temporal v2 + vendor weekly table
- [ ] Semantic validated neighbors
- [ ] Brief card + feed badge (minimal)
- [ ] Investigation thread suggestions
- [ ] Explainable risk bump
- [ ] Drawer top chip

**Exit:** Correlation changes what analysts see without opening Intel tab last.

### Phase 4 — Depth

- [ ] `GET /api/correlation/clusters`
- [ ] Watchlist correlation hints
- [ ] Forge/detection overlap for cluster
- [ ] PDF campaign section
- [ ] Webhook message enrichment

### Phase 5 — Ops

- [ ] `GET /api/admin/correlation/status`
- [ ] Metrics: hit rate, empty rate (log or admin)
- [ ] Deprecate v1 table write path if redundant
- [ ] `SYSTEM_DESIGN.md` + `TECHNICAL_INVENTORY.md` update

---

## 19. Configuration (env / admin schema)

Add to `config_schema.py` when implementing (admin-tunable):

| Key | Default | Purpose |
|-----|---------|---------|
| `OTX_IOC_SYNC_MAX_PER_RUN` | 500 | Pulse IOC download budget |
| `OTX_CVE_SYNC_DAYS` | 30 | CVE pulse refresh window |
| `CORRELATION_VENDOR_ANOMALY_RATIO` | 3.0 | Temporal threshold |
| `CORRELATION_CACHE_HOURS` | 6 | Request cache |
| `CORRELATION_MITRE_MIN_OVERLAP` | 0.25 | Actor filter |
| `CORRELATION_SEMANTIC_ENABLED` | 1 | Level 4 on/off |

Document in `.env.example` + `ONBOARDING.md`.

---

## 20. Files to touch (reference)

| Area | Files |
|------|-------|
| Engine | `backend/correlation/*.py` |
| OTX | `backend/feeds/otx.py`, `backend/database.py` |
| Scheduler | `backend/scheduler.py` |
| API | `backend/routers/cves.py`, optional `routers/admin.py` |
| IOC | `backend/enrichment/ioc.py` (if wired) |
| UI | `frontend/src/components/DetailDrawer.jsx`, `IOCLookup.jsx`, `MorningBrief.jsx`, `api.js` |
| Risk | `backend/scoring/risk.py`, `frontend/src/scoring/riskScore.js` |
| Brief | `backend/brief/service.py` |
| Tests | `backend/tests/test_correlation.py`, fixtures |
| Docs | `API_REFERENCE.md`, `SYSTEM_DESIGN.md`, `TECHNICAL_INVENTORY.md` |

---

## 21. Acceptance criteria (v2 complete)

- [ ] Pulse co-occurrence drives campaign clusters; not IP-only headline
- [ ] Domain/hash/URL edges implemented; IP downranked appropriately
- [ ] OTX prioritized ingest with visible backlog metric (admin)
- [ ] IOC lookup and correlation return consistent related CVE sets
- [ ] Every finding includes `evidence` + analyst `summary`
- [ ] Degraded mode without OTX is explicit and still useful (local boosters)
- [ ] Brief or feed surfaces at least one campaign signal without opening drawer
- [ ] Risk or investigation integration shipped (at least one)
- [ ] Cache invalidates after nightly correlation
- [ ] `test_correlation.py` ≥ 15 tests, CI green
- [ ] No new request-time OTX HTTP calls on drawer open

---

## 22. Claude Code prompt (short)

```text
Implement BRIEFR Correlation v2 per docs/CORRELATION_V2_PLAN.md.

Read the plan end-to-end, then engine.py, feeds/otx.py, DetailDrawer CorrelationFindings.

Start Phase 1 only unless instructed otherwise. One PR per phase.
OTX is the spine; include local boosters and product wiring in later phases per plan.
Explainable evidence only — no black-box scores.
Run pytest and npm build before push.
```

---

## 23. Open decisions (defaults chosen)

| Question | Decision |
|----------|----------|
| Break API or additive fields? | **Additive** `campaigns` + `meta` first; deprecate v1 shape later |
| Keep v1 `correlation_infrastructure` table? | **Write during migration**; switch read to campaigns; drop in phase 5 |
| Campaign ID format? | `camp_{sha256(pulse_id)[:12]}` for pulse-rooted; merge hash for IOC-only |
| Groq for correlation? | **No** — scheduler ML stays product extraction only |

---

*End of plan. Implement Phase 1 → 2 → 3 in order.*
