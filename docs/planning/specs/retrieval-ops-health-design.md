# Retrieval ops: health + auto-on-ingest (fail-safe) — design

**Status:** Accepted (maintainer 2026-07-19) — auto-on-ingest **default on**; proceed to implementation plan  
**Parent:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md),  
[`retrieval-engine-e7-design.md`](retrieval-engine-e7-design.md)  
**HANDOVER cue:** “admin retrieval health / operator knobs” after E8  

## Intent

E1–E8 already ship pgvector, hybrid FEED search, freshness, techniques,
campaigns, and search tokens. Remaining gap is **ops honesty + auto index
warmth with fail-safes** — not more retrieval features.

**Operator goal:** turn embeddings on once; the index stays warm automatically;
if something breaks, FEED still works (keyword) and Admin shows *why*.

## Locked decisions

| Topic | Decision |
|-------|----------|
| Approach | **B** — two real switches; Admin couples them when enabling embeddings |
| Order | **Fail-safe visibility first**, then auto coupling |
| Live index truth | Counts and pending from multi-entity **`embeddings`** table (not legacy `cve_embeddings`) |
| `EMBEDDINGS_PGVECTOR` | Stay **env-only** escape hatch (default on). Do not add to Admin UI |
| Master kill | `EMBEDDINGS_ENABLED=0` stops model, ingest-tail, scheduled backfill (master stays **opt-in**, default off) |
| Auto default | **`EMBEDDINGS_AUTO_ON_INGEST` default on (`1`)** — when embeddings are enabled, ingest-tail runs unless explicitly set to `0` |
| Auto kill | `EMBEDDINGS_AUTO_ON_INGEST=0` stops ingest-tail only; hybrid search can stay on |
| Caps (fail-safe) | Keep `EMBEDDINGS_INGEST_MAX_PER_RUN` (default 25) and `EMBEDDINGS_MAX_PER_RUN` (default 2000) |
| Search path fail-safe | Unchanged: keyword fallback + FEED quiet status label |
| Non-goals | RAG/chat, ranking sliders, request-path bulk embed, forcing `EMBEDDINGS_ENABLED=1` globally |

## Approach B (auto coupling) — exact behavior

1. Admin config already has `EMBEDDINGS_ENABLED` (default **off** — master opt-in).
2. Promote `EMBEDDINGS_AUTO_ON_INGEST` and `EMBEDDINGS_INGEST_MAX_PER_RUN` into
   `config_schema` (ml section) so they are Admin-editable.
3. **Runtime default:** `EMBEDDINGS_AUTO_ON_INGEST` defaults to **`1`** (on) in
   code, `.env.example`, and config schema. Effective ingest-tail still requires
   `EMBEDDINGS_ENABLED=1` (existing `embeddings_auto_on_ingest_enabled()` gate).
4. **Coupling rule (UI/apply path — belt and suspenders with the new default):**
   - When the operator saves `EMBEDDINGS_ENABLED` from `0` → `1`, if
     `EMBEDDINGS_AUTO_ON_INGEST` is not explicitly being set in the same save,
     **also set `EMBEDDINGS_AUTO_ON_INGEST=1`** (covers installs that still have
     an old `=0` in `.env` / `app_settings`).
   - Operator may later set `AUTO_ON_INGEST=0` while leaving embeddings on
     (fail-safe under CPU load).
   - Enabling embeddings does **not** change ingest max; defaults stay 25.
5. Do **not** force `EMBEDDINGS_ENABLED=1` on existing deploys.

## Fail-safe visibility (health)

### API

`GET /api/admin/retrieval/health` (admin-auth) returns a small JSON payload:

| Field | Meaning |
|-------|---------|
| `embeddings_enabled` | Effective flag |
| `auto_on_ingest` | Effective flag |
| `pgvector_writes` | Effective `EMBEDDINGS_PGVECTOR` (read-only in UI) |
| `model` | Active model name |
| `extension_vector` | Postgres: present/absent; SQLite: `n/a` (BLOB shim) |
| `counts` | `{ cve, technique, campaign, total }` from `embeddings` for active model |
| `pending` | Cheap SQL count of **missing / `migrated:` only** (excludes Python-side hash-drift — Gemini medium) |
| `last_backfill` | Last `embeddings_backfill` job summary if available (when, embedded totals, error) |
| `last_ingest_tail` | Last auto-on-ingest result from `sync_state` (`embeddings.ingest_tail.last`) — success or error (Gemini medium) |
| `degraded` | Optional `{ reason }` when search would be keyword-only (disabled / no extension / cold) |
| `counts` | Always filtered by **active model** (`WHERE model = ?`) |

