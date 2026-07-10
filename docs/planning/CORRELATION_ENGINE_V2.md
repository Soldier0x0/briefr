# BRIEFR Correlation Engine — Evidence-Honest Redesign (plan of record)

**Status:** Plan of record — **no implementation in this document**
**Date:** 2026-07-11
**Audit basis:** Direct codebase trace on `main` (`2b5a588`, in sync with `origin/main`,
2026-07-11). `graphify-out/` **not** used as source of truth.
**Naming note:** the shipped engine already self-identifies as v2
(`correlation/config.py`: `ENGINE_VERSION = "2.0"`, `CAMPAIGN_ALGORITHM_VERSION =
"2.0.0-phase2"`). This document defines the evolution of that engine; the completed
target is `ENGINE_VERSION = "3.0"`. The file name follows the maintainer's request.

**Central principles (non-negotiable):**

> 1. Core correlation stays **deterministic, LLM-free, and reproducible** with zero
>    AI API keys. LLMs may later *narrate* correlation output; they never *produce* it.
> 2. The goal is **fewer, stronger, traceable relationships** — never more edges.
> 3. Confidence measures **whether a relationship is true**. Severity, asset
>    relevance, and priority are separate dimensions and must never leak into it.
> 4. Runs on 2-core / 16 GB self-hosted hardware; no new services, daemons,
>    databases, or background loops — everything rides the existing nightly job.

**Explicitly NOT in scope:** graph databases, STIX/RDF evidence stores, Bayesian
networks, dynamic source-reputation learning, ≥3-hop link discovery, LLM-in-the-loop
correlation, citation-crawling of external report URLs, CPE-perfect entity
resolution, materialized views. See §19.

---

## 1. Executive summary

BRIEFR's correlation engine is honest, deterministic, cheap, and analyst-respecting —
a genuinely good foundation. But it is a **single-source (OTX) co-occurrence system
whose "confidence" measures cluster size and severity, not evidence truth**. The audit
found two outright ranking/fan-out defects, one economically dead confidence path, and
one ingestion-vs-observation time conflation. Source independence, conflict handling,
per-edge temporal data, and quality measurement do not exist.

The fix is **not** an evidence-graph platform. It is thirteen narrow, dependency-ordered
PRs (§18) that make the existing pipeline evidence-honest: fix the defects, rebuild
confidence from evidence, capture observation time, dedupe mirrored pulses into
campaign families, corroborate IOC edges with ThreatFox, surface conflicts instead of
resolving them silently, and measure whether any of it worked.

Stopping after PR-4 already removes the worst false-confidence generators.

---

## 2. Conceptual vocabulary

These eight concepts are distinct. Conflating them is the root defect of the current
engine. Every future correlation change must respect this table.

| Concept | Definition | Lives in | May influence | Must never influence |
|---|---|---|---|---|
| **Evidence** | A typed, id-stamped, timestamped receipt derived from source observations (`same_pulse`, `shared_indicator`, `threatfox_corroboration`, `technique_overlap`) | Evidence arrays on correlation results; source mirror tables | Confidence, provenance display | — |
| **Relationship confidence** | Likelihood the relationship is *true*, derived only from evidence strength, corroboration, independence, freshness, and conflicts | `correlation/confidence.py` | Priority (as one input), escalation gates, UI pills | — |
| **Source reliability** | Static trust class of the asserting source: government > vendor > curated feed > community > unknown. Analyst verdicts outrank all | Static class map (config) | Confidence (via evidence weighting) | Severity, priority directly |
| **Source independence** | Whether N assertions are N observations or one observation mirrored N times (pulse families, distinct authors, distinct feeds) | `pulse_families` table; corroboration counting | Confidence (corroboration factor) | — |
| **Freshness** | Age of the *observation* (`observed_at`), decayed per evidence type at read time. Distinct from data-plumbing recency (`ingested_at`) | Read-time decay functions | Confidence (freshness factor), lifecycle | — |
| **Context / relevance** | Whether the relationship matters *to this operator*: stack match, asset tiers, sector, watchlist | `scoring/environment.py`, stack gating, cluster ranking | Priority, ranking, gating (what is shown) | Confidence (a link is equally true on or off your stack) |
| **Threat severity** | Asset-independent exploitation credibility: KEV, EPSS, exploit maturity, CVSS, momentum | `scoring/threat.py` | Priority | Confidence |
| **Operational priority** | The triage answer (P1–P4, correlation priority score): threat × environment × correlation escalation | `scoring/priority.py`, `correlation/priority.py` | Analyst ordering | Confidence |

Litmus test for any future change: *"does this fact make the link more likely to be
REAL, or more likely to be IMPORTANT?"* Real → confidence. Important → priority.

---

## 3. Current-state architecture (as of `2b5a588`)

### 3.1 Pipeline

```
SOURCES                     INGESTION (scheduler.py)            STORAGE
NVD/cvelistv5/vulnrichment  nvd_incremental_sync, …          →  cves ("vendor:product" strings)
CISA KEV / VulnCheck KEV    kev_metadata_sync, vulncheck_kev →  kev_deadlines, cves.is_kev
EPSS                        epss_score_sync                  →  epss_history
ExploitDB/Metasploit/PoC    exploit_sources_sync             →  cve_exploits, cves.has_poc
MITRE ATT&CK + CTID maps    weekly_mitre_refresh             →  mitre_techniques, cve_technique_map,
                                                                mitre_groups(+aliases), group_technique_map
ATLAS                       atlas_version_check              →  atlas_techniques, cve_atlas_map
OTX pulses + pulse IOCs     otx_nightly_correlation,         →  otx_pulses, otx_cve_pulses,
                            otx_continuous_sync                 otx_pulse_iocs (normalized at ingest)
ThreatFox                   threatfox_sync                   →  threatfox_iocs (never joins correlation)
VT/AbuseIPDB/GreyNoise/     analyst-triggered IOC Lookup     →  ioc_cache (6-hour TTL)
MalwareBazaar/URLhaus       only (routers/ioc.py)
```

