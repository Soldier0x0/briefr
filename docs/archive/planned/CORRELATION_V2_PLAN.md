# BRIEFR Correlation Engine v2 — Implementation Plan

> **⚠️ SUPERSEDED (2026-07-09) BY:**
> [`docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md`](../../BRIEFR_ARCHITECTURE_REVIEW_2026-07.md) **§3.**
> This plan's "current state (v1)" framing is **materially outdated**: the code
> is at ~phase 3 (phases 1–2 shipped, phase 3 partial). Campaigns, typed IOC
> edges, hub suppression, IOC normalization, enrichment confirmation, analyst
> dismiss/restore, MITRE overlap %, temporal, and a correlation priority score
> are all **implemented**. Do **not** treat the phase checklists below as the
> open backlog. The remaining valuable work is three small PRs (lifecycle
> computation, feed campaign badge, drawer chip + investigation pivot); phases
> 4–5 are **parked**; a generic graph / Neo4j / `correlation_campaign_edges`
> persistence is on the **do-not-build** list. This file is retained for
> historical design context only.

**Status:** ~~Implementation spec (ready for Claude Code / human implementers)~~ **SUPERSEDED — historical**  
**Last updated:** 2026-06-20  
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
8. **Trustworthy:** Hub/noise suppression, enrichment confirmation, analyst dismiss feedback, and one coherent “related” story in the UI (see §24).

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
| **Exploit tooling** | `cve_exploits`, exploit sync | Same ExploitDB ID, Metasploit module, Nuclei template, or GitHub PoC repo (`source_urls`) |
| **Co-exploitation window** | KEV dates, `epss_history`, `cve_change_history` | Members with synchronized exploitation signals within N days |
| **EPSS / change** | `epss_history`, `cve_change_history` | Synchronized jumps in cluster |
| **CWE family** | CVE CWE fields | Same weakness class + vendor week |
| **Package** | OSV enrichment on detail | Shared library (e.g. `vendor:product`) |
| **Semantic** | `cve_embeddings`, `/related` | Level 4 — neighbor validated by pulse/IOC when possible |
| **MITRE actor** | `cve_technique_map`, `mitre_groups` | Technique **overlap %**, top 3 groups — not “any technique” |
| **Temporal vendor** | improved baseline table | Stack-aware vendor spike + KEV/exploit compound |

### 6.3 Enrichment confirmation (existing IOC sources)

Use data BRIEFR already fetches — **scheduler-side or cached only**, never new per-drawer HTTP:

| Confirmation | Source | Effect on confidence |
|--------------|--------|----------------------|
| Shared IP + GreyNoise `malicious` | `feeds/extended.py` / IOC cache | IP edge bump (+1 level, cap high) |
| Shared IP + GreyNoise `benign` / riot | same | Downgrade or omit edge |
| Shared hash + MalwareBazaar hit | abuse.ch enrichment | Strong hash edge |
| Shared URL + URLhaus active | abuse.ch enrichment | Strong URL edge |

Implement in `correlation/confirm.py`; read from `ioc_cache` where available.

### 6.4 Degraded mode (no `OTX_API_KEY`)

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
  "attribution_disclaimer": "OTX community pulse — unverified attribution",
  "attribution_conflict": false,
  "lifecycle": "emerging|active|declining|stale"
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
| GreyNoise malicious on shared IP | bump +1 (cap high) |
| GreyNoise benign/riot on shared IP | downgrade or omit |
| Hub CVE / mega-pulse edge (§24.1) | downgrade or cap cluster growth |
| OTX adversary ≠ MITRE top group | `attribution_conflict: true`, lower confidence |

---

## 8. Data model changes

### 8.1 Extend / normalize OTX storage

**Option A (preferred):** dimension table `otx_pulses` + keep `otx_cve_pulses` as link table.

| Table | Purpose |
|-------|---------|
| `otx_pulses` | pulse_id PK, name, author, created_date, adversary, malware_families JSON, tags JSON, targeted_countries JSON, ioc_count, fetched_at |
| `otx_cve_pulses` | cve_id + pulse_id (FK), fetched_at |
| `otx_pulse_iocs` | unchanged PK; store **canonical** `ioc_value` + normalized `ioc_type`; index `(ioc_value, ioc_type)` |

Migrate: backfill `otx_pulses` from existing `otx_cve_pulses` rows on upgrade. Run IOC canonicalization pass on existing `otx_pulse_iocs` rows (§24.2).

