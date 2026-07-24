# ADR-004 — Move correlation off the request path (precomputed edges)

## Status

**ACCEPTED — 2026-07-14.** Decides the fix for the CRITICAL reliability finding
REL-1/REL-2 (correlation on request path). Continues the `docs/decisions/ADR-00N`
sequence. Relates to ADR-002 (Operational Priority, which depends on correlation
for escalation).

## Relationship to the correlation-engine-v2 spec (what this ADR amends)

The v3 correlation program is **complete** (PR-1…PR-13, #473…#513). This ADR is a
**new increment on top of that shipped work**, not a reopening or rewrite of its PR queue.
Precisely:

- **Supersedes spec §3.3 ("On-demand per CVE")** as the *computation* model: per-CVE edge
  computation moves from request time (`engine.py::get_correlation_for_cve`, 6 h
  `feed_cache`) to a scheduler job writing precomputed rows. The request path becomes a
  cheap indexed read. The spec's *scoring semantics* (degree-penalized confidence from
  PR-3/PR-4, receipts, hub suppression, `priority.py` caps) are **unchanged** and are
  reused by the precompute job.
- **Consistent with the spec's central principle 4** ("no new services, daemons … 
  everything rides the existing nightly job"): the precompute is a scheduler job in the
  existing APScheduler, not a new daemon.
- **Consistent with the spec's NOT-in-scope list** ("materialized views"): the decision
  below prefers a plain application table over a matview for the same reasons the spec
  gives (SQLite testability, no refresh locks).
- **Builds on shipped infrastructure:** `ioc_degree` (spec PR-3, #487) and
  `hub_suppress.py` are prerequisites this ADR consumes, not new work.

The spec remains the authority on correlation *semantics* (confidence, evidence, campaign
lifecycle); this ADR is the authority on *where the computation runs*. If they conflict on
that question, this ADR wins.

## Context

The correlation feature and the drawer's Operational-Priority hero **time out on
production-scale data**. Verified 2026-07-14 on a restored production DB (idle pool,
scheduler off, post-`ANALYZE`):

- `GET /api/cves/{id}/correlation` → **~61s**, returns `correlation_unavailable` for
  hub-IOC-heavy CVEs (request-ids `d402be3a60944d2d`, `798ee0970b184e80`). It succeeds for
  low-degree CVEs, so it is **data-dependent**.
- `POST /api/cves/{id}/risk` → **~61s** because operational-priority escalation runs the same
  correlation query; the OP hero is gated on that response and therefore **never renders**
  (returns `null`), so the drawer opens without the ADR-002 headline.

**Root cause:** the shared-IOC query self-joins `otx_pulse_iocs` (**132,802 rows**) on
`(ioc_type, ioc_value)` across `otx_cve_pulses` (**49,209 rows**). Hub IOCs shared by many
pulses produce O(n²) fan-out that exceeds the 60s DB command timeout. Indexes are present;
this is a cardinality/algorithm problem. Critically, this heavy work runs **on the request
path**, violating `docs/CONTRIBUTOR_RULES.md` danger zone 6 ("heavy work never runs on the request path").

## Decision

1. **Precompute correlation edges in the scheduler**, not per request. A scheduler job
   computes and persists per-CVE correlation results (campaigns / shared-infra / actor /
   temporal) into a dedicated store; the request path performs a cheap indexed read.
2. **Degree-cap / suppress hub IOCs before joining.** Use the existing `ioc_degree` table to
   exclude or down-weight indicators above a degree threshold, so a single popular IP/domain
   can't fan a CVE out to thousands of pulses. Push `LIMIT` and degree filters into SQL.
3. **Decouple the Operational-Priority hero from correlation.** Compute + return OP / Threat /
   Environment from cheap signals (KEV/EPSS/CVSS/asset) synchronously so the hero renders
   < 1s; apply correlation-based escalation asynchronously (or from precomputed edges) once
   available. `escalated_by_correlation` becomes an eventually-consistent enrichment, never a
   blocker.
4. **Honest states** when precomputed data is missing/stale: return an explicit
   "computing"/"unavailable" status the UI renders distinctly from "no correlations"
   (UI plan E1-3), including a request-id.
5. **Preserve the public API shape** of `/correlation` and `/risk` so the frontend needs no
   contract change; only latency and the internal computation location change.

## Migration strategy

- Introduce the precompute job + storage behind a **feature flag** (e.g.
  `CORRELATION_PRECOMPUTE_ENABLED`), defaulting off, so rollout is controlled and instantly
  reversible to the current on-request path.
- If persistence requires schema, add a **new forward-only Alembic migration** and additive
  table(s) (`docs/CONTRIBUTOR_RULES.md` — never edit an applied migration). Keep SQLite
  test-parity per the `db/` danger-zone rules.
- Backfill via the scheduler; measure p95 for `/correlation` and `/risk` on the restored
  production dataset before/after; assert budgets (p95 `/correlation` < 2s; OP hero < 1s).
- Flip the flag on once budgets are met and review comments are addressed.

## Risks

- **Staleness:** precomputed edges lag live pulses — acceptable for correlation; document the
  refresh cadence and show freshness in the UI.
- **Storage growth:** bounded by degree-capping + retention (align with the existing
  `cache_retention_cleanup` job).
- **Semantic drift** from degree-capping (dropping hub IOCs may hide weak links) — validate
  against shipped correlation v3 semantics; expose suppressed-edge
  counts (the spec already tracks `hub_suppressed_edge_count`).
- **Scheduler load:** run within existing `SCHEDULER_DB_CONCURRENCY`; ensure lock ids stay in
  sync with `routers/admin.py` (`docs/CONTRIBUTOR_RULES.md` danger zone 2).

## Alternatives considered

1. **Just raise the 60s command timeout.** Rejected — hides the problem, ties up connections,
   still slow for users, risks pool exhaustion.
2. **Add/adjust indexes only.** Rejected — indexes already exist; the cost is fan-out
   cardinality, not lookup.
3. **Materialized view for the self-join.** Viable variant of "precompute"; a scheduler job
   writing an application table is preferred for degree-capping logic and testability, but a
   matview is an acceptable implementation detail.
4. **Compute on request with a hard `LIMIT` + degree filter (no precompute).** Partial
   mitigation; may bring many CVEs under budget but remains request-path heavy work and risks
   truncated/inconsistent results. Rejected as the primary fix; acceptable as an interim.

## Future roadmap

- Correlation graph visualization (safe once reads are cheap).
- Incremental edge updates on ingest rather than full recompute.
- Correlation quality metrics surfaced in admin (ties to `correlation_metrics`).

## Consequences

- The flagship feature and the ADR-002 hero become fast and reliable regardless of a CVE's
  IOC degree. Correlation becomes eventually-consistent (a deliberate tradeoff). One new
  additive table/migration and one scheduler job are introduced when implemented (not by this
  doc). Owned on the reliability track, parallel to the UI modernization effort.