### 3.2 Nightly batch — `correlation/engine.py::run_nightly_correlation`

1. Vendor volume anomalies vs 90-day baseline → `correlation_temporal` (full rewrite).
2. Actor/sector findings per recent CVE: ATT&CK group technique-overlap ≥ 0.25 (top 3)
   + OTX pulse `adversary` strings → `correlation_actor`.
3. Campaign rebuild (`correlation/campaigns.py::build_campaigns_from_pulses`):
   **DELETE everything, then one campaign per OTX pulse co-tagging ≥ 2 CVEs.**
   Campaign id = `camp_` + sha256(pulse_id)[:12] — stable across rebuilds.
   Lifecycle computed in `correlation/lifecycle.py`. Cache prefix `correlation:v2:` purged.

### 3.3 On-demand per CVE — `engine.py::get_correlation_for_cve` (6 h feed_cache)

1. `ioc_graph.py::find_shared_infrastructure_v2` — self-join `otx_pulse_iocs` through
   `otx_cve_pulses` for peer CVEs sharing typed IOCs; per-edge confidence from
   `confidence.py::confidence_for_ioc_edge`; suppression-filtered.
2. `campaigns.py::get_campaigns_for_cve` — campaigns containing the CVE, expanded with
   strong-IOC (hash/domain) peers, hub-filtered (`hub_suppress.py`: peers in > 50
   pulses dropped, 25-member cap), confidence adjusted, evidence receipts built,
   KEV/exploit boosters applied.
3. Actor + temporal (temporal gated to stack/KEV/PoC relevance).
4. `priority.py::compute_correlation_priority` — additive capped score:
   campaign ≤ 40, infra ≤ 25, actor ≤ 20, temporal ≤ 15, scaled by
   confidence fraction {high 1.0, medium 0.625, low 0.25}.

### 3.4 Consumers

DetailDrawer Intel/Related tabs ("WHY BRIEFR LINKED THESE CVEs" panel: receipts, link
strength, `why_not_higher`); feed campaign badge + campaign-peer-of-pinned sort boost
(`routers/cves.py` `CVE_ORDER_BY`); Morning Brief "Active campaigns on your stack";
Forge Campaigns tab; PDF campaign paragraph; watchlist webhook campaign hint; IOC
watchlist retro-match (`ioc/retro_match.py`); `scoring/priority.py::
correlation_escalation` (P2/P3 → one band up, tightly guarded); admin correlation
status (`correlation/status.py`).

### 3.5 Where the ideal SOURCE→…→ANALYST model deviates

Present and real: ingestion, IOC normalization at ingest (`ioc_normalize.py`),
relationship→campaign→priority→surface, per-finding receipts, analyst suppression.
Missing entirely: an EVIDENCE layer distinct from source mirrors; OBSERVATION
timestamps (only ingestion `fetched_at` survives); SOURCE as a modeled object
(hardcoded `["otx"]`); independence; stored conflict states; quality measurement.
Dead: `correlation_infrastructure` table (created in schema, written by nothing).
Orphaned: `threatfox_iocs` (ingested, used only for watchlist retro-match).

---

## 4. Audit — strengths (preserve)

1. **Deterministic, LLM-free, cheap, versioned, cached.** The trust anchor.
2. **Typed IOC edges with graduated strength** (hash > domain/URL > IP) — correct practice.
3. **`why_not_higher` receipts** — the engine explains why confidence *isn't* higher;
   the frontend renders it faithfully (`utils/correlationPresentation.js`).
4. **Analyst suppression** with scopes + reason taxonomy, persisted across rebuilds,
   respected before campaign promotion.
5. **Hub suppression concept** and member caps — the system already distrusts mega-hubs.
6. **Restraint:** campaigns/infrastructure are non-overlapping tiers; temporal
   anomalies gated to relevance; multi-hop bounded; hardcoded honesty
   ("OTX community pulse — unverified attribution").
7. **The scoring split** (Threat vs Environment vs Operational Priority, ADR-002) —
   architecturally correct separation; correlation escalation is tightly guarded
   (high confidence AND same-pulse AND shared hash/domain).
8. **Stable campaign identity** — suppressions and references survive rebuilds.

---

## 5. Audit — defects and false-confidence mechanisms

### 5.1 Verified defects (file:line on `2b5a588`)

