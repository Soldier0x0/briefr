# PHASE 3 — Correlation · Risk Scoring · Detection · AI · Scheduler & Background Jobs · Caching

*Refreshed from pinned baseline `ff23c18a4925b3b7082a2b1d1600884324d90d02`; re-verified on
current branch HEAD `267f174b`. Engines: `correlation/`, `scoring/`, `detection/`,
`ai/`, `scheduler.py` (+ `scheduler_locks.py`), `read_cache.py` + `db/cache.py`.*

---

## Executive Summary

BRIEFR's engines are its differentiator and they are, individually, thoughtfully built. The
**correlation engine** (v2, `ENGINE_VERSION`-tagged) is deliberately DB-backed with **no
external calls on the on-demand path** — OTX/IOC data is pre-cached by nightly jobs — with a
feedback/confidence/suppression subsystem. The **risk engine** is a deterministic six-component
weighted model (v1.1b). The **detection engine** spans Sigma/YARA/SIEM/Nuclei generation plus a
composer. The **AI layer** is a genuinely mature task-based multi-provider LLM router with
failover chains, circuit breakers, per-job provider skipping, quota, and an operations recorder.
The **scheduler** runs 31 jobs with per-job `asyncio.Lock`s.

The systemic risks are about **correctness-under-scale and heuristic accuracy**, not basic
function. Current HEAD improved adjacent durability and documentation (single scheduler owner via
`BRIEFR_SCHEDULER_ENABLED`, Procrastinate job-ownership registry, stack-backfill idempotency), but
the Phase 3 engine risks still reproduce: (1) the hot read cache is **process-local and unbounded**;
(2) scheduler job locks are still **process-local `asyncio.Lock`s**; (3) actor/sector attribution
still uses keyword/substring matching; (4) scheduler lock-id coverage is still mostly convention;
(5) scoring still has FE/BE duplication risk (Phase 1 F1.3 / F3.5), although the API is now the
canonical runtime source.

**Overall Score: 7 / 10 (unchanged).** Single-node posture is stronger than the raw score because
current docs and flags enforce one scheduler owner; horizontal-scale readiness remains below the
product baseline until cache/lock state is externalized.

---

## Findings

| ID | Status | Priority | Class | Current disposition |
|---|---|---:|---|---|
| F3.1 | OPEN | HIGH | Architectural | `read_cache.py` remains a plain process-local dict with no max size, LRU, single-flight, or metrics. |
| F3.2 | OPEN · mitigated single-owner | HIGH | Architectural | `BRIEFR_SCHEDULER_ENABLED=0` supports API-only workers, but locks are still per-process. |
| F3.3 | OPEN | MEDIUM | Architectural | Actor/sector matching still depends on sector strings and substring/structured-sector overlap. |
| F3.4 | OPEN · partial guards | MEDIUM | Quick Win | Job catalog and Procrastinate ownership are tested; scheduler lock-map parity is not. |
| F3.5 | OPEN · partial mitigation | HIGH | Architectural | Backend risk/threat APIs are canonical; frontend still ships fallback weights and local threat logic. |
| F3.6 | OPEN · confirmed | MEDIUM | Architectural | LLM circuit, quota, and per-job skip state are process-local module state. |
| F3.7 | OPEN · partial tests | MEDIUM | Quick Win | Sigma/YARA/composer tests exist, but no golden-output/validator gate for all generated content. |
| F3.8 | OPEN · partial tests | MEDIUM | Architectural | `_recover_db_transaction()` still exists; precompute failure tests reduce but do not remove the smell. |
| F3.9 | OPEN | LOW | Quick Win | No hit/miss/size/eviction observability for the hot read cache. |

### F3.1 — Hot read cache is process-local and unbounded (no eviction, no cross-process share) · Status: OPEN · Priority: HIGH · Architectural
- **Location:** `backend/read_cache.py` — `_store: dict[str, tuple[float, Any]]`,
  `DEFAULT_TTL_SECONDS = 45.0`, `cached_read()`. No max size, no LRU, no eviction beyond
  per-key TTL-on-read.
- **Description:** The in-process TTL cache never evicts stale keys unless they're read again;
  a growing key space (per-CVE, per-filter cache keys) accumulates entries indefinitely →
  memory growth. It's also per-process: with `uvicorn --workers N` or multiple replicas, each
  worker has its own cache, so hit rates drop and upstream/DB load multiplies, and different
  workers can serve different snapshots of the same endpoint.