**Store `targeted_countries`** — already parsed in `_normalize_pulse`, currently dropped.

### 8.2 Campaign cluster tables (new)

| Table | Purpose |
|-------|---------|
| `correlation_campaigns` | campaign_id, primary_pulse_id (nullable), label, adversary, malware JSON, confidence, member_count, **lifecycle**, **campaign_version**, computed_at |
| `correlation_campaign_members` | campaign_id, cve_id, role (optional) |
| `correlation_campaign_edges` | campaign_id, cve_id_a, cve_id_b, edge_type, evidence JSON |
| `correlation_suppressions` | id, scope (`edge`/`campaign`/`pulse`/`cve_pair`), key JSON, reason, created_at — analyst dismiss feedback (§24.5) |

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
| `correlation/ioc_normalize.py` | Canonical IOC types/values at ingest (§24.2) |
| `correlation/hub_suppress.py` | Hub CVE / mega-pulse downranking (§24.1) |
| `correlation/confirm.py` | GreyNoise / abuse.ch confirmation from cache |
| `correlation/local.py` | KEV, exploit, CWE, package, EPSS, co-exploitation timing boosters |
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
  "campaigns": [
    {
      "campaign_id": "camp_abc123",
      "label": "Ransomware wave Q1",
      "members": ["CVE-2024-0001", "CVE-2024-0002"],
      "confidence": "medium",
      "evidence": [{ "type": "same_pulse", "pulse_id": "..." }]
    }
  ],
  "infrastructure": [],
  "actor": [],
  "temporal": [],
  "semantic": [],
  "boosters": { "kev": [], "exploit": [] },
  "meta": { "cache_hit": false, "engine_version": "2.0" }
}
```

Update `API_REFERENCE.md` in same PR as response shape stabilizes.

### 11.2 Analyst suppress (Phase 2)

`POST /api/cves/{cve_id}/correlation/suppress`

```json
{
  "scope": "cve_pair|pulse_id|campaign_id|ioc_edge",
  "key": { "cve_id_b": "CVE-..." },
  "reason": "optional analyst note"
}
```

`DELETE` same path with scope/key to undo (or operator reset in admin Phase 5).

### 11.3 Optional phase 4

`GET /api/correlation/clusters?stack=1&limit=20` — brief/feed consumer.

### 11.3 Admin phase 5

`GET /api/admin/correlation/status` — last run, campaigns count, OTX IOC coverage %, backlog.

---

## 12. UI / UX

### 12.1 Detail drawer (`CorrelationFindings`)

- **Campaign-first** layout: pulse name, members, shared indicators, adversary/malware/countries.
- Plain language (use `correlation/copy.py` or frontend catalog mirror).
- **Receipts** expandable: “Show evidence.”
- **Dismiss** action: “Not related” per finding/campaign → writes `correlation_suppressions` (§24.5).
- **Attribution conflict** banner when OTX adversary ≠ MITRE group (§24.6).
- Link: pivot IOC, open correlated CVE, “Add cluster to investigation” (phase 3).
- Top-of-drawer chip when findings exist: “Linked to N other CVEs” (phase 3).
- Empty states:
  - `otx_status: not_configured` → explain OTX key
  - `no_signals` → “No campaign links found”
  - `warming` → “OTX sync in progress”

### 12.2 Related CVE lanes (unified UX contract)

The drawer currently shows three unrelated “related” concepts. v2 must make them **coherent** (§24.4):

| Lane | API | UI label |
|------|-----|----------|
| Campaign | `/correlation` → `campaigns` | “Campaign link” |
| Same product | `/related` (`product_heuristic`) | “Same product family” |
| Semantic | `/related` (`embeddings`) | “Similar description” |
| IOC pivot | IOC lookup `related_cves` | “Same pulse / indicator” |

Rules:
- Never show the same CVE twice without explaining **why** (badge per lane).
- Correlation members rank above semantic neighbors in default sort.
- Cross-link: “Also related via same product” under campaign members when applicable.

### 12.3 IOC Lookup

- Reuse same cluster data for `related_cves` — consistent labels.

### 12.4 Brief / feed (phase 3)

- Brief card: “Campaign: {label} — {n} CVEs on your stack”
- Feed row badge: `Campaign` when `member_of_campaign` on list API (optional lightweight join or nightly marker column on `cves`).

### 12.5 PDF (`pdfReport.js`)

- Campaign paragraph + disclaimer; not actor bullet dump only.

### 12.6 Admin (operator)

- Correlation status widget on Overview or dedicated Observability row.
- Link from analyst Intel status when `open_circuits`-style correlation issues exist.

Align copy with `docs/ADMIN_ANALYST_OPERATOR_MODE.md` analyst register.

---

## 13. Product integrations

| Consumer | Behavior | Phase |
|----------|----------|-------|
| **Risk score** | Small explainable bump when correlated peer is KEV or stack-matched high EPSS | 3 |
| **Morning brief** | Surface top 1–3 **active** campaigns affecting stack (lifecycle filter) | 3 |
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
2. Anomaly when current week count / **rolling N-week average** ≥ threshold (`CORRELATION_VENDOR_ANOMALY_RATIO`, default 3.0; baseline window `CORRELATION_VENDOR_BASELINE_WEEKS`, default 8).  
3. **Gate:** only surface to analyst if vendor ∈ stack OR cluster has KEV/exploit booster.  
4. Per-CVE: attach vendor anomalies only for CVE’s vendors.

### 15.1 Co-exploitation timing (local booster)

Independent of vendor volume — detect **synchronized exploitation windows** across cluster members:

| Signal | Window | Source |
|--------|--------|--------|
| KEV `date_added` alignment | configurable (default 14d) | `kev_deadlines` |
| EPSS jump | same window | `epss_history` |
| `has_poc` / exploit first seen | same window | `cve_exploits`, `cves` |
| CVSS/EPSS change | same window | `cve_change_history` |

Surface as booster receipt: “3 CVEs in this cluster saw exploitation signals within 10 days.”

---

## 16. Semantic layer (Level 4)

1. Call existing embedding neighbor logic (do not re-embed on request path).  
2. For each neighbor, **validate**: same campaign OR shared IOC OR same CWE family.  
   CWE-only validation requires a **specific** child CWE (not a top-level bucket) and rejects known-generic parents (e.g. CWE-20, CWE-77, CWE-119, CWE-200) unless vendor/product also overlap.  
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
| Hub CVE does not blow up cluster | §24.1 noise control |
| GreyNoise benign downgrades shared IP edge | §24.3 confirmation |
| Analyst suppression hides edge on rebuild | §24.5 feedback |
| OTX vs MITRE attribution conflict flagged | §24.6 trust |
| Related vs correlation lane labels distinct | §24.4 UX |
| Rejected CVE pruned from cluster | Data hygiene |
| Stable campaign ordering across runs | Determinism |
| Cached correlation API < 200ms p95 | Performance budget |

Use in-memory SQLite with seed rows in `tests/fixtures/correlation/`. Target **≥ 20 tests** at v2 complete (was 15; quality cases add 5+).

---

## 18. Implementation phases

Phases 1–2 **must** include quality controls from §24 — not deferred to ops.

### Phase 1 — Foundation (OTX data + pulse clusters)

- [ ] `otx_pulses` dimension + migrate `targeted_countries`
- [ ] `correlation/ioc_normalize.py` — canonical IOC types/values at ingest (§24.2)
- [ ] Prioritized CVE/pulse IOC sync; raise IOC budget; merge job clarity
- [ ] `correlation/hub_suppress.py` — hub CVE / mega-pulse caps in clustering (§24.1)
- [ ] `correlation/campaigns.py` nightly pulse clustering + **incremental** member updates
- [ ] `correlation_campaigns` + members tables (include `lifecycle`, `campaign_version`)
- [ ] Prune rejected/non-existent CVE IDs from clusters after NVD sync
- [ ] Read campaigns in `get_correlation_for_cve`; v2 cache key
- [ ] Tests: pulse clustering + hub suppression fixture
- [ ] Invalidate cache after nightly job

**Exit:** Drawer shows pulse-centric campaign for CVEs with OTX data. Hub CVE does not create spurious mega-clusters in test fixture.

### Phase 2 — IOC graph + confidence + multi-IOC + trust

- [ ] `ioc_graph.py` domain/hash/URL edges, Jaccard, noise filter
- [ ] `confidence.py` + evidence arrays (incl. `attribution_conflict`, `lifecycle`)
- [ ] `confirm.py` — GreyNoise / abuse.ch confirmation from `ioc_cache` (§24.3)
- [ ] `correlation_suppressions` table + dismiss API + UI action (§24.5)
- [ ] Unified IOC lookup table usage
- [ ] Related-lane UX contract in drawer (§24.4) — labels, no silent duplicates
- [ ] Analyst copy catalog (backend or shared); sanitize OTX pulse strings for display
- [ ] Redesigned `CorrelationFindings` UI
- [ ] `API_REFERENCE.md` update

**Exit:** Findings have receipts; multi-IOC works; IOC tab agrees with drawer; analyst can dismiss bad edges; benign GreyNoise IPs downranked.

### Phase 3 — Local boosters + product wiring

- [ ] `local.py` KEV/exploit/CWE/package boosters on campaigns
- [ ] Co-exploitation timing booster (§15.1)
- [ ] CISA KEV cluster annotations (`known_ransomware`, shared `vendor_project`, due dates)
- [ ] MITRE overlap refactor + attribution conflict policy (§24.6)
- [ ] Temporal v2 + vendor weekly table
- [ ] Semantic validated neighbors
- [ ] Incident/news fuzzy match to campaign label (receipt-backed, optional)
- [ ] Stack-first default sort for all campaign findings (§24.7)
- [ ] Brief card + feed badge (minimal) — **active** campaigns only
- [ ] Investigation thread suggestions
- [ ] Explainable risk bump
- [ ] Drawer top chip

**Exit:** Correlation changes what analysts see without opening Intel tab last. Stack-matched campaigns rank first.

### Phase 4 — Depth

- [ ] `GET /api/correlation/clusters`
- [ ] Watchlist correlation hints (prioritize watchlisted peers in sort)
- [ ] Forge/detection overlap for cluster
- [ ] PDF campaign section + OTX pulse citation links
- [ ] Webhook message enrichment
- [ ] Atlas case-study narrative booster (2+ cluster CVEs in same study)

### Phase 5 — Ops

- [ ] `GET /api/admin/correlation/status`
- [ ] Metrics: hit rate, empty rate, dismiss rate, top noisy pulses (§24.8)
- [ ] Operator reset for `correlation_suppressions`
- [ ] Deprecate v1 table write path if redundant
- [ ] Performance indexes verified; cached API p95 < 200ms
- [ ] `SYSTEM_DESIGN.md` + `TECHNICAL_INVENTORY.md` update

---

## 19. Configuration (env / admin schema)

Add to `config_schema.py` when implementing (admin-tunable):

| Key | Default | Purpose |
|-----|---------|---------|
| `OTX_IOC_SYNC_MAX_PER_RUN` | 500 | Pulse IOC download budget |
| `OTX_CVE_SYNC_DAYS` | 30 | CVE pulse refresh window |
| `CORRELATION_VENDOR_ANOMALY_RATIO` | 3.0 | Temporal threshold |
| `CORRELATION_VENDOR_BASELINE_WEEKS` | 8 | Rolling average window for vendor weekly baseline (§15) |
| `CORRELATION_CACHE_HOURS` | 6 | Request cache |
| `CORRELATION_MITRE_MIN_OVERLAP` | 0.25 | Actor filter |
| `CORRELATION_SEMANTIC_ENABLED` | 1 | Level 4 on/off |
| `CORRELATION_HUB_CVE_PULSE_CAP` | 50 | Pulses per CVE before hub downrank (§24.1) |
| `CORRELATION_MAX_CAMPAIGN_MEMBERS` | 25 | Hard cap per campaign in API response |
| `CORRELATION_COEXPLOIT_WINDOW_DAYS` | 14 | Co-exploitation timing window (§15.1) |
| `CORRELATION_CONFIRM_ENABLED` | 1 | GreyNoise/abuse.ch confirmation layer |

Document in `.env.example` + `ONBOARDING.md`.

---

## 20. Files to touch (reference)

| Area | Files |
|------|-------|
| Engine | `backend/correlation/*.py` |
| OTX | `backend/feeds/otx.py`, `backend/database.py` |
| Scheduler | `backend/scheduler.py` |
| API | `backend/routers/cves.py`, optional `routers/admin.py` |
| IOC | `backend/enrichment/ioc.py`, `backend/feeds/extended.py` |
| UI | `frontend/src/components/DetailDrawer.jsx`, `IOCLookup.jsx`, `MorningBrief.jsx`, `api.js` |
| Risk | `backend/scoring/risk.py`, `frontend/src/scoring/riskScore.js` |
| Brief | `backend/brief/service.py` |
| Tests | `backend/tests/test_correlation.py`, fixtures |
| Docs | `API_REFERENCE.md`, `SYSTEM_DESIGN.md`, `TECHNICAL_INVENTORY.md` |

---

## 21. Acceptance criteria (v2 complete)

- [ ] Pulse co-occurrence drives campaign clusters; not IP-only headline
- [ ] Domain/hash/URL edges implemented; IP downranked appropriately
- [ ] Hub CVE / mega-pulse suppression prevents spurious mega-clusters (§24.1)
- [ ] IOC normalization at ingest; type drift (`IP`/`IPv4`) handled (§24.2)
- [ ] GreyNoise / abuse.ch confirmation adjusts confidence (§24.3)
- [ ] Analyst dismiss persists and suppresses edges on rebuild (§24.5)
- [ ] Related lanes in drawer are labeled and non-contradictory (§24.4)
- [ ] Attribution conflicts surfaced, not merged silently (§24.6)
- [ ] Stack-first sort for campaign findings (§24.7)
- [ ] OTX prioritized ingest with visible backlog metric (admin)
- [ ] IOC lookup and correlation return consistent related CVE sets
- [ ] Every finding includes `evidence` + analyst `summary`
- [ ] Degraded mode without OTX is explicit and still useful (local boosters)
- [ ] Brief or feed surfaces at least one **active** campaign without opening drawer
- [ ] Risk or investigation integration shipped (at least one)
- [ ] Cache invalidates after nightly correlation
- [ ] `test_correlation.py` ≥ 20 tests, CI green
- [ ] Cached correlation API p95 < 200ms
- [ ] No new request-time OTX HTTP calls on drawer open
- [ ] OTX pulse/adversary strings sanitized before UI/PDF render

---

## 22. Claude Code prompt (short)

```text
Implement BRIEFR Correlation v2 per docs/CORRELATION_V2_PLAN.md.

Read the plan end-to-end, then engine.py, feeds/otx.py, DetailDrawer CorrelationFindings.

Start Phase 1 only unless instructed otherwise. One PR per phase.
OTX is the spine; include local boosters and product wiring in later phases per plan.
Phase 1–2 must ship §24 quality controls (hub suppression, IOC normalize, confirmation, dismiss).
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
| Multi-hop edges shown? | **1-hop default**; 2-hop only with receipts + lower confidence (§24.9) |
| Analyst dismiss storage? | **`correlation_suppressions` table**; operator can reset in admin |

---

## 24. Quality & trust controls

This section is **required**, not optional polish. OTX-maximal correlation without these controls produces noise analysts will ignore.

### 24.1 Hub CVE and mega-pulse suppression

**Problem:** High-visibility CVEs (e.g. Log4Shell) appear in hundreds of OTX pulses and glue unrelated CVEs into false campaigns.

**Rules:**
1. Track `pulse_count_per_cve` and `member_count_per_pulse` at build time.
2. When a CVE exceeds `CORRELATION_HUB_CVE_PULSE_CAP` (default 50), downrank edges **through** that CVE — do not let it expand clusters via weak IOC overlap alone.
3. Cap campaign growth: max `CORRELATION_MAX_CAMPAIGN_MEMBERS` (default 25) in API response; paginate or summarize overflow.
4. Apply inverse-frequency weight: edges via rarely-shared pulses score higher than edges via ubiquitous pulses.
5. **Test fixture required:** one hub CVE must not create a 20+ member campaign from a single shared CDN IP.

Implement in `correlation/hub_suppress.py`; call from `campaigns.py` and `ioc_graph.py`.

### 24.2 IOC normalization pipeline

**Problem:** Type drift (`IP` vs `IPv4`), defanged values, and URL variance create duplicate or false edges.

**At ingest** (`correlation/ioc_normalize.py`, called from `store_otx_pulse_iocs`):
| Step | Rule |
|------|------|
| Type canonicalization | Map `IP`, `IPV4`, `IPV6` → consistent enum |
| Defang refang | `hxxp`, `[.]`, `[:] ` → normal form before storage |
| Hash case | Lowercase hex |
| Domain | Lowercase, punycode where applicable |
| URL | Normalize scheme/host; optional path trim policy |
| Noise ranges | Flag RFC1918, link-local, known CDN resolver patterns for downrank (not delete) |

Store canonical value in `otx_pulse_iocs.ioc_value`; keep raw optional in evidence JSON for receipts.

### 24.3 Enrichment confirmation layer

**Problem:** “Shared IP” from OTX alone is weak; BRIEFR already has GreyNoise and abuse.ch data.

**Rules** (see §6.3):
- Read from `ioc_cache` / scheduler-precomputed enrichment — **no new HTTP on drawer open**.
- Shared IP + GreyNoise `malicious` → confidence bump.
- Shared IP + GreyNoise `benign` / riot → downgrade or omit from findings (still in evidence if operator mode).
- Shared hash + MalwareBazaar → strong edge confirmation.
- Shared URL + URLhaus active → strong edge confirmation.

If confirmation data is stale/missing, finding stands on OTX evidence alone with `why_not_higher: "No enrichment confirmation available"`.

### 24.4 Unified “related CVE” lanes (drawer contract)

**Problem:** `/related`, `/correlation`, and IOC `related_cves` can disagree in the same drawer.

**Contract:**
1. Each lane has a **fixed label** (see §12.2 table).
2. Default sort: campaign > stack-matched > KEV > watchlisted > other.
3. Same CVE in multiple lanes → show once in primary lane, cross-reference in secondary (“Also: similar description”).
4. IOC lookup `related_cves` must use the same campaign tables as `/correlation` after Phase 2.

### 24.5 Analyst dismiss / suppress feedback

**Problem:** One bad OTX pulse poisons the experience indefinitely.

**Implementation:**
- UI: “Not related” on finding or whole campaign.
- `POST /api/cves/{cve_id}/correlation/suppress` (or nested under correlation router) writes `correlation_suppressions`.
- Scopes: `cve_pair`, `pulse_id`, `campaign_id`, `ioc_edge` (type + value).
- Nightly rebuild **respects** suppressions.
- Admin: operator can list/reset suppressions (Phase 5).
- Optional: log dismiss events for noisy-pulse metrics (§24.8).

### 24.6 Attribution conflict policy

**Problem:** OTX adversary strings often disagree with MITRE groups.

**Rules:**
1. Never merge OTX adversary and MITRE group into one actor name silently.
2. Set `attribution_conflict: true` when top MITRE group (overlap ≥ threshold) ≠ normalized OTX adversary.
3. UI shows both with disclaimer; confidence capped at `medium`.
4. Infrastructure findings (shared IOC) do not imply attribution — separate receipts.
5. Prefer MITRE for technique-backed claims; OTX for community campaign labels only.

### 24.7 Stack-first ranking

**Problem:** Correlation that ignores the operator’s stack feels academic.

**Default sort** for campaign members and cluster list:
1. On stack (`filter_cves_matching_stack`)
2. Watchlisted
3. KEV
4. High EPSS (≥ 0.5) or `has_poc`
5. Confidence level
6. Recency (campaign `lifecycle` = emerging/active first)

Apply in API response ordering and brief/feed selection.

### 24.8 Observability (quality metrics)

Beyond admin “last run” status, track:
| Metric | Use |
|--------|-----|
| % CVEs with ≥1 campaign | Coverage health |
| Avg members per campaign | Detect hub blowups |
| Dismiss rate per pulse_id | Identify noisy pulses |
| % findings with confirmation | Enrichment value |
| Cached API latency p95 | Performance regression |

Expose in `GET /api/admin/correlation/status` (Phase 5).

### 24.9 Multi-hop policy

- **Default:** 1-hop only (direct campaign member or direct IOC edge).
- **2-hop** (A↔B↔C): allowed only when both hops have receipts; confidence capped at `low`; omitted from brief/webhooks.
- No unbounded transitive closure.

### 24.10 Campaign lifecycle

Nightly compute `lifecycle` on `correlation_campaigns`:

| State | Criteria |
|-------|----------|
| `emerging` | New member added in last 7d |
| `active` | Member with KEV, exploit, or EPSS jump in last 14d |
| `declining` | No activity 30d+ |
| `stale` | Pulse age > 12 months AND no local boosters |

Brief, feed badges, and webhooks prefer `emerging` / `active`. Drawer may show `stale` collapsed by default.

### 24.11 Incremental rebuild and determinism

- Campaign build updates only pulses/CVEs/IOCs changed since last run (track watermark in `sync_state`).
- Bump `campaign_version` when algorithm changes.
- Stable tie-break: sort by `cve_id` ASC, then `confidence` DESC.
- Rejected CVEs purged from members after NVD/cvelistV5 sync.

### 24.12 Display safety

OTX pulse names, adversary strings, and tags are user-generated. Sanitize (strip HTML, length cap) before UI and PDF. Never `dangerouslySetInnerHTML` pulse content.

---

*End of plan. Implement Phase 1 → 2 → 3 in order. Phase 1–2 must satisfy §24.*