| # | Defect | Location | Consequence |
|---|---|---|---|
| D1 | Peer truncation is **alphabetical before ranking**: `sorted(by_peer.items())[:limit]` slices 20 peers by CVE-ID order, then sorts by strength | `correlation/ioc_graph.py:80` | A hash-sharing CVE-2025-* peer is silently dropped in favor of an IP-sharing CVE-2014-* |
| D2 | **Unbounded IOC fan-out**: no per-IOC degree cap in `_shared_ioc_rows`; `is_noise_ip` covers RFC1918/loopback/reserved only | `ioc_graph.py:16`, `ioc_normalize.py:63` | Public resolvers, CDN edges, sinkhole domains, popular hashes create dense cliques of plausible-looking edges across unrelated CVEs |
| D3 | **Confirmation path is economically dead**: GreyNoise/MalwareBazaar/URLhaus bumps read `ioc_cache`, populated *only* by analyst-triggered IOC Lookup (`routers/ioc.py:143`) with a **6-hour TTL** (`db/cache.py:16`) | `correlation/confirm.py` | In production a confirmation modifier fires only if an analyst looked up that exact IOC in the last 6 h. Tests pass because tests seed the cache |
| D4 | **Ingestion time masquerades as observation time**: lifecycle "emerging" fires on `otx_cve_pulses.fetched_at` < 7 d; momentum's "New OTX pulse" uses `fetched_at` too | `lifecycle.py:74-77`, `scoring/risk.py:530-561` | First OTX backfill marks years-old campaigns "emerging" for a week |
| D5 | **Member count → confidence** (≥ 4 members = high) | `campaigns.py:26-31` | Rewards exactly the promiscuous roundup pulses hub suppression distrusts; inverted signal |
| D6 | **KEV/exploit boosters raise confidence** | `campaigns.py:328-331` | Category error: a peer being exploited says nothing about whether the *link* is real. Severity laundered into truth; double-counted with priority caps |
| D7 | **Attribution conflict is substring matching** while `mitre_groups.aliases` sits unused | `confidence.py:115-128` | "Fancy Bear" vs "APT28" flagged as a conflict; real multi-pulse conflicts unchecked |
| D8 | `correlation_infrastructure` table dead; IOC observation timestamps (OTX indicator `created`) dropped at ingest | `db/init.py:381`, `feeds/otx.py:228-240` | Schema debt; temporal data permanently lost at ingest |
| D9 | Feed campaign-peer-of-pinned boost ignores campaign confidence and lifecycle | `routers/cves.py:414-422` | One pinned CVE inside a 25-member hub pulse boosts 24 possibly-unrelated CVEs |
| D10 | Composite lookup for the hot self-join relies on single-column `(ioc_value)` index | `alembic/versions/001:287` | Avoidable cost on the most-run correlation query |

### 5.2 Structural gaps

- **Single-source epistemology.** Every campaign/infrastructure edge derives from OTX
  community pulses. One anonymous author = one campaign at up-to-high confidence.
  `author` stored, never used. Five pulses mirroring one blog post = five "campaigns";
  corroboration and duplication are indistinguishable.
- **Actor correlation is weak inference presented as correlation.** Sparse CTID
  CVE→technique maps (often 1–3 techniques) → group overlap ≥ 0.25 matches dozens of
  groups on generic techniques; sector match is keyword-in-description.
- **No feedback loop, no measurement.** Suppressions are stored but never aggregated;
  nothing measures precision, rejection rate, or edge survival across releases.
- **No conflict states, no retraction visibility.** Pulses that vanish upstream take
  their campaigns with them silently on the next rebuild.

### 5.3 False-confidence summary

| Mechanism | Why it is false confidence |
|---|---|
| Member count → confidence (D5) | Big pulses are usually *lower*-precision |
| KEV booster → confidence (D6) | Severity ≠ truth; already counted in priority |
| N mirrored pulses → N campaigns | Duplication presented as breadth |
| "high" on one anonymous pulse + one shared domain | No independence, no author weight, no observation freshness |
| "Emerging" from `fetched_at` (D4) | Data-plumbing recency presented as threat recency |

---

## 6. Target architecture

A disciplined vocabulary over mostly-existing tables — **not** a generic evidence graph.

- **ENTITY** — CVE (canonical id); Campaign (pulse *family*, §10); Actor (MITRE group
  id + aliases; OTX adversary strings resolved against aliases or kept as explicitly
  *unresolved labels*); Technique; Vendor (string, acknowledged-fuzzy — see §19).