- **Why it matters:** "Deployed to thousands of organizations" implies some run multi-worker or
  behind a horizontally-scaled deployment; a per-process unbounded cache is both a memory-leak
  vector and a correctness/consistency hazard at scale.
- **Evidence:** `read_cache.py` is a bare dict + monotonic clock; comment "No Redis — dict +
  monotonic clock"; no size cap or eviction sweep.
- **Risk:** Unbounded memory; inconsistent responses across workers; cache-stampede on cold keys.
- **Recommended solution:** (a) Bound the cache: add a max-entry LRU (e.g. `cachetools.TTLCache`
  or a small LRU) and a periodic sweep of expired keys. (b) Add single-flight/coalescing so
  concurrent misses on the same key await one build (stampede protection). (c) For multi-replica
  deployments, make the cache backend pluggable (in-process default; optional Redis) OR document
  that BRIEFR is single-process-per-node and enforce `workers=1` guidance. (d) Emit hit/miss
  metrics.
- **Acceptance criteria:** Cache size is bounded under a load test that inserts >N distinct keys;
  concurrent identical misses trigger one `build()`; hit-rate metric exposed.
- **Effort:** Medium. **Type:** Architectural.

### F3.2 — Scheduler locks are in-process `asyncio.Lock`s → no protection across workers/replicas · Status: OPEN (mitigated single-owner) · Priority: HIGH · Architectural
- **Location:** `backend/scheduler_locks.py` (`_LOCKS: dict[str, asyncio.Lock]`),
  `backend/scheduler.py` (each job wraps `async with get_lock(...)`; also relies on APScheduler
  `max_instances=1` for lockless jobs).
- **Description:** Job overlap is prevented by `asyncio.Lock` and APScheduler `max_instances=1`,
  both of which are **process-scoped**. Current production guidance explicitly supports
  `BRIEFR_SCHEDULER_ENABLED=0` API-only workers and one scheduler owner, which mitigates normal
  deployments. If two processes/replicas are started with the scheduler enabled, they can still run
  `nvd_incremental_sync`, `nightly_correlation`, `scheduled_backup`, etc. simultaneously →
  duplicate ingest, double correlation writes, racing backups.
- **Why it matters:** This is the core reason the Procrastinate/durable-job migration exists
  (Phase 2 F2.2). Until it lands, safe horizontal scaling requires exactly one scheduler owner,
  which is an easy operational mistake to make.
- **Evidence:** locks are `asyncio.Lock()`; `main.py` starts the scheduler in every process
  unless `BRIEFR_SCHEDULER_ENABLED=0`, and logs the API-only-worker path when disabled.
- **Risk:** Double-writes / corrupted ingest / racing backups under horizontal scale.
- **Recommended solution:** Short-term: document and enforce a single scheduler owner (leader
  election, or the `BRIEFR_SCHEDULER_ENABLED=0` API-only worker pattern already present — make it
  the default for all-but-one replica) and add a startup log stating scheduler ownership.
  Long-term: move mutual exclusion to **Postgres advisory locks** (or Procrastinate's durable
  queue) so exclusion is cluster-wide. Complete F2.2.
- **Acceptance criteria:** With two processes started, a given job body executes at most once per
  schedule tick (integration test with a DB advisory lock); ownership is logged at startup.
- **Effort:** Medium–Large. **Type:** Architectural.

### F3.3 — Actor/sector attribution is free-text keyword matching (brittle, misclassification-prone) · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** `backend/correlation/engine.py` — `SECTOR_KEYWORDS` (11 sectors × keyword lists),
  `extract_sectors_from_text()`, `find_actor_sector_correlation()`.
- **Description:** Sector relevance (which feeds actor/sector correlation and can escalate
  operational priority) is derived by substring/keyword matching over actor description text.
  Keyword matching has no negation handling, no disambiguation ("bank" in "riverbank"), and
  depends on upstream phrasing; it will both over- and under-match.
- **Why it matters:** Attribution errors propagate into correlation confidence and risk
  escalation shown to analysts — a false "your sector is targeted" signal erodes trust and can
  misdirect response, the opposite of the product's purpose.
