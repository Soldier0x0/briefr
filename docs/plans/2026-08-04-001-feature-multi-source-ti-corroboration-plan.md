---
artifact_contract: ce-unified-plan/v1
artifact_readiness: design-proposed
product_contract_source: ce-design
title: Multi-Source Threat Intelligence Corroboration
date: 2026-08-04
status: proposed — design review
last_reviewed: 2026-08-04 (initial); 2026-08-06 (line-ref audit only — design decisions left to owner, see §10 Q7/Q8)
reviewed_against: main @ correlation v2 phase 2 (confidence.py, ioc_graph.py, threatfox_corroboration.py), scheduler.py, source_rate_limits.py, db/schema_inventory.py
---

# Multi-Source Threat Intelligence Corroboration — Design

## POV (ce-pov)

**Grade: Adopt — phased, low risk**

BRIEFR already ships two proven ingestion archetypes and a deterministic confidence engine. The extension should **not** invent a third pipeline; it should make the existing ThreatFox **catalog-mirror → read-time corroboration** pattern source-agnostic and register additional catalog sources into it. This is the smallest surface that reuses every required seam:

- **Ingestion:** reuse `resilient_client` circuit/pacing, `tracking.has_quota`/`record_api_call`, per-source `PACING_PROFILES`, and the bulk `fetch → normalize → upsert` shape.
- **Scheduler:** reuse the `run_threatfox_sync` job template (`scheduler.py:924-960`), its lock registration (`scheduler_locks.py:13`), `_job_progress` / `_write_job_last_run`, and env-driven interval registration (`scheduler.py:2276-2286`).
- **Normalization:** reuse `correlation/ioc_normalize.py` (`normalize_ioc_type` `:47`, `normalize_ioc` `:111`, `refang` `:40`) — zero new canonical types.
- **Confidence:** reuse `confidence_for_ioc_edge` (`confidence.py:34-145`) and `corroboration_factor` (`freshness.py:60-63`) as-is. The function already accepts a `corroborated_by` list and its `corroboration_k = 1 + (1 if corroborated_by else 0)` (`confidence.py:114`) generalizes deterministically to `1 + len(corroborated_by)` — one independent upstream observation per receipt (see §3.5, where the tradeoff vs. distinct-source counting is called out as an open question).
- **Determinism:** no LLM anywhere on this path. Every step is a pure mapping (upstream type → canonical type), SQL, or a pure arithmetic factor. Source count → corroboration factor is a closed-form, capped function.

**Caveats that shape the work:**

1. **One unified mirror table, not one per source.** A single `ti_mirror_iocs(source, ref_id, …)` keeps joins, `retro_match`, and corroboration single-path and deterministic. ThreatFox is migrated onto it via backfill; a compat view keeps legacy readers working during transition.
2. **The corroboration seam is currently ThreatFox-hardcoded.** `batch_threatfox_hits` (`threatfox_corroboration.py:61-117`) and `retro_match.py:46-47` both name `threatfox_iocs`. Generalizing this is the core of the work; the source registry must be data-driven, not per-source `if` chains.
3. **`corroboration_factor` saturates.** With the current formula, three independent sources already cap the factor at 1.0. More sources than that add evidence depth (receipts) but no score headroom — set expectations in UI copy accordingly.
4. **CVE-pulse sources (OTX-style) are a separate, larger workstream.** Adding a *second* pulse graph source (e.g. MISP) touches `_shared_ioc_rows` (`ioc_graph.py:24-48`), campaign clustering, and `ioc_degree`; it is deliberately out of scope for this plan (see §8).

**Reversibility:** Tier 1 — additive. New table + new jobs; existing `threatfox_iocs` readers keep working via compat view until cutover. Rollback = revert migration + unregister jobs; no data destroyed.

---

## 1. Context — how the current architecture works

### 1.1 Two ingestion archetypes

| Archetype | Example | Fetch | Store | Consumed by |
|-----------|---------|-------|-------|-------------|
| **A — CVE-pulse source** | OTX | `feeds/otx.py` `fetch_cve_pulses`/`fetch_pulse_iocs` | denormalized mirror `otx_cve_pulses`, `otx_pulse_iocs`, `otx_pulses` (`db/init.py:436-490`) + `feed_cache` | correlation graph (`ioc_graph.py`), campaigns (`campaigns.py`), families, degree, retro-match |
| **B — Bulk catalog mirror** | ThreatFox | `feeds/threatfox.py` `fetch_threatfox_iocs` (bulk `get_iocs`) | `threatfox_iocs` app table (`db/threatfox.py:9-45`) | read-time corroboration (`threatfox_corroboration.py`), retro-match |