- **OBSERVATION** — a source asserting something at a time: pulse row, pulse-IOC row,
  ThreatFox row, KEV row. Carries `observed_at` (the source's claim time) and
  `ingested_at` (fetch time). ~80 % present today; missing `observed_at` on pulse IOCs.
- **EVIDENCE** — a typed, id-stamped receipt derived from observations:
  `same_pulse`, `shared_indicator`, `threatfox_corroboration`, `technique_overlap`.
  `evidence_id = sha256(type + canonical inputs)` → stable, referenceable receipts.
- **SOURCE** — `{name, class}`, class ∈ {government, vendor, curated_feed, community,
  local_analyst}. KEV = government; ThreatFox = curated_feed; OTX = community;
  analyst verdicts = local_analyst (outranks all). Static map; no dynamic reputation.
- **RELATIONSHIP** — CVE↔CVE (infrastructure / campaign membership), CVE↔Actor,
  CVE↔Technique. Always: evidence list + confidence vector + temporal fields.
- **CONTEXT** — stack match, asset tiers, sector. Modifies *relevance/priority and
  gating*, never confidence (§2).
- **CONFIDENCE** — §7. **CONFLICT** — §11. **PROVENANCE** — §8.
- **CAMPAIGN** — a pulse family (deduped), not a pulse. **CLUSTER** — the ranked
  consumer view (existing `clusters.py`, unchanged role).

Flow: observations → deterministic evidence builders (versioned rules) →
relationships with confidence vectors → campaign/family aggregation →
context-relevance labeling → priority. Analyst feedback (suppress / confirm)
re-enters as `local_analyst` evidence.

---

## 7. Confidence model

Analyst-facing output stays **LOW / MEDIUM / HIGH** (UI continuity), computed from an
exposed factor vector. All read-time pure functions; constants are tunable defaults
via the existing `correlation/config.py` env pattern; nothing decayed is ever stored.

```python
# ── Per IOC edge ─────────────────────────────────────────────
BASE = {"HASH": 0.9, "DOMAIN": 0.6, "URL": 0.65, "IP": 0.3}

degree_factor(d) = 1.0 if d <= 3 else 1.0 / (1.0 + log2(d / 3))
    # d = distinct CVEs sharing this IOC (from ioc_degree, §14)

freshness(t, age_days) = max(0.25, 0.5 ** (age_days / HALF_LIFE[t]))
    # age from observed_at; fallback ingested_at (flagged in the receipt)
    HALF_LIFE = {"IP": 30, "URL": 60, "DOMAIN": 120, "HASH": 365}
    # hash identity never expires; its contextual weight does

corroboration(k) = min(1.0, 0.6 + 0.2 * log2(1 + k))
    # k = independent source families asserting this edge:
    # each pulse FAMILY counts once; ThreatFox counts once

edge_score = BASE[type] * degree_factor(d) * freshness(t, age) * corroboration(k)
edge_level = HIGH if ≥ 0.65, MEDIUM if ≥ 0.40, else LOW
# every factor ≠ 1.0 emits a why_not_higher reason string

# ── Per campaign ─────────────────────────────────────────────
score = 0.5                                  # same-pulse co-tag base (NOT member count)
score += 0.3 * max(edge_score of member IOC edges, default 0)
score += 0.15 if ≥ 2 pulse families or ThreatFox corroboration else 0
score += 0.10 if ≥ 3 distinct pulse authors else 0
score -= 0.20 if pulse ioc_count > hub cap or member_count > 15   # hubbiness
score -= 0.20 while an attribution conflict is unresolved          # §11
# KEV/exploit boosters: REMOVED from confidence → priority-only
# (they already have CAP_CAMPAIGN/CAP_INFRASTRUCTURE room in priority.py)
```

API shape (additive): `"confidence": "medium", "confidence_factors":
[{"factor": "corroboration", "value": 0.6, "reason": "single community source"}, …]`.
Existing `why_not_higher` becomes the top factor's reason — field kept for
compatibility.

A single number *was* hiding uncertainty; the fix is exposing the vector, not a
probabilistic engine.

---

## 8. Evidence & provenance model

Extend the existing receipt format — do **not** build a lineage store.

```json
{ "type": "shared_indicator", "evidence_id": "ev_9f2c…",
  "ioc_type": "DOMAIN", "value": "bad.example",
  "source": {"name": "otx", "class": "community",
              "record": "pulse:663d…", "author_count": 2},
  "observed_at": "2026-06-28T…", "ingested_at": "2026-07-09T…",
  "extraction": "ioc_normalize@2.0", "rule": "shared_indicator@3.0",
  "contribution": {"level": "medium",
                    "why_not_higher": "IOC seen across 9 CVEs (hub penalty)"},
  "corroborated_by": ["threatfox:ioc_812…"], "conflicts": [] }
```

**Analyst trace path:** drawer panel → evidence receipt → pulse id / ThreatFox id →
local mirror row (`otx_pulses`, `threatfox_iocs`) → upstream URL. Every hop already
has a table; only ids and timestamps need to ride along.

`intel/provenance.py` (section-level status/as-of lines) is a different, working
concern — **data freshness of feeds** — and stays as-is.

---

## 9. Temporal model

Column semantics (on existing tables; no event store):

| Field | Meaning | Status |
|---|---|---|
| `observed_at` | The source's claim time: pulse `created`, OTX indicator `created`, ThreatFox `first_seen`, KEV `date_added` | **New** on `otx_pulse_iocs`; others exist |
| `ingested_at` | Existing `fetched_at`. Display ("data as of") and cache logic **only** — never lifecycle/momentum input again | Exists; misused today (D4) |
| `first_seen` / `last_seen` | min/max `observed_at` across a relationship's evidence | New columns on `correlation_campaigns`; per-edge computed at read time |
| `inferred_at` | Existing `computed_at` | Exists |
| `superseded_at` / `retracted_at` | Campaign whose pulse family vanished upstream: flagged for 30 days (excluded from default views), then pruned — never silently deleted | New, set during rebuild |

**Decay:** per-type half-lives (§7). CVE facts and technique mappings do not decay.
**Lifecycle:** re-derived exclusively from `observed_at` streams (pulse created, KEV
added, EPSS history activity, CVE published/modified). Fixes D4.
**Event ordering** (published → PoC → KEV → pulse): rendered as a drawer timeline from
data already local. **Display only — no causal inference from sequence.**

---

## 10. Source reliability & independence

**Reliability** = the static class map in §6. Justification for static-not-learned:
feedback volume on a solo self-hosted install is far too sparse to train anything;
a learned reputation would be noise wearing a model's coat.

**Independence** — the highest-value structural change:

- **Pulse families.** Two pulses belong to one family when their normalized non-hub
  IOC sets (each ≥ 3 IOCs) have Jaccard ≥ 0.7, **or** their CVE member sets and
  normalized pulse names are identical. Families = connected components; family id =
  hash of the lexically-first member pulse id (stable). Computed nightly,
  incrementally for new/changed pulses, bounded by generating candidate pairs only
  through shared non-hub IOCs.
- **Campaign = family.** N mirrored pulses collapse into one campaign whose
  `independent_sources` counts families (not pulses) and `author_count` counts
  distinct authors. Existing campaign-id suppressions of any family member map to
  the family campaign.
- **ThreatFox as a true second source.** Already mirrored locally
  (`threatfox_iocs` with `first_seen`, `confidence_level`, malware family) and
  currently orphaned. An OTX IOC edge whose canonical value also appears in ThreatFox
  gains `corroborated_by` and counts once in the corroboration factor. Genuinely
  independent, already-ingested, zero new network calls.
- **What this deliberately approximates:** true citation lineage (A cites B) is
  unknowable without crawling reference URLs (rejected, §19). IOC-set similarity is a
  deterministic, local, good-enough proxy for "derived reporting."

The dead `ioc_cache` confirmation path (D3) is demoted: GreyNoise/MalwareBazaar/URLhaus
results render as **opportunistic annotations** on receipts but no longer move
confidence levels. ThreatFox becomes the persistent corroboration source instead.

---

## 11. Conflict handling

Narrow and explicit — two conflict types, computed at read time, **no dedicated
conflicts table** (volume will be tiny; a table is unjustified state):

1. **Attribution conflict.** Pulse-family adversary strings vs MITRE technique-overlap
  actors vs other families' adversaries, compared through `mitre_groups.aliases`
  (alias-expanded, lowercased). Mismatch → both claims attached to the campaign
  result: `{claim_a: {value, source, observed_at}, claim_b: …, status: "unresolved"}`.
  Effect: −0.2 confidence while unresolved. **Never auto-picks a winner.**
  "Fancy Bear" vs "APT28" resolves as *same alias family — no conflict* (fixes D7).
2. **Exploitation dispute.** `is_kev` vs `is_vulncheck_exploited` vs no-PoC-anywhere:
  data already present; rendered as dual-sourced claims in the drawer and threat
  sentences. Not resolved, displayed.

**Retraction** (the only safe negative evidence besides analyst verdicts): a pulse or
IOC gone upstream marks derived evidence `superseded` and the campaign `retracted_at`
(§9) — visible for 30 days, then pruned. Absence of expected evidence is otherwise
**never** treated as evidence of absence: silence in a community feed measures the
feed, not the threat.

**Analyst resolution:** `correlation_feedback` (§14) with verdicts
`confirm | reject | resolve_conflict{winner}` — same UX pattern as the existing
suppress modal. Analyst verdicts are `local_analyst` class and always win.

---

## 12. Multi-hop invariant

Current restraint is correct — codified as an invariant: **max 2 hops, enumerated
path types only.**

| Path | Status |
|---|---|
| CVE –pulse– CVE | keep (campaign) |
| CVE –IOC– CVE | keep (infrastructure, degree-capped) |
| CVE –technique– group | keep, relabeled **"possible actors (technique inference)"** |
| pinned-CVE –campaign– CVE | keep (feed boost), gated on confidence ≥ MEDIUM and lifecycle ∈ {active, emerging} (fixes D9) |
| IOC → CVEs (analyst pivot) | keep |
| CVE –IOC– CVE –IOC– CVE (transitive) | **rejected** — the classic TIP noise generator |

Confidence propagation for the one 2-hop path: `min(hop levels) − one level`.
Path explainability: the path *is* the evidence list. No general traversal API.

---

## 13. Correlation quality metrics

Nightly snapshot into `correlation_metrics` (one row/day), computed inside the
existing nightly job:

- **Precision proxies:** analyst rejection rate (suppressions ÷ surfaced findings,
  30 d window), confirmation rate (`correlation_feedback`), suppression-reason
  distribution (a rising "shared hosting / CDN" share = normalization gap; the
  taxonomy already exists in `correlationPresentation.js`).
- **Structure health:** weak-edge ratio (IP-only ÷ all), hub-suppressed edge count,
  IOC degree p95, campaign duplicate-merge count, avg independent source families per
  campaign, orphan ratio (CVEs with pulses but zero surviving edges).
- **Stability:** campaign survival (fraction of yesterday's ids alive), member churn,
  edge survival over 30 d.
- **Freshness:** stale-edge ratio (freshness factor < 0.5), median evidence age.

**Explicitly not quality metrics:** total edges, total campaigns, coverage %.
(They remain fine as *operational* stats in admin status.)

Every correlation PR from Phase 1 onward states its expected metric movement in its
acceptance criteria, giving before/after on the operator's real data.

---

## 14. Database impact (PostgreSQL production; SQLite parity per CLAUDE.md danger zone 1)

All forward-only Alembic + `db/init.py` SQLite parity + parallel `_SQLITE`/`_PG`
constants. Test both ways (default suite + `DATABASE_URL` Postgres).

| Change | Kind | Notes |
|---|---|---|
| `CREATE INDEX idx_otx_pulse_iocs_type_value ON otx_pulse_iocs(ioc_type, ioc_value)` | index | Hot self-join currently rides single-column `(ioc_value)` (fixes D10) |
| `DROP TABLE correlation_infrastructure` | cleanup | Dead (D8); only schema/migration references exist |
| `otx_pulse_iocs.observed_at TEXT NULL` | ALTER | No backfill; NULL = fallback to `fetched_at`, flagged |
| `correlation_campaigns` + `family_id`, `first_seen`, `last_seen`, `independent_sources INT`, `author_count INT`, `retracted_at TEXT NULL` | ALTER | |
| `pulse_families(pulse_id PK, family_id, jaccard REAL, computed_at)` | new table | Nightly incremental; small |
| `ioc_degree(ioc_type, ioc_value, cve_count INT, pulse_count INT, computed_at, PK(ioc_type, ioc_value))` | new table | Nightly truncate-and-rebuild, one `INSERT…SELECT` — **plain table, not a matview** (SQLite-testable, no refresh locks) |
| `correlation_feedback(id, cve_id, scope, scope_key, verdict, reason, created_by, created_at, UNIQUE(cve_id, scope, scope_key, verdict))` | new table | Mirrors `correlation_suppressions` shape |
| `correlation_metrics(day PK, …counters)` | new table | One row/day, ~15 columns |

**Query risks:** pulse-family Jaccard is the only quadratic-shaped computation —
bounded by generating pairs only via shared non-hub IOCs (`ioc_degree`-filtered) and
computing incrementally. The nightly campaign rebuild keeps its proven
DELETE+rebuild shape, keyed by `family_id`, with retraction flagging instead of
silent row loss.

---

## 15. Performance constraints and budgets

Assumptions (dev-DB row counts were not queryable during the audit — verify before
PR-9): `cves` 10⁴–3×10⁵; OTX ingestion is tier-capped (~200 CVEs/night backlog,
500 pulse-IOC fetches/run per `correlation/config.py`), so `otx_pulse_iocs`
plausibly 10⁵–low-10⁶ and `otx_pulses` 10³–10⁴.

| Item | Budget |
|---|---|
| `ioc_degree` rebuild | one GROUP BY over `otx_pulse_iocs` — seconds at 10⁶ rows |
| Pulse families | thousands of candidate pairs after hub filtering; Python set-Jaccard nightly, < 1 min on 2 cores |
| Read-time confidence vector | pure arithmetic on rows already fetched; cached 6 h as today |
| Storage | new tables ≪ existing OTX mirrors; metrics 1 row/day |
| Net nightly-job cost | +1–3 min worst case; wall-time reported in job stats |
| New daemons / services / DBs / LLM calls | **zero** |

---

## 16. Analyst UX requirements (correlation surfaces only — no UI redesign)

The DetailDrawer "WHY BRIEFR LINKED THESE CVEs" panel is the right shape — extend it:

1. **WHY CONNECTED** — existing intro + receipts (unchanged pattern).
2. **CONFIDENCE** — keep the LOW/MEDIUM/HIGH pill; expanding it shows the factor list
   (strength / corroboration / independence / freshness / conflict, each with reason).
   `why_not_higher` becomes the first factor row.
3. **SUPPORTING vs CONFLICTING** — a "Conflicting" subsection when a conflict exists;
   both claims with source + `observed_at`; "unresolved" is a legitimate labeled state.
4. **FRESHNESS** — per-receipt "observed <relative time>" + stale tint when decay
   < 0.5; distinct from the existing section-level as-of line (`IntelProvenanceLine`).
5. **PROVENANCE** — receipt rows link pulse id → OTX URL, ThreatFox id → local record;
   show `rule@version`.
6. **TIMELINE** — one horizontal strip: published → PoC → KEV → first pulse → last
   activity (all data local; display only).
7. **FEEDBACK** — beside "Mark as unrelated": **"Confirm link"** (one click → metrics).
8. Campaign badge tooltip gains independence wording ("2 independent source families" /
   "single community pulse"). Every new pill keeps the tooltip/legend rule
   (PRODUCT.md principle 1); dark-terminal density rules unchanged.

---

## 17. Migration strategy

Five phases; each shippable; API changes additive (existing fields never removed
mid-phase); no env flag to toggle old-vs-new confidence (flags double the test matrix
— the changelog + factor vector explain the shift instead).
`CAMPAIGN_ALGORITHM_VERSION` bumps at Phases 1 and 3 (existing cache-prefix purge
handles invalidation).

- **Phase 0 — Correctness (no semantic change):** D1 ranking fix, D10 index, D8 table
  drop. Instant precision win.
- **Phase 1 — Honest confidence:** `ioc_degree` + degree penalties (D2); member-count
  base and KEV boosters removed from confidence (D5, D6 — boosters stay in priority);
  factor vector in API; `ioc_cache` confirmations demoted to annotations (D3).
- **Phase 2 — Temporal truth:** capture `observed_at` (D8); lifecycle/momentum on
  observation time (D4); read-time decay + UI staleness; timeline strip.
- **Phase 3 — Independence:** pulse families; campaign = family; corroboration
  counting; ThreatFox joins IOC-edge corroboration; author diversity; retraction
  visibility.
- **Phase 4 — Conflict, feedback, measurement:** alias-aware attribution (D7),
  confirm feedback, `correlation_metrics`, admin surface, feed-boost gating (D9).

Stopping after Phase 1 already removes the worst false-confidence generators.

---

## 18. PR plan (dependency-ordered; prefer narrow PRs)

Common to all PRs: pytest both SQLite-default **and** `DATABASE_URL` Postgres for any
`db/` change; `npm run build` + browser verification for UI PRs; update
`docs/PRODUCT_STATUS.md` + `SYSTEM_DESIGN.md` when runtime behavior changes and
`API_REFERENCE.md` when endpoints change — same PR.

**PR-1 — Rank infrastructure peers by evidence, not alphabet (Phase 0).**
Invariant: peer truncation never drops a stronger peer for a weaker one.
Modify: `correlation/ioc_graph.py` (build all peers → score → sort → slice).
Schema: none. Tests: 25-peer fixture where the strongest peer is lexically last.
Compat/perf risk: none (output-order change only).
Accept: existing tests green; new test proves strong-peer retention.

**PR-2 — Composite index + drop `correlation_infrastructure` (Phase 0).**
Invariant: no code path references the dropped table (verified: schema/migration only).
Modify: Alembic 015, `db/init.py`, `migration/sqlite_to_postgres.py`.
Tests: migration up on both engines. Accept: `EXPLAIN` on the `_shared_ioc_rows`
self-join uses the composite index on PG.

**PR-3 — `ioc_degree` table + degree-penalized edge confidence (Phase 1).**
Invariant: rebuild idempotent, single `INSERT…SELECT`; degree only ever lowers
confidence. Modify: Alembic 016, `db/correlation.py`, `engine.py` (nightly),
`confidence.py` (`degree` param), `ioc_graph.py`; add ~a dozen literal public-resolver
IPs (8.8.8.8 etc.) to the noise check — a constant, **not** a curated feed.
Tests: degree-50 IP edge → LOW with hub reason; rebuild wall-time in job stats.
Compat: some edges drop a level — intended; changelog note.

**PR-4 — Remove severity and size from confidence (Phase 1).**
Invariant: nothing in campaign confidence may reference KEV/exploit or member count.
Modify: `campaigns.py`, `confidence.py` (`campaign_confidence` rewrite per §7),
`priority.py` (booster sentence moves); rewrite `test_correlation.py::
test_kev_booster_bumps_campaign_confidence` to assert booster affects **priority**
only. Compat: campaign confidences shift down — the point of the PR; UI enum
unchanged. Accept: no `is_kev`/`has_poc` reads inside confidence functions.

**PR-5 — Confidence factor vector in API + drawer expansion (Phase 1).**
Additive `confidence_factors` on campaigns/infrastructure; drawer factor list.
Modify: `confidence.py`, `campaigns.py`, `ioc_graph.py`, `IntelTab.jsx`,
`correlationPresentation.js`; `API_REFERENCE.md`. Tests: backend factor snapshot;
frontend unit test. Risk: none (additive).

**PR-6 — Capture `observed_at` on pulse IOCs (Phase 2).**
Modify: Alembic 017, `feeds/otx.py::fetch_pulse_iocs` (keep indicator `created`),
`db/correlation.py::replace_otx_pulse_iocs`. Nullable, no backfill.
Tests: round-trip incl. NULL fallback. Risk: none.

**PR-7 — Lifecycle + momentum use observation time (Phase 2).**
Invariant: `fetched_at` never feeds lifecycle or momentum.
Modify: `lifecycle.py` (drop `member_link_fetched_at` in favor of pulse/indicator
observed dates; fallback CVE published/modified), `scoring/risk.py` (OTX momentum
signal uses pulse `created_date`). Tests: **backfilled old pulse ≠ emerging** (the D4
regression test). Compat: fewer "emerging" badges after OTX bootstrap — correct.

**PR-8 — Read-time freshness decay + UI staleness (Phase 2).**
Modify: `confidence.py` (half-life table, env-tunable via `config.py` pattern),
receipts gain `observed_at`/freshness reason, drawer stale tint + timeline strip.
Tests: 200-day-old IP edge decays below MEDIUM; NULL `observed_at` flagged not decayed
to floor. Risk: some edges drop a level — intended.

**PR-9 — Pulse families + campaign dedup + retraction visibility (Phase 3).**
Invariant: campaign id stable per family; suppressions of any member pulse's old
campaign id map to the family campaign; vanished families flag `retracted_at`, never
silent-delete. Modify: Alembic 018 (`pulse_families`, campaign columns),
`campaigns.py` (rebuild keyed by family), `db/correlation.py`, `clusters.py`
(exclude retracted by default). Tests: two mirrored pulses → one campaign with
`author_count = 2`; distinct pulses stay separate; suppression migration; retraction
flag lifecycle. Perf: candidate pairs bounded via `ioc_degree`; wall-time budget in
job stats. Compat: campaign count drops (dedup) — changelog.

**PR-10 — ThreatFox corroboration on IOC edges (Phase 3).**
Modify: `ioc_graph.py` (read-time join on canonical value → `corroborated_by`),
`confidence.py` (corroboration factor counts it); verify/add index on
`threatfox_iocs(ioc_type, ioc_value)`. Tests: OTX+ThreatFox edge outranks OTX-only.
Risk: none (additive).

**PR-11 — Alias-aware attribution + conflict surfacing (Phase 4).**
Modify: `confidence.py::attribution_conflict` (alias-expanded via
`mitre_groups.aliases`), `campaigns.py` (attach dual claims per §11), drawer
"Conflicting" subsection. No new table. Tests: APT28/"Fancy Bear" no-conflict;
genuine mismatch renders both claims with sources.

**PR-12 — Analyst confirm feedback (Phase 4).**
Modify: Alembic 019 (`correlation_feedback`), POST/DELETE endpoints alongside the
suppress endpoints (`routers/cves.py:1524` pattern), drawer "Confirm link" button,
audit-log entry, `API_REFERENCE.md`. Tests: round-trip, uniqueness, audit entry.

**PR-13 — `correlation_metrics` nightly snapshot + admin surface (Phase 4).**
Modify: Alembic 020, `engine.py::run_nightly_correlation` (compute §13 counters),
`correlation/status.py`, admin intel-status page row, feed-boost gating in
`routers/cves.py` `CVE_ORDER_BY` (D9 — one-line gate, rides this PR).
Tests: snapshot math on fixtures; gated boost ordering test.
Accept: metrics visible in admin; this closes the measurement loop for PRs 1–12.

---

## 19. What NOT to build (rejected with reasons)

- **Graph database / generic evidence-graph / RDF / STIX store.** Three relationship
  shapes; PostgreSQL joins express them. A graph layer adds ops burden, zero precision.
- **Bayesian networks / probabilistic scoring.** Unverifiable priors, unexplainable
  posteriors. "MEDIUM because: single community source, fresh hash" beats `0.6237`.
- **Dynamic source-reputation learning.** Solo-install feedback volume is far too
  sparse; static class weights + author *diversity counts* give ~90 % of the value.
- **Citation-lineage crawling of reference URLs.** Expensive, brittle, privacy-
  expanding. Pulse-family Jaccard is the deterministic local proxy.
- **Transitive ≥ 3-hop discovery / "hidden link" mining.** Directly opposes
  fewer-stronger-relationships.
- **Automatic negative-evidence inference** ("no pulses in 30 d → downgrade").
  Absence in a community feed measures the feed, not the threat. Only retractions
  and analyst verdicts qualify.
- **LLM-in-the-loop correlation.** Violates central principle 1. (LLM narration of
  already-computed receipts is acceptable later — optional, labeled.)
- **Stored/background decay.** Decay is a read-time pure function; storing decayed
  values destroys reproducibility.
- **CPE-perfect vendor/product entity resolution.** Disproportionate effort;
  graduated asset matching + honest "vendor strings are fuzzy" labeling is the trade.
- **Materialized views.** Plain nightly-rebuilt tables are simpler, SQLite-testable,
  and refresh-lock-free at this scale.
- **A curated CDN/cloud-IP denylist feed.** Maintenance burden; the degree penalty
  handles popular IOCs organically. Only a ~dozen literal public resolvers ship as a
  constant (PR-3).
- **Old-vs-new confidence env flag.** Doubles the test matrix; the factor vector and
  changelog explain the shift instead.

---

## 20. Changes from the original audit proposal (self-review record)

Applied before this document was written:

1. **Dropped the `correlation_conflicts` table.** Conflict volume will be tiny;
   conflicts are now computed at read time and attached to results; only analyst
   *resolutions* persist, via `correlation_feedback`. One table and one migration
   removed.
2. **Compressed 14 PRs → 13.** `ioc_degree` and the degree-penalized confidence merged
   (PR-3) — the table alone would ship dead weight. Feed-boost gating (D9) and
   retraction visibility folded into PR-13 and PR-9 respectively instead of standing
   alone.
3. **Rejected the curated CDN/DNS denylist** from the original PR-4; replaced with the
   degree penalty plus a ~dozen-literal public-resolver constant.
4. **Simplified pulse-family membership** to two deterministic rules (IOC Jaccard ≥ 0.7
   with ≥ 3 non-hub IOCs each, or identical CVE set + identical normalized name),
   removing the fuzzy name-similarity shortcut.
5. **All formula constants declared tunable defaults** via the existing
   `correlation/config.py` env pattern rather than hardcoded semantics.
6. **Versioning clarified** (header): current engine is already "v2"; this plan
   targets `ENGINE_VERSION = "3.0"` despite the requested file name.

---

## 21. Open questions requiring maintainer decisions

1. **Confidence regression communication (PR-4).** Campaign confidences will visibly
   drop once size/severity stop inflating them. Recommended: ship with changelog +
   factor vector in the same release train (PR-4 + PR-5 together), no toggle flag.
   Confirm acceptance of the one-time visible drop.
2. **Pulse-family thresholds (PR-9).** Defaults: Jaccard ≥ 0.7, ≥ 3 non-hub IOCs per
   pulse. Should these be validated against the operator's real OTX mirror before
   PR-9 lands (recommended), or accepted as shipped defaults?
3. **Suppression migration on campaign dedup (PR-9).** Recommended: old campaign-id
   suppressions of any family member map to the family campaign. Alternative
   (drop them) loses analyst work. Confirm.
4. **Confirm-link UI (PR-12).** Worth drawer space on a solo-analyst install, or ship
   API-only first and add the button with PR-13's metrics page?
5. **Half-life defaults (PR-8).** IP 30 d / URL 60 d / DOMAIN 120 d / HASH 365 d are
   defensible defaults but unvalidated against a real mirror. Accept as env-tunable
   defaults, or calibrate first?
6. **Feed ordering change (PR-13 / D9).** Gating the campaign-peer-of-pinned boost on
   confidence ≥ MEDIUM + lifecycle ∈ {active, emerging} changes feed order — a
   product decision, not just a correctness fix. Confirm.
7. **Scale verification.** §15 row-count assumptions could not be verified during the
   audit (sandbox limitation). Run the row counts before PR-9 to confirm the pulse-
   family budget.