No request-path model inference. Cheap SQL + existing job status only.

### UI

- Thin panel on **Admin → AI operations** (Overview or a “Retrieval” subsection):
  show the health fields + link to Scheduler job + API keys search tokens.
- Fix AI ops `features.embeddings.vector_count` to count rows in **`embeddings`**
  (optionally show legacy count as secondary “legacy_cve_embeddings”).
- Fix scheduler catalog copy: job embeds CVE + technique + campaign, not
  “CVE description” only.

### Storage / explorer (small)

Add `embeddings` to admin `_STORAGE_TABLES` and explorer registry (read-only
browse). Keep `cve_embeddings` for legacy visibility.

## Operator knobs (Admin)

| Knob | Admin? | Notes |
|------|--------|-------|
| `EMBEDDINGS_ENABLED` | Yes (exists) | Master; enable path couples auto-on-ingest |
| `EMBEDDINGS_AUTO_ON_INGEST` | **Add** | Fail-safe off-switch for ingest tail |
| `EMBEDDINGS_INGEST_MAX_PER_RUN` | **Add** | Cap fail-safe |
| `EMBEDDINGS_MAX_PER_RUN` | Yes (exists) | Scheduled backfill cap |
| `EMBEDDINGS_SYNC_INTERVAL_HOURS` | Yes (exists) | |
| `EMBEDDINGS_MODEL` / `CACHE_DIR` | Yes (exists) | Model change still implies re-embed (doc only) |
| `EMBEDDINGS_PGVECTOR` | **No** | Env escape hatch only |
| Search token rate limit | Yes (exists) | Unchanged |

## PR sequence

| PR | Scope |
|----|--------|
| **RH-1** | Health API + AI ops count fix + catalog copy + storage/explorer `embeddings` + thin Admin panel |
| **RH-2** | Config schema for auto-on-ingest + ingest max; Admin enable coupling (B); docs (`PRODUCT_STATUS`, `API_REFERENCE`, HANDOVER/SPRINT tick) |

RH-1 before RH-2 so auto never lands without a truthful gauge.

## Error handling

| Failure | Behavior |
|---------|----------|
| Embeddings disabled | Health `degraded.reason=disabled`; FEED keyword |
| No `vector` extension (Postgres) | Health reports absent; hybrid falls back per existing code |
| Auto-on-ingest errors mid-NVD | Log + continue NVD commit path (do not fail ingest); record error in `sync_state` for health API; pending left for scheduled backfill |
| Cap hit on ingest | Embed first N; remainder pending |
| Health SQL fails | 500 with request_id; panel shows error state distinct from empty |

## Testing

- Unit: count from `embeddings` by `entity_type`; coupling helper
  (enable → sets auto; explicit auto=0 preserved on unrelated saves).
- API: admin-only health; shape contract.
- Config: schema includes new fields; apply path coupling.
- Regression: `EMBEDDINGS_ENABLED=0` still no-ops backfill/ingest tail.
- Frontend build for Admin panel.

## Acceptance

- [ ] AI ops vector number matches `embeddings` (or clearly labels both).
- [ ] Health endpoint shows coverage/pending/extension/flags without loading the model.
- [ ] `EMBEDDINGS_AUTO_ON_INGEST` defaults to on; enabling embeddings in Admin also sets it on (covers stale `=0`); operator can turn auto off alone.
- [ ] Caps remain enforced; keyword fallback unchanged.
- [ ] `EMBEDDINGS_PGVECTOR` not in Admin UI.
- [ ] Docs updated in the same PRs.

## Out of scope / later

- Similarity floor / hybrid weight knobs  
- Golden ranking dashboards  
- Procrastinate migration for backfill  
- Self-service anything unrelated to retrieval  
