# ADR-002 — BRIEFR scoring axes and Operational Priority

## Status

**ACCEPTED — 2026-07-09.** Supersedes the "scoring surfacing is open / needs
browser validation" framing in `docs/BRIEFR_ARCHITECTURE_REVIEW_2026-07.md` §4.
The core scoring semantics are decided here from repository evidence. Browser
validation may later tune presentation and threshold constants; it does **not**
block this decision. Implementation is task **M1** (deterministic).

## Context

BRIEFR's analyst Overview headline is the BRIEFR Risk Score v1.1b `total` — a
single additive 0–100 blend of six components. The review (PR #345 §4) flagged a
semantic failure. This ADR verifies it in code and decides the scoring
architecture. Constraints (non-negotiable): deterministic, explainable,
versioned, testable, backend/frontend consistent, **LLM-independent**; EPSS is
consumed, never re-derived.

## Current implementation (verified in code)

`backend/scoring/risk.py::calculate_risk_score` — v1.1b, weights sum 1.00:

| Component | Weight | Raw source |
|-----------|--------|-----------|
| Asset | 0.35 | `resolve_asset_component` (`scoring/asset_match.py`) |
| KEV | 0.25 | `_kev_score_v11b` (recency tiers 0.84–1.0) |
| EPSS | 0.15 | `_num(epss_score, 0.0)` (missing → 0.0) |
| Exploit | 0.10 | `_exploit_score_v11b` (metasploit 1.0 / weaponised 0.88 / poc 0.55 / has_poc 0.35) |
| CVSS | 0.10 | `cvss_score / 10` |
| Momentum | 0.05 | `calculate_momentum` (EPSS trend + OTX/KEV recency) |

`total = round(Σ raw·weight·100, 0.1)` — pure additive, no compounding.

**Three deterministic scores exist:**
1. **Risk Score v1.1b** — the Overview headline. Asset-inclusive.
2. **Correlation Priority** (`correlation/priority.py`) — 0–100 from
   campaign/infrastructure/actor/temporal signals; returned by `/correlation`.
3. **Investigation Score** (`scoring/investigation.py`) — fuses
   `risk_total·0.45 + correlation_priority·0.40 + intel·0.15`; served by
   `GET /api/cves/{id}/investigation-score`. Frontend `api.js`
   `fetchCVEInvestigationScore` is defined but **has zero component callers**
   (verified) — the score is **orphaned**.

**Inputs are persisted `cves`/`kev_deadlines` columns** (`is_kev`, `epss_score`,
`has_poc`, `cvss_score`, `affected_products`, `cpe_matches`) — not live
enrichment calls. A transient provider failure therefore cannot move the score
mid-request.

**Backend/frontend parity:** `frontend/src/scoring/riskScore.js` mirrors the
weights and asset tiers. It already classifies exposure display into `NOT_LOADED`
/ `NO_MATCH` / graded tiers (`getAssetExposureStatus`, `inferAssetMatchSemantics`)
and labels the no-profile case "EXPOSURE UNKNOWN" with a `formulaNote`:
"0.500 × 35% × 100 = 17.5 pts (neutral scoring input — not exposure probability)."

## Semantic failure (verified, precisely scoped)

`resolve_asset_component` returns:

- **No profile loaded → `DEFAULT_ASSET_UNKNOWN = 0.5`** → `0.5·0.35·100 = 17.5`
  points folded into the headline `total`.
- **Profile loaded, authoritative no match → `0.0`** → `0` points.

So **UNKNOWN environment banks 17.5 phantom "positive" points that a proven
NO-MATCH does not.** The failure is **not** that loading a profile can lower
priority — a proven NO-MATCH *legitimately* reducing urgency is correct. The
failure is that **"we don't know" is encoded as fabricated positive numeric
evidence**, and that the single headline number conflates two different
questions (how dangerous is this vuln? vs does it affect me?). The frontend
already narrates this as a "placeholder," which is an admission that the number
is not meaningful — the fix is to stop banking it, not to re-label it.

## Decision drivers

1. Deterministic, explainable, reproducible from stored inputs.
2. "Unknown" must never masquerade as evidence.
3. Threat (danger) must be legible independently of environment (relevance).
4. Confirmed exploitation (KEV) must dominate a low probabilistic EPSS.
5. Fuzzy product matches must not read as vulnerable-version proof.
6. Correlation must inform urgency without double-counting or rewarding weak edges.
7. Minimal new surface; reuse the existing tested component functions.

## Options considered

- **A — keep one unified blended score.** Rejected: to keep one number when
  environment is unknown you must either fold a placeholder (the current bug) or
  renormalize (making no-profile and profile scores non-comparable). Conflation
  persists.
- **B — three co-equal visible numbers (Threat / Environment / Operational
  Priority).** Rejected as the default surface: three headline numbers create
  "which do I sort by?" ambiguity; an Operational Priority *number* alongside its
  own inputs is redundant.
- **C — internal axes → one derived Operational Priority number (review's
  in-principle pick).** Rejected *as naively specified*: deriving Operational
  Priority as `Threat·0.4 + Env·0.4 + Corr·0.2` is exactly the arbitrary
  decorative weighted average the drivers forbid — it recreates v1.1b's
  conflation with extra steps and re-imports the placeholder problem via a
  blended Env term.
- **D — CHOSEN.** Threat Score is the honest **primary number** (asset-independent,
  0–100, KEV-floored). Environment Relevance is a **categorical tier**, never a
  number folded into Threat. Operational Priority is a **deterministic rule-based
  P1–P4 band** derived from (Threat band × Environment tier), with Correlation as
  a **bounded escalation qualifier**. UNKNOWN environment yields a *provisional*
  priority off the Threat band — no fabricated points.

## DECISION

Adopt **Option D**. The analyst surface is: **Operational Priority band (P1–P4)**
as the "what do I do," **Threat Score (0–100)** as the "how dangerous" number,
and an **Environment Relevance tier** chip as the "is it mine." One number, one
tier, one band — each answering a distinct question, each deterministic.

### Threat Score semantics

**Question:** "How credible/imminent is exploitation of this vulnerability,
independent of my environment?" Range **0–100**, versioned **Threat v1.0**.

Reuse the v1.1b component raws (same KEV recency tiers, exploit graduation, EPSS
pass-through, CVSS/10, momentum) but **drop asset** and **renormalize the five
non-asset weights** (sum 0.65) to 0–100:

```
w_kev=0.25/0.65=.3846  w_epss=0.15/0.65=.2308  w_exploit=0.10/0.65=.1538
w_cvss=0.10/0.65=.1538  w_momentum=0.05/0.65=.0769
threat_additive = 100 · Σ (w_k · raw_k)
Threat = is_kev ? max(threat_additive, KEV_FLOOR=80) : threat_additive
```

- **KEV = contribution AND floor.** Recency lives in the additive contribution
  (`_kev_score_v11b` tiers); the **floor of 80** guarantees a CISA-confirmed
  exploited CVE is at least Critical-band, so confirmed exploitation dominates a
  near-zero EPSS. A higher additive (KEV + high EPSS + weaponised) wins over the floor.
- **EPSS = weighted contribution** (probabilistic likelihood), pass-through 0–1;
  **missing → 0** (never re-derived, never fabricated).
- **CVSS = weighted contribution only, never a floor** — high CVSS alone is
  theoretical severity, not active threat.
- **Exploit = graduated weighted contribution** (metasploit > weaponised > poc).
- **Momentum = small weighted contribution** (trajectory).

Threat bands: **CRIT ≥ 80 · HIGH 60–79 · MED 40–59 · LOW < 40.**

### Environment Relevance semantics

**Categorical tier + optional evidence score; never folded into Threat.**
Versioned **Environment v1.0**. Tiers (mapped from `resolve_asset_component` /
`asset_match_info`):

| Tier | Meaning | Source signal |
|------|---------|---------------|
| **CONFIRMED** | Exact vulnerable CPE version match | backend CPE score 100 / fuzzy "exact CPE match" (1.0) |
| **LIKELY** | Product/CPE matches, **version unverified** | CPE product 0.9 / OS 0.8 |
| **POSSIBLE** | Vendor or product-name match, version unverified | product 0.75 / vendor 0.65 |
| **WEAK** | Description/text overlap only | 0.35–0.55 |
| **NO_MATCH** | Profile loaded, authoritatively no match | 0.0 with profile |
| **UNKNOWN** | No profile loaded | profile is None |

**When new asset knowledge moves priority:** UNKNOWN→CONFIRMED/LIKELY **increases**
priority; UNKNOWN→NO_MATCH **decreases** it (legitimate); UNKNOWN→WEAK/POSSIBLE
leaves it ~**unchanged** (fuzzy ≠ proof). A fuzzy/product match is **never** treated
as vulnerable-version proof — only CONFIRMED (exact version) confers full weight.

### UNKNOWN environment behavior

UNKNOWN is a **state, not a number**. It contributes **zero** to Threat and does
not fabricate points. Operational Priority for UNKNOWN uses the **Threat band as
provisional priority**, flagged `provisional: true` ("environment unknown —
priority may change once a profile is loaded"). This is the option chosen from
review §7 ("Threat Score with UNKNOWN qualifier"). The prior review's claim that
"loading a profile must never lower operational priority" is **corrected**: a
proven NO_MATCH may lower it; only *fabricated positive evidence from UNKNOWN* is
forbidden.

### Correlation Priority interaction

Correlation is an **escalation qualifier on Operational Priority only** — never a
Threat input, never a weighted term. Rule: if the CVE is a member of an
**active or emerging** campaign with **≥1 high-confidence edge** (same-pulse +
shared hash/domain), escalate the base Operational Priority by **one band, capped
at P1, and only when the base is P2 or P3** (never lift P4 informational).
**Many weak edges** (IP-only, low confidence, stale lifecycle) → **no escalation**.
Correlation Priority (0–100) remains available separately in the Intel tab.

**Double-counting audit:** the anchor's KEV/EPSS/exploit feed **Threat only**;
correlation's KEV/exploit boosters come from **peer** CVEs and feed the
**escalation qualifier only** (as a capped one-band bump, not re-added points) —
distinct entities, no double count. Known minor overlap: OTX pulse recency
appears in the anchor's momentum (Threat, 5%) and, indirectly, in campaign
lifecycle; mitigated by gating escalation on **campaign structure** (≥2 members +
strong edge), not recency. Documented as a bounded limitation.

### Operational Priority semantics

**Question (accepted):** "How urgently should I investigate this CVE in my
environment right now?" Output: **band P1–P4** + `provisional` + `escalated_by_correlation`
+ `rationale`. Deterministic rule table (base), then correlation escalation:

| Threat ↓ / Env → | CONFIRMED | LIKELY | POSSIBLE/WEAK | UNKNOWN* | NO_MATCH |
|------------------|-----------|--------|---------------|----------|----------|
| **CRIT (≥80)**   | P1 | P1 | P2 | P1 | P3 |
| **HIGH (60–79)** | P1 | P2 | P2 | P2 | P3 |
| **MED (40–59)**  | P2 | P2 | P3 | P3 | P4 |
| **LOW (<40)**    | P3 | P3 | P4 | P4 | P4 |

\* UNKNOWN → `provisional: true`. Then: correlation escalation lifts base
P2→P1 or P3→P2 (capped P1; P4 not escalated). **P1 is reserved** for CONFIRMED
version match, genuine Critical threat, or a correlation-escalated High —
POSSIBLE/WEAK/LIKELY-unverified never reach P1 on match alone (guards the
"correct product, wrong version" trap).

**Sorting:** Operational Priority band (P1<P2<P3<P4) → Threat Score desc →
Environment tier rank → `cve_id` asc (stable, fully reproducible from stored
inputs). Coarse bands are intentional triage buckets; the Threat number + tier +
rationale disambiguate equal-band CVEs.

### Investigation Score decision — **DELETE**

The fused Investigation Score is **deleted** (route + `api.js`
`fetchCVEInvestigationScore` stub) in M1. Rationale: (1) its formula
(`risk·0.45 + correlation·0.40 + intel·0.15`) is precisely the arbitrary weighted
average this ADR rejects; (2) it re-imports the UNKNOWN=0.5 bug through
`risk_total`; (3) it double-counts OTX recency (momentum inside risk + intel
freshness); (4) it is orphaned dead code (zero callers). Its **intent** — one
triage headline fusing threat, environment, and correlation — is **adopted** as
the rule-based Operational Priority with correct, non-double-counting semantics.

## Scenario matrix

Threat computed with the formula above; raws per v1.1b component functions.

| # | Setup | Threat | Env | Corr | OP band | Rationale |
|---|-------|-------:|-----|------|---------|-----------|
| **S1** | CVSS 9.8, KEV(≤7d), EPSS 0.02, PoC, mom 0.8, no profile | additive 68.6 → **floor 80 (CRIT)** | UNKNOWN | — | **P1 provisional** | KEV floor carries; env unknown |
| **S2** | S1 + confirmed CPE version match | 80 (CRIT) | CONFIRMED | — | **P1** | confirmed + exploited |
| **S3** | S1 + authoritative NO match | 80 (CRIT) | NO_MATCH | — | **P3** | proven not yours → de-escalated (legit) |
| **S4** | CVSS 9.8, not KEV, EPSS 0.05, no exploit, mom 0.1, unknown | **17 (LOW)** | UNKNOWN | — | **P4** | high CVSS but no active threat |
| **S5** | CVSS 6.5, KEV(≤7d), EPSS 0.9, PoC, mom 0.8, confirmed | **83.8 (CRIT)** | CONFIRMED | — | **P1** | medium CVSS does not suppress real exploitation |
| **S6** | high threat (~85), weak fuzzy overlap, version unverified | 85 (CRIT) | POSSIBLE | — | **P2** | fuzzy ≠ proof; "verify version" flag; not P1 |
| **S7** | medium threat (~41), 1 strong active campaign edge | 41 (MED) | UNKNOWN | escalate | base P3 → **P2** | one strong edge escalates one band |
| **S8** | high threat (~65), many weak IP-only edges | 65 (HIGH) | UNKNOWN | none | **P2** | weak edges do not escalate |
| **S9** | low threat (~20), confirmed asset match | 20 (LOW) | CONFIRMED | — | **P3** | yours but not actively threatened → scheduled |
| **S10** | no profile, exploit enrichment pending, KEV(≤7d) EPSS 0.5 CVSS 8 | floor **80 (CRIT)** | UNKNOWN | — | **P1 provisional** | pending exploit = 0 contribution (not negative); FR1 flags provenance |

**Surprising/important:** S3 (loading a profile legitimately drops P1→P3 via
NO_MATCH — corrects the review's over-strong claim); S4 (a CVSS 9.8 reads
Threat 17 — the honest "theoretical" case, previously masked); S7 vs S8 (one
strong edge escalates, many weak edges do not — the asymmetry that stops weak-edge
inflation); S10 (pending enrichment never fabricates or subtracts).

## Backend contract (for M1)

- `scoring/threat.py` (or extend `risk.py`): `calculate_threat_score(cve, momentum_score) -> {version:"threat-1.0", score, band, components{kev,epss,exploit,cvss,momentum: {raw,weight,points}}, kev_floor_applied}`. Asset-independent.
- `classify_environment(cve, profile, backend_match_score) -> {tier, score, version_verified, evidence_label}` — reuse `resolve_asset_component`/`asset_match_info`; map to the six-tier enum; UNKNOWN when `profile is None`, NO_MATCH when profile present and score 0.
- `derive_operational_priority(threat_band, env_tier, corr_escalation) -> {band, provisional, escalated_by_correlation, rationale}` — pure rule table above.
- `correlation_escalation(correlation_result) -> bool` — true iff an active/emerging campaign with ≥1 high-confidence edge; read from the already-fetched correlation result (no new request-path correlation compute).
- API: the risk/overview response **additively** gains `threat`, `environment`,
  `operational_priority`. v1.1b `total`/`components` retained for **one release**
  as `legacy_risk_v11b` (for any external consumer), **removed from headline
  display**. `GET /api/cves/{id}/investigation-score` **deleted**.

## Frontend contract (for M1)

- `riskScore.js` mirrors `calculate_threat_score`, `classify_environment`,
  `derive_operational_priority` deterministically (parity tests over S1–S10).
- `OverviewTab.jsx` headline: **Operational Priority band** (primary chip) +
  **Threat Score** (0–100 number) + **Environment tier** chip. "WHY THIS SCORE"
  shows Threat components + Environment tier + correlation-escalation reason.
  Remove the blended v1.1b `total` from display. Delete `fetchCVEInvestigationScore`.

## Versioning strategy

Threat v1.0, Environment v1.0, Operational Priority v1.0 — emitted in the API.
Bump when floors, renormalized weights, band thresholds, or the priority rule
table change (each bump needs new tests + HANDOVER sign-off). EPSS never
re-derived. LLM output never influences any axis.

## Testing contract (for M1)

- Backend: `test_threat_score.py` (KEV floor ⇒ ≥80; CVSS-only ⇒ LOW; medium-CVSS
  + KEV + metasploit ⇒ CRIT; EPSS pass-through; EPSS/exploit missing ⇒ 0);
  `test_environment_tiers.py` (UNKNOWN vs NO_MATCH distinct; fuzzy caps at
  POSSIBLE/WEAK); `test_operational_priority.py` (full matrix + correlation
  escalation + provisional + sorting). Parity assertions for S1–S10.
- Frontend: `riskScore.test.js` parity for the matrix + tier classification.
- Browser validation (presentation only, non-blocking): render S1–S10; confirm no
  phantom 17.5; UNKNOWN shows provisional; NO_MATCH de-escalates; equal-band CVEs
  distinguishable by Threat + rationale.

## Migration / compatibility

Additive API fields; v1.1b endpoint/response unchanged for one release; investigation-score
deletion is safe (zero consumers, verified). No SQL, no scheduler, no deploy changes
(no danger zones touched). Forward-only; no migration needed.

## Adversarial validation

Attacked as a skeptical vulnerability analyst and a skeptical data scientist:

| # | Challenge | Outcome |
|---|-----------|---------|
| 1 | KEV + extremely low EPSS | KEV floor 80 ⇒ CRIT. **Drove the KEV-floor decision.** |
| 2 | CVSS 10 + no exploitation | Threat ~16 LOW — honest, not misleading (S4). |
| 3 | Medium CVSS + active exploitation at scale | KEV floor + EPSS + exploit ⇒ 84 CRIT (S5). **Reinforced KEV floor.** |
| 4 | UNKNOWN environment (most users) | Threat is the headline number (asset-independent); no fabricated 17.5; provisional flag. **The core fix.** |
| 5 | Incorrect fuzzy match | POSSIBLE/WEAK, capped P2, "verify version"; never P1/proof. |
| 6 | Correct product, non-vulnerable version | LIKELY(unverified) → P2 not P1; P1 needs CONFIRMED exact version. **Drove P1-reserved rule.** |
| 7 | Many weak common-infra edges | No escalation (gated on high-confidence campaign). |
| 8 | One strong active-campaign edge | Escalates one band, capped P1. **Asymmetry vs #7.** |
| 9 | Material EPSS change between refreshes | Threat rebands deterministically; reproducible from stored EPSS. |
| 10 | KEV added after scoring | Threat floors to 80; priority escalates. Expected direction. |
| 11 | Temporary enrichment-provider failure | Inputs are persisted `cves` columns ⇒ **Threat does not move**; FR1 flags provenance. |
| 12 | Equal OP band, different reasons | Within-band sort by Threat + rationale chips disambiguate; coarse bands intentional. |

**Strongest challenges:** #1/#3 (KEV vs low EPSS) and #6 (product vs version).
Both **changed the architecture**: they produced the KEV floor and the
"P1 reserved for CONFIRMED / genuine Critical" rule. #11 was neutralized by the
verified fact that inputs are persisted, not live.

**Known limitations / future-version triggers:** (a) Environment tiers depend on
imperfect CPE/fuzzy matching — a future Threat/Env v1.1 could use authoritative
CPE version-range evaluation to firm up LIKELY→CONFIRMED; (b) the minor
momentum↔campaign OTX-recency overlap; (c) band thresholds (80/60/40) and the KEV
floor (80) are deterministic constants a corpus study (fed by browser validation)
may tune — a tuning is a version bump, not a redesign.

## Consequences

Analysts get an honest, asset-independent Threat number, an explicit Environment
tier, and a deterministic P1–P4 action band. "Unknown" stops inflating scores;
proven no-match legitimately de-escalates; confirmed exploitation dominates;
fuzzy matches never masquerade as version proof; correlation informs urgency
without double-counting. Three overlapping scores collapse to one coherent
surface. Cost: M1 adds three small pure functions + display changes + parity
tests, and deletes orphaned code.

## Rejected alternatives

- Renormalizing v1.1b into one asset-inclusive number (Option A) — conflation persists.
- Three co-equal headline numbers (Option B) — sort ambiguity.
- Operational Priority as a weighted average of Threat/Env/Correlation (naive Option C) — recreates the blend it replaces.
- Keeping/refactoring the Investigation Score in place — carries its double-count and placeholder re-import.
- Making CVSS a floor — rewards theoretical severity as active threat.

## Implementation boundary for M1

M1 is **STANDARD CODING AGENT SUFFICIENT** and makes **zero** scoring-architecture
decisions — every semantic, threshold, floor, tier, and rule is fixed above. M1
implements the backend + frontend contracts, deletes the Investigation Score,
adds the tests, and browser-verifies presentation. M1 must **not** change v1.1b
weights, re-derive EPSS, involve an LLM, or alter the rule table without a new ADR.