Both archetypes share the outbound HTTP and quota stack:

- `resilient_request`/`resilient_get` (`resilient_client.py:282-363`): per-source pacing queue, retries, circuit breakers, health registry.
- `has_quota`/`record_api_call` (`tracking.py:723`, `tracking.py:424`): hourly/daily/monthly accounting into `api_usage`.
- Per-source `PACING_PROFILES` (`source_rate_limits.py:62-175`) and API-key env map `_SOURCE_API_KEY_ENV` (`:198-211`).
- Scheduler wrapper per job: `get_lock` guard, `_job_progress`, `_write_job_last_run`, `max_instances=1`.

### 1.2 The corroboration seam (the part we generalize)

`find_shared_infrastructure_v2` (`ioc_graph.py:87-180`) computes shared-infrastructure edges between CVEs from `otx_pulse_iocs`. For each edge it:

1. fetches per-value confirmations from `ioc_cache` (`confirmations_for_iocs_batch`, `confirm.py:31-48`),
2. looks up ThreatFox mirror rows via `batch_threatfox_hits` (`threatfox_corroboration.py:61-117`), building `corroborated_by` receipts `threatfox:{ioc_id}` (`corroboration_receipt` `:23-24`),
3. calls `confidence_for_ioc_edge(ioc_type, confirmations=…, is_noise_ip=…, degree=…, observed_at=…, ingested_at=…, corroborated_by=…)` (`ioc_graph.py:112-120`).

`confidence_for_ioc_edge` (`confidence.py:34-145`) then:
- assigns a **base level by type** (`:61-74`): `HASH→high`, `DOMAIN/URL→medium`, `IP→low`;
- applies **degree penalty** (`:97-106`): `degree > 10 → low`, `degree > 3 → downrank 1`; applied last so a confirmation bump can't rescue a hub;
- applies **freshness** via per-type half-life (`config.py:12-17`) and `numeric_edge_level` (`freshness.py:66-79`);
- applies **corroboration**: `corroboration_k = 1 + (1 if corroborated_by else 0)` (`confidence.py:114`) → `corroboration_factor(k) = min(1.0, 0.6 + 0.2·log2(1+k))` (`freshness.py:60-63`).

The evidence `sources` field already tolerates `["otx", "threatfox"]` (`ioc_graph.py:148-150`).

### 1.3 Registration surfaces a new source must touch

A table must be registered in: `db/init.py` (both the Postgres and SQLite create blocks), `db/schema_inventory.py` (INTEL vs APP + move order), an Alembic migration, `db/cache_retention.py` (purge), and `intel_snapshot/merge_rules.py` **if** it is an intel-schema table. A source must be registered in: `source_rate_limits.py` (pacing profile + key env), `tracking.py` (`API_LIMITS` + optionally `IOC_QUOTA_SERVICES`), `scheduler_locks.py` (lock), and the scheduler setup block.

---

## 2. Goals & non-goals

### Goals

1. Integrate additional threat intelligence catalog sources (e.g. URLhaus, MalwareBazaar, Feodo Tracker, PhishTank) as first-class corroboration evidence for the existing confidence engine.
2. Reuse the bulk-mirror ingestion archetype end-to-end (fetch → normalize → upsert → scheduler → read-time corroboration).
3. Generalize the corroboration path so the number of independent sources is data-driven and feeds the existing deterministic `corroboration_factor`.
4. Keep every behavior deterministic, idempotent, and testable on both SQLite and Postgres.
5. Preserve backward compatibility for existing readers of `threatfox_iocs` during migration.

### Non-goals

- **No LLM, embeddings, or learned scoring** on the evidence path. (The existing OTX *prioritization* may still use `ml.embeddings` for CVE selection; that is orthogonal and out of scope.)
- **No second CVE-pulse graph source.** The `ioc_graph`/campaign graph stays OTX-driven in this plan.
- **No new canonical IOC types.** Everything maps through `normalize_ioc_type`.
- **No change to per-edge confirmations** (`ioc_cache` GreyNoise/MalwareBazaar/URLhaus lookups) — separate mechanism, unchanged.