- **Evidence:** `SECTOR_KEYWORDS` literal lists; `extract_sectors_from_text` is keyword-based.
- **Risk:** Misattributed sector targeting → wrong prioritization; analyst distrust.
- **Recommended solution:** (a) Add a confidence tier to keyword matches and surface it in the UI
  (already partly present via `confidence.py` — ensure sector match confidence is distinct and
  visible). (b) Prefer structured signals where available (ATT&CK group→sector mappings, curated
  actor-sector tables) over free-text scraping; use keywords only as a low-confidence fallback.
  (c) Add regression fixtures with known actor descriptions and expected sectors, including
  negative cases. (d) Consider the existing LLM router for a bounded, cached classification of
  actor→sector with a human-auditable record.
- **Acceptance criteria:** Sector matches carry an explicit confidence; a fixture suite covers
  true/false positives; UI distinguishes high- vs low-confidence sector claims.
- **Effort:** Medium. **Type:** Architectural.

### F3.4 — Scheduler lock-id ↔ job-id ↔ admin-router coupling enforced by convention, not a test · Status: OPEN (partial guards) · Priority: MEDIUM · Quick Win
- **Location:** `backend/scheduler_locks.py` (keys "must match the `id=` strings passed to
  `scheduler.add_job()` exactly"), `backend/scheduler.py` (`add_job(..., id=...)`),
  `backend/routers/admin.py` (uses the lock mapping for job-status/LOCKED UI). CLAUDE.md danger
  zone 2 calls this out explicitly.
- **Description:** Three files must agree on the exact set of job-id strings; drift (a renamed
  job, a new job without a lock, a stale lock) is caught only by human vigilance. Some jobs
  intentionally have no lock (rely on `max_instances=1`) — the distinction is a comment.
- **Why it matters:** A silent desync means a job runs unlocked (overlap) or the admin UI shows
  wrong LOCKED state — both are the kind of bug that surfaces only in production incidents.
- **Evidence:** header comment in `scheduler_locks.py` enumerates lockless jobs by hand. Current
  guards cover adjacent surfaces only: `tests/test_job_catalog_coverage.py` checks frontend
  `JOB_CATALOG` vs `scheduler.add_job(id=...)`, and `tests/test_job_ownership_registry.py` checks
  APScheduler vs Procrastinate namespace ownership. Neither asserts that every scheduler job id is
  in `_LOCKS` or an executable `LOCKLESS_JOBS` allowlist.
- **Recommended solution:** Add a test that introspects the registered APScheduler jobs at
  startup and asserts: every job id either has a `_LOCKS` entry or is on an explicit
  `LOCKLESS_JOBS` allowlist; no `_LOCKS` key is orphaned; admin-router's job list matches. Make
  the allowlist a real constant, not a comment.
- **Acceptance criteria:** Renaming a job id without updating locks fails a test; orphan locks
  fail a test.
- **Effort:** Quick Win. **Type:** Quick Win.

### F3.5 — Risk scoring duplicated across backend and frontend (carried from F1.3) · Status: OPEN (partial mitigation) · Priority: HIGH · Architectural
- **Location:** `backend/scoring/risk.py` (`calculate_risk_score`, v1.1b weights) vs
  `frontend/src/scoring/riskScore.js` (`calculateThreatScore`, duplicated `DEFAULT_WEIGHTS`).
- **Description:** See Phase 1 F1.3. The runtime direction is improved: `POST
  /api/cves/{id}/risk` computes Threat Score, Environment, Operational Priority, and legacy
  `risk.py` output server-side, while `GET /api/config/risk` sources weights from backend
  constants. The engine-level concern remains because `frontend/src/scoring/riskScore.js` still
  ships fallback `DEFAULT_WEIGHTS` and local `calculateThreatScore` / OP helper logic, so stale
  fallback or client-only paths can drift from API/PDF.
- **Why it matters:** Risk score is the engine's primary output; two implementations guarantee
  eventual drift.
- **Evidence:** `backend/scoring/risk.py:get_risk_weights()` is covered by
  `tests/test_config_risk_endpoint.py`; the frontend still declares `DEFAULT_WEIGHTS` and local
  threat/priority helpers in `riskScore.js`.
- **Recommended solution:** Frontend renders server-provided components/score/band only; delete
  client recomputation/fallbacks where possible, or generate a shared contract. Keep the backend
  config endpoint but add a FE/BE fixture parity gate for threat/priority semantics, not only
  backend weight exposure.
- **Acceptance criteria:** Weight change in `risk.py` without FE update fails CI; FE score == API
  score for a fixed fixture.
- **Effort:** Small (guard) / Medium (unify). **Type:** Architectural + Quick-Win guard.

### F3.6 — LLM router is strong, but circuit-breaker/quota state is process-local too · Status: OPEN (confirmed) · Priority: MEDIUM · Architectural
- **Location:** `backend/ai/llm_router.py`, `ai/llm_session.py` (`provider_circuit_open`,
  `mark_provider_empty_response`, `is_provider_skipped_in_job`), `ai/quota.py`,
  `resilient_client.py` (`CircuitOpenError`, `record_source_success`).
- **Description:** The failover design is correct (ordered chains, one attempt/provider,
  never-parallel-per-CVE, circuit breaker). Current HEAD confirms circuit-open state, quota
  snapshots, and per-job provider-skip live in process memory. In a multi-worker deployment each
  worker re-learns provider outages independently, and quota/advisory warnings can diverge across
  processes.
- **Why it matters:** Provider outage handling and quota are cost/reliability controls; if
  process-local, a scaled deployment burns extra failed calls and can exceed provider quotas.
- **Evidence:** `resilient_client._health` is a module-level dict; `ai/quota._snapshots` is a
  module-level dict; `ai/llm_session._job_empty_providers` is a `ContextVar`.
- **Recommended solution:** Ensure quota/circuit state that must be global is persisted (DB or a
  shared store); document which signals are intentionally per-process. Since LLM work runs in the
  scheduler (single owner today), the impact is bounded now — revisit alongside F3.2/F2.2.
- **Acceptance criteria:** Quota counters are consistent across workers; circuit state backing is
  documented.
- **Effort:** Medium. **Type:** Architectural.

### F3.7 — Detection generation is template-driven; needs golden-output regression coverage · Status: OPEN (partial tests) · Priority: MEDIUM · Quick Win
- **Location:** `backend/detection/` — `sigma_generator.py` (714), `siem_queries.py` (558,
  `{CVE_ID}` placeholder templating), `yara_generator.py`, `composer.py`, `class_router.py`,
  `nuclei_parser.py`.
- **Description:** Detections (Sigma/YARA/SIEM/Nuclei) are generated from templates + extracted
  artifacts. Generated security content must be *syntactically valid and stable*; a silent
  template regression ships broken detections to defenders.
- **Why it matters:** A broken Sigma/YARA rule is worse than none — it gives false assurance.
  This is the engine whose defects most directly harm the end user's security posture.
- **Evidence:** placeholder templating (`"{CVE_ID}": cve_id or "CVE-XXXX-XXXXX"`); large
  generator files. Current tests cover Sigma CWE templates, YARA hash helpers, Nuclei parsing, and
  composer artifact injection, but they are assertion-style unit tests rather than a golden-output
  suite with external Sigma/YARA validators.
- **Recommended solution:** Add golden-file regression tests: for a fixed set of CVE fixtures,
  snapshot generated Sigma/YARA/SIEM output and diff on change (force intentional review). Where a
  validator exists (e.g. `sigma` CLI / YARA compile), run it in CI against generated samples.
- **Acceptance criteria:** Generated rules compile/validate in CI; output changes require an
  updated golden snapshot.
- **Effort:** Quick Win–Medium. **Type:** Quick Win.

### F3.8 — Nightly correlation transaction recovery is bespoke (`_recover_db_transaction`) · Status: OPEN (partial tests) · Priority: MEDIUM · Architectural
- **Location:** `backend/correlation/engine.py` — `_recover_db_transaction()`,
  `run_nightly_correlation()`, `_compute_correlation_for_cve()`.
- **Description:** The nightly correlation job has custom transaction-recovery logic, implying it
  can leave the DB session in a bad state mid-run. Bespoke recovery is a smell that the write
  boundary isn't cleanly transactional (ties to Phase 2 F2.9).
- **Why it matters:** A partially-applied nightly correlation produces inconsistent analyst views
  until the next successful run; hand-rolled recovery is easy to get subtly wrong.
- **Evidence:** `_recover_db_transaction()` is still called repeatedly in `run_nightly_correlation`.
  `tests/test_correlation_precompute.py` now covers snapshot persistence under one failure path,
  but the bespoke recovery helper remains the write-boundary smell.
- **Recommended solution:** Wrap per-CVE correlation writes in explicit savepoints so one failed
  CVE rolls back only its own work without poisoning the batch; remove ad-hoc recovery. Add a
  test that a mid-batch failure leaves prior CVEs committed and the failing one absent (not
  partial).
- **Acceptance criteria:** Injected mid-batch failure yields consistent state (no partial rows);
  no bespoke session-recovery needed.
- **Effort:** Medium. **Type:** Architectural.

### F3.9 — No cache observability (hit-rate/eviction/size) across either cache tier · Status: OPEN · Priority: LOW · Quick Win
- **Location:** `read_cache.py`, `db/cache.py` (feed cache TTLs `_IOC_TTL_HOURS=6`,
  `_CIRCL_CACHE_TTL_HOURS=168`).
- **Description:** Neither cache exposes hit/miss/size/eviction metrics, so cache effectiveness
  and the memory risk in F3.1 are invisible in production.
- **Recommended solution:** Add counters (hits, misses, size, evictions) surfaced via the metrics
  layer / an admin diagnostics endpoint. Feeds Phase 6 (Performance) and Phase 8 (Observability).
- **Acceptance criteria:** Cache hit-rate visible in admin/metrics; alertable memory size.
- **Effort:** Quick Win. **Type:** Quick Win.

---

## Resolved since last audit

No F3.1–F3.9 findings are fully resolved on current HEAD. Adjacent mitigations landed (single
scheduler owner flag, Procrastinate ownership registry, stack-backfill idempotency, risk config
endpoint, detection unit coverage), but each original finding still has a live source-code basis.

## Overall Score: **7 / 10**

| Sub-audit | Score |
|---|---|
| Correlation Engine | 7 / 10 |
| Risk Scoring Engine | 7 / 10 |
| Detection Engine | 7 / 10 |
| AI Integration | 7.5 / 10 |
| Scheduler & Background Jobs | 6.5 / 10 |
| Caching Strategy | 5.5 / 10 |

## Strengths
- Correlation is DB-backed with zero external calls on the on-demand path (pre-cached nightly) —
  the right latency/reliability boundary; versioned engine with confidence/feedback/suppression.
- Mature LLM router: ordered per-task failover, circuit breakers, per-job provider skip, quota,
  operations recorder; LLM/ML work runs off the request path in the scheduler.
- Deterministic, testable risk model; broad detection generation (Sigma/YARA/SIEM/Nuclei).
- Per-job lock discipline and `max_instances=1` show overlap-awareness.
- Current owner flags and job-ownership tests reduce accidental dual-job-system overlap.

## Weaknesses
- Both caches process-local + unbounded (F3.1); scheduler locks in-process only (F3.2).
- Keyword-based sector attribution (F3.3); convention-only lock-id sync (F3.4).
- Duplicated risk scoring (F3.5); possibly process-local quota/circuit state (F3.6).

## Immediate Action Items
1. Bound `read_cache` (max size + eviction sweep) and add single-flight (F3.1).
2. Add the scheduler job-id/lock-id parity test + explicit `LOCKLESS_JOBS` allowlist (F3.4).
3. Add the risk-weight FE/BE parity contract test (F3.5).
4. Add golden-file + validator tests for generated detections (F3.7).

## Long-Term Recommendations
1. Move mutual exclusion to Postgres advisory locks / durable queue (F3.2) and enforce single
   scheduler ownership until then.
2. Make cache backend pluggable (Redis) for multi-replica deployments (F3.1).
3. Add confidence tiers + structured sources to attribution (F3.3); transactional per-CVE
   correlation writes (F3.8).
4. Persist global quota/circuit state where required (F3.6).

## Production-Readiness Assessment (Phase 3 areas)
**Conditionally ready — 7/10, single-node.** The engines are correct and well-designed for a
**single-process / one scheduler owner** deployment, which is the documented self-hosted footprint.
The blocking risks appear specifically **under horizontal scale**: process-local caches (F3.1),
in-process scheduler locks (F3.2), and process-local LLM circuit/quota state (F3.6) can cause
double-writes, inconsistent reads, or repeated failed provider calls if an operator runs multiple
scheduler-enabled replicas. Attribution accuracy (F3.3) and detection-output stability (F3.7) are
quality risks that affect analyst trust regardless of scale. Recommend: ship single-node now with
explicit scaling guidance; treat F3.1/F3.2/F3.6 as prerequisites for supported horizontal scale.
