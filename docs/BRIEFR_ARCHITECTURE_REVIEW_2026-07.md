# BRIEFR Architecture Review — July 2026

**Type:** Principal security-product + software-architecture review (durable reasoning artifact)
**Author role:** frontier-reasoning session (see §11 AI-agent development model)
**Reviewed against:** `origin/main` @ `5423194` (through PR #344), code as source of truth
**Date:** 2026-07-09
**Status:** Authoritative reasoning record. Execution planning lives in
[`SPRINT_2026-07.md`](SPRINT_2026-07.md); shipped production truth lives in
[`PRODUCT_STATUS.md`](PRODUCT_STATUS.md). This document explains *why* the sprint
order, correlation direction, scoring direction, and production priorities were
chosen so future agents do not repeat this repository-wide investigation.

> **How to use this doc.** Read §1 (verdict) and §12 (execution graph) first. The
> deep per-subsystem reasoning (§3–§10) is reference — consult the relevant
> section before touching that subsystem. §14 is the priority stack and the
> do-not-build list.

---

## 1. Executive architecture verdict

BRIEFR is an **architecturally mature** self-hosted analyst intelligence pane. In
~30–40 build-days it reached a state most conventional teams would call late-beta:
a deterministic multi-source ingestion + enrichment + scoring + correlation +
detection pipeline behind a dark-terminal React UI, on a Postgres-required
runtime with real resilience primitives (circuit breakers, an outbound API queue,
per-source health) and a working deploy surface.

**Strongest product capabilities (preserve):**

- **Correlation engine (v2, deterministic).** Pulse-seeded campaign clustering
  with typed IOC edges, hub suppression, IOC normalization, enrichment
  confirmation, analyst dismiss/restore, MITRE technique-overlap %, and a
  correlation priority score. This is genuine, explainable intelligence — not a
  research toy. It is the single most under-marketed asset in the repo.
- **Risk Score v1.1b.** Deterministic, versioned, explainable, unit-tested,
  LLM-independent, mirrored backend↔frontend.
- **Detection compose pipeline.** Deterministic CWE/ATT&CK class router feeding
  Sigma / SIEM / log-patterns consistently, with a `DetectionContext` envelope
  and an optional (off-by-default) LLM overlay that cannot author raw rules.
- **Resilience + provenance plumbing.** `resilient_client` (per-source
  last_success / last_error / circuit state), `api_queue`, `_recover_db_transaction`
  for Postgres transaction-abort recovery, LLM `{provider, model}` provenance in
  `feed_cache`.

**Weakest architectural seams (the real backlog):**

1. **Scoring presentation, not scoring math.** Three deterministic scores exist —
   Risk v1.1b, Correlation Priority, and a *fused* Investigation Score — but the
   fused score is **orphaned** (backend route + `api.js` stub, no UI caller), and
   the analyst-facing headline blends "threat" and "environment relevance" into
   one number whose `0.5` asset placeholder (when no profile is loaded) means
   neither. This is the top **product-semantic** risk. (§4)
2. **Production upgrade safety.** `deploy/briefr-update.sh` has no Alembic step,
   its health check only warns, there is no rollback, and the intel smoke gate is
   warn-only by default. CI proves a backup *round-trip*; it does not prove a
   *production recovery procedure*. This is the top **production** risk. (§10)
3. **Correlation is shipped but under-surfaced.** A core capability barely changes
   analyst behavior because it lives mostly in one drawer tab: no feed-level
   campaign badge, `lifecycle` is hardcoded `"active"`, and correlation does not
   visibly feed risk or investigation. (§3)
4. **Enrichment absence is ambiguous at the analyst level.** The source layer can
   distinguish failed/rate-limited/not-configured; the CVE drawer cannot always
   distinguish "no data" from "enrichment pending" from "source down." (§5)

**What BRIEFR should optimize for next (in order):** (1) make a production upgrade
*trustworthy*; (2) make the shipped scoring + correlation intelligence *coherent
and visible* to the analyst; then (3) opportunistic UI-layer and performance
cleanup. Everything else (open-core, learning track, correlation phases 4–5,
STIX, Monitor alerts) stays parked. See §12 for the wave graph.

**One-line verdicts:**

| Subsystem | Verdict |
|-----------|---------|
| Correlation architecture | **INCREMENTALLY EVOLVE** (§3) |
| Risk scoring architecture | **PRESERVE MATH, FIX PRESENTATION via ADR — Option C in principle** (§4) |
| Intelligence freshness/provenance | Source-level good; **add a minimal per-CVE provenance line** (§5) |
| Scheduler / failure recovery | **PRESERVE**; APScheduler is sufficient — no Celery/Redis/Kafka (§6) |
| Investigation workflow | Evidence-collection + navigation; **wire the 3–5 high-value pivots, do not build case management** (§7) |
| Detection workflow | **PRESERVE**; deterministic and sound (§8) |
| Performance | **Evidence-first**; only gzip is a clear quick win, rest defer/measure (§9) |
| Production/recovery | **Top priority**; J1/J3 + restore runbook before any trusted upgrade (§10) |

---

## 2. Current product architecture map (factual, from code)

Stage-by-stage, with the primary modules, key tables, scheduled jobs, API routes,
and frontend consumers actually present on `main`.

### 2.1 External intelligence sources → ingestion → normalization → persistence

| Stage | Primary modules | Key tables | Scheduled jobs | Notes / limitations |
|-------|-----------------|-----------|----------------|---------------------|
| CVE core | `feeds/nvd.py`, `feeds/cvelistv5.py`, `feeds/vulnrichment.py` | `cves` (cvss, cwe_ids, affected_products, cpe_matches, source_urls, has_poc, is_kev, epss_*) | `nvd_incremental_sync`, `cvelistv5_incremental_sync`, `vulnrichment_snapshot_sync` | CVSS v4 ignored; only CISA-ADP container parsed (C1 audit) |
| KEV | `feeds/kev.py`, `db/*` | `kev_deadlines`, `cves.is_kev` | `kev_metadata_sync` | ransomware/CWE fields stored; some detail fields returned but unrendered |
| EPSS | `feeds/epss.py` | `cves.epss_score/percentile`, `epss_history` | `epss_score_sync` | consumed, never re-derived (correct) |
| Exploit indices | `scheduler`/`exploit_sync`, `feeds/nuclei_index.py`, `feeds/extended.py` | `cve_exploits` | `exploit_sources_sync` | ExploitDB/Metasploit/PoC-in-GitHub/Nuclei/Sploitus |
| OTX (correlation spine) | `feeds/otx.py`, `feeds/otx_continuous.py`, `correlation/ioc_normalize.py` | `otx_pulses`, `otx_cve_pulses`, `otx_pulse_iocs` | `otx_nightly_correlation`, `otx_continuous_sync` | IOC canonicalized at ingest |
| On-demand overlays | `feeds/extended.py` (CIRCL, Sploitus, GreyNoise), `feeds/osv.py` | `feed_cache`, `ioc_cache` | (request/on-demand) | GreyNoise on-demand only (E8), 50/wk free tier |
| MITRE | `feeds/mitre.py` | `mitre_groups`, `group_technique_map`, `cve_technique_map` | `weekly_mitre_refresh`, `atlas_version_check` | ATT&CK + ATLAS |
| Embeddings (optional) | `ml/*` | `cve_embeddings` | `embeddings_backfill` | env-gated, CPU-only, scheduler-side |

Persistence is PostgreSQL-required in production (`BRIEFR_REQUIRE_POSTGRES=1`);
the `db/` package is Postgres-native (Post-B), SQLite path retained for tests
only. All shared SQL uses `?` placeholders adapted by `db/pg_adapt.py` (danger
zone 1).

### 2.2 Enrichment → scoring → correlation → detection → investigation → UI

| Stage | Primary modules | Key tables/keys | Jobs | API routes | Frontend consumers |
|-------|-----------------|-----------------|------|-----------|--------------------|
| LLM enrichment | `ai/llm_router.py`, `detection/context_llm_sync.py` | `feed_cache` (`detection_ctx:*`, provenance) | `llm_product_extraction`, `detection_context_llm` (off default) | — | (indirect) |
| Scoring | `scoring/risk.py`, `scoring/asset_match.py`, `matching/cpe.py`, `scoring/investigation.py` | (computed) | — | `/api/cves/{id}/risk`, `/risk` inline, `/investigation_score` **(orphaned)** | `OverviewTab`, `riskScore.js` |
| Correlation | `correlation/*` (engine, campaigns, ioc_graph, confidence, priority, confirm, suppressions, local, hub_suppress, ioc_normalize), `db/correlation.py` | `correlation_campaigns`, `correlation_campaign_members`, `correlation_suppressions`, `correlation_actor`, `correlation_temporal` | `nightly_correlation`, `otx_nightly_correlation` | `/api/cves/{id}/correlation`, `/correlation/suppress[ions]` | `DetailDrawer/IntelTab.jsx`, `correlationPresentation.js` |
| Detection | `detection/class_router.py`, `sigma_generator.py`, `siem_queries.py`, `context*.py`, `nuclei_parser.py`, `rule_sources.py` | `feed_cache` (`detection_ctx:*`) | `detection_context_sync`, `detection_context_llm` | `/api/cves/{id}/detection` (Detect tab) | Detect tab, Forge |
| Investigation | `frontend InvestigationContext/Panel`, `observableExtraction.js`, PDF utils | (client state) | — | detail/related/IOC routes | `DetailDrawer`, `InvestigationPanel`, `IOCLookup` |
| Brief / feed | `brief/service.py`, `routers/cves.py` | (reads `cves`, `correlation_campaigns`) | (brief compose) | `/api/stats`, `/api/cves`, brief | `MorningBrief`, `CVEFeed`, `StatsRow` |
| Admin / ops | `routers/admin.py`, `routers/health.py`, `resilient_client.py`, `api_queue.py` | `audit_log`, `api_usage`, sync_state | many | `/api/admin/*`, `/api/health` | Admin pages, Wallboard |

**Known cross-cutting limitations:** (a) three scores, one orphaned (§4);
(b) correlation not surfaced outside the drawer + brief (§3); (c) `lifecycle`
hardcoded `"active"`; (d) `correlation_infrastructure` is dead schema (no
writers/readers — drop in a future migration); (e) per-CVE enrichment provenance
is thin (§5).

---

## 3. Correlation architecture review

### 3.1 Factual pipeline (as implemented, not as planned)

```
INPUTS      OTX pulses/IOCs (otx_*), cve_technique_map + mitre_groups,
            cves (is_kev/has_poc/affected_products/published), ioc_cache (GreyNoise/abuse.ch)
   │
NORMALIZE   correlation/ioc_normalize.py — canonical type (IP/DOMAIN/URL/HASH),
            defang/refang, hash lowercase, domain/url canonicalization, noise-IP flag
   │
MATCH/LINK  campaigns.build_campaigns_from_pulses (nightly): one campaign per pulse
            linking ≥2 CVEs → correlation_campaigns + _members.
            get_campaigns_for_cve (on-demand): expands with strong-IOC peers
            (hash/domain) via ioc_graph, applies hub_suppress.filter_campaign_members.
            ioc_graph.find_shared_infrastructure_v2 (on-demand): typed shared-IOC peers.
            engine.find_actor_sector_correlation: MITRE technique-overlap % + OTX adversary.
            engine.find_temporal_anomalies (nightly): vendor weekly-volume spikes.
   │
EVIDENCE    per finding: evidence[] (same_pulse / shared_indicator / kev_booster /
            exploit_booster / enrichment_confirmation), summary, sources, why_not_higher,
            attribution_conflict, attribution_disclaimer
   │
CONFIDENCE  confidence.py — deterministic, relationship-type-specific:
            HASH=high, DOMAIN/URL=medium, IP=low; bump on GreyNoise malicious /
            MalwareBazaar / URLhaus / KEV+exploit boosters; downrank on noise-IP /
            GreyNoise benign; campaign base from member count (_confidence_for_pulse)
   │
PERSIST     correlation_campaigns / _members / _suppressions / _actor / _temporal;
            6h feed_cache key correlation:v2:{cve}:{sector}; invalidated on nightly
   │
API         GET /api/cves/{id}/correlation (campaigns, infrastructure, actor, temporal,
            boosters, priority, otx_status); POST/DELETE .../correlation/suppress[ions]
   │
UI          DetailDrawer/IntelTab.jsx — campaign-first, receipts, dismiss/restore,
            attribution-conflict banner, otx_status empty states; correlationPresentation.js
   │
INVEST/DETECT  brief/service.py _active_campaigns_for_stack (stack-matched campaigns in
               Morning Brief); IOC lookup related_cves_for_ioc (unified graph).
               NOT wired to risk score or detection context.
```

### 3.2 Signal inventory

| Signal | Source | Deterministic? | Matching logic | Confidence contribution | FP risk | Collision risk | Explainable evidence | Freshness / recompute / invalidation |
|--------|--------|----------------|----------------|-------------------------|---------|----------------|----------------------|--------------------------------------|
| **Same-pulse (campaign)** | `otx_cve_pulses` | Yes | 2+ CVEs share `pulse_id` | base by member count (`≥4 high, ≥2 medium`) | Med — mega-pulses glue unrelated CVEs | Med — hub CVEs | `same_pulse` receipt w/ pulse name | nightly rebuild; hub_suppress caps; prune on NVD sync |
| **Shared HASH** | `otx_pulse_iocs` | Yes | canonical hash equality across pulses | high | Low | Low | `shared_indicator` | on-demand; noise n/a |
| **Shared DOMAIN** | same | Yes | canonical domain equality | medium | Low–Med | Low | `shared_indicator` | on-demand |
| **Shared URL** | same | Yes | canonical URL equality | medium | Med | Low | `shared_indicator` | on-demand |
| **Shared IP** | same | Yes | IP equality | low (downrank noise/RFC1918) | **High** (CDN/shared infra) | High | `shared_indicator` + noise flag | on-demand; `is_noise_ip` downrank |
| **Enrichment confirmation** | `ioc_cache` (GreyNoise/MalwareBazaar/URLhaus) | Yes | cached classification lookup | bump/downrank IP/hash/url edge | Low | Low | `enrichment_confirmation` receipt | reads cache only, never new HTTP |
| **MITRE actor overlap** | `cve_technique_map`, `mitre_groups` | Yes | `|CVE∩group| / |CVE|` ≥ 0.25, top 3 | medium if ≥0.5 else low | Med | Med | technique_overlap value | per-CVE nightly |
| **OTX adversary** | `otx_cve_pulses.adversary` | Yes | non-empty string | low | High (community strings) | Med | actor row | nightly |
| **Temporal vendor spike** | `cves.published` + `affected_products` | Yes | week/avg ≥3.0, stack-or-signal gated | priority points only | Med | Med (vendor token) | volume sentence | nightly global rebuild |
| **KEV/exploit booster** | `cves.is_kev/has_poc` | Yes | peer membership carries KEV/PoC | +1 confidence step (cap high) | Low | Low | `kev_booster`/`exploit_booster` | live |

### 3.3 Signal strength classification

- **Architecturally valid & correctly implemented (1):** same-pulse campaigns,
  shared HASH/DOMAIN edges, enrichment confirmation, IOC normalization, hub
  suppression, analyst dismiss/restore, MITRE technique-overlap %, unified IOC
  pivot (`related_cves_for_ioc`), attribution-conflict flagging, display safety
  (`sanitize_pulse_text`). These directly answer prompt Q "what evidence should
  be retained / how should confidence be calculated" — the answers are already in
  code and correct.
- **Valid but badly presented (2):** the whole campaign story is drawer-only.
  Brief surfaces stack campaigns but the **feed has no campaign badge**, so an
  analyst scanning the feed never learns a CVE is part of a cluster. `priority`
  is computed but competes with three raw arrays in the UI.
- **Weak heuristic needing stronger evidence semantics (3):** **shared-IP-only
  edges** (CDN/shared-host collision — mitigated by noise flag + confirmation but
  still the weakest signal); **campaign confidence from member count alone**
  (`_confidence_for_pulse`) — a 4-CVE pulse is "high" regardless of pulse
  quality; **OTX adversary strings** (community, unverified — correctly capped
  low + conflict-flagged, keep as-is).
- **Stale implementation artifact (4):** `lifecycle` is written hardcoded
  `"active"` in `build_campaigns_from_pulses` — §24.10 lifecycle computation
  (emerging/active/declining/stale) is **not** implemented; `correlation_infrastructure`
  table is dead schema.
- **Misleading / should be removed (5):** none currently shipped to the analyst.
  (The v1 "shared IP headline" concern from the plan is already fixed — campaigns
  are pulse-first and IP is downranked.)

### 3.4 Evidence & confidence model — already equivalent to the proposed abstraction

The prompt asks whether BRIEFR needs a generic:

```
relationship{source_entity,target_entity,relationship_type,confidence,evidence[]}
evidence{evidence_type,source,value,observed_at,strength,explanation}
```

**It already has the semantic equivalent, in purpose-built tables + response
shapes.** A campaign/infrastructure finding carries `members`/`cve_id_b`
(entities), an implicit `relationship_type` (campaign vs infrastructure vs actor
vs temporal), `confidence` (deterministic level), and `evidence[]` with typed
entries (`same_pulse`, `shared_indicator` with `ioc_type`/`value`,
`enrichment_confirmation`, boosters), plus `why_not_higher`, `sources`, and
`attribution_conflict`. This satisfies the abstraction's intent.

**Therefore: do NOT introduce a generic typed-relationship table, a graph
database, or Neo4j.** PostgreSQL comfortably serves this workload (CVE-sized
corpus; on-demand joins are cached 6h). A generic graph model would be a
duplicate abstraction with migration cost and no measured requirement — exactly
the "wrong abstraction" trap the planning brief warns against.

**Confidence should stay relationship-type-specific (already is), not global.** A
shared hash is categorically stronger evidence than a shared IP; a single global
confidence knob would erase that. **Temporal decay:** do not add decay to
*confidence*; instead compute the already-scaffolded `lifecycle` field and let
brief/feed prefer emerging/active — that is the honest way to express staleness
without silently mutating evidence strength. **Stale evidence invalidation** is
handled by nightly rebuild + `prune_invalid_campaign_members` + cache
invalidation; the only missing piece is lifecycle computation.

### 3.5 Scoring interaction

Correlation does **not** feed Risk Score v1.1b (correct — keep risk deterministic
and self-contained). A separate `compute_correlation_priority` (correlation/priority.py,
"v3") turns the four arrays into one 0–100 triage number, and
`compute_investigation_score` (scoring/investigation.py) fuses risk 45% /
correlation 40% / intel 15%. The fused score is **orphaned** (see §4). The
explainable-risk-bump idea (plan §13) should remain a *derived* surface (priority
/ investigation score), never a hidden weight inside v1.1b.

### 3.6 Correlation v2 plan — phase review (`docs/archive/planned/CORRELATION_V2_PLAN.md`)

| Phase | Plan intent | Real state (code) | Verdict |
|-------|-------------|-------------------|---------|
| **1 — Foundation** (otx_pulses, IOC normalize, prioritized sync, hub suppress, campaigns, prune, v2 cache) | Pulse clusters | `otx_pulses` + `campaigns.py` + `hub_suppress.py` + `ioc_normalize.py` + prune + v2 cache all present | **SHIPPED** |
| **2 — IOC graph + confidence + trust** (ioc_graph, confidence, confirm, suppressions, unified IOC, lane UX, sanitize) | Receipts + multi-IOC + dismiss | `ioc_graph.py`, `confidence.py`, `confirm.py`, `suppressions.py` + API + IntelTab dismiss/restore + `sanitize_pulse_text` | **SHIPPED** |
| **3 — Local boosters + product wiring** (local boosters, co-exploit timing, MITRE overlap, temporal v2, semantic, brief/feed, invest, risk bump, drawer chip) | Actionable | boosters + MITRE overlap + temporal + brief campaigns **shipped**; co-exploit timing, semantic-validated neighbors, **feed badge**, investigation wiring, drawer chip **NOT shipped** | **PARTIALLY SHIPPED** |
| **4 — Depth** (clusters API, watchlist hints, Forge overlap, PDF section, webhook enrich, Atlas booster) | — | not implemented | **STILL VALUABLE but PARK** |
| **5 — Ops** (admin correlation status, metrics, reset suppressions, deprecate v1, perf indexes) | — | partial (feed health exists; no dedicated correlation-status endpoint) | **KEEP PARKED** (activate only if operators report correlation opacity) |

The plan's own "current state (v1)" framing is **materially outdated** — code is
at ~phase 3. The plan file is being given a SUPERSEDED header pointing here.

### 3.7 Recommended correlation implementation order (only what earns its keep)

1. **C-Evolve-1 — Lifecycle computation** (backend, deterministic): implement
   §24.10 in the nightly build (emerging/active/declining/stale from member
   recency + KEV/exploit/EPSS activity). Removes the hardcoded `"active"` lie and
   unlocks honest brief/feed filtering. *Small PR.*
2. **C-Evolve-2 — Feed campaign badge** (backend marker + frontend): a lightweight
   `member_of_campaign` boolean/lifecycle on the list API (nightly marker column
   or cheap join) + a feed badge with an explain tooltip. Turns a drawer-only
   capability into a scanning-level signal. *Small PR; coordinate feed surface
   with any I4 render work.*
3. **C-Evolve-3 — Drawer "linked to N CVEs" chip + investigation pivot** (frontend):
   top-of-drawer chip when campaigns exist; "add campaign to investigation"
   action. *Small PR; shared surface with §4 scoring-surfacing and H — sequence,
   don't parallelize.*

Everything beyond this (co-exploitation timing, semantic-validated neighbors,
clusters API, webhook/PDF/Forge enrichment, admin correlation status) is **parked**
until an operator or analyst signal justifies it.

### 3.8 Do-NOT-build (correlation)

- Generic typed-relationship table / graph DB / **Neo4j** — no measured need;
  Postgres suffices; the evidence model already exists.
- LLM-created relationship edges or LLM confidence decisions — correlation must
  stay deterministic; LLM may only summarize already-established evidence.
- `correlation_campaign_edges` persistence — campaigns are pulse-rooted and edges
  are cheaply recomputed on demand; persisting them adds write cost for no read.
- Multi-hop transitive closure beyond the plan's 1-hop default.
- Correlation phases 4–5 wholesale.

### CORRELATION ARCHITECTURE VERDICT: **INCREMENTALLY EVOLVE**

The pipeline is deterministic, explainable, and already implements the
relationship+evidence abstraction in purpose-built tables. It does not need
preservation-as-frozen (real gaps: lifecycle, feed surfacing, member-count-only
campaign confidence), and it categorically does not need redesign or replacement
(no generic graph, no Neo4j, no LLM correlation). Evolve it with three small,
high-leverage PRs (§3.7); park the rest.

---

## 4. Risk scoring architecture review

### 4.1 Exact v1.1b formula (verified in `scoring/risk.py` + `scoring/asset_match.py`)

`total = round( Σ raw[k] × weight[k] × 100, 0.1 )` — pure additive weighted sum,
no amplification/compounding.

| Component | Weight | Raw derivation |
|-----------|--------|----------------|
| Asset | 35% | `resolve_asset_component`: profile+CPE backend tiers (1.0/0.55/partial), else fuzzy graduation; **no profile → `DEFAULT_ASSET_UNKNOWN = 0.5`** |
| KEV | 25% | `_kev_score_v11b`: not-KEV 0; KEV no-date 0.84; ≤7d 1.0; ≤30d 0.94; ≤90d 0.88; else 0.84 |
| EPSS | 15% | `_num(epss_score, 0.0)` clamped 0–1 (missing → 0.0 in the v11b path) |
| Exploit | 10% | `_exploit_score_v11b`: metasploit 1.0; weaponised 0.88; poc 0.55; has_poc/exploits 0.35; none 0 |
| CVSS | 10% | `cvss_score / 10` (9.8 → 0.98) |
| Momentum | 5% | `calculate_momentum` (EPSS trend + OTX recency + KEV recency + rapid exploitation), clamped 0–1 |

**Unknown-asset behavior confirmed:** no profile → asset raw `0.5` →
`0.5 × 0.35 × 100 = 17.5` weighted points, a fixed floor for *every* no-profile
CVE. `hasProfile: false` is returned; `test_risk_score_v11b.py` locks this.
**CVSS 9.8 contribution confirmed:** `0.98 × 0.10 × 100 = 9.8` points.
**Ceiling without a profile:** `17.5 + 25 + 15 + 10 + 10 + 5 = 82.5`.

### 4.2 Scenario matrix (illustrative decompositions using the real formula)

Points = `raw × weight × 100`. "No profile" ⇒ asset 0.5 ⇒ 17.5.

| # | Scenario | asset | kev | epss | exploit | cvss | mom | **Total** | Displayed band | Analyst reads | Semantic risk |
|---|----------|------:|----:|-----:|--------:|-----:|----:|----------:|----------------|---------------|---------------|
| 1 | KEV + PoC + high EPSS (0.9) + unknown asset, CVSS 9.8, mom 1.0, KEV no-date | 17.5 | 21.0 | 13.5 | 5.5 | 9.8 | 5.0 | **72.3** | High | urgent | asset floor inflates a no-context CVE |
| 2 | KEV + exact CPE stack match (1.0), EPSS 0.3, PoC 0.35, CVSS 8.8, mom 0.3 | 35.0 | 21.0 | 4.5 | 3.5 | 8.8 | 1.5 | **74.3** | High | mine + exploited | *should* dominate but lands near #1 |
| 3 | Critical CVSS 9.8, no KEV, EPSS 0.02, no exploit, unknown asset | 17.5 | 0 | 0.3 | 0 | 9.8 | 0 | **27.6** | Low–Med | not urgent | reasonable, but 17.5 is >half the score |
| 4 | Medium CVSS 5.5 + KEV recent (1.0) + Metasploit (1.0), EPSS 0.6, mom 0.8, unknown asset | 17.5 | 25.0 | 9.0 | 10.0 | 5.5 | 4.0 | **71.0** | High | actively exploited | good — exploitation lifts medium CVSS |
| 5 | No KEV + high EPSS (0.85) + PoC (0.55), CVSS 8.0, mom 0.5, unknown asset | 17.5 | 0 | 12.75 | 5.5 | 8.0 | 2.5 | **46.3** | Medium | watch | no-KEV 25% slice caps it hard |
| 6 | Profile loaded, weak match (0.45 desc-mention), KEV 0.84, EPSS 0.4, PoC 0.35, CVSS 7.5, mom 0.2 | 15.75 | 21.0 | 6.0 | 3.5 | 7.5 | 1.0 | **54.8** | Medium | lower than #1 despite a real match | **inversion**: real weak match (15.75) < unknown (17.5) |
| 7 | No asset profile at all | 17.5 | — | — | — | — | — | floor 17.5 / ceiling **82.5** | — | — | placeholder ≠ exposure |
| 8 | Fuzzy product match, no version proof (0.75), no KEV, EPSS 0.3, PoC 0.35, CVSS 7.0 | 26.25 | 0 | 4.5 | 3.5 | 7.0 | 0 | **41.3** | Medium | maybe mine | fuzzy match inflates relevance without version proof |

### 4.3 Semantic conflicts

1. **Blended headline conflates two questions.** 65% of the weight answers "how
   dangerous is this vulnerability?" (KEV/EPSS/exploit/CVSS/momentum) and 35%
   answers "does it affect *me*?" (asset). One number cannot rank both
   truthfully; a globally severe CVE and a locally relevant one collapse into the
   same 0–100 scale.
2. **The `0.5` asset placeholder is the specific semantic failure.** Folding a
   "we don't know" into the headline as 17.5 guaranteed points (a) inflates every
   no-profile score, and (b) produces the **inversion in scenario 6**: a genuine
   weak match (0.45 → 15.75) scores *lower* than knowing nothing (0.5 → 17.5), so
   loading a profile can *reduce* a CVE's score. The inversion is in fact sharper
   than the scenario shows: when a profile *is* loaded but nothing matches,
   `resolve_asset_component` → `asset_match_info` returns **`0.0`**, not `0.5` —
   so a loaded-but-unmatched CVE contributes **0** asset points, a full 17.5
   below the no-profile floor. Knowing your environment and finding no match is
   penalized relative to knowing nothing. That is user-hostile.
3. **Additivity is a feature, not a bug — but it drives the "feels low"
   complaint** (documented #339: KEV + PoC + CVSS 9.8 = 62.9). No compounding
   means severe combinations never exceed the sum of their capped slices. This is
   *correct* for explainability; the fix is presentation, not multipliers.
4. **Fuzzy-match inflation (scenario 8):** a product-name match without
   vulnerable-version proof contributes real asset points as if confirmed.

### 4.4 Option comparison (analyst decision semantics, not aesthetics)

- **Option A — one BRIEFR Risk Score (status quo).** Simple, one number to rank.
  But it conflates threat + environment and hardcodes the dishonest `0.5`
  placeholder. *Rejected as the end state.*
- **Option B — expose Threat / Environment Relevance / Operational Priority as
  three visible numbers.** Most honest decomposition. But three headline numbers
  raise cognitive load and invite "which do I sort by?" confusion in a scanning
  feed. *Rejected as the default surface.*
- **Option C — separate deterministic axes internally, derive ONE clearly-defined
  Operational Priority for the headline.** Keep Risk v1.1b and Correlation
  Priority as internal axes; when no profile is loaded, the headline reflects
  **threat** (do not fold the `0.5` placeholder in), and Environment is shown as
  an explicit "unknown" state rather than a number. **This is the direction the
  repo already half-built** (Correlation Priority + the orphaned Investigation
  Score). *Recommended — in principle.*

### 4.5 Resolution — ADR-002 (CLOSED 2026-07-09)

> **RESOLVED by [`docs/decisions/ADR-002-operational-priority.md`](decisions/ADR-002-operational-priority.md)
> (ACCEPTED).** The decision was made from repository evidence and did not require
> browser validation; browser validation now only tunes presentation and threshold
> constants.

The decision is **Option D**, not the naive Option C this review floated. Naive
Option C (deriving one priority number as `Threat·0.4 + Env·0.4 + Corr·0.2`) is the
arbitrary weighted average the semantics forbid — it recreates the v1.1b
conflation. Option D:

- **Threat Score (0–100, asset-independent, KEV-floored)** is the honest headline
  number — v1.1b components minus asset, renormalized, with a **KEV floor of 80**
  so confirmed exploitation dominates a low EPSS.
- **Environment Relevance is a categorical tier** (CONFIRMED / LIKELY / POSSIBLE /
  WEAK / NO_MATCH / UNKNOWN), never a number folded into Threat.
- **Operational Priority is a deterministic P1–P4 rule table** over
  (Threat band × Environment tier), with **Correlation as a bounded one-band
  escalation qualifier** (active/emerging campaign + high-confidence edge; many
  weak edges never escalate).
- **UNKNOWN** contributes zero and yields a *provisional* priority off the Threat
  band — no fabricated `0.5`/17.5 points.
- **Investigation Score → DELETED** (its formula is the rejected weighted average;
  it re-imports the placeholder via `risk_total`, double-counts OTX recency, and
  is orphaned). Its intent survives as Operational Priority.

**Correction to an earlier claim in this review:** §4.3 framed "loading a profile
can *lower* the score" as the defect. ADR-002 refines this — a **proven NO_MATCH
legitimately de-escalates** priority (scenario S3). The actual defect is narrower:
**UNKNOWN is encoded as fabricated positive evidence** (17.5 phantom points that
NO_MATCH does not get). ADR-002's requirement is "unknown is never a misleading
numeric contribution," **not** "loading a profile can never lower priority."

### RISK SCORING ARCHITECTURE VERDICT: **PRESERVE THE MATH — DECIDED IN ADR-002 (Option D)**

Risk Score v1.1b's per-component math is deterministic, explainable, versioned,
tested, LLM-independent — sound, and reused as-is for the Threat axis. The failure
was presentation (a blended headline + the `0.5` UNKNOWN placeholder). Resolved by
ADR-002: Threat Score (number) + Environment Relevance (tier) + Operational
Priority (P1–P4 rule band), Correlation as a bounded escalation qualifier,
Investigation Score deleted. No weight tweaking; EPSS never re-derived.
Implementation is the now-deterministic task **M1**.

---

## 5. Intelligence confidence & freshness review

### 5.1 Source audit (as implemented)

Per-source resilience state lives in `resilient_client` (`last_success`,
`last_error`, `circuit_open_until`) and is exposed via `get_feed_health` →
`/api/health` + admin. `api_queue` paces outbound calls; LLM provenance
(`{provider, model}`) is stored in `feed_cache`. Cache TTL/retention is mapped in
the C3 audit (sprint doc).

| Source | Cadence | Job | last_success/attempt | Stale threshold | Provenance stored | Analyst-visible provenance | Partial / rate-limit / retry / circuit |
|--------|---------|-----|----------------------|-----------------|-------------------|----------------------------|-----------------------------------------|
| NVD | incremental | `nvd_incremental_sync` | resilient_client | admin health only | watermark (sync_state) | no per-CVE | queue + circuit + retry |
| KEV | periodic | `kev_metadata_sync` | resilient_client | — | row dates | KEV badge/date | circuit |
| EPSS | daily | `epss_score_sync` | resilient_client | — | epss_history dates | sparkline | circuit |
| OTX | nightly + continuous | `otx_*` | resilient_client | — | fetched_at | `otx_status` (not_configured) | budgeted, retries=0 bulk |
| Exploit indices | periodic | `exploit_sources_sync` | resilient_client | — | per-source replace | exploit list | circuit |
| GreyNoise | on-demand (E8) | — | ioc_cache | 48h feed_cache | classification | quota UI | on-demand only |
| CIRCL/Sploitus/OSV | on-demand | — | feed_cache | per-key | cache keys | drawer sections | best-effort |
| LLM (product/detection) | scheduler | `llm_product_extraction`, `detection_context_llm` | feed_cache | — | `{provider, model}` | none surfaced | router failover chain |

### 5.2 State-distinguishability taxonomy

| State | Distinguishable today? | Where |
|-------|------------------------|-------|
| **NO DATA FOUND** | Partially | empty query result with a healthy source — but the drawer rarely says "checked, nothing found" vs "not checked" |
| **SOURCE NOT CONFIGURED** | Yes (OTX), partial elsewhere | `otx_status: not_configured`; GreyNoise quota UI |
| **SOURCE RATE LIMITED** | Yes at source level | `circuit_open` / api_queue pacing in admin/health — **not** at CVE level |
| **SOURCE STALE** | Weak | `last_success` tracked; no explicit age-threshold surfaced to the analyst |
| **SOURCE FAILED** | Yes at source level | `last_error` + `circuit_open` in admin/health |
| **ENRICHMENT PENDING** | **No** at analyst level | a not-yet-processed CVE looks identical to "no data" in the drawer |

### 5.3 Where absence is misread as negative evidence

The highest-risk confusions, in priority order: **exploit availability**
("no exploits" vs "exploit sync stale/down"); **IOC/OTX enrichment** ("no
campaign" vs "OTX not configured" — *this one is already handled* via
`otx_status`); **detection context** ("no context" vs "LLM job off/failed");
**GreyNoise** (on-demand, may simply be un-run). EPSS/KEV are least ambiguous
(explicit dates).

### 5.4 Minimum analyst-facing freshness model (avoid badge spam)

One **provenance line per intel section** (not per field): "As of `<time>` ·
`<source>` · [checked / pending / source unavailable]". Reuse the existing
`resilient_client` state + cache `fetched_at`; do not turn a source failure into
a blocking CVE error. The single most valuable increment: distinguish
**ENRICHMENT PENDING** from **NO DATA** in the drawer's exploit + detection +
correlation sections. This is a small, deterministic, self-contained task
(§12 Wave 3).

---

## 6. Scheduler & failure-recovery review

APScheduler with per-job `id=` strings (kept in sync with `routers/admin.py` lock
mapping — danger zone 2), `resilient_client` circuit breakers, `api_queue`
serialization, and `engine._recover_db_transaction` for Postgres
transaction-abort recovery. **No distributed task system is warranted** — the
corpus is CVE-sized, jobs are idempotent and schedule-driven, and a single
scheduler instance is a deliberate constraint (see the deploy-unit `workers=1`
comment). Do **not** add Celery/Redis/Kafka.

### Failure-mode matrix

| Subsystem | Failure | Current behavior | Recovery | Operator visibility | Data risk | Recommended action |
|-----------|---------|------------------|----------|---------------------|-----------|--------------------|
| Any HTTP source | 429 | circuit trips after threshold; optional feeds fail-fast (`retries=0` bulk), required wait | cooldown auto-closes; `reset_circuit` admin | `circuit_open` + `last_error` in admin/health | Low (cached) | keep; expose per-CVE "source unavailable" |
| Any HTTP source | timeout | same circuit path | cooldown | admin/health | Low | keep |
| Any source | malformed response | per-feed try/except, row skipped | next run | `last_error` (sometimes) | Low–Med (silent skip) | log skip counts in job stats |
| LLM | provider fails mid-batch | `llm_router` failover chain (Groq→Gemini→Cerebras→OpenRouter) | next provider / template fallback | thin (feed_cache provenance) | Low (off by default) | surface last LLM job status in admin |
| LLM | all providers fail | deterministic template fallback; no `detection_ctx` written | next run | thin | Low | keep; ensure no "empty = done" write |
| Backend | restart during enrichment | job re-runs on schedule; per-source cache partial w/ TTL | candidate reselected (`get_recent_cve_ids_for_otx`) | job status | **Med** — partial data can look complete until TTL | add "enrichment pending/partial" marker (§5) |
| DB | transaction fails | `_recover_db_transaction` rollback; loop continues | next CVE / next run | logs | Low | keep |
| api_queue | task active at process death | in-memory queue lost; re-enqueued next run | next scheduler tick | queue status (#341) | Low (idempotent) | keep — durable queue is over-engineering here |
| Circuit | opens | optional fail-fast, required wait+pause | cooldown / admin reset | admin/health | Low | keep |
| Multi-source | one source ok, another fails for same CVE | additive per-source enrichment; drawer shows what's present | per-source retry on cache miss | none per-CVE | Med (looks complete) | per-section provenance (§5) |
| Enrichment | partial data on next run | re-attempted per-source on cache miss; TTL governs | TTL expiry | none | Med | §5 provenance closes this |

**Does work retry / wait / mis-treat partial as complete / leave stale metadata /
skip candidates / recover circuits / show the operator?** Retries and waits are
correct; circuits recover; the operator sees source health and (post-#341) queue
tasks. The one real gap is that **partial enrichment can read as complete at the
analyst level** — closed by the §5 per-section provenance line, not by new
infrastructure.

### SCHEDULER VERDICT: **PRESERVE.** Architecture is sound; the only additive work is analyst-facing provenance (§5). No distributed queue.

---

## 7. Investigation workflow review

**Flow (as implemented):** Start investigation (`InvestigationContext`) → session
notice + sidebar capture hint → CVE selection (feed distinguishes opened /
investigating / bulk-select, #339) → drawer navigation → observable extraction
(`observableExtraction.js`, staged extract→validate→classify→prioritize, #339
point 7) → IOC enrichment (IOC lookup) → correlation pivots (drawer IntelTab) →
related CVEs → PDF/report export.

**Precise classification:** this is primarily **evidence collection + navigation
recording** with a lightweight investigation thread. It is **not** case management
(no assignment, status workflow, SLA, multi-user case objects) and should not
become one — that boundary is explicit in the product position and ROADMAP
non-goals.

**Highest-value improvements (3–5), in order:**

1. **Turn correlation into an investigation pivot** (ties to §3.7-3): "add
   campaign to investigation" + "linked to N CVEs" chip. A correlation
   relationship that doesn't create a pivot has limited product value; this is
   the highest-leverage investigation upgrade.
2. **Resolve the score story** (ties to §4/ADR-002): the investigation thread is
   the natural home for a fused Operational Priority *if* the ADR adopts it.
3. **Observable pivot quality**: ensure extracted observables (post-#339) feed
   IOC lookup + correlation `related_cves_for_ioc` consistently (unified graph is
   already there — verify the UI uses it end-to-end).
4. **Investigation trail persistence** (only if analysts ask): currently
   client-side; a durable trail is a *small* additive step, not a case system —
   keep parked until requested.

Do **not** add case assignment, workflow states, or multi-analyst case objects.

---

## 8. Detection workflow review

**Path (as implemented):** CVE → `DetectionContext` (`detection_ctx:{cve}` cache,
scheduler-written) → `class_router._resolve_detection_class` (CWE→slug /
ATT&CK→slug, deterministic) → Sigma (`sigma_generator`, CWE class templates when
no technique, `briefr_basis`) / SIEM (`class_queries`) / log patterns — all three
aligned by the router → Nuclei artifact injection (`nuclei_parser`, deterministic)
→ optional LLM overlay (`context_llm_sync`, off by default, JSON extract only,
never raw Sigma).

- **Strong deterministic behavior:** the class router unifies Sigma/SIEM/log
  outputs; CWE templates give technique-less CVEs a specific rule; community Sigma
  stays primary, generated rules are framed as a supplement (D5).
- **Weak fallback behavior:** the generic template path (`briefr_basis: generic`)
  is honestly labeled experimental but is genuinely low-value — acceptable as a
  clearly-marked floor.
- **Semantic contradictions:** none material. The LLM overlay is correctly
  prevented from hiding deterministic routing weaknesses (it enriches artifacts,
  it does not author or re-route).
- **Missing analyst context / correlation opportunity:** cluster technique overlap
  (correlation §3) → hunt scope is the natural next seam (plan phase 4, **parked**).
  Correlation evidence *could* raise detection-context confidence, but only as an
  explainable, deterministic annotation — not an LLM decision.

### DETECTION VERDICT: **PRESERVE.** Deterministic, layered, honest. Correlation→detection fusion stays parked until §3.7 lands.

---

## 9. Performance architecture review

Track I was audited earlier; re-classified against current main. The dataset is
CVE-sized — measure before reaching for infrastructure.

| Item | Classification | Note |
|------|----------------|------|
| I1 dialect cache | **OBSOLETE** | Post-B3 deleted `db/dialect.py` — correctly cancelled |
| I2 gzip (nginx + middleware) | **HIGH-CONFIDENCE QUICK WIN** | 1.24 MB bundle ships uncompressed; additive deploy change |
| I3 lazy-load PDF | **HIGH-CONFIDENCE QUICK WIN** | jsPDF+html2canvas in entry chunk; dynamic import |
| I4 feed scroll render | **THEORETICAL until profiled** | `React.memo` + rAF; verify with profiler first |
| I5 TTL hot-read cache | **HIGH-CONFIDENCE QUICK WIN** | `/api/stats`, `/kev/deadlines`, `/health` — in-process dict TTL |
| I6 detail enrichment off pool | **MEASURED-ish** | pool-hold during external I/O is real; but measure `duration_ms` |
| I7 `/api/cves` query (pg_trgm, JOIN, count cache) | **DEFER UNTIL TRAFFIC / measure** | `EXPLAIN ANALYZE` first |
| I8 tab code-splitting | **QUICK WIN (bundle)** | after I3 |
| I9 pause hidden-tab polling | **QUICK WIN** | one shared `document.hidden` hook |
| I10 bulk upsert | **MEASURED (ingest)** | row-by-row loop over 5k CVEs; scheduler-path only |
| Phase 3 (multi-worker, keyset, virtualization) | **DEFER UNTIL TRAFFIC** | blocked on shared rate-limit store + single-instance scheduler |

**Recommended order:** I2 → I5 → I3 → I8 → I9 (all quick wins, mostly
parallel-safe across surfaces) → then I10 (ingest) and I6 (measure first) → I4/I7
only after profiling proves the bottleneck. **Do not** convert GreyNoise to
background bulk enrichment (intentionally on-demand, E8). Bundle/query items paste
before/after numbers per Spec I.

---

## 10. Production & recovery review

**Deploy surface (real):** systemd units (`briefr-backend.service`, backup
service+timer, pg-backup service+timer, `briefr.target`), nginx confs (http +
https + security-header snippets), `frontend/dist` via nginx, `briefr-update.sh`,
`briefr-restore.sh`, `smoke-intel.sh`, `check-backend.sh`, `docker-compose.postgres.yml`.

**Verified gaps (danger zone 5 — deploy scripts run on a live box):**

- `briefr-update.sh` has **no Alembic migration step** (grep confirms). Forward-only
  migrations are the compatibility promise but the update path never runs them.
- The post-restart health check **only warns** — it prints `check-backend.sh` as a
  *suggestion* rather than running it, and there is **no rollback** if the new
  backend fails to start.
- The intel smoke gate (`smoke-intel.sh`) runs but is **warn-only** unless
  `BRIEFR_STRICT_SMOKE=1`.

**CI backup round-trip ≠ production recovery procedure.** Post-B4
(`test_backup_roundtrip_postgres.py`) proves `run_backup` → wipe → `restore_backup`
preserves row counts *in CI on ephemeral Postgres*. It does **not** prove a
Debian-box operator can recover: it doesn't exercise age-encryption decryption on
the box, systemd stop/start ordering, nginx/dist coherence, or a real restore
runbook. **Do not automate a destructive production restore from CI.**

**Minimum work before a BRIEFR upgrade can be trusted on the Debian box:**
J1 (Alembic step + real health gate + defined rollback), J3 (strict smoke default),
J4 (release checklist), and a **written restore runbook** (break-glass, manual,
operator-run — not CI-automated). This is Wave 1 and blocks trusting any upgrade.

---

## 11. AI-agent development model

BRIEFR is built **primarily by AI coding agents**, not a conventional
multi-person team. ~30–40 build-days (including ~1 idle week) produced the current
state. **Implementation speed is not the scarce resource** — correct architecture,
correct security semantics, task decomposition, context isolation, PR blast-radius
control, deterministic validation, and repository coherence are. Planning must
optimize for those, not for human sprint velocity. A well-scoped deterministic PR
lands fast; the expensive failures are wrong abstractions, duplicate work, and
architectural churn.

**Task-type → model-class mapping (used throughout §12 and the sprint doc):**

| Task type | Model class | When |
|-----------|-------------|------|
| **HIGH-REASONING** architecture decision | **FRONTIER REASONING** | genuinely underdetermined design choice needing analyst-facing validation or cross-subsystem judgment |
| **AUDIT / repo-trace** | FRONTIER or STANDARD | enumerate + verify claims against code |
| **DETERMINISTIC IMPLEMENTATION** | **STANDARD CODING AGENT** | spec exists, surface is bounded, verification is mechanical |
| **ADVERSARIAL VALIDATION** | independent reasoning pass | second-model review before merge (Gemini + specs) |

This review deliberately **made every architecture decision the repo has evidence
for** so future prompts are mostly deterministic. The only remaining
FRONTIER-REASONING item is ADR-002 (scoring surfacing), because its blocker is
analyst-facing validation, not missing repo evidence.

---

## 12. Recommended execution graph (wave model)

Not a linear backlog. Waves gate on dependency + production risk; within a wave,
tasks are parallel-safe **only when they touch disjoint code surfaces**. Shared
surfaces are called out explicitly (advisor constraint: scoring-surfacing and
H2/H4 both touch `DetailDrawer` → never parallelize them).

```
WAVE 1  Production trust (blocks trusting any upgrade)         [deploy surface]
        J1 ── J3 ── J4 ── J5(restore runbook)   (J1→J3 sequential; J4/J5 parallel-safe)
                    │
WAVE 2  Intelligence coherence (highest product value)
        ├─ ADR-002  scoring surfacing  ───────────────► M1 scoring surfacing impl
        │   (FRONTIER)                                   (STANDARD, after ADR)  [OverviewTab/DetailDrawer]
        ├─ C-Evolve-1 lifecycle (STANDARD)  ── C-Evolve-2 feed badge (STANDARD) [correlation/*, feed]
        └─ I2 gzip (STANDARD, deploy)   ‖ parallel-safe with all of Wave 2
                    │
WAVE 3  Cleanup / opportunistic
        ├─ FR1 per-CVE provenance line (STANDARD)  [drawer sections]
        ├─ H-verify (AUDIT) → close H1/H3/H5/H6; H2/H4 only if justified  [DetailDrawer — NOT ‖ M1/C-Evolve-3]
        ├─ I5, I3, I8, I9 perf quick wins (mostly ‖)
        └─ C-Evolve-3 drawer chip + investigation pivot [DetailDrawer — sequence after M1/H]
                    │
WAVE 4  Parked (activate only on explicit signal)
        F (open-core) · G (learning) · correlation phases 4–5 · STIX · Monitor alerts · I7/I4/Phase-3 perf
```

**Active task cards** (full execution detail — objective, files, non-goals, DoD,
validation, PR boundary — lives in `SPRINT_2026-07.md`; summarized here):

| ID | Type | Model | Deps | Parallel-safe with | Objective | DoD |
|----|------|-------|------|--------------------|-----------|-----|
| **J1** | IMPLEMENTATION | STANDARD | — | J4, J5, I2, Wave-2 corr | Alembic step + real health gate + rollback in `briefr-update.sh` | failed start doesn't wedge box; OPERATIONS documents atomic-or-safe |
| **J3** | IMPLEMENTATION | STANDARD | J1 | J4, J5 | strict smoke gate default | broken build exits non-zero via smoke |
| **J4** | IMPLEMENTATION (doc) | STANDARD | — | J1, J3, J5 | release/version phasing checklist | checklist encodes compatibility promise |
| **J5** | IMPLEMENTATION (doc) | STANDARD | — | J1, J3, J4 | **production restore runbook** (manual break-glass) | operator can restore from age-encrypted backup on box; explicitly not CI-automated |
| **ADR-002** | HIGH-REASONING | FRONTIER | browser review | (decision only) | decide Threat/Environment/Operational-Priority surface | ADR merged; Investigation Score adopted or deleted |
| **M1** | IMPLEMENTATION | STANDARD | ADR-002 | I2, C-Evolve-1/2 (NOT H2/H4/C-Evolve-3) | implement ADR-002 scoring surface | Overview shows decided surface; no `0.5` folded into headline; tests |
| **C-Evolve-1** | IMPLEMENTATION | STANDARD | — | J*, M1, I2 | lifecycle computation (§24.10) | nightly writes emerging/active/declining/stale; tests |
| **C-Evolve-2** | IMPLEMENTATION | STANDARD | C-Evolve-1 | J*, M1, I2 | feed campaign badge + explain tooltip | feed shows badge; list API marker; build green |
| **I2** | IMPLEMENTATION | STANDARD | — | everything (deploy surface) | nginx gzip + GZipMiddleware | `Content-Encoding: gzip` on bundle + `/api/cves` |
| **FR1** | IMPLEMENTATION | STANDARD | — | perf items | per-CVE per-section provenance line (§5) | drawer distinguishes pending/no-data/source-down |
| **H-verify** | AUDIT | STANDARD | — | perf | re-read H1/H3/H5/H6 vs A+E; tick or narrow | closed with PR#s or scoped |
| **C-Evolve-3** | IMPLEMENTATION | STANDARD | M1, H | (sequence on DetailDrawer) | drawer chip + "add campaign to investigation" | chip renders; pivot adds cluster |

Validation gates: every wave ends green `./scripts/verify-local.sh`
(`pytest` + `npm run build`); UI items browser-verified; SQL items checked on both
dialects (danger zone 1); deploy items additive-only (danger zone 5).

---

## 13. Roadmap activation verdict

| Item | Verdict | Why |
|------|---------|-----|
| Correlation v2 **phase 3 tail** (lifecycle, feed badge, drawer chip, investigation pivot) | **ACTIVATE NOW** (Wave 2/3, as C-Evolve-1/2/3) | shipped engine is under-surfaced; small high-leverage PRs |
| Correlation v2 **phases 4–5** (clusters API, webhook/PDF/Forge enrich, admin status, metrics) | **KEEP PARKED** | no operator/analyst signal yet; depth before breadth is premature |
| Scoring surfacing / Operational Priority | **ACTIVATE NOW as ADR-002** (FRONTIER) | top product-semantic risk; needs analyst validation |
| Production update/rollback safety (J1/J3/J4/J5) | **ACTIVATE NOW** (Wave 1) | top production risk; blocks trusted upgrades |
| Freshness/provenance (FR1) | **ACTIVATE AFTER DEPENDENCY** (Wave 3) | valuable, small; not blocking |
| Track H (ui/ layer) | **ACTIVATE H-verify NOW; H2/H4 conditional** | Track E shipped the behaviors; do not force a design system |
| Performance Track I | **ACTIVATE quick wins (I2/I5/I3/I8/I9) after Wave 1–2** | evidence-first; measure I4/I6/I7 |
| Monitor / watchlist **alerts** | **KEEP PARKED** | product idea; not built; no current demand |
| STIX 2.1 export | **KEEP PARKED** (V1.5 interop seam) | no consumer yet; stub only if trivial |
| V1.5 threat-model UI depth / rule proof bench | **KEEP PARKED** | after detection + correlation surfacing stabilize |
| KEV backlog / VulnCheck tier / ThreatFox | **KEEP PARKED** (V1.5) | aggregator depth; no quota pressure now |
| V2.0 compose / platform / multi-worker | **KEEP PARKED** | private single-operator deploy; blocked on shared rate-limit store |
| Open-core prep (F2/F3-tail) | **KEEP PARKED** (after J/H/I) | headers/CONTRIBUTING should describe what actually ships |
| Documentation rollout / onboarding (G) | **KEEP PARKED** (last) | refresh after code stabilizes |
| Generic graph DB / Neo4j | **SUPERSEDED / REMOVE** | §3.4 — evidence model already exists in Postgres |

---

## 14. Final architecture priorities

### TOP 10 NEXT ARCHITECTURAL PRIORITIES

| # | Priority | Why it matters | Dependency | Task type | Model class | Product impact |
|---|----------|----------------|-----------|-----------|-------------|----------------|
| 1 | **J1 update/rollback safety** | An upgrade can currently wedge the production box | — | IMPLEMENTATION | STANDARD | trust to ship at all |
| 2 | **J5 restore runbook** | CI round-trip ≠ recoverable box | — | IMPLEMENTATION (doc) | STANDARD | disaster recovery |
| 3 | **J3 strict smoke default** | broken intel deploys complete silently | J1 | IMPLEMENTATION | STANDARD | deploy safety |
| 4 | **ADR-002 scoring surfacing** | headline conflates threat+environment; `0.5` placeholder inverts real matches | browser review | HIGH-REASONING | FRONTIER | correct triage semantics |
| 5 | **M1 scoring surface impl** | makes ADR-002 real; kills the orphaned score ambiguity | ADR-002 | IMPLEMENTATION | STANDARD | analyst decision quality |
| 6 | **C-Evolve-1 lifecycle** | removes hardcoded `"active"`; unlocks honest brief/feed | — | IMPLEMENTATION | STANDARD | correlation honesty |
| 7 | **C-Evolve-2 feed campaign badge** | correlation stops being drawer-only | C-Evolve-1 | IMPLEMENTATION | STANDARD | correlation visibility |
| 8 | **I2 gzip** | 1.24 MB uncompressed bundle, one additive change | — | IMPLEMENTATION | STANDARD | load time |
| 9 | **FR1 per-CVE provenance** | "pending" vs "no data" vs "source down" | — | IMPLEMENTATION | STANDARD | intel trust |
| 10 | **C-Evolve-3 + investigation pivot** | correlation → a real analyst pivot | M1, H | IMPLEMENTATION | STANDARD | investigation value |

### DO NOT BUILD YET

- **Generic typed-relationship table / graph database / Neo4j** — the
  evidence+confidence model already exists in purpose-built Postgres tables (§3.4).
- **LLM-driven correlation or LLM confidence** — correlation must stay
  deterministic; LLM summarizes established evidence only.
- **Correlation phases 4–5 wholesale** (clusters API, webhook/PDF/Forge
  enrichment, admin correlation-status) — park until operator/analyst signal.
- **`correlation_campaign_edges` persistence** — recompute on demand.
- **Case-management features** (assignment, workflow states, multi-analyst cases)
  — violates the product boundary.
- **Weight tweaking in Risk v1.1b** without ADR-002 + new tests + HANDOVER sign-off.
- **Distributed task system** (Celery/Redis/Kafka) — APScheduler is sufficient.
- **Multi-worker uvicorn / Redis cache / read replicas / frontend virtualization**
  — blocked on shared rate-limit store; corpus is CVE-sized; measure first.
- **STIX / Monitor alerts / open-core flip / learning track** — parked by roadmap
  verdict (§13).
- **Detection LLM authoring raw Sigma** — overlay stays JSON-extract only.

---

---

## Appendix A — Next 10 executable agent prompts (dependency order)

Each prompt is **self-contained and directly copyable** into a coding agent. It
carries the architectural decision already made in this review so the agent does
not re-derive it. Classification: **FRONTIER REASONING REQUIRED** (analyst-facing
judgment) vs **STANDARD CODING AGENT SUFFICIENT** (deterministic spec). Repository
conventions for all prompts: branch off fresh `origin/main`; one PR per prompt;
verify with `cd backend && pytest tests/ -q` and, for any frontend change,
`cd frontend && npm run build` + browser verification; read
`gemini-code-assist[bot]` review comments before merge; SQL changes checked on
both SQLite (tests) and Postgres (production, danger zone 1); `deploy/` changes
additive only (danger zone 5); update `PRODUCT_STATUS.md`/`SYSTEM_DESIGN.md` when
runtime behavior changes and `API_REFERENCE.md` when endpoints change.

### Prompt 1 — J1: update/rollback safety — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr (self-hosted CVE/threat-intel analyst pane; FastAPI backend, React/Vite frontend, PostgreSQL-required prod). Read CLAUDE.md danger zone 5.
Objective: Make `deploy/briefr-update.sh` a safe, atomic-or-recoverable production update.
Inspect: deploy/briefr-update.sh, deploy/check-backend.sh, deploy/lib.sh, backend/alembic/ (migration ordering), docs/OPERATIONS.md, docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md §10.
Known decision: the update script today has NO Alembic step, its health check only PRINTS check-backend.sh as a suggestion (does not run it), and there is no rollback on failed start.
Required behavior: (1) run forward-only `alembic upgrade` in order as part of the update, before restarting the backend; (2) after restart, actually RUN a health gate (curl /api/health with retries AND run check-backend.sh), failing the update non-zero if unhealthy; (3) define a rollback path so a failed start does not leave the box wedged (e.g. keep the prior release/venv and restore it, or stop-and-report with clear operator instructions — pick the simplest safe option and document it). Additive only; do not break existing systemd/nginx/cloudflared deploys.
Non-goals: no destructive DB restore; no CI automation of production restore; no runtime app code.
Testing: shellcheck clean; document the update path as atomic-or-safe in docs/OPERATIONS.md; describe the manual verification you performed.
DoD: a deliberately failing backend start does not wedge the box and exits non-zero; OPERATIONS documents the flow.
PR: title "deploy: J1 update path — alembic + health gate + rollback"; explain the rollback semantics.
```

### Prompt 2 — J3: strict smoke gate default — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Read CLAUDE.md danger zone 5.
Objective: Make the post-deploy intel smoke check fail the deploy by default instead of warning.
Inspect: deploy/briefr-update.sh (BRIEFR_STRICT_SMOKE handling), deploy/smoke-intel.sh, docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md §10.
Known decision: smoke-intel.sh already runs but only WARNS on failure unless BRIEFR_STRICT_SMOKE=1. Flip the default to strict; keep an opt-out env (e.g. BRIEFR_SKIP_SMOKE=1 or BRIEFR_STRICT_SMOKE=0) for break-glass.
Required behavior: a failing smoke check makes the update exit non-zero by default; document the opt-out.
Non-goals: do not change what smoke-intel.sh tests; no app code. Depends on J1 (health gate) landing first.
Testing: simulate a broken intel path and confirm non-zero exit; confirm opt-out still allows completion.
DoD: default-strict smoke gate; opt-out documented in the script header + OPERATIONS.
PR: title "deploy: J3 strict smoke gate by default".
```

### Prompt 3 — J4: release/version phasing checklist — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Doc-only task.
Objective: Encode the ROADMAP compatibility promise as a short pre-release checklist so each release stays a small independent phase.
Inspect: docs/ROADMAP.md (Compatibility promise), docs/OPERATIONS.md, deploy/ units, docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md §10.
Known decision: releases must remain additive for existing systemd/nginx/cloudflared deploys; migrations forward-only; additive API `meta` fields.
Required behavior: add a concise release checklist (additive-migrations verified, API additive, systemd/nginx additive, backup taken, smoke green, rollback path known) to docs/OPERATIONS.md.
Non-goals: no runtime change; no new top-level docs (extend OPERATIONS).
DoD: checklist merged in OPERATIONS.
PR: title "docs: J4 release phasing checklist".
```

### Prompt 4 — J5: production restore runbook — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Doc-only task. Read CLAUDE.md danger zone 5.
Objective: Write a manual, break-glass production RESTORE runbook for the Debian box. CI proves a backup round-trip (Post-B4) but NOT that an operator can recover a real box.
Inspect: deploy/briefr-restore.sh, deploy/briefr-pg-backup.sh, deploy/lib.sh, deploy/briefr-backend.service + briefr.target, docs/OPERATIONS.md, docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md §10.
Known decision: backups are age-encrypted under /var/lib/briefr/backups; Postgres 16 (often Docker at /opt/infra/postgres). The runbook is MANUAL and operator-run; do NOT automate a destructive restore from CI.
Required behavior: step-by-step runbook — age-decrypt the chosen backup, stop services (briefr.target), run briefr-restore.sh, run alembic upgrade, verify health + row counts, start services; include a pre-restore safety backup step and a "what to check if it fails" section.
Non-goals: no CI automation; no destructive defaults; no runtime code.
DoD: an operator can restore from an age-encrypted backup by following the runbook; merged into docs/OPERATIONS.md.
PR: title "docs: J5 production restore runbook".
```

### Prompt 5 — ADR-002: scoring axes / Operational Priority — CLOSED (ACCEPTED 2026-07-09)

**No longer an open prompt.** ADR-002 is decided:
[`docs/decisions/ADR-002-operational-priority.md`](decisions/ADR-002-operational-priority.md)
(ACCEPTED, Option D). Decision summary: Threat Score (0–100, asset-independent,
KEV floor 80) is the headline number; Environment Relevance is a categorical tier;
Operational Priority is a deterministic P1–P4 rule table; Correlation is a bounded
one-band escalation qualifier; the Investigation Score is DELETED. The
implementation is Prompt 6 (M1), now fully deterministic.

### Prompt 6 — M1: Threat / Environment / Operational Priority surface — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr (self-hosted CVE/threat-intel analyst pane; FastAPI backend, React/Vite frontend, PostgreSQL-required prod). Read CLAUDE.md.
Prerequisite: docs/decisions/ADR-002-operational-priority.md (ACCEPTED). Implement EXACTLY its contract. You make ZERO scoring-architecture decisions — every semantic, threshold, floor, tier, and rule is fixed in the ADR.
Objective: Replace the blended BRIEFR Risk Score v1.1b headline with the ADR-002 surface: Threat Score (number) + Environment Relevance (tier) + Operational Priority (P1–P4 band); delete the orphaned Investigation Score.
Inspect: backend/scoring/risk.py, backend/scoring/asset_match.py (resolve_asset_component: profile None → 0.5; profile + no match → 0.0), backend/scoring/investigation.py (DELETE), backend/routers/cves.py (risk route + /investigation-score route to DELETE + /correlation), frontend/src/scoring/riskScore.js, frontend/src/api.js (fetchCVEInvestigationScore to DELETE), frontend/src/components/DetailDrawer/OverviewTab.jsx.

BACKEND — add pure functions (new backend/scoring/threat.py + backend/scoring/priority.py, or extend risk.py):
1. calculate_threat_score(cve, momentum_score) -> {version:"threat-1.0", score(0-100), band, components{kev,epss,exploit,cvss,momentum:{raw,weight,points}}, kev_floor_applied:bool}. Reuse v1.1b raws (_kev_score_v11b, _exploit_score_v11b, epss=_num(epss_score,0.0), cvss=cvss/10, momentum). Renormalize the 5 NON-asset weights over 0.65: kev .3846, epss .2308, exploit .1538, cvss .1538, momentum .0769. threat_additive = 100*Σ(w*raw). If is_kev: Threat = max(threat_additive, 80). Bands: CRIT≥80, HIGH 60-79, MED 40-59, LOW<40. EPSS/exploit missing → 0 (never fabricate, never re-derive EPSS).
2. classify_environment(cve, profile, backend_match_score) -> {tier, score, version_verified:bool, evidence_label}. Reuse resolve_asset_component/asset_match_info. Map: profile None → UNKNOWN; profile & score 0 → NO_MATCH; exact CPE version (1.0) → CONFIRMED; CPE product 0.9 / OS 0.8 → LIKELY; product 0.75 / vendor 0.65 → POSSIBLE; 0.35–0.55 text → WEAK.
3. derive_operational_priority(threat_band, env_tier, corr_escalation:bool) -> {band("P1".."P4"), provisional:bool, escalated_by_correlation:bool, rationale}. Pure rule table (ADR §Operational Priority): 
   CONFIRMED: CRIT→P1,HIGH→P1,MED→P2,LOW→P3;  LIKELY: CRIT→P1,HIGH→P2,MED→P2,LOW→P3;  POSSIBLE/WEAK: CRIT→P2,HIGH→P2,MED→P3,LOW→P4;  UNKNOWN(provisional=true): CRIT→P1,HIGH→P2,MED→P3,LOW→P4;  NO_MATCH: CRIT→P3,HIGH→P3,MED→P4,LOW→P4.
   Then if corr_escalation and base∈{P2,P3}: lift one band (P2→P1, P3→P2), cap P1, never lift P4.
4. correlation_escalation(correlation_result) -> bool: true iff a campaign with lifecycle in (active,emerging) AND ≥1 high-confidence edge (same-pulse + shared hash/domain). Read from the correlation result already fetched on the detail path — do NOT add a new request-path correlation compute.
5. API: risk/overview response ADDS threat, environment, operational_priority (additive). Retain v1.1b total/components for ONE release as legacy_risk_v11b (external-consumer compat) but it is NOT displayed. DELETE the GET /api/cves/{id}/investigation-score route.

FRONTEND:
6. riskScore.js mirrors calculate_threat_score + classify_environment + derive_operational_priority deterministically (parity with backend).
7. OverviewTab headline: Operational Priority band (primary chip) + Threat Score (0-100) + Environment tier chip. "WHY THIS SCORE" shows Threat components + Environment tier + correlation-escalation reason. Remove the blended v1.1b total from display. Delete api.js fetchCVEInvestigationScore.

UNKNOWN behavior: contributes 0 to Threat (no 17.5 placeholder); Operational Priority uses Threat band as provisional (provisional=true). NO_MATCH: de-escalates per table. Fuzzy (POSSIBLE/WEAK/LIKELY-unverified): never P1 on match alone — P1 needs CONFIRMED exact version or genuine CRIT threat or a correlation-escalated HIGH. Correlation: escalation qualifier only, never a Threat input, never a weighted term.

Non-goals: do NOT change v1.1b weights; do NOT re-derive EPSS; no LLM influence on any axis; no case management; no SQL/scheduler/deploy changes. NOT parallel-safe with H2/H4 or C-Evolve-3 (shared DetailDrawer) — sequence them.

Testing: backend/tests/test_threat_score.py (KEV floor ⇒ ≥80; CVSS-only ⇒ LOW; medium-CVSS+KEV+metasploit ⇒ CRIT; EPSS pass-through; missing EPSS/exploit ⇒ 0), test_environment_tiers.py (UNKNOWN vs NO_MATCH distinct; fuzzy caps at POSSIBLE/WEAK), test_operational_priority.py (full matrix + correlation escalation + provisional + sorting). Assert all of ADR-002 scenarios S1–S10. Frontend riskScore.test.js parity for the matrix. npm run build. Browser-verify Overview for S1/S2/S3/S4/S6/S9 (no phantom 17.5; UNKNOWN provisional; NO_MATCH de-escalates).
Compatibility: additive API; v1.1b endpoint unchanged; investigation-score deletion is safe (zero callers, verified).
Versioning: emit threat-1.0 / environment-1.0 / operational-priority-1.0.
DoD: headline shows Threat + Environment tier + P1–P4 band per ADR-002; no fabricated 17.5 for UNKNOWN; NO_MATCH de-escalates; S1–S10 pass backend + frontend; Investigation Score route + stub deleted; update PRODUCT_STATUS.md CVE-Overview row to the shipped surface in the same PR.
PR: one PR, title "feat(scoring): M1 Threat/Environment/Operational-Priority per ADR-002".
```

### Prompt 7 — C-Evolve-1: correlation lifecycle computation — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Read docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md §3.
Objective: Compute campaign `lifecycle` in the nightly correlation build instead of hardcoding "active".
Inspect: backend/correlation/campaigns.py (build_campaigns_from_pulses writes lifecycle="active" hardcoded), correlation/config.py, backend/brief/service.py (_active_campaigns_for_stack), the CORRELATION_V2_PLAN §24.10 lifecycle table (emerging/active/declining/stale).
Known decision: deterministic only. emerging = new member in last 7d; active = a member with KEV/exploit/EPSS activity in last 14d; declining = no activity 30d+; stale = pulse age > 12 months AND no local boosters. Do NOT add confidence decay; lifecycle is a separate field.
Required behavior: build_campaigns_from_pulses computes and stores lifecycle per campaign from member recency + KEV/exploit/EPSS signals; brief/feed may then prefer emerging/active.
Non-goals: no new tables; no schema for edges; no UI in this PR (feed badge is C-Evolve-2).
Testing: backend/tests/test_correlation.py — a fixture per lifecycle state asserts the computed value; pytest green on SQLite and (via CI) Postgres.
DoD: real lifecycle values written nightly; tests cover each state.
PR: title "feat(correlation): C-Evolve-1 campaign lifecycle computation".
```

### Prompt 8 — C-Evolve-2: feed campaign badge — STANDARD CODING AGENT SUFFICIENT (after C-Evolve-1)

```
Repo: Soldier0x0/briefr. Read review §3.7. Prerequisite: C-Evolve-1 lifecycle merged.
Objective: Surface campaign membership at the feed-scan level with an explainable badge.
Inspect: backend/routers/cves.py (list path CVE_SELECT), backend/db/correlation.py, frontend CVEFeed.jsx, CVECard.jsx, correlationPresentation.js.
Known decision: the correlation engine is drawer-only today; make it a scanning signal. Use a NIGHTLY marker (e.g. a boolean/lifecycle column set when campaigns rebuild) or a cheap join — do NOT recompute correlation per row on the list request path (danger zone 6: no heavy work on the request path).
Required behavior: list API additively returns member_of_campaign (+lifecycle); feed renders a small "Campaign" badge with a discoverable explain tooltip (PRODUCT.md principle 1 — every pill ships an explanation).
Non-goals: no per-request correlation recompute; no drawer changes (that is C-Evolve-3).
Testing: pytest for the marker/join; npm run build; browser-verify the badge + tooltip; confirm no added request-path query cost beyond the marker.
DoD: feed shows the badge; list API additive; build green.
PR: title "feat(correlation): C-Evolve-2 feed campaign badge".
```

### Prompt 9 — I2: response compression (gzip) — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Read CLAUDE.md danger zones 5; review §9.
Objective: Ship JS/CSS/JSON compressed (the ~1.24 MB entry bundle + feeds currently ship uncompressed).
Inspect: deploy/nginx-briefr.conf, deploy/nginx-briefr-http.conf, backend/main.py (middleware).
Known decision: add nginx gzip for JS/CSS/SVG/JSON (additive per deploy compatibility promise) + FastAPI GZipMiddleware as a fallback for direct backend access.
Required behavior: `curl -H 'Accept-Encoding: gzip'` shows `Content-Encoding: gzip` for the bundle and for /api/cves.
Non-goals: no brotli dependency; no other nginx changes; additive only.
Testing: verify the curl header locally; record before/after transfer size in the PR.
DoD: gzip active for static bundle + /api/cves via nginx, with middleware fallback.
PR: title "perf: I2 gzip for static + API responses".
```

### Prompt 10 — FR1: per-CVE intel provenance line — STANDARD CODING AGENT SUFFICIENT

```
Repo: Soldier0x0/briefr. Read review §5.
Objective: In the CVE drawer, distinguish "checked / pending / source-unavailable" per intel section so absence of enrichment is not read as negative evidence.
Inspect: backend/resilient_client.py (get_feed_health: last_success/last_error/circuit_open), backend/db/cache.py (feed_cache fetched_at), backend/routers/cves.py (detail path), frontend DetailDrawer intel sections (exploits, detection, correlation/IntelTab).
Known decision: OTX already exposes otx_status (not_configured); extend the same honesty to exploit + detection sections. One provenance line per SECTION (not per field) — no badge spam. A source failure must never block rendering the CVE.
Required behavior: each intel section shows "as of <time> · <source> · [checked | pending | source unavailable]" derived from resilient_client state + cache timestamps.
Non-goals: no per-field badges; no blocking error on source failure; no new intel sources.
Testing: pytest for the provenance-state derivation; npm run build; browser-verify pending vs no-data vs source-down states.
DoD: exploit + detection + correlation drawer sections distinguish the three states.
PR: title "feat(intel): FR1 per-section provenance line".
```

**Prompts 11–12 (next after the above, for continuity):** **H-verify** (AUDIT,
STANDARD — re-read H1/H3/H5/H6 vs Tracks A+E, close with PR numbers or narrow
scope; then decide H2/H4) and **C-Evolve-3** (STANDARD — drawer campaign chip +
"add campaign to investigation" pivot; **shares `DetailDrawer` with M1/H — sequence,
do not parallelize**). Full cards in `SPRINT_2026-07.md`.

---

*End of review. Execution planning: `SPRINT_2026-07.md`. Continuation context:
`HANDOVER.md`. Shipped truth: `PRODUCT_STATUS.md`. This document is the durable
reasoning record — future agents should read it before re-investigating
correlation, scoring, freshness, scheduler, or production architecture.*