---

## 3. Proposed architecture

### 3.1 A data-driven source registry

Introduce a single registry, `backend/sources/registry.py`, that declares each catalog source as a frozen descriptor:

| Field | Meaning | Example |
|-------|---------|---------|
| `source_key` | stable identifier used as PK prefix + `sources` label | `"urlhaus"` |
| `enabled_env` / key env | gating env var + API-key env var (reused from `_SOURCE_API_KEY_ENV`) | `URLHAUS_SYNC_ENABLED`, `ABUSECH_AUTH_KEY` |
| `pacing_key` | key into `PACING_PROFILES` | `"urlhaus"` |
| `sync_interval_hours_env` | env for scheduler interval | `URLHAUS_SYNC_INTERVAL_HOURS` |
| `sync_window_days_env` | env for fetch window (where upstream supports) | `URLHAUS_SYNC_DAYS` |
| `fetch` | async fn returning raw parsed rows (bulk or paged) | `feeds.urlhaus.fetch_recent()` |
| `parse_row` | pure fn: upstream dict → `(ioc_type, ioc_value, ref_id, malware, threat_type, confidence_level, first_seen)` | `feeds.urlhaus.parse()` |
| `mirror_type_map` | upstream type → canonical type string (input to `normalize_ioc_type`) | `{"url": "url", "domain": "domain"}` |
| `receipt_prefix` | receipt format `f"{prefix}:{ref_id}"` | `"urlhaus"` |
| `retention_hours` | purge window | `24 * 7` |

Registration is declarative; the ingestion, scheduler, and corroboration layers iterate the registry rather than branching per source. This is the determinism guarantee: adding a source is configuration plus two pure functions, never a new branch in scoring.

### 3.2 Unified mirror table

Replace the implicit single-source assumption with one table:

```
ti_mirror_iocs (
  source           TEXT NOT NULL,          -- registry source_key
  ref_id           TEXT NOT NULL,          -- upstream id (e.g. urlhaus id)
  ioc_type         TEXT NOT NULL,          -- canonical (IP/DOMAIN/URL/HASH)
  ioc_value        TEXT NOT NULL,          -- canonical lowercased value
  raw_ioc          TEXT DEFAULT '',
  malware          TEXT DEFAULT '',
  threat_type      TEXT DEFAULT '',
  confidence_level INTEGER DEFAULT 0,
  first_seen       TEXT DEFAULT '',
  fetched_at       TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (source, ref_id)
);
CREATE INDEX idx_ti_mirror_type_value ON ti_mirror_iocs (ioc_type, ioc_value);
CREATE INDEX idx_ti_mirror_source ON ti_mirror_iocs (source);
```

- This mirrors `threatfox_iocs` (`db/init.py:749-759` Postgres / `:1092-1102` SQLite) plus a `source` column; `ioc_type`/`ioc_value` hold canonical values as produced by `normalize_ioc`.
- It is an **app-schema** table (operator-local evidence, not published intel), matching `threatfox_iocs` in `APP_TABLES` (`schema_inventory.py:48`).

### 3.3 Migration of ThreatFox

Phased, reversible:

1. **Phase 0:** create `ti_mirror_iocs` (Alembic + both `db/init.py` blocks + inventory + retention + snapshot-ignore).
2. **Phase 1:** add a compat **view** `threatfox_iocs` → `SELECT … FROM ti_mirror_iocs WHERE source='threatfox'` so `retro_match.py:46` and any other legacy reader keep working unmodified during transition.
3. **Phase 2:** backfill current `threatfox_iocs` rows into `ti_mirror_iocs` (`source='threatfox'`), switch writes in `db/threatfox.py` to the unified upsert, and flip readers to the generalized path.
4. **Phase 3:** after a soak window, drop the physical `threatfox_iocs` table (or keep the view; decide by data size at cutover).

### 3.4 Generalized corroboration

Replace `batch_threatfox_hits` (`threatfox_corroboration.py:61-117`) with a source-agnostic `batch_source_evidence(db, iocs)` that:

- for each registered source, maps canonical `(ioc_type, ioc_value)` to that source's mirror query (join on canonical type + lowercased value, exactly as today for ThreatFox `:95-103`);
- returns `{(ioc_type, ioc_value): [rows with source + ref_id + confidence_level + …]}`;
- builds receipts `f"{source}:{ref_id}"` (preserving today's `threatfox:{ioc_id}` format for the migrated source).

**Open question (raised during review, unresolved):** ThreatFox downcasts URLs to `DOMAIN` at ingest (`feeds/threatfox.py:29-30`, host stored as `ioc_value`, full URL in `raw_ioc`) **and** at read time (`_threatfox_lookup_pair:36-50` extracts the host for the join). If URLhaus rows are stored as canonical `URL` (per §3.1's `mirror_type_map: {"url": "url"}`), `batch_source_evidence` must decide how a `URL` row corroborates an OTX `DOMAIN` edge — either keep a read-time host-extraction transform (matches current ThreatFox behavior for both `DOMAIN` and `URL` edges) or store URLhaus URLs downcast to `DOMAIN`. Both are viable; see §10 Q8.

`find_shared_infrastructure_v2` (`ioc_graph.py:87-180`) then:
- collects corroboration receipts from **all** sources instead of ThreatFox only (`:107-111`);
- sets `sources = ["otx"] + distinct corroborating source keys` (`:148-150`);
- passes the full `corroborated_by` list into `confidence_for_ioc_edge` unchanged.

### 3.5 Confidence reuse (unchanged algorithm)

Only one line generalizes:

- `confidence.py:114` — `corroboration_k = 1 + (1 if corroborated_by else 0)` becomes
  `1 + len(corroborated_by or [])` (equivalent when `corroborated_by` is a single-element list; deterministic for N).

**Open question (raised during review, unresolved):** `corroborated_by` is a receipt list with **one entry per matching mirror row** (`ioc_graph.py:106-111` builds it from *every* `tf_rows` row, no dedup; `batch_threatfox_hits` appends every row, `threatfox_corroboration.py:109-116`). `threatfox_iocs` is unique only on `ioc_id` (`db/init.py:750`), so a single source can emit several receipts for one canonical value (e.g. two ThreatFox rows, different `ioc_id`, same domain/host/IP). Under `1 + len(corroborated_by)` that inflates `k` to 3 with one source, jumping `corroboration_factor` from 0.917 to 1.0 (`freshness.py:63`) — i.e. **each receipt is treated as an independent observation, not each source**. The original plan wording implies that is intended (`corroboration_receipt` = one per upstream `ioc_id`; `confidence.py:133` calls them "independent … observation"); the reviewer flagged it because it changes single-source confidence. Whether `k` should count observations or distinct sources is left to the design owner (see §10 Q7).

Everything else — base levels, degree penalty, freshness half-lives, `corroboration_factor`, `numeric_edge_level`, `aggregate_infrastructure_confidence` — stays byte-for-byte identical. `corroboration_factor` already caps at 1.0 (`freshness.py:63`), so multi-source evidence saturates predictably.

---

## 4. Ingestion reuse (per new source)

Each new source implements exactly the ThreatFox shape:

1. **Fetch** (`feeds/<source>.py`): use `resilient_request`/`resilient_get` with the source's pacing key, `record_api_call(source, 1)`, circuit-open guard returning `[]`, and a `has_quota(source)` gate where the source has a quota (mirrors `feeds/threatfox.py:91-138`).
2. **Parse/normalize** (`feeds/<source>.py`): a pure `parse_row` that maps upstream type through the source's `mirror_type_map` → `normalize_ioc_type` → `normalize_ioc` (canonical value). Skip rows that fail `normalize_ioc` (returns `None`), matching `normalize_ioc_row` semantics (`ioc_normalize.py:161-171`). No text mining; upstream fields copied verbatim (same policy as `fetch_pulse_iocs`, `feeds/otx.py:232-245`).
3. **Store** (`db/<source>.py` or a shared `db/ti_mirror.py`): `INSERT … ON CONFLICT(source, ref_id) DO UPDATE …` mirroring `upsert_threatfox_iocs` (`db/threatfox.py:9-45`); caller commits.

A single shared `db/ti_mirror.py` upsert takes `source` as a parameter, so sources add zero new DB code.

---

## 5. Scheduler reuse

One generic job runner `run_catalog_sync(source_key)` (reusing the `run_threatfox_sync` template `scheduler.py:924-960`):

- guard with `get_lock(f"{source_key}_sync")` (new entries in `scheduler_locks.py`, matching `threatfox_sync` at `:13`);
- `_job_progress[source_key + "_sync"]`, `_write_job_last_run(source_key + "_sync", …)`;
- skip when the source's API key is absent (log debug, return True) — identical to ThreatFox `:939-942`.

Registration in the scheduler setup block mirrors the ThreatFox block (`scheduler.py:2276-2286`):

- `IntervalTrigger(hours=<env default>, timezone=sched_tz)`,
- `id="<source>_sync"`, `replace_existing=True`, `max_instances=1`, `coalesce=True`,
- `next_run_time = now + offset` (staggered) to avoid thundering herd at boot.

Exemplar config/env (all with sensible defaults, matching existing conventions):

| Source | API key env | Interval env (default) | Window env (default) | Pacing key |
|--------|-------------|------------------------|-----------------------|------------|
| ThreatFox (existing) | `ABUSECH_AUTH_KEY` | `THREATFOX_SYNC_INTERVAL_HOURS` (24) | `THREATFOX_SYNC_DAYS` (7) | `threatfox` |
| URLhaus | `ABUSECH_AUTH_KEY` | `URLHAUS_SYNC_INTERVAL_HOURS` (24) | `URLHAUS_SYNC_DAYS` (7) | `urlhaus` |
| MalwareBazaar | `ABUSECH_AUTH_KEY` | `MALWAREBAAZAAR_SYNC_INTERVAL_HOURS` (24) | `MALWAREBAAZAAR_SYNC_DAYS` (7) | `malwarebazaar` |
| (next sources…) | … | … | … | … |

Pacing profiles for `urlhaus`, `malwarebazaar`, `threatfox`, `circl`, `virustotal`, `abuseipdb` already exist (`source_rate_limits.py:93-168`); new upstreams get one-line additions to `PACING_PROFILES` plus `API_LIMITS` in `tracking.py`.

---

## 6. Determinism guarantees

- **No LLM / embeddings / learned weights** anywhere in fetch, parse, store, or scoring for this feature.
- **Canonicalization is total and pure**: every value passes `normalize_ioc_type` then `normalize_ioc` (`ioc_normalize.py:47-143`); unknowns survive as their canonical type and are scored by the existing rules.
- **Scoring is closed-form**: base level + degree penalty + freshness half-life + `corroboration_factor(k)`, all pure functions of stored columns (`confidence.py`, `freshness.py`). Source count k is a plain integer.
- **Ordering is deterministic**: corroboration receipts are collected per `(ioc_type, ioc_value)` and the peer sort key in `find_shared_infrastructure_v2` (`ioc_graph.py:169-178`) is unchanged.
- **Idempotent upserts**: `ON CONFLICT(source, ref_id)` — re-running a sync converges to the same rows.
- **Scheduler is non-overlapping**: lock + `max_instances=1` + `coalesce=True` for every job.

---

## 7. Registration checklist (for each new source + table)

| Surface | File | Action |
|---------|------|--------|
| Table create (PG) | `db/init.py` (~`threatfox_iocs` `:749`) | add `ti_mirror_iocs` |
| Table create (SQLite) | `db/init.py` (`:1092`) | add `ti_mirror_iocs` |
| Schema inventory | `db/schema_inventory.py` | add to `APP_TABLES` + `APP_TABLE_MOVE_ORDER` |
| Alembic | `alembic/versions/` | new migration (create table + backfill + view) |
| Retention | `db/cache_retention.py` | per-source purge in the cleanup job |
| Intel snapshot | `intel_snapshot/merge_rules.py` | app table → not exported (no action; verify) |
| Pacing profile | `source_rate_limits.py` | add `PACING_PROFILES` + key env if new |
| Quota/limits | `tracking.py` | add `API_LIMITS` entry (+ `IOC_QUOTA_SERVICES` if surfaced) |
| Scheduler lock | `scheduler_locks.py` | add `<source>_sync` lock |
| Scheduler job | `scheduler.py` | register job block + `run_catalog_sync` |
| Corroboration | `correlation/threatfox_corroboration.py` (or new `correlation/source_evidence.py`) | generalize to `batch_source_evidence` |
| Retro-match | `ioc/retro_match.py` | switch UNION to unified table/view |
| Confidence | `correlation/confidence.py:114` | `1 + len(corroborated_by or [])` |
| UI copy | `frontend/src/` (IOCLookup evidence panel) | surface multi-source receipts + sources list |

---

## 8. Out of scope: CVE-pulse (OTX-style) sources — future work

A second **pulse-graph** source (e.g. MISP events) would reuse the OTX ingestion archetype (fetch → `otx_pulses`-shaped mirror → `ioc_degree`) but requires:

- generalizing `_shared_ioc_rows` (`ioc_graph.py:24-48`) and `ioc_edges_between`/`batch_ioc_edges_for_peers` (`:182-274`) to UNION over a `source` column,
- generalizing campaign clustering (`campaigns.py`) and `pulse_families.py:136-152`,
- deciding how `ioc_degree` counts across sources, and
- schema split / snapshot implications for a second intel pulse mirror.

This is a distinct, larger workstream and intentionally excluded here. The catalog-mirror extension in this plan is the low-risk first step and does not preclude it.

---

## 9. Phasing & verification

### Phase 0 — Unified table + migration
- Alembic migration + both `db/init.py` create blocks + inventory + retention.
- **Verify:** `cd backend && pytest tests/ -q`; row-count parity script (old `threatfox_iocs` vs backfilled rows).

### Phase 1 — Generalize corroboration (ThreatFox migrated, still single source)
- `ti_mirror_iocs` upsert; compat view; `batch_source_evidence`; `confidence.py:114` change.
- **Verify:** correlation confidence tests unchanged for single-source case; `find_shared_infrastructure_v2` evidence identical pre/post for migrated rows. (The §10 Q7 choice on `k` semantics may require a new test once decided.)

### Phase 2 — First additional source (URLhaus)
- `feeds/urlhaus.py` (fetch + parse via registry), scheduler job, pacing/quota/limits, retention.
- **Verify:** end-to-end `run_catalog_sync("urlhaus")`; `batch_source_evidence` returns URLhaus receipts; confidence bump when OTX DOMAIN edge is corroborated by both ThreatFox and URLhaus; `corroboration_factor` saturates at 3 sources.

### Phase 3 — Second source (MalwareBazaar) + retro-match cutover
- Generalize `retro_match.py` UNION to `ti_mirror_iocs`.
- **Verify:** watchlist retro-match hits across ThreatFox + URLhaus + MalwareBazaar mirrors; drop legacy physical table after soak.

### Merge gate
- `./scripts/verify-local.sh` green (per AGENTS.md).

---

## 10. Open questions

1. **Source list scope** — which catalog sources are in the first release? Proposed: URLhaus (domain/url) + MalwareBazaar (hash), both reuse `ABUSECH_AUTH_KEY` and existing abuse.ch pacing. Feodo Tracker / PhishTank as stretch.
2. **Mirror table name** — `ti_mirror_iocs` vs `source_ioc_evidence`; pick one before migration.
3. **Compat view lifetime** — keep `threatfox_iocs` as a permanent view or drop the physical table in Phase 3? (Data size at cutover decides.)
4. **Confidence saturation copy** — surface "corroborated by N independent sources" in the UI even when the factor is already capped, so users see depth.
5. **Retention policy per source** — uniform 7-day window (matching `OTX_TABLE_RETENTION_HOURS` `cache_retention.py:47`) vs per-source env.
6. **`IOC_QUOTA_SERVICES`** — urlhaus and malwarebazaar already appear in the IOC Lookup quota panel (`tracking.py:145-152`; served by `GET /api/usage/ioc` → `routers/meta.py` → `get_ioc_usage_stats`). The only genuinely open part: should the **bulk-sync** API calls for URLhaus/MalwareBazaar/ThreatFox also be counted there (they use the same `record_api_call` path), or stay scheduler-only like ThreatFox today? Propose: add a sync-count aggregate per source so operators see catalog-sync volume without mixing it into the per-lookup IOC quota counters.
7. **Corroboration `k` semantics** — should `corroboration_k = 1 + len(corroborated_by)` count **independent observations** (each mirror row = one receipt, as the original wording implies) or **distinct sources** (each source contributes at most +1)? Both are deterministic; the choice changes single-source confidence whenever one source emits multiple rows for a value. See §3.5.
8. **URL storage for URLhaus** — store upstream `url` rows as canonical `URL` (full value, downcast at read time, as the §3.1 example implies) or downcast to `DOMAIN` at ingest like ThreatFox? Affects whether `batch_source_evidence` needs a read-time host-extraction join. See §3.4.
